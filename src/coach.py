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

load_dotenv()

logger = logging.getLogger(__name__)


GAME_COACHING_PROMPT = """You are a chess coach for a {age}-year-old player named {name} (rated ~{rating}).
Analyze this game and produce coaching insights.

## Player Info
- Name: {name}
- Age: {age}
- Rating: {rating}
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

1. "narrative" — A 2-3 paragraph game story for the child. Use encouraging, concrete language.
   Say "you" not "the player". No chess jargon a {age}-year-old wouldn't know.
   Explain what happened like telling a story. Celebrate good moves, be gentle about mistakes.

2. "key_lesson" — The single most important takeaway from this game, in 1-2 sentences.
   Make it specific and actionable, not generic.

3. "practical_focus" — One specific thing to practice, framed as a fun challenge.
   Example: "Before moving a piece, count how many enemy pieces are looking at that square."

4. "critical_moments" — A JSON array of the 3-5 most important moments. Each object has:
   - "move_number": int
   - "side": "white" or "black"
   - "what_happened": 1-2 sentences a child can understand
   - "what_was_better": 1-2 sentences about the better move
   - "move_played": the move in notation
   - "best_move": the engine's recommended move

5. "coach_notes" — Technical summary for the chess coach. Use precise chess terminology.
   Include: opening assessment, critical tactical moments, endgame technique (if applicable),
   specific weaknesses to address in lessons, and recommended training exercises.
   2-3 paragraphs, professional tone.

Respond with ONLY valid JSON, no markdown code fences or extra text."""


def _build_analysis_text(moves: list[dict]) -> str:
    """Format move analysis into readable text for the prompt."""
    lines = []
    for m in moves:
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
        lines.append(line)
    return "\n".join(lines)


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


def coach_game(game_id: int, provider: str = "claude",
               model: str | None = None, db_path: str | None = None) -> dict:
    """Generate coaching insights for a single analyzed game.

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

    prompt = GAME_COACHING_PROMPT.format(
        name=name,
        age=age,
        rating=rating,
        player_color=game["player_color"],
        result=game["result"],
        pgn=game["pgn"][:3000],  # Truncate very long PGNs
        analysis_text=_build_analysis_text(moves),
        critical_moments=_build_critical_moments(moves),
    )

    # Call LLM
    logger.info("Coaching game %d with %s...", game_id, provider)

    if provider == "claude":
        default_model = "claude-opus-4-6"
        raw = _call_claude(prompt, model or default_model)
    elif provider == "openai":
        default_model = "gpt-5.4"
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

    provider_model = f"{provider}:{used_model}"
    conn.execute(
        """INSERT OR REPLACE INTO game_coaching
        (game_id, provider, narrative, key_lesson, practical_focus,
         critical_moments_json, coach_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (game_id, provider_model, coaching.get("narrative"),
         coaching.get("key_lesson"), coaching.get("practical_focus"),
         critical_json, coaching.get("coach_notes")),
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
                  db_path: str | None = None, limit: int = 0) -> int:
    """Generate coaching for analyzed but uncoached games.

    Args:
        limit: Max games to coach (0 = all pending).

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
            coach_game(row["id"], provider=provider, model=model, db_path=db_path)
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
                    coach_game(row["id"], provider=provider, model=model, db_path=db_path)
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
