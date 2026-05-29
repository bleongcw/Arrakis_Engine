# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""LLM coaching layer for ArrakisEngine.

Generates age-appropriate coaching insights from Stockfish analysis
using reasoning LLMs (Claude, ChatGPT, Gemini, Grok, Mistral, DeepSeek, Qwen, Ollama).
"""

import json
import logging
import time
from datetime import datetime

from src.llm_providers import call_provider, resolve_model
from src.models import init_db
from src.tiers import get_tier

logger = logging.getLogger(__name__)


GAME_COACHING_PROMPT = """You are a professional chess coach for a {age}-year-old player named {name} (rated ~{rating}).
Analyze this game and produce coaching insights.

## Skill Tier: {tier_label} {tier_icon} ({tier_description})

## Game Character
This game has been classified as: **{game_type}**
{game_type_guidance}

## Tone Guidelines
- Professional, succinct, and encouraging — like a warm but serious coach who respects the child's intelligence.
- Keep language age-appropriate for a {age}-year-old: short sentences, concrete examples, no abstract theory.
- Language level: {language_level}
- Celebrate effort and good decisions, not just results. A loss with brave play deserves praise.
- When pointing out mistakes, frame them as learning opportunities, never criticism.
- Be specific — say "your knight move to f3 was smart because it protects the center" rather than "good move."
- Keep it brief: quality over quantity. One clear point beats three vague ones.
{tone_modifier}
{custom_instructions_section}
{detail_modifier}
{focus_modifier}

## IMPORTANT: Variety and Freshness
- VARY your writing style, structure, and analogies across different games.
- Do NOT start every narrative the same way. Mix up your openings: sometimes start with the most exciting moment, sometimes with the opening, sometimes with what the opponent did.
- Use different analogies and metaphors each time — draw from sports, adventures, puzzles, building things, nature, strategy games, etc. Do NOT reuse the same analogy patterns.
- Vary sentence length and rhythm. Sometimes use short punchy sentences. Sometimes longer flowing ones.
- For tips and advice, do NOT always use the same phrasing patterns like "Next time you see X, try Y." Mix it up: ask questions ("What if you tried...?"), use challenges ("See if you can spot..."), share coach secrets ("Here's a trick strong players use..."), use stories ("Imagine your pieces are a team and...").
{previous_coaching_guidance}
{player_trajectory}
{phase_classification_summary}

## Trap Awareness (well-known traps your opponent could have played in this opening)
{relevant_traps_block}

## Trajectory-Aware Coaching
- Where the trajectory snapshot above (if present) shows measurable progress, acknowledge it concretely (e.g. "your endgame conversion has been climbing — this game shows why").
- If this game illustrates a weakness that the trajectory flags as recurring, note the recurrence GENTLY — once, in passing. Don't re-lecture the player on it.
- Tie this game's key_lesson and practical_focus to the broader trajectory where the connection is real. Do NOT restate the numbers — the trajectory is for you to reason from, not to read back to the player.

## Focus Areas for {tier_label} Players
{focus_areas}

## Player Info
- Name: {name}
- Age: {age}
- Rating: {rating}
- Tier: {tier_label}
- Color: {player_color}
- Result: {result}

## PGN
{pgn}

## Move-by-Move Engine Analysis
{analysis_text}

## Critical Moments (biggest eval swings)
{critical_moments}

## Instructions
Produce a JSON response with these exact keys:

1. "game_type" — A short label for the character of this game (e.g. "tactical battle",
   "positional grind", "opening disaster", "comeback victory", "time pressure collapse",
   "endgame marathon", "miniature", "quiet draw"). Pick the most fitting description.

2. "narrative" — A 2-3 paragraph game story for the child. Use encouraging, concrete language.
   Say "you" not "the player". No chess jargon a {age}-year-old wouldn't know.
   Explain what happened like telling a story. Celebrate good moves, be gentle about mistakes.
   IMPORTANT: Tailor the narrative to the game type — a wild tactical game should feel exciting
   and dramatic; a quiet positional game should highlight patience and planning; a time trouble
   game should discuss the clock; a comeback should build suspense.

3. "key_lesson" — The single most important takeaway from this game, in 1-2 sentences.
   Make it specific and actionable, not generic. The wording and angle MUST be different
   from any previous lessons listed in the coaching history section, even when you are
   reinforcing a theme the player keeps hitting. If the same theme keeps appearing, go
   deeper, find a fresh angle, or tie it to the trajectory snapshot below.

4. "practical_focus" — One specific thing to practice, framed as a fun challenge.
   Example: "Before moving a piece, count how many enemy pieces are looking at that square."
   The wording MUST be different from previous practical_focus items in the coaching history,
   even when reinforcing a recurring weakness.

