# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""LLM coaching layer for ArrakisEngine.

Generates age-appropriate coaching insights from Stockfish analysis
using either Claude Opus 4.6 or ChatGPT 5.4 Pro (swappable).
"""

import json
import logging
import os
import time

from dotenv import load_dotenv

from src.models import init_db
from src.tiers import get_tier

load_dotenv()

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
   Make it specific and actionable, not generic. MUST be different from any previous lessons
   listed in the coaching history section (if provided). If the same theme keeps appearing,
   go deeper or find a different angle.

4. "practical_focus" — One specific thing to practice, framed as a fun challenge.
   Example: "Before moving a piece, count how many enemy pieces are looking at that square."
   MUST be different from previous practical_focus items in the coaching history (if provided).

5. "critical_moments" — A JSON array of the {critical_moments_count} most important moments. Each object has:
   - "move_number": int
   - "side": "white" or "black"
   - "what_happened": 1-2 sentences a child can understand
   - "what_was_better": 1-2 sentences about the better move
   - "move_played": the move in notation
   - "best_move": the engine's recommended move

6. "opening_analysis" — A JSON object analyzing the opening choice:
   - "opening_name": the name of the opening played (e.g. "Italian Game", "Sicilian Defense")
   - "player_role": "white" if the player chose the opening, or "black" if responding to it
   - "opening_quality": "good", "acceptable", or "poor" — was this a sound opening choice for their level?
   - "correct_counter_moves": true or false — if playing black, did the player respond with correct/principled counter-moves? If playing white, did they follow the main line or deviate poorly?
   - "opening_summary": 2-3 sentences explaining the opening choice. For white: was the system appropriate? Did they develop pieces logically? For black: did they play the correct response to white's opening? Where did they first deviate from good play?
   - "opening_tip": One specific, actionable tip about this opening for a {age}-year-old.

7. "player_feedback" — A personal letter to the child (2-3 paragraphs) written directly to them.
   This is the most important section — it should feel like a kind, encouraging coach talking
   to a {age}-year-old {tier_label}-level player after their game.

   REQUIREMENTS:
   - Address {name} by name. Use "you" throughout.
   - Start by celebrating what they did well — find at least 2 specific good decisions.
   - Frame every mistake as a growth opportunity, but VARY how you do this. Do not always use
     "Next time you see X, try Y." Mix approaches: questions, challenges, stories, analogies.
   - Include 2-4 practical, actionable tips (vary the number — not always exactly 3).
     Pick tips that are DIFFERENT from any listed in the coaching history below.
     If the player has been working on something from a previous game, acknowledge progress
     or gently remind them if the same issue appeared again.
   - End with encouragement, but vary the style — sometimes a challenge for next game,
     sometimes a compliment about their growth, sometimes a fun chess fact or quote.
   - Match language to a {age}-year-old at {tier_label} level: {language_level}
   - Be warm but not patronizing. Respect their intelligence while keeping it accessible.
   - Reference specific moves from THIS game to make it personal, not generic.
   - CRITICALLY: If coaching history is provided, DO NOT repeat the same praise patterns,
     the same tips, or the same closing encouragements. Be creative and fresh each time.

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
    """Extract the top N critical moments by eval swing."""
    sorted_moves = sorted(moves, key=lambda m: m["swing_cp"] or 0, reverse=True)
    critical = sorted_moves[:top_n]
    lines = []
    for m in critical:
        lines.append(
            f"  Move {m['move_number']} ({m['side']}): {m['move_played']} "
            f"— lost {m['swing_cp']}cp (win%: {m['win_prob_before']:.1f}% → "
            f"{m['win_prob_after']:.1f}%). Best was {m['best_move'] or '?'}"
        )
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


def _call_claude(prompt: str, model: str) -> str:
    """Call Anthropic Claude API with extended thinking."""
    import anthropic

    api_key = os.getenv("ARRAKIS_ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ARRAKIS_ANTHROPIC_API_KEY not set in environment")

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model,
        max_tokens=16000,
        thinking={
            "type": "adaptive",
        },
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text from response (skip thinking blocks)
    for block in response.content:
        if block.type == "text":
            return block.text

    raise ValueError("No text content in Claude response")


def _call_openai(prompt: str, model: str) -> str:
    """Call OpenAI Responses API."""
    from openai import OpenAI

    api_key = os.getenv("ARRAKIS_OPENAI_API_KEY")
    if not api_key:
        raise ValueError("ARRAKIS_OPENAI_API_KEY not set in environment")

    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=model,
        instructions="You are an expert chess coach. Respond only with valid JSON.",
        input=prompt,
    )

    return response.output_text


def _parse_llm_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        # Remove code fences
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def coach_game(game_id: int, provider: str | None = "claude",
               model: str | None = None, db_path: str | None = None,
               config: dict | None = None) -> dict:
    """Generate coaching insights for a single analyzed game.

    Args:
        config: Full config dict (from config.yaml). If provided, coaching
                settings (tone, detail_level, focus_areas, custom_instructions)
                are read from config["coaching"].

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

    # Fetch coaching history to avoid repetition
    coaching_history = _fetch_coaching_history(conn, game["player_id"], game_id)
    if coaching_history:
        previous_coaching_guidance = coaching_history
    else:
        previous_coaching_guidance = ("\n## Coaching History\n"
                                      "No previous coaching history — this is the first coached game. "
                                      "Set a strong, encouraging foundation.\n")

    # Load coaching config for customization
    coaching_config = config.get("coaching", {}) if config else {}

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
    logger.info("Coaching game %d with %s...", game_id, provider)

    if provider == "claude":
        default_model = coaching_config.get("anthropic_model", "claude-opus-4-6")
        raw = _call_claude(prompt, model or default_model)
    elif provider == "openai":
        default_model = coaching_config.get("openai_model", "gpt-5.4")
        raw = _call_openai(prompt, model or default_model)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    used_model = model or default_model

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

    provider_model = f"{provider}:{used_model}"
    conn.execute(
        """INSERT OR REPLACE INTO game_coaching
        (game_id, provider, narrative, key_lesson, practical_focus,
         critical_moments_json, opening_analysis_json, player_feedback, coach_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (game_id, provider_model, coaching.get("narrative"),
         coaching.get("key_lesson"), coaching.get("practical_focus"),
         critical_json, opening_json,
         coaching.get("player_feedback"), coaching.get("coach_notes")),
    )
    conn.execute(
        "UPDATE games SET coaching_status = 'complete' WHERE id = ?",
        (game_id,),
    )
    conn.commit()
    conn.close()

    logger.info("Coaching complete for game %d", game_id)
    return coaching


def coach_pending(provider: str = "claude", model: str | None = None,
                  db_path: str | None = None, limit: int = 0,
                  config: dict | None = None) -> int:
    """Generate coaching for analyzed but uncoached games.

    Args:
        limit: Max games to coach (0 = all pending).
        config: Full config dict (from config.yaml) for coaching customization.

    Returns the number of games coached.
    """
    conn = init_db(db_path)
    sql = """SELECT id FROM games
        WHERE analysis_status = 'complete' AND coaching_status = 'pending'"""
    if limit > 0:
        sql += f" LIMIT {limit}"
    pending = conn.execute(sql).fetchall()
    conn.close()

    total_pending = len(pending)
    logger.info("Found %d games to coach%s", total_pending,
                f" (limited to {limit})" if limit > 0 else "")

    # Rate limit advisory
    if provider == "openai":
        logger.warning(
            "⚠️  OpenAI rate limits: gpt-5.4 has 10k TPM limit (~1 game/min). "
            "Recommended: --limit 5 per batch with 10s delay between calls. "
            "For higher throughput, use --provider claude or upgrade your OpenAI plan."
        )
    elif provider == "claude":
        logger.info(
            "Using Claude API. Recommended: --limit 10-20 per batch."
        )

    coached = 0
    for i, row in enumerate(pending):
        logger.info("Coaching game %d/%d (id=%d)", i + 1, len(pending), row["id"])
        try:
            coach_game(row["id"], provider=provider, model=model, db_path=db_path, config=config)
            coached += 1
            # Rate limit: wait 10s between API calls to avoid 429s
            if i < len(pending) - 1:
                logger.info("Waiting 10s for rate limit cooldown...")
                time.sleep(10)
        except Exception as e:
            logger.error("Failed to coach game %d: %s", row["id"], e)
            if "429" in str(e) or "rate_limit" in str(e).lower():
                logger.info("Rate limited — waiting 60s before retry...")
                time.sleep(60)
                # Retry once after cooldown
                try:
                    coach_game(row["id"], provider=provider, model=model, db_path=db_path, config=config)
                    coached += 1
                    continue
                except Exception as retry_e:
                    logger.error("Retry failed for game %d: %s", row["id"], retry_e)
            err_conn = init_db(db_path)
            err_conn.execute(
                "UPDATE games SET coaching_status = 'error' WHERE id = ?",
                (row["id"],),
            )
            err_conn.commit()
            err_conn.close()

    return coached