5. "critical_moments" — A JSON array of the {critical_moments_count} most important moments. Each object has:
   - "move_number": int
   - "side": "white" or "black"
   - "what_happened": 1-2 sentences a child can understand
   - "what_was_better": 1-2 sentences about the better move
   - "move_played": the move in notation
   - "best_move": the engine's recommended move
   - "motifs_found": list of strings — tactical themes (v1.14.0) the BEST move executed,
     COPIED VERBATIM from the "tactical motifs — PLAYED: ..." annotations in the
     critical-moments context block above. Valid values: "fork", "pin", "skewer",
     "discovered_check", "mate_threat", "removing_defender", "hanging_piece",
     "trapped_piece". Empty list if no motifs annotated.
   - "motifs_missed": list of strings — tactical themes the PLAYED move missed
     (the delta — themes the best move had but the actual move didn't), also
     COPIED VERBATIM from the "tactical motifs — MISSED: ..." annotations above.
     Empty list if no motifs were missed. DO NOT INVENT MOTIF NAMES — if a
     critical move has no motif annotation in the context block above, both
     fields must be empty arrays.

6. "opening_analysis" — A JSON object analyzing the opening choice:
   - "opening_name": the name of the opening played (e.g. "Italian Game", "Sicilian Defense")
   - "player_role": "white" if the player chose the opening, or "black" if responding to it
   - "opening_quality": "good", "acceptable", or "poor" — was this a sound opening choice for their level?
   - "correct_counter_moves": true or false — if playing black, did the player respond with correct/principled counter-moves? If playing white, did they follow the main line or deviate poorly?
   - "opening_summary": 2-3 sentences explaining the opening choice. For white: was the system appropriate? Did they develop pieces logically? For black: did they play the correct response to white's opening? Where did they first deviate from good play?
   - "opening_tip": One specific, actionable tip about this opening for a {age}-year-old.

7. "player_feedback" — A structured phase-by-phase coaching review for the child,
   written directly to them. Address {name} by name. Use "you" throughout.

   OUTPUT FORMAT (v1.13.0+): The value of "player_feedback" must be a single string
   containing EXACTLY these 5 markdown sections in this order, separated by blank
   lines, using these exact headings. Do NOT skip any heading. Do NOT add extra
   headings beyond these 5. Do NOT change the emoji/text in the headings.

   ## ♟ Opening
   2-3 sentences. Name the opening that was played (use the opening_analysis you
   produced for key #6 as the source of truth). Note how the player's moves
   compared to the standard theory of this opening — exact match, slight deviation,
   off-book early. Reference 1-2 specific opening moves only if they meaningfully
   illustrate the deviation. Build on opening_analysis; do NOT repeat its exact wording.

   ## ⚔ Middlegame
   2-3 sentences. Identify the key middlegame moments. Name 1-2 specific mistakes
   or blunders by move number. CRITICAL: only use move numbers that appear in the
   "Move Quality by Phase" section above — do NOT invent move numbers. Explain
   why each was wrong in age-appropriate language.
   v1.14.0+: when a critical move has a tactical motif annotation in the
   "Critical Moments (biggest eval swings)" block above (look for "tactical
   motifs — MISSED: fork" etc.), CITE THE MOTIF BY NAME — e.g. "you missed
   a knight fork on f7" or "your opponent set up a pin you didn't see."
   Convert motif identifiers to natural language: "fork" → "fork", "pin" →
   "pin", "skewer" → "skewer", "discovered_check" → "discovered check",
   "mate_threat" → "mate threat", "removing_defender" → "removing the
   defender", "hanging_piece" → "free piece capture", "trapped_piece" →
   "trapped piece." v1.17.0 added: "back_rank_mate" → "back-rank mate",
   "deflection" → "deflection", "overloaded_defender" → "overloaded defender",
   "zugzwang" → "zugzwang" (use sparingly — advanced endgame concept).
   Do NOT invent motifs that aren't annotated.

   ## ♔ Endgame
   1-2 sentences. If the game reached an endgame (moves >30): assess conversion
   quality, technique, king activity. If the game ended before move 30: write
   exactly: "This game ended in the middlegame — no endgame technique needed today."
   v1.14.0+: same motif-citation rule applies — if a critical endgame move has
   a motif annotation, cite it by name.

   ## 🪤 Watch Out For (Trap Awareness)
   1-2 sentences. Pick ONE trap from the "Trap Awareness" section above that's most
   relevant — name it, describe in one sentence what the opponent could have done
   to spring it, and what move would have refuted it. If no traps were listed in
   the context above, write exactly: "Your opponent didn't have any well-known
   traps available in this opening — but stay alert for tactics on every move."

   ## 🎯 Top 3 Improvements
   A numbered list (1., 2., 3.) of exactly 3 specific things to focus on next game.
   Each item is ONE sentence, concrete, observable. Good: "Find one knight outpost
   before move 15." Bad: "Play more accurately." Pick items DIFFERENT from any
   listed in the coaching history. If the player has been working on something
   from a previous game, item 1 can acknowledge progress or gently remind them.

   GENERAL REQUIREMENTS (across all 5 sections):
   - Match language to a {age}-year-old at {tier_label} level: {language_level}
   - Be warm but not patronizing. Respect their intelligence while keeping it accessible.
   - Reference specific moves from THIS game to make it personal, not generic.
   - If coaching history is provided, DO NOT repeat the same praise patterns or tips.

8. "coach_notes" — Technical summary for the chess coach. Use precise chess terminology.
   Include: opening assessment, critical tactical moments, endgame technique (if applicable),
   specific weaknesses to address in lessons, and recommended training exercises.
   2-3 paragraphs, professional tone.

Respond with ONLY valid JSON, no markdown code fences or extra text."""


def _build_analysis_text(moves: list[dict], max_moves: int = 80) -> str:
    """Format move analysis into readable text for the prompt.

    For games with many moves, sends a compact summary:
    - Always include the first 10 moves (opening)
    - Always include all inaccuracies, mistakes, and blunders with context
    - Include a stats summary for skipped sections
    - Cap total output to max_moves lines to control token usage
    """
    if len(moves) <= max_moves:
        # Short game — send everything
        return _format_moves(moves)

    # Long game — send smart selection
    noteworthy = {"inaccuracy", "mistake", "blunder"}
    opening_end = min(20, len(moves))  # first 10 full moves = 20 half-moves

    selected = set()
    # Always include opening
    for i in range(opening_end):
        selected.add(i)

    # Include all noteworthy moves + 1 move of context before/after
    for i, m in enumerate(moves):
        if m.get("classification") in noteworthy:
            for j in range(max(0, i - 1), min(len(moves), i + 2)):
                selected.add(j)

    # Build output with gap markers
    lines = []
    total_moves = len(moves)
    player_moves = [m for m in moves if m.get("swing_cp", 0) is not None]
    avg_loss = sum(m.get("swing_cp", 0) or 0 for m in player_moves) / max(len(player_moves), 1)
    lines.append(f"  [Game summary: {total_moves} half-moves, avg loss {avg_loss:.0f}cp]")

    prev_idx = -2
    for i in sorted(selected):
        if i > prev_idx + 1:
            gap = i - prev_idx - 1
            lines.append(f"  [...{gap} moves omitted (good/excellent)...]")
        lines.append(_format_single_move(moves[i]))
        prev_idx = i

    if prev_idx < len(moves) - 1:
        gap = len(moves) - 1 - prev_idx
        lines.append(f"  [...{gap} moves omitted (good/excellent)...]")

    return "\n".join(lines)


def _format_single_move(m: dict) -> str:
    """Format a single move for the prompt."""
    classification = m["classification"] or "?"
    symbol = {"excellent": "!", "good": ".", "inaccuracy": "?!",
              "mistake": "?", "blunder": "??", "?": ""}.get(classification, "")
    line = (
        f"  {m['move_number']}.{'.. ' if m['side'] == 'black' else ' '}"
        f"{m['move_played']}{symbol} "
        f"(eval: {m['eval_before_cp']}cp → {m['eval_after_cp']}cp, "
        f"swing: {m['swing_cp']}cp, "
        f"win%: {m['win_prob_before']:.1f}% → {m['win_prob_after']:.1f}%)"
    )
    if m["best_move"] and m["best_move"] != m["move_played"]:
        line += f" [best: {m['best_move']}]"
    return line


def _format_moves(moves: list[dict]) -> str:
    """Format all moves (for short games)."""
    return "\n".join(_format_single_move(m) for m in moves)


def _build_critical_moments(moves: list[dict], top_n: int = 5) -> str:
    """Extract the top N critical moments by eval swing.

    v1.14.0: surfaces motif tags (motifs_json) when present on a move row —
    these are the tactical themes (fork/pin/skewer/etc.) detected by the
    analyzer at analysis time. The LLM uses these to cite specific
    motifs by name in feedback rather than inferring from raw eval swings.
    """
    sorted_moves = sorted(moves, key=lambda m: m["swing_cp"] or 0, reverse=True)
    critical = sorted_moves[:top_n]
    lines = []
    for m in critical:
        line = (
            f"  Move {m['move_number']} ({m['side']}): {m['move_played']} "
            f"— lost {m['swing_cp']}cp (win%: {m['win_prob_before']:.1f}% → "
            f"{m['win_prob_after']:.1f}%). Best was {m['best_move'] or '?'}"
        )
        # v1.14.0: motif tags. motifs_json shape: {played, best, missed}.
        motifs_raw = m.get("motifs_json")
        if motifs_raw:
            try:
                motifs = json.loads(motifs_raw) if isinstance(motifs_raw, str) else motifs_raw
                missed = motifs.get("missed") or []
                played = motifs.get("played") or []
                tag_parts = []
                if missed:
                    tag_parts.append(f"MISSED: {', '.join(missed)}")
                if played:
                    tag_parts.append(f"PLAYED: {', '.join(played)}")
                if tag_parts:
                    line += f"  ⟶ tactical motifs — {' | '.join(tag_parts)}"
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        lines.append(line)
    return "\n".join(lines)


def _detect_game_type(moves: list[dict], game: dict) -> tuple[str, str]:
    """Detect the character of the game and return (type_label, coaching_guidance).

    Analyzes move patterns, eval swings, game length, and result to classify
    the game and provide type-specific coaching guidance.
    """
    total_moves = len(moves)
    player_color = game["player_color"]
    result = game["result"]

    # Count classifications
    blunders = sum(1 for m in moves if m.get("classification") == "blunder"
                   and m.get("side") == player_color)
    mistakes = sum(1 for m in moves if m.get("classification") == "mistake"
                   and m.get("side") == player_color)
    excellent = sum(1 for m in moves if m.get("classification") == "excellent"
                    and m.get("side") == player_color)

    # Eval swings (large shifts in advantage)
    big_swings = sum(1 for m in moves if abs(m.get("swing_cp", 0) or 0) > 200)

    # Check for comeback or collapse
    player_was_losing = False
    player_was_winning = False
    for m in moves:
        wp = m.get("win_prob_after", 50) or 50
        if player_color == "black":
            wp = 100 - wp
        if wp < 25:
            player_was_losing = True
        if wp > 75:
            player_was_winning = True

    # Time pressure: check if late moves exist (proxy — games with many moves)
    is_long = total_moves > 80
    is_short = total_moves < 30

    # Classify
    if is_short and (blunders >= 2 or mistakes >= 3):
        game_type = "opening disaster"
        guidance = ("Focus on what went wrong early. Be extra gentle — short losses feel bad. "
                    "Find something positive even if it's small. Emphasize that everyone has "
                    "these games, even grandmasters. Focus the lesson on the opening phase.")
    elif is_short and result == "win":
        game_type = "miniature victory"
        guidance = ("This was a quick win! Celebrate the tactical sharpness. "
                    "But also gently note that the opponent made it easy — "
                    "focus on what to do when opponents play better moves.")
    elif player_was_losing and result == "win":
        game_type = "comeback victory"
        guidance = ("This is a dramatic comeback story! Build suspense in the narrative. "
                    "Praise the fighting spirit and resilience. Highlight the turning point. "
                    "But also address how they got into trouble in the first place.")
    elif player_was_winning and result == "loss":
        game_type = "collapse from winning position"
        guidance = ("Handle this sensitively — losing a won game is painful. "
                    "Acknowledge how well they played in the first part. "
                    "Focus the lesson on technique: converting advantages, not rushing, "
                    "and staying focused when ahead. Be extra encouraging.")
    elif big_swings >= 4:
        game_type = "wild tactical battle"
        guidance = ("This was a rollercoaster! Make the narrative exciting and dramatic. "
                    "Focus on calculation and pattern recognition. "
                    "Highlight both the thrilling attacks and the defensive moments.")
    elif is_long and big_swings < 2:
        game_type = "positional grind"
        guidance = ("This was a patient, strategic game. Praise the stamina and focus. "
                    "Highlight positional concepts: piece placement, pawn structure, "
                    "controlling key squares. Use analogies about planning and patience.")
    elif is_long:
        game_type = "endgame marathon"
        guidance = ("This game went deep into the endgame. Focus on endgame technique: "
                    "king activity, passed pawns, piece coordination. "
                    "Praise the patience required for long games.")
    elif excellent >= 5 and blunders == 0:
        game_type = "excellent performance"
        guidance = ("This was a strong game! Be genuinely impressed. "
                    "Point out the specific excellent moves and why they were strong. "
                    "Challenge them to maintain this level. Set a higher bar for next time.")
    elif result == "draw":
        game_type = "hard-fought draw"
        guidance = ("Draws can be just as instructive as wins. Highlight what went well. "
                    "Discuss whether the draw was a good result or a missed opportunity. "
                    "Focus on the moments where the game could have gone either way.")
    else:
        game_type = "standard game"
        guidance = ("Analyze the game on its own merits. Look for the most interesting "
                    "moments and patterns. Find the unique story of this particular game.")

    return game_type, guidance


def _fetch_coaching_history(conn, player_id: int, current_game_id: int,
                           limit: int = 5) -> str:
    """Fetch recent coaching history for this player to avoid repetition.

    Returns a formatted string for inclusion in the prompt, or empty string
    if no history exists.
    """
    rows = conn.execute(
        """SELECT gc.key_lesson, gc.practical_focus, gc.narrative, g.result,
                  g.player_color, g.date_played
           FROM game_coaching gc
           JOIN games g ON gc.game_id = g.id
           WHERE g.player_id = ? AND gc.game_id != ?
           ORDER BY g.date_played DESC
           LIMIT ?""",
        (player_id, current_game_id, limit),
    ).fetchall()

    if not rows:
        return ""

    lines = [
        "",
        "## Coaching History (recent games — DO NOT repeat these)",
        "Below are the lessons and practice focuses from the player's recent games.",
        "You MUST provide DIFFERENT advice this time. Build on previous coaching,",
        "acknowledge progress on past tips if relevant, but give fresh insights.",
        "",
    ]
    for i, row in enumerate(rows, 1):
        result_str = f"{row['player_color']}, {row['result']}"
        date_str = row["date_played"] or "unknown date"
        lines.append(f"### Game {i} ({date_str}, {result_str})")
        lines.append(f"- **Key lesson:** {row['key_lesson'] or 'N/A'}")
        lines.append(f"- **Practice focus:** {row['practical_focus'] or 'N/A'}")
        # Include first 100 chars of narrative to show tone used
        narrative = row["narrative"] or ""
        if narrative:
            lines.append(f"- **Narrative opening:** {narrative[:150]}...")
        lines.append("")

    return "\n".join(lines)


def _maybe_refresh_patterns(conn, player_id: int,
                            db_path: str | None,
                            stale_after_days: int = 7) -> None:
    """v1.8.0: refresh player_patterns when stale or out-of-date with games.

    Calls compute_player_patterns when:
      - no patterns row exists for this player yet, OR
      - the patterns row is older than ``stale_after_days``, OR
      - there are completed games dated after the patterns' period_end
        (the patterns missed games that have since been analyzed).

    compute_player_patterns is pure-Python (no LLM call) so this is cheap
    — typically a few seconds per player on a full DB. We do NOT call
    generate_trend_summary here (that's a paid LLM round-trip).
    """
    row = conn.execute(
        """SELECT updated_at, period_end FROM player_patterns
        WHERE player_id = ? ORDER BY updated_at DESC LIMIT 1""",
        (player_id,),
    ).fetchone()

    needs_refresh = False
    if not row:
        needs_refresh = True
    else:
        try:
            updated = datetime.fromisoformat(row["updated_at"])
            if (datetime.now() - updated).days >= stale_after_days:
                needs_refresh = True
        except (TypeError, ValueError):
            needs_refresh = True
        if not needs_refresh and row["period_end"]:
            # Are there completed games dated after the patterns' window?
            newer = conn.execute(
                """SELECT COUNT(*) AS n FROM games
                WHERE player_id = ? AND analysis_status = 'complete'
                AND date_played > ?""",
                (player_id, row["period_end"]),
            ).fetchone()
            if newer and (newer["n"] or 0) > 0:
                needs_refresh = True

    if not needs_refresh:
        return

    try:
        from src.patterns import compute_player_patterns
        logger.info("Auto-refreshing player_patterns for player %d (stale or out-of-date)",
                    player_id)
        compute_player_patterns(player_id, db_path=db_path)
    except Exception as e:
        # Pattern refresh is best-effort. If it fails, fall through and
        # let build_trajectory_block return an empty block — coaching
        # still proceeds, just without trajectory injection.
        logger.warning("Auto-refresh of player_patterns failed for player %d: %s",
                       player_id, e)


def _parse_llm_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences and thinking tags."""
    import re

    text = text.strip()
    # Strip <think>...</think> blocks from reasoning models (DeepSeek-R1, Qwen3)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if text.startswith("```"):
        # Remove code fences
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate using the standard ~4 chars/token heuristic.

    Accurate enough for context-window safety decisions and diagnostic
    logging; not a substitute for a real tokenizer when precision matters."""
    return max(1, len(text) // 4)


def _count_history_games(history_text: str) -> int:
    """Count how many games appear in the injected coaching-history block.
    The block uses `### Game N` headings; this counts those."""
    if not history_text:
        return 0
    return history_text.count("### Game ")


# ---------------------------------------------------------------------------
# v1.13.0: phase-structured player_feedback context
# ---------------------------------------------------------------------------
#
# Two pieces of prompt context the LLM previously had to infer from the
# raw moves list — now pre-computed for accuracy:
#
#   1. _phase_classification_summary — per-phase counts + the specific
#      move numbers where mistakes/blunders happened. Stops the LLM
#      inventing move numbers and gives it a structured spine for the
#      Middlegame / Endgame sections of the new player_feedback.
#
#   2. _traps_for_opening — looks UP into the v1.4.0 trap library to
#      find well-known traps that share the same opening prefix as
#      this game. Answers "what trap could the opponent have unleashed
#      in this opening?" — the inverse of the existing _match_trap
#      direction (which asks "did my game match a trap line?").

# How many plies of the game's opening prefix we compare against trap
# library entries. 6 plies = 3 full moves — captures the named-opening
# family (Italian / Sicilian / French / etc.) without being so specific
# that only the exact main line matches.
_TRAP_OPENING_PREFIX_PLIES = 6

# Minimum number of matching plies for a trap to count as "same opening
# family." 4 plies = 2 full moves — covers cases like Scholar's Mate
# starting 1.e4 e5 2.Bc4 where the trap diverges from the player's
# choice on move 3 but they're still in the same opening territory.
_TRAP_OPENING_MIN_MATCH_PLIES = 4


def _phase_classification_summary(moves: list[dict], player_color: str) -> str:
    """Per-phase breakdown of the player's move-quality classifications.

    Returns a markdown text block listing, for each game phase, how many
    inaccuracies / mistakes / blunders the player committed, plus the
    specific move numbers where mistakes and blunders happened. The LLM
    uses this to ground statements like "your 18.Qh4 was a mistake"
    without inventing move numbers.

    v1.13.0+
    """
    from src.patterns import _classify_game_phase

    # phase → {classification → count}, plus phase → [move_numbers] for mistake+blunder
    counts: dict[str, dict[str, int]] = {
        "opening": {"inaccuracy": 0, "mistake": 0, "blunder": 0},
        "middlegame": {"inaccuracy": 0, "mistake": 0, "blunder": 0},
        "endgame": {"inaccuracy": 0, "mistake": 0, "blunder": 0},
    }
    flagged: dict[str, list[tuple[int, str]]] = {
        "opening": [],
        "middlegame": [],
        "endgame": [],
    }

    for m in moves:
        if m.get("side") != player_color:
            continue
        cls = m.get("classification")
        if cls not in ("inaccuracy", "mistake", "blunder"):
            continue
        phase = _classify_game_phase(m.get("move_number", 0))
        counts[phase][cls] += 1
        if cls in ("mistake", "blunder"):
            flagged[phase].append((m.get("move_number", 0), cls))

    def _phase_line(phase: str, label: str) -> str:
        c = counts[phase]
        f = flagged[phase]
        flagged_str = (
            ", ".join(f"{mn} ({cls})" for mn, cls in f) if f else "(none)"
        )
        return (
            f"- {label}: {c['inaccuracy']} inaccuracies, "
            f"{c['mistake']} mistakes, {c['blunder']} blunders\n"
            f"  → mistake/blunder moves: {flagged_str}"
        )

    return (
        "## Move Quality by Phase (your moves only)\n"
        + _phase_line("opening", "Opening (moves 1-15)") + "\n"
        + _phase_line("middlegame", "Middlegame (moves 16-30)") + "\n"
        + _phase_line("endgame", "Endgame (moves 31+)")
    )


def _traps_for_opening(pgn_text: str, max_results: int = 3) -> list[dict]:
    """Find well-known traps that share this game's opening prefix.

    Returns up to ``max_results`` trap library entries whose `moves`
    array begins with the SAME opening as this game's first
    ``_TRAP_OPENING_PREFIX_PLIES`` plies. Used by the v1.13.0
    "Watch Out For (Trap Awareness)" section of player_feedback.

    Different from _match_trap (which asks "did my game match a
    trap?") — this asks "what traps could the opponent have unleashed
    from this opening?" Forward-looking, not retrospective.

    Returns [] if no traps share the opening (rare openings, off-book
    early). The prompt handles the empty case gracefully.
    """
    from src.patterns import _extract_san_moves, _load_trap_library

    if not pgn_text:
        return []

    game_prefix = _extract_san_moves(
        pgn_text, max_moves=_TRAP_OPENING_PREFIX_PLIES
    )
    if len(game_prefix) < _TRAP_OPENING_MIN_MATCH_PLIES:
        return []

    library = _load_trap_library()
    if not library:
        return []

    # Collect (lcp, entry) pairs for any trap with a sufficient prefix match,
    # then sort by LCP descending so we prefer specific opening matches
    # (5 plies — Italian Bc4) over generic ones (4 plies — any 1.e4 e5 with
    # both knights developed). Library is already depth-sorted internally,
    # so for equal LCP we naturally get the deepest trap first.
    candidates: list[tuple[int, dict]] = []
    for entry in library:
        sig = entry.get("moves") or []
        if len(sig) < _TRAP_OPENING_MIN_MATCH_PLIES:
            continue
        cap = min(len(game_prefix), len(sig), _TRAP_OPENING_PREFIX_PLIES)
        lcp = 0
        for i in range(cap):
            if game_prefix[i] == sig[i]:
                lcp += 1
            else:
                break
        if lcp >= _TRAP_OPENING_MIN_MATCH_PLIES:
            candidates.append((lcp, entry))
    # Stable sort by -lcp keeps depth-order within each LCP tier
    candidates.sort(key=lambda x: -x[0])
    return [entry for _lcp, entry in candidates[:max_results]]


def _format_relevant_traps_block(traps: list[dict]) -> str:
    """Render the trap-awareness context block for the coaching prompt."""
    if not traps:
        return (
            "(no well-known traps share this opening prefix — the position "
            "is off-book from the trap library)"
        )
    lines = []
    for t in traps:
        name = t.get("name", "Unknown trap")
        eco = t.get("eco", "?")
        depth = t.get("depth") or len(t.get("moves") or [])
        # First 8 plies of the trap's SAN string for context
        moves_san = (t.get("moves_san") or "")[:120]
        if len(t.get("moves_san", "") or "") > 120:
            moves_san += "…"
        lines.append(
            f"- {name} ({eco}, {depth} plies deep) — line: {moves_san}"
        )
    return "\n".join(lines)


# v1.13.0 requires the LLM to emit player_feedback as 5 markdown sections
# in this exact order using these exact headings (modulo the leading `## `).
# v1.13.2's validator checks the response for compliance and records the
# state in coaching_meta_json so silent format drift (older models, prompt
# regressions, provider quirks) is visible in logs + UI badges instead of
# being masked by the frontend's legacy single-block fallback.
_REQUIRED_FEEDBACK_HEADINGS: tuple[str, ...] = (
    "♟ Opening",
    "⚔ Middlegame",
    "♔ Endgame",
    "🪤 Watch Out For",
    "🎯 Top 3 Improvements",
)


def _validate_player_feedback_structure(feedback_text: str | None) -> dict:
    """v1.13.2: check that a player_feedback response has the 5 required
    markdown headings introduced in v1.13.0.

    Returns a dict suitable for storage in coaching_meta_json:

        {
          "compliant": bool,               # True iff ALL 5 required present
          "missing_headings": list[str],   # subset of _REQUIRED_FEEDBACK_HEADINGS
          "extra_headings":   list[str],   # headings the LLM added beyond the spec
          "headings_found":   int,         # 0..N for log brevity
        }

    Heading detection is permissive — accepts `## ♟ Opening` and
    `## ♟ Opening (anything after)` so the trap-awareness heading variant
    `## 🪤 Watch Out For (Trap Awareness)` still counts. Case-sensitive on
    the heading text itself because the emoji + capitalization are spec.

    Returns compliant=False for null/empty input (callers can treat that
    as "nothing to validate" — legacy entries pre-v1.13.0 just don't get
    a compliance check).
    """
    if not feedback_text:
        return {
            "compliant": False,
            "missing_headings": list(_REQUIRED_FEEDBACK_HEADINGS),
            "extra_headings": [],
            "headings_found": 0,
        }

    # Extract `## <heading>` lines (the heading text after `## `, trimmed)
    found_headings: list[str] = []
    for line in feedback_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            found_headings.append(stripped[3:].strip())

    missing = []
    for req in _REQUIRED_FEEDBACK_HEADINGS:
        # A required heading is present if any found heading starts with it
        # (so "🪤 Watch Out For" matches "🪤 Watch Out For (Trap Awareness)")
        if not any(h.startswith(req) for h in found_headings):
            missing.append(req)

    # Anything the LLM added beyond the spec — useful to track forward-compat
    # drift but not a failure condition.
    extras: list[str] = []
    for h in found_headings:
        if not any(h.startswith(req) for req in _REQUIRED_FEEDBACK_HEADINGS):
            extras.append(h)

    return {
        "compliant": len(missing) == 0,
        "missing_headings": missing,
        "extra_headings": extras,
        "headings_found": len(found_headings),
    }


def coach_game(game_id: int, provider: str | None = "claude",
               model: str | None = None, db_path: str | None = None,
               config: dict | None = None,
               dump_prompt_to: "str | None" = None,
               trajectory_enabled: bool | None = None) -> dict:
    """Generate coaching insights for a single analyzed game.

    Args:
        config: Full config dict (from config.yaml). If provided, coaching
                settings (tone, detail_level, focus_areas, custom_instructions,
                coaching_trajectory_enabled) are read from config["coaching"].
        dump_prompt_to: If set (v1.6.0+), the full assembled prompt is written
                to this path with a `_game{id}.txt` suffix. Useful for
                verifying that coaching history is actually being injected
                and for inspecting the full LLM input.
        trajectory_enabled: v1.8.0+ explicit override for the
                ``coaching_trajectory_enabled`` config flag. When True/False
                this takes precedence; when None the config value is used
                (defaults to True). Set to False from CLI ``--no-trajectory``
                for debugging A/B comparisons.

    Returns the parsed coaching data dict.
    """
    conn = init_db(db_path)

    # Fetch game info
    game = conn.execute(
        """SELECT g.*, p.display_name, p.age, p.rating as player_current_rating
        FROM games g JOIN players p ON g.player_id = p.id
        WHERE g.id = ?""",
        (game_id,),
    ).fetchone()

    if not game:
        conn.close()
        raise ValueError(f"Game {game_id} not found")

    if game["analysis_status"] != "complete":
        conn.close()
        raise ValueError(f"Game {game_id} not yet analyzed (status: {game['analysis_status']})")

    # Fetch move analysis
    moves = conn.execute(
        """SELECT * FROM move_analysis WHERE game_id = ?
        ORDER BY move_number, CASE side WHEN 'white' THEN 0 ELSE 1 END""",
        (game_id,),
    ).fetchall()
    moves = [dict(m) for m in moves]

    if not moves:
        conn.close()
        raise ValueError(f"No move analysis found for game {game_id}")

    # Build prompt
    name = game["display_name"] or "Player"
    age = game["age"] or 9
    rating = game["player_rating"] or game["player_current_rating"] or 1000

    # Get tier for adaptive coaching
    tier = get_tier(rating)
    focus_areas_text = "\n".join(f"- {area}" for area in tier.focus_areas)

    # Detect game type for tailored coaching angle
    game_type, game_type_guidance = _detect_game_type(moves, dict(game))

    # Load coaching config for customization (read first so history depth can be configured)
    coaching_config = config.get("coaching", {}) if config else {}

    # Fetch coaching history to avoid repetition.
    # `coaching_history_count` controls how many recent coached games are injected
    # into the prompt; default 5, range 1-20. Each game adds ~500 prompt tokens.
    history_count = coaching_config.get("coaching_history_count", 5)
    try:
        history_count = int(history_count)
    except (TypeError, ValueError):
        history_count = 5
    history_count = max(1, min(20, history_count))

    coaching_history = _fetch_coaching_history(
        conn, game["player_id"], game_id, limit=history_count
    )
    if coaching_history:
        previous_coaching_guidance = coaching_history
    else:
        previous_coaching_guidance = ("\n## Coaching History\n"
                                      "No previous coaching history — this is the first coached game. "
                                      "Set a strong, encouraging foundation.\n")

    # v1.8.0: Player trajectory injection. Pulls the latest player_patterns
    # row and surfaces 6-8 measured cross-game signals (weakest phase,
    # tactical miss rate, ACPL trend direction, etc.) so the per-game
    # coach is aware of the player's broader arc, not just this one game.
    # The flag defaults to True; explicit argument wins over config.
    if trajectory_enabled is None:
        cfg_traj = coaching_config.get("coaching_trajectory_enabled", True)
        trajectory_enabled = bool(cfg_traj)

    if trajectory_enabled:
        # Auto-refresh patterns when stale (>7 days old) or when new
        # completed games exist beyond the patterns' period_end. The
        # compute is pure-Python (no LLM) so this is cheap.
        _maybe_refresh_patterns(conn, game["player_id"], db_path)
        # Lazy import — see src/dashboard_server.py:191 for the same
        # pattern. Avoids any circular-import risk between coach and
        # patterns at module-load time.
        from src.patterns import build_trajectory_block
        player_trajectory, trajectory_diag = build_trajectory_block(
            conn, game["player_id"]
        )
    else:
        player_trajectory = ""
        trajectory_diag = {
            "trajectory_injected": False,
            "trajectory_age_days": None,
            "weakest_phase": None,
            "trend_direction": None,
        }

    # Build tone modifier from config
    tone = coaching_config.get("tone", "balanced")
    tone_modifiers = {
        "encouraging": ("\n- Lean heavily toward praise and positive reinforcement. "
                        "Frame every mistake gently. Use enthusiastic, warm language. "
                        "Celebrate even small victories."),
        "balanced": "",
        "technical": ("\n- Use more precise chess terminology. Be direct about errors. "
                      "Focus on concrete analysis over emotional encouragement. "
                      "Treat the player as a serious student of the game."),
    }
    tone_modifier = tone_modifiers.get(tone, "")

    # Build detail level modifier
    detail_level = coaching_config.get("detail_level", "standard")
    detail_modifiers = {
        "concise": ("\n## Response Length: CONCISE\n"
                    "Keep all sections SHORT. Narrative: 1-2 paragraphs max. "
                    "Player feedback: 1 paragraph. Max 2 tips. "
                    "Critical moments: top 3 only. Coach notes: 1 paragraph."),
        "standard": "",
        "detailed": ("\n## Response Length: DETAILED\n"
                     "Provide THOROUGH analysis. Narrative: 3-4 paragraphs. "
                     "Player feedback: 3-4 paragraphs with 4+ tips. "
                     "Include more context for each critical moment. "
                     "Explain the 'why' behind each suggestion. "
                     "Coach notes: 2-3 detailed paragraphs."),
    }
    detail_modifier = detail_modifiers.get(detail_level, "")

    # Build focus areas modifier
    all_focus = {"openings", "tactics", "endgames", "time_management", "positional_play"}
    selected_focus = set(coaching_config.get("focus_areas", list(all_focus)))
    if selected_focus and selected_focus != all_focus:
        focus_labels = {
            "openings": "opening theory and preparation",
            "tactics": "tactical patterns and calculations",
            "endgames": "endgame technique",
            "time_management": "time management and clock usage",
            "positional_play": "positional understanding and strategy",
        }
        areas_text = ", ".join(focus_labels.get(a, a) for a in selected_focus if a in focus_labels)
        focus_modifier = (f"\n## Coach's Priority Focus\n"
                          f"The coach wants EXTRA emphasis on: {areas_text}. "
                          f"When relevant to this game, prioritize analysis of these areas. "
                          f"However, do not force-fit these if the game does not feature them.")
    else:
        focus_modifier = ""

    # Build custom instructions section
    custom_instructions = coaching_config.get("custom_instructions", "").strip()
    if custom_instructions:
        custom_instructions_section = (
            f"\n## Coach's Custom Instructions\n"
            f"The following are special instructions from the coach. Follow these carefully:\n"
            f"{custom_instructions}")
    else:
        custom_instructions_section = ""

    # v1.13.0: phase-classification summary + trap-awareness context.
    # These give the LLM grounded move-number lists and opening-specific
    # trap candidates so the new 5-section player_feedback can reference
    # mistakes accurately and name relevant traps the opponent could
    # have unleashed.
    phase_classification_summary = _phase_classification_summary(
        moves, game["player_color"]
    )
    relevant_traps_block = _format_relevant_traps_block(
        _traps_for_opening(game["pgn"] or "")
    )

    prompt = GAME_COACHING_PROMPT.format(
        name=name,
        age=age,
        rating=rating,
        tier_label=tier.label,
        tier_icon=tier.icon,
        tier_description=tier.description,
        language_level=tier.language_level,
        focus_areas=focus_areas_text,
        critical_moments_count=tier.critical_moments_count,
        game_type=game_type,
        game_type_guidance=game_type_guidance,
        previous_coaching_guidance=previous_coaching_guidance,
        player_trajectory=player_trajectory,
        phase_classification_summary=phase_classification_summary,
        relevant_traps_block=relevant_traps_block,
        tone_modifier=tone_modifier,
        detail_modifier=detail_modifier,
        focus_modifier=focus_modifier,
        custom_instructions_section=custom_instructions_section,
        player_color=game["player_color"],
        result=game["result"],
        pgn=game["pgn"][:2000],  # Truncate long PGNs to save tokens
        analysis_text=_build_analysis_text(moves),
        critical_moments=_build_critical_moments(moves),
    )

    # Call LLM — use config defaults for provider/model if not explicitly specified
    if not provider:
        provider = coaching_config.get("default_provider", "claude")

    used_model = resolve_model(provider, model, coaching_config)

    # v1.6.0 Phase 2 diagnostics: visibility into history injection + prompt size.
    # v1.8.0 adds trajectory injection status and freshness.
    history_games_injected = _count_history_games(previous_coaching_guidance)
    prompt_tokens_est = _estimate_tokens(prompt)
    history_tokens_est = _estimate_tokens(previous_coaching_guidance)
    trajectory_tokens_est = _estimate_tokens(player_trajectory)
    traj_state = "injected" if trajectory_diag.get("trajectory_injected") else "skipped"
    traj_age = trajectory_diag.get("trajectory_age_days")
    traj_age_str = f"{traj_age}d" if traj_age is not None else "n/a"
    logger.info(
        "Coaching game %d with %s:%s — history=%d games (~%d tokens), "
        "trajectory=%s (age=%s, ~%d tokens), full prompt ~%d tokens",
        game_id, provider, used_model,
        history_games_injected, history_tokens_est,
        traj_state, traj_age_str, trajectory_tokens_est,
        prompt_tokens_est,
    )

    # Optional prompt dump — writes the full prompt to a file for inspection.
    # Useful for "did history actually get in?" verification.
    if dump_prompt_to:
        try:
            from pathlib import Path
            dump_path = Path(dump_prompt_to)
            # Treat as a directory if:
            #   - the path already exists and is a directory
            #   - the path ends with a separator
            #   - the path has no file suffix (e.g. "/tmp/prompts")
            # Otherwise treat as a file path; append `_game_{id}` to avoid
            # clobbering across games.
            looks_like_dir = (
                (dump_path.exists() and dump_path.is_dir())
                or str(dump_prompt_to).endswith(("/", "\\"))
                or not dump_path.suffix
            )
            if looks_like_dir:
                dump_path.mkdir(parents=True, exist_ok=True)
                out_file = dump_path / f"prompt_game_{game_id}.txt"
            else:
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                out_file = dump_path.with_name(
                    f"{dump_path.stem}_game_{game_id}{dump_path.suffix}"
                )
            out_file.write_text(prompt, encoding="utf-8")
            logger.info("Prompt dumped to %s (%d bytes)", out_file, len(prompt))
        except Exception as e:
            logger.warning("Failed to dump prompt for game %d: %s", game_id, e)

    raw = call_provider(provider, prompt, model=used_model,
                        coaching_config=coaching_config)

    # Parse response
    try:
        coaching = _parse_llm_response(raw)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response for game %d: %s", game_id, e)
        logger.debug("Raw response: %s", raw[:500])
        conn.execute(
            "UPDATE games SET coaching_status = 'error' WHERE id = ?",
            (game_id,),
        )
        conn.commit()
        conn.close()
        raise

    # Store in database
    critical_json = json.dumps(coaching.get("critical_moments", []))
    opening_json = json.dumps(coaching.get("opening_analysis", {}))

    # v1.13.2: validate the player_feedback structure. The v1.13.0 prompt
    # requires 5 markdown sections (♟ Opening / ⚔ Middlegame / ♔ Endgame /
    # 🪤 Watch Out For / 🎯 Top 3 Improvements). Older or less-compliant
    # models silently drop the formatting and produce freeform paragraphs,
    # which the frontend then renders via the legacy single-block fallback —
    # masking the format degradation. Logging + meta persistence surfaces
    # the drift in logs and the UI badge.
    feedback_validation = _validate_player_feedback_structure(
        coaching.get("player_feedback")
    )
    if not feedback_validation["compliant"]:
        logger.warning(
            "Coaching game %d (%s:%s): player_feedback NON-COMPLIANT with "
            "v1.13.0 5-section spec. Missing %d/%d required headings: %s. "
            "Consider switching to a newer reasoning model.",
            game_id, provider, used_model,
            len(feedback_validation["missing_headings"]),
            len(_REQUIRED_FEEDBACK_HEADINGS),
            feedback_validation["missing_headings"],
        )

    # v1.6.0: persist coaching meta (history depth, prompt size, model). Lets
    # the UI show "based on N recent games" stamps and lets us correlate
    # coaching quality with prompt context after the fact.
    # v1.8.0: also persist trajectory injection status + age so the UI can
    # render a "30-day trajectory (Nd old)" stamp and so we can compare
    # coaching quality with/without trajectory after the fact.
    # v1.13.2: also persist player_feedback structural compliance so the UI
    # can render a ⚠ badge when the LLM produced freeform output instead
    # of the required 5-section format.
    meta = {
        "history_games_injected": history_games_injected,
        "history_tokens_estimate": history_tokens_est,
        "prompt_tokens_estimate": prompt_tokens_est,
        "provider": provider,
        "model": used_model,
        "trajectory_injected": trajectory_diag.get("trajectory_injected", False),
        "trajectory_age_days": trajectory_diag.get("trajectory_age_days"),
        "trajectory_weakest_phase": trajectory_diag.get("weakest_phase"),
        "trajectory_trend_direction": trajectory_diag.get("trend_direction"),
        "trajectory_tokens_estimate": trajectory_tokens_est,
        "feedback_structure_compliant": feedback_validation["compliant"],
        "feedback_missing_headings": feedback_validation["missing_headings"],
    }
    meta_json = json.dumps(meta)
    coaching["meta"] = meta  # also surface to the immediate caller's response

    provider_model = f"{provider}:{used_model}"
    conn.execute(
        """INSERT OR REPLACE INTO game_coaching
        (game_id, provider, narrative, key_lesson, practical_focus,
         critical_moments_json, opening_analysis_json, player_feedback,
         coach_notes, coaching_meta_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (game_id, provider_model, coaching.get("narrative"),
         coaching.get("key_lesson"), coaching.get("practical_focus"),
         critical_json, opening_json,
         coaching.get("player_feedback"), coaching.get("coach_notes"),
         meta_json),
    )
    conn.execute(
        "UPDATE games SET coaching_status = 'complete' WHERE id = ?",
        (game_id,),
    )
    conn.commit()
    conn.close()

    logger.info("Coaching complete for game %d", game_id)
    return coaching


def _is_rate_limit_error(e: Exception) -> bool:
    """Check if an exception is a rate limit (429) error."""
    msg = str(e).lower()
    return "429" in msg or "rate_limit" in msg or "rate limit" in msg


def _is_auth_error(e: Exception) -> bool:
    """Check if an exception is an authentication/authorization error."""
    msg = str(e).lower()
    return "401" in msg or "403" in msg or "invalid api key" in msg or "not set" in msg


def coach_pending(provider: str = "claude", model: str | None = None,
                  db_path: str | None = None, limit: int = 0,
                  config: dict | None = None,
                  cancel_event: "threading.Event | None" = None,
                  progress_callback: "callable | None" = None,
                  player: str | None = None,
                  dump_prompt_to: "str | None" = None,
                  trajectory_enabled: bool | None = None) -> dict:
    """Generate coaching for analyzed but uncoached games with robust error handling.

    Args:
        limit: Max games to coach (0 = all pending).
        config: Full config dict (from config.yaml) for coaching customization.
        cancel_event: threading.Event — if set, the batch stops gracefully.
        progress_callback: Optional callback(coached, errors, total, message)
                          for real-time progress updates.
        player: Optional username — if provided, only coach this player's games.
        dump_prompt_to: Optional path (v1.6.0+) — if set, full prompts are
                          written to this path (one file per game).

    Returns dict with {coached, errors, skipped, aborted, abort_reason}.
    """
    import threading as _threading

    conn = init_db(db_path)

    # Resolve player filter to player_id
    player_id = None
    if player:
        row = conn.execute("SELECT id FROM players WHERE username = ?", (player,)).fetchone()
        if row:
            player_id = row["id"]
        else:
            logger.warning("Player '%s' not found — coaching all pending games.", player)

    sql = """SELECT id FROM games
        WHERE analysis_status = 'complete' AND coaching_status = 'pending'"""
    params = []
    if player_id:
        sql += " AND player_id = ?"
        params.append(player_id)
    sql += " ORDER BY date_played ASC"
    if limit > 0:
        sql += f" LIMIT {limit}"
    pending = conn.execute(sql, params).fetchall()
    conn.close()

    total_pending = len(pending)
    result = {"coached": 0, "errors": 0, "skipped": 0, "total": total_pending,
              "aborted": False, "abort_reason": None}

    if total_pending == 0:
        logger.info("No pending games to coach.")
        return result

    logger.info("Found %d games to coach%s", total_pending,
                f" (limited to {limit})" if limit > 0 else "")

    # Rate limiting configuration per provider
    if provider == "openai":
        base_delay = 15  # seconds between calls
        logger.info("Using OpenAI — base delay %ds between calls.", base_delay)
    else:
        base_delay = 10  # Claude has more generous limits
        logger.info("Using Claude API — base delay %ds between calls.", base_delay)

    current_delay = base_delay
    consecutive_failures = 0
    max_consecutive_failures = 3  # Abort batch after this many in a row
    max_retries_per_game = 3     # Retries for rate-limited games

    for i, row in enumerate(pending):
        # ── Check cancellation ──
        if cancel_event and cancel_event.is_set():
            result["skipped"] = total_pending - i
            result["aborted"] = True
            result["abort_reason"] = "Cancelled by user"
            logger.info("Coaching batch cancelled by user at game %d/%d", i + 1, total_pending)
            break

        game_id = row["id"]

        # ── Skip if already coached (e.g. per-game coaching clicked during batch) ──
        check_conn = init_db(db_path)
        current_status = check_conn.execute(
            "SELECT coaching_status FROM games WHERE id = ?", (game_id,)
        ).fetchone()
        check_conn.close()
        if current_status and current_status["coaching_status"] == "complete":
            logger.info("Game %d already coached — skipping (%d/%d)", game_id, i + 1, total_pending)
            result["skipped"] += 1
            continue

        logger.info("Coaching game %d/%d (id=%d)", i + 1, total_pending, game_id)

        if progress_callback:
            progress_callback(
                result["coached"], result["errors"], total_pending,
                f"Coaching game {i + 1} of {total_pending} with {provider}..."
            )

        # ── Attempt coaching with retries ──
        success = False
        for attempt in range(1, max_retries_per_game + 1):
            try:
                coach_game(game_id, provider=provider, model=model,
                           db_path=db_path, config=config,
                           dump_prompt_to=dump_prompt_to,
                           trajectory_enabled=trajectory_enabled)
                success = True
                consecutive_failures = 0  # Reset on success
                # Gradually recover delay back to base after successful calls
                if current_delay > base_delay:
                    current_delay = max(base_delay, current_delay - 5)

                # ── Check cancellation immediately after LLM call ──
                if cancel_event and cancel_event.is_set():
                    result["coached"] += 1
                    result["skipped"] = total_pending - i - 1
                    result["aborted"] = True
                    result["abort_reason"] = "Cancelled by user"
                    logger.info("Coaching cancelled after completing game %d/%d", i + 1, total_pending)
                    break
                break

            except Exception as e:
                error_msg = str(e)

                if _is_rate_limit_error(e):
                    # ── Rate limit: exponential backoff ──
                    backoff = min(30 * (2 ** (attempt - 1)), 300)  # 30s, 60s, 120s (max 5min)
                    logger.warning(
                        "Rate limited on game %d (attempt %d/%d). "
                        "Waiting %ds before retry...",
                        game_id, attempt, max_retries_per_game, backoff
                    )
                    # Increase delay for all subsequent games in this batch
                    current_delay = min(current_delay + 10, 60)
                    # Interruptible backoff sleep
                    if cancel_event:
                        cancel_event.wait(backoff)
                        if cancel_event.is_set():
                            result["skipped"] = total_pending - i
                            result["aborted"] = True
                            result["abort_reason"] = "Cancelled by user"
                            return result
                    else:
                        time.sleep(backoff)
                    continue  # Retry

                elif _is_auth_error(e):
                    # ── Auth error: abort immediately ──
                    result["errors"] += 1
                    result["skipped"] = total_pending - i - 1
                    result["aborted"] = True
                    result["abort_reason"] = f"Authentication error: {error_msg}"
                    logger.error("Auth error — aborting batch: %s", error_msg)
                    _mark_game_error(game_id, db_path)
                    return result

                else:
                    # ── Other error: don't retry, count as failure ──
                    logger.error("Failed to coach game %d (attempt %d): %s",
                                 game_id, attempt, error_msg)
                    break  # Don't retry non-rate-limit errors

        if not success:
            result["errors"] += 1
            consecutive_failures += 1
            _mark_game_error(game_id, db_path)

            # ── Consecutive failure circuit breaker ──
            if consecutive_failures >= max_consecutive_failures:
                result["skipped"] = total_pending - i - 1
                result["aborted"] = True
                result["abort_reason"] = (
                    f"Stopped after {max_consecutive_failures} consecutive failures. "
                    f"Last error: {error_msg}"
                )
                logger.error(
                    "Aborting batch: %d consecutive failures. Last error: %s",
                    consecutive_failures, error_msg
                )
                break
        else:
            result["coached"] += 1

        # ── Delay before next game ──
        if i < total_pending - 1:
            logger.info("Waiting %ds before next game...", current_delay)
            # Use cancel_event as interruptible sleep
            if cancel_event:
                cancel_event.wait(current_delay)
                if cancel_event.is_set():
                    result["skipped"] = total_pending - i - 1
                    result["aborted"] = True
                    result["abort_reason"] = "Cancelled by user"
                    break
            else:
                time.sleep(current_delay)

    # Final progress update
    if progress_callback:
        progress_callback(
            result["coached"], result["errors"], total_pending,
            "Coaching complete."
        )

    logger.info(
        "Coaching batch finished: %d coached, %d errors, %d skipped%s",
        result["coached"], result["errors"], result["skipped"],
        f" (ABORTED: {result['abort_reason']})" if result["aborted"] else ""
    )
    return result


def _mark_game_error(game_id: int, db_path: str | None):
    """Mark a game's coaching status as error."""
    err_conn = init_db(db_path)
    err_conn.execute(
        "UPDATE games SET coaching_status = 'error' WHERE id = ?",
        (game_id,),
    )
    err_conn.commit()
    err_conn.close()
