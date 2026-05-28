# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Cross-game pattern detection for ArrakisEngine.

Aggregates analysis across all games per player to find recurring
themes: opening performance, ACPL trends, blunder frequency by
game phase, and performance vs. rated opponents.
"""

import json
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import chess.pgn
import io

from src.models import init_db

logger = logging.getLogger(__name__)

# Trap library — loaded lazily on first call to _load_trap_library().
# Built once by `python scripts/build_traps.py` and vendored at the path below.
_TRAP_LIBRARY_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend" / "public" / "data" / "traps.json"
)
_trap_library_cache: list[dict] | None = None


def _get_opening_name(pgn_text: str) -> str:
    """Extract opening name from PGN headers."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return "Unknown"
    eco = game.headers.get("ECOUrl", "")
    opening = game.headers.get("Opening", "")
    if opening:
        return opening
    if eco:
        # Extract name from ECOUrl like /openings/Kings-Pawn-Opening
        parts = eco.rstrip("/").split("/")
        if parts:
            return parts[-1].replace("-", " ")
    return "Unknown"


def _classify_game_phase(move_number: int) -> str:
    """Classify move into game phase."""
    if move_number <= 15:
        return "opening"
    elif move_number <= 30:
        return "middlegame"
    else:
        return "endgame"


def compute_player_patterns(player_id: int, db_path: str | None = None,
                            period_days: int = 30) -> dict:
    """Compute comprehensive pattern stats for a player.

    Returns a stats dict covering openings, phases, trends, and more.
    """
    conn = init_db(db_path)

    # Fetch all analyzed games for this player
    games = conn.execute(
        """SELECT g.* FROM games g
        WHERE g.player_id = ? AND g.analysis_status = 'complete'
        ORDER BY g.date_played""",
        (player_id,),
    ).fetchall()

    if not games:
        conn.close()
        logger.info("No analyzed games for player %d", player_id)
        return {}

    games = [dict(g) for g in games]
    game_ids = [g["id"] for g in games]

    # Fetch all move analysis for these games
    placeholders = ",".join("?" * len(game_ids))
    all_moves = conn.execute(
        f"""SELECT * FROM move_analysis
        WHERE game_id IN ({placeholders})
        ORDER BY game_id, move_number,
        CASE side WHEN 'white' THEN 0 ELSE 1 END""",
        game_ids,
    ).fetchall()
    all_moves = [dict(m) for m in all_moves]

    # Group moves by game
    moves_by_game = defaultdict(list)
    for m in all_moves:
        moves_by_game[m["game_id"]].append(m)

    stats = {
        "total_games": len(games),
        "results": _compute_results(games),
        "openings": _compute_opening_stats(games),
        "acpl_trend": _compute_acpl_trend(games, moves_by_game),
        "phase_analysis": _compute_phase_analysis(games, moves_by_game),
        "rating_performance": _compute_rating_performance(games),
        "move_quality": _compute_move_quality(games, moves_by_game),
        "time_class_stats": _compute_time_class_stats(games),
        # Phase 1 advanced metrics
        "accuracy": _compute_accuracy(games, moves_by_game),
        "consistency": _compute_consistency(games, moves_by_game),
        "danger_zones": _compute_danger_zones(games, moves_by_game),
        "endgame_conversion": _compute_endgame_conversion(games, moves_by_game),
        "time_control_performance": _compute_time_control_performance(games, moves_by_game),
        # Phase 2 deeper insights
        "critical_positions": _compute_critical_positions(games, moves_by_game),
        "comeback_collapse": _compute_comeback_collapse(games, moves_by_game),
        "opening_acpl": _compute_opening_acpl(games, moves_by_game),
        "opening_repertoire": _compute_opening_repertoire(games, moves_by_game),
        "tactical_misses": _compute_tactical_misses(games, moves_by_game),
        # v1.15.0: per-motif aggregation across the same 30-day window.
        # Empty when no games have motifs_json yet (pre-v1.14.0 or
        # not-yet-rescanned). See _compute_motif_summary docstring.
        "motif_summary": _compute_motif_summary(games, moves_by_game, period_days),
        "repertoire_consistency": _compute_repertoire_consistency(games),
        # Time pressure analysis
        "time_pressure": _compute_time_pressure(games, moves_by_game),
        # v1.4.0 Self-Analysis
        "loss_openings": _compute_loss_openings(games),
        "strong_openings": _compute_strong_openings(games),
        "trap_falls": _compute_trap_falls(games),
        "your_arsenal": _compute_your_arsenal(games),
    }

    # Store patterns — preserve existing trend_summary
    now = datetime.now()
    period_start = (now - timedelta(days=period_days)).strftime("%Y-%m-%d")
    period_end = now.strftime("%Y-%m-%d")

    # Check for existing trend_summary to preserve it across recomputes
    existing = conn.execute(
        """SELECT id, trend_summary FROM player_patterns
        WHERE player_id = ? ORDER BY updated_at DESC LIMIT 1""",
        (player_id,),
    ).fetchone()

    existing_summary = existing["trend_summary"] if existing else None

    conn.execute(
        """INSERT OR REPLACE INTO player_patterns
        (player_id, period_start, period_end, stats_json, trend_summary, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))""",
        (player_id, period_start, period_end, json.dumps(stats), existing_summary),
    )
    conn.commit()
    conn.close()

    logger.info("Computed patterns for player %d: %d games analyzed", player_id, len(games))
    return stats


def _compute_results(games: list[dict]) -> dict:
    """Overall win/loss/draw stats."""
    results = {"win": 0, "loss": 0, "draw": 0}
    for g in games:
        results[g["result"]] = results.get(g["result"], 0) + 1
    total = len(games)
    return {
        "wins": results["win"],
        "losses": results["loss"],
        "draws": results["draw"],
        "win_rate": round(results["win"] / total * 100, 1) if total else 0,
    }


def _extract_opening_moves(pgn_text: str, max_moves: int = 15) -> str:
    """Extract the first N moves from a PGN as a move text string."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return ""
    moves = []
    node = game
    move_count = 0
    while node.variations:
        node = node.variations[0]
        move_count += 1
        if move_count > max_moves * 2:  # max_moves is full moves (2 half-moves each)
            break
        moves.append(node.san())

    # Format as standard move text: 1.e4 e5 2.Nf3 Nc6 ...
    parts = []
    for i, san in enumerate(moves):
        if i % 2 == 0:
            parts.append(f"{i // 2 + 1}.{san}")
        else:
            parts.append(san)
    return " ".join(parts)


def _compute_opening_stats(games: list[dict]) -> dict:
    """Win rate by opening name, split by color.

    Returns {"all": [...], "white": [...], "black": [...]}.
    Each opening entry includes opening_moves (PGN fragment) and
    game_list (metadata for all games using that opening).
    """
    def _aggregate(game_list):
        openings = defaultdict(lambda: {
            "games": 0, "wins": 0, "losses": 0, "draws": 0,
            "game_list": [], "representative_pgn": None,
        })
        for g in game_list:
            name = _get_opening_name(g["pgn"])
            openings[name]["games"] += 1
            if g["result"] == "win":
                openings[name]["wins"] += 1
            elif g["result"] == "loss":
                openings[name]["losses"] += 1
            else:
                openings[name]["draws"] += 1
            # Collect game metadata for the game list
            openings[name]["game_list"].append({
                "game_id": g["id"],
                "date": g["date_played"],
                "opponent": g.get("opponent_username") or str(g.get("opponent_rating", "?")),
                "result": g["result"],
            })
            # Use earliest game as representative (games are sorted by date)
            if openings[name]["representative_pgn"] is None:
                openings[name]["representative_pgn"] = g["pgn"]

        result = []
        for name, data in sorted(openings.items(), key=lambda x: x[1]["games"], reverse=True):
            if data["games"] >= 2:
                # Extract opening moves from representative game
                opening_moves = ""
                if data["representative_pgn"]:
                    opening_moves = _extract_opening_moves(data["representative_pgn"])
                # Sort game_list by date descending (most recent first)
                data["game_list"].sort(
                    key=lambda x: x["date"] or "", reverse=True
                )
                result.append({
                    "name": name,
                    "games": data["games"],
                    "wins": data["wins"],
                    "losses": data["losses"],
                    "draws": data["draws"],
                    "win_rate": round(data["wins"] / data["games"] * 100, 1),
                    "opening_moves": opening_moves,
                    "game_list": data["game_list"],
                })
        return result[:20]

    white_games = [g for g in games if g["player_color"] == "white"]
    black_games = [g for g in games if g["player_color"] == "black"]

    return {
        "all": _aggregate(games),
        "white": _aggregate(white_games),
        "black": _aggregate(black_games),
    }


# ── v1.4.0 Self-Analysis: loss/strong openings + trap matching ────────────


def _load_trap_library() -> list[dict]:
    """Load the curated trap library from frontend/public/data/traps.json.

    Cached on first call. Returns [] if the file is missing (e.g. fresh
    clone before `python scripts/build_traps.py` has been run).

    Each entry: {eco, name, moves_san, moves: list[str], depth: int}.
    Library is pre-sorted deepest-first by the build script so callers
    iterating in order naturally pick the most-specific match.
    """
    global _trap_library_cache
    if _trap_library_cache is not None:
        return _trap_library_cache
    if not _TRAP_LIBRARY_PATH.exists():
        logger.warning(
            "Trap library not found at %s — run `python scripts/build_traps.py`",
            _TRAP_LIBRARY_PATH,
        )
        _trap_library_cache = []
        return _trap_library_cache
    try:
        with open(_TRAP_LIBRARY_PATH, "r", encoding="utf-8") as f:
            _trap_library_cache = json.load(f)
        logger.info("Loaded %d trap signatures", len(_trap_library_cache))
    except (OSError, json.JSONDecodeError) as e:
        logger.exception("Failed to load trap library: %s", e)
        _trap_library_cache = []
    return _trap_library_cache


def _extract_san_moves(pgn_text: str, max_moves: int = 30) -> list[str]:
    """Extract a flat list of SAN moves from a PGN. max_moves is plies."""
    if not pgn_text:
        return []
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
    except Exception:
        return []
    if game is None:
        return []
    moves: list[str] = []
    node = game
    while node.variations and len(moves) < max_moves:
        node = node.variations[0]
        try:
            moves.append(node.san())
        except Exception:
            break
    return moves


def _match_trap(game_moves: list[str], trap_library: list[dict]) -> dict | None:
    """Longest-prefix match of game_moves against the trap library.

    Returns the matching trap entry (with eco, name, depth) or None.

    The library is sorted deepest-first so the first match is the most-
    specific one (e.g. matches "Halloween Gambit, Oldtimer Variation"
    in preference to plain "Halloween Gambit" if both apply).
    """
    if not game_moves or not trap_library:
        return None
    for entry in trap_library:
        sig = entry.get("moves") or []
        if len(sig) > len(game_moves):
            continue
        if sig and game_moves[: len(sig)] == sig:
            return entry
    return None


def _frequency_label(count: int) -> str:
    """Bucket a recurrence count into the user-facing frequency vocabulary."""
    if count >= 6:
        return "Frequent"
    if count >= 3:
        return "Occasional"
    return "Rare"


def _aggregate_openings_by_outcome(games: list[dict], outcome: str) -> dict:
    """Group games by opening name, split by player color, filtered to one
    outcome ('win' or 'loss'). Used for both 'Fix Your Openings' (loss)
    and 'Your Strengths' (win).

    Returns {white: [...], black: [...]} sorted by count descending.
    """
    def _aggregate(game_list: list[dict]) -> list[dict]:
        # Group all games (any outcome) by opening, then count wins/losses
        by_opening: dict[str, dict] = defaultdict(lambda: {
            "total": 0, "wins": 0, "losses": 0, "draws": 0,
            "recent_game_ids": [],
        })
        for g in game_list:
            name = _get_opening_name(g["pgn"])
            entry = by_opening[name]
            entry["total"] += 1
            if g["result"] == "win":
                entry["wins"] += 1
            elif g["result"] == "loss":
                entry["losses"] += 1
            else:
                entry["draws"] += 1
            if g["result"] == outcome:
                entry["recent_game_ids"].append(g["id"])

        out = []
        for name, e in by_opening.items():
            outcome_count = e["wins"] if outcome == "win" else e["losses"]
            if outcome_count == 0:
                continue
            # Need at least 2 games in that opening to flag a pattern
            if e["total"] < 2:
                continue
            rate = round(outcome_count / e["total"] * 100, 1)
            # Keep the most recent 5 games (input is date-ascending, so
            # take the tail and reverse for newest-first display).
            recent = list(reversed(e["recent_game_ids"]))[:5]
            out.append({
                "name": name,
                "total": e["total"],
                "wins": e["wins"],
                "losses": e["losses"],
                "draws": e["draws"],
                "rate": rate,
                "recent_game_ids": recent,
            })
        # Sort by raw outcome count first, then by rate (so 8 losses out of
        # 10 ranks above 5 losses out of 5 if the user has a long history).
        sort_key = (
            (lambda x: (-x["losses"], -x["rate"]))
            if outcome == "loss"
            else (lambda x: (-x["wins"], -x["rate"]))
        )
        out.sort(key=sort_key)
        return out[:10]

    white_games = [g for g in games if g["player_color"] == "white"]
    black_games = [g for g in games if g["player_color"] == "black"]
    return {
        "white": _aggregate(white_games),
        "black": _aggregate(black_games),
    }


def _compute_loss_openings(games: list[dict]) -> dict:
    """Openings where the player loses most often (split by color).
    Drives the 'Fix Your Openings — ELO leaks' panel."""
    return _aggregate_openings_by_outcome(games, outcome="loss")


def _compute_strong_openings(games: list[dict]) -> dict:
    """Openings where the player wins most often (split by color).
    Drives the 'Your Strengths' panel."""
    return _aggregate_openings_by_outcome(games, outcome="win")


def _aggregate_traps_by_outcome(
    games: list[dict],
    outcome: str,
    trap_library: list[dict],
) -> list[dict]:
    """For each game with the matching outcome, try to detect a named trap
    from the curated library, then aggregate by trap name.

    Returns a list of {name, eco, count, win_rate, recent_dates,
    recent_game_ids, frequency_label, trend} sorted by count descending.
    Only traps with at least 1 occurrence appear; results are capped at 8.

    `recent_game_ids` (added in v1.4.3) lists up to 5 game IDs where the
    requested outcome happened, newest-first — so the UI can link the
    player back to the actual game where they fell into (or won with)
    the trap.
    """
    if not trap_library:
        return []

    # First pass: detect a trap on every game (regardless of outcome)
    # so we can compute a true win-rate per trap.
    per_trap: dict[str, dict] = defaultdict(lambda: {
        "name": None,
        "eco": None,
        "total": 0,         # total games that hit this trap
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "outcome_events": [],  # (date, game_id) pairs where requested outcome happened
    })

    for g in games:
        moves = _extract_san_moves(g["pgn"], max_moves=20)
        trap = _match_trap(moves, trap_library)
        if trap is None:
            continue
        key = trap["name"]
        rec = per_trap[key]
        rec["name"] = trap["name"]
        rec["eco"] = trap.get("eco")
        rec["total"] += 1
        if g["result"] == "win":
            rec["wins"] += 1
        elif g["result"] == "loss":
            rec["losses"] += 1
        else:
            rec["draws"] += 1
        if g["result"] == outcome:
            # Track (date, id) pair so we can sort newest-first while still
            # carrying the game_id forward for the UI link.
            rec["outcome_events"].append(
                (g.get("date_played") or "", g.get("id"))
            )

    out = []
    for key, rec in per_trap.items():
        outcome_count = rec["wins"] if outcome == "win" else rec["losses"]
        if outcome_count == 0:
            continue
        win_rate = round(rec["wins"] / rec["total"] * 100, 1) if rec["total"] else 0
        # Sort events newest-first; keep top 5
        rec["outcome_events"].sort(key=lambda x: x[0], reverse=True)
        top = rec["outcome_events"][:5]
        recent_dates = [d for (d, _gid) in top if d]
        recent_game_ids = [gid for (_d, gid) in top if gid is not None]
        out.append({
            "name": rec["name"],
            "eco": rec["eco"],
            "count": outcome_count,
            "total": rec["total"],
            "wins": rec["wins"],
            "losses": rec["losses"],
            "draws": rec["draws"],
            "win_rate": win_rate,
            "recent_dates": recent_dates,
            "recent_game_ids": recent_game_ids,
            "frequency_label": _frequency_label(outcome_count),
            # Trend is reserved for a future v1.5 enhancement (compare
            # current period vs prior). For now, "flat" is a safe default.
            "trend": "flat",
        })
    out.sort(key=lambda x: (-x["count"], x["name"]))
    return out[:8]


def _compute_trap_falls(games: list[dict]) -> list[dict]:
    """Recurring named traps the player keeps LOSING to.
    Drives the 'You Fall For — Avoid these!' panel."""
    return _aggregate_traps_by_outcome(games, "loss", _load_trap_library())


def _compute_your_arsenal(games: list[dict]) -> list[dict]:
    """Recurring named traps the player keeps WINNING with.
    Drives the 'Your Arsenal — Keep using!' panel."""
    return _aggregate_traps_by_outcome(games, "win", _load_trap_library())


# ──────────────────────────────────────────────────────────────────────────


def _per_move_player_loss(m: dict, side: str, eval_cap: int = 1000) -> int:
    """Per-move centipawn loss with the v1.7.1 rules, used everywhere
    that computes ACPL from a move row.

    Rules (must match `src/analyzer.py` and `src/models.py::backfill_acpl_for_games`):

      1. If `move_played == best_move`, loss = 0 (engine's #1 choice
         can't be a "mistake", including mate-delivering moves).
      2. Otherwise cap each eval at ±EVAL_CAP, difference them from
         `side`'s perspective, take max(0, ·).
      3. Cap the resulting per-move loss at EVAL_CAP (Lichess
         convention — any single move contributes at most EVAL_CAP to
         the average).

    Centralized in v1.7.4 — previously 7 sites each had their own
    inline copy of this logic, only one of which (the ACPL trend chart,
    fixed in v1.7.1) had the played-best and per-move-cap rules.
    Inflated values on Phase ACPL, Opening ACPL, Time-Control ACPL,
    Consistency, Opening Repertoire, and Tactical Misses are all
    eliminated by routing through this single function.

    Args:
        m: A move_analysis row dict.
        side: "white" or "black" — the moving side.
        eval_cap: Cap magnitude in centipawns (default 1000).

    Returns the per-move loss in centipawns, in [0, eval_cap].
    """
    played = m.get("move_played")
    best = m.get("best_move")
    if played and best and played == best:
        return 0
    before = max(-eval_cap, min(eval_cap, m.get("eval_before_cp") or 0))
    after = max(-eval_cap, min(eval_cap, m.get("eval_after_cp") or 0))
    if side == "white":
        raw = max(0, before - after)
    else:
        raw = max(0, after - before)
    return min(raw, eval_cap)


def _compute_acpl_trend(games: list[dict],
                        moves_by_game: dict[int, list[dict]]) -> list[dict]:
    """ACPL trend using per-game stored ACPL (±1000cp capped).

    Uses the pre-computed ACPL stored on each game (backfilled with
    capped evaluations). Falls back to computing from moves if ACPL
    is not yet stored.

    Returns weekly buckets with average ACPL and individual game data points.
    """
    EVAL_CAP = 1000
    weekly = defaultdict(lambda: {"acpl_sum": 0, "games": 0, "game_points": []})

    for g in games:
        if not g["date_played"]:
            continue
        try:
            dp = g["date_played"]
            date = datetime.strptime(dp, "%Y-%m-%d %H:%M:%S") if " " in dp else datetime.strptime(dp, "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        week_start = (date - timedelta(days=date.weekday())).strftime("%Y-%m-%d")

        game_acpl = g.get("acpl")

        # Fallback: compute from moves if not stored. v1.7.4: now routes
        # through the shared _per_move_player_loss helper (matches the
        # backfill_acpl_for_games logic).
        if game_acpl is None:
            player_moves = [
                m for m in moves_by_game.get(g["id"], [])
                if m["side"] == g["player_color"]
            ]
            if not player_moves:
                continue
            losses = [
                _per_move_player_loss(m, m["side"], EVAL_CAP)
                for m in player_moves
            ]
            game_acpl = round(sum(losses) / len(losses), 1) if losses else None

        if game_acpl is not None:
            weekly[week_start]["acpl_sum"] += game_acpl
            weekly[week_start]["games"] += 1
            weekly[week_start]["game_points"].append({
                "date": g["date_played"],
                "acpl": game_acpl,
                "result": g["result"],
            })

    trend = []
    for week, data in sorted(weekly.items()):
        if data["games"] > 0:
            trend.append({
                "week": week,
                "acpl": round(data["acpl_sum"] / data["games"], 1),
                "games": data["games"],
                "game_points": data["game_points"],
            })

    return trend


def _compute_phase_analysis(games: list[dict],
                            moves_by_game: dict[int, list[dict]]) -> dict:
    """Blunder/mistake frequency by game phase."""
    phases = {
        "opening": {"moves": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0, "cp_loss": 0},
        "middlegame": {"moves": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0, "cp_loss": 0},
        "endgame": {"moves": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0, "cp_loss": 0},
    }

    EVAL_CAP = 1000
    for g in games:
        player_moves = [
            m for m in moves_by_game.get(g["id"], [])
            if m["side"] == g["player_color"]
        ]
        for m in player_moves:
            phase = _classify_game_phase(m["move_number"])
            phases[phase]["moves"] += 1
            # v1.7.4: use the shared helper so mate-transition moves don't
            # inflate per-phase ACPL (especially endgame, where mates land)
            phases[phase]["cp_loss"] += _per_move_player_loss(
                m, m["side"], EVAL_CAP,
            )
            if m["classification"] == "blunder":
                phases[phase]["blunders"] += 1
            elif m["classification"] == "mistake":
                phases[phase]["mistakes"] += 1
            elif m["classification"] == "inaccuracy":
                phases[phase]["inaccuracies"] += 1

    # Add ACPL per phase
    for phase_data in phases.values():
        if phase_data["moves"] > 0:
            phase_data["acpl"] = round(phase_data["cp_loss"] / phase_data["moves"], 1)
        else:
            phase_data["acpl"] = 0

    return phases


def _compute_rating_performance(games: list[dict]) -> dict:
    """Performance vs. higher/lower/equal rated opponents."""
    buckets = {
        "vs_higher": {"games": 0, "wins": 0, "losses": 0, "draws": 0},
        "vs_lower": {"games": 0, "wins": 0, "losses": 0, "draws": 0},
        "vs_equal": {"games": 0, "wins": 0, "losses": 0, "draws": 0},
    }

    for g in games:
        pr = g["player_rating"]
        opp = g["opponent_rating"]
        if pr is None or opp is None:
            continue

        diff = opp - pr
        if diff > 50:
            bucket = "vs_higher"
        elif diff < -50:
            bucket = "vs_lower"
        else:
            bucket = "vs_equal"

        buckets[bucket]["games"] += 1
        if g["result"] == "win":
            buckets[bucket]["wins"] += 1
        elif g["result"] == "loss":
            buckets[bucket]["losses"] += 1
        else:
            buckets[bucket]["draws"] += 1

    for bucket_data in buckets.values():
        total = bucket_data["games"]
        bucket_data["win_rate"] = round(bucket_data["wins"] / total * 100, 1) if total else 0

    return buckets


def _compute_move_quality(games: list[dict],
                          moves_by_game: dict[int, list[dict]]) -> dict:
    """Overall move quality distribution."""
    quality = {"excellent": 0, "good": 0, "inaccuracy": 0, "mistake": 0, "blunder": 0}
    total = 0

    for g in games:
        player_moves = [
            m for m in moves_by_game.get(g["id"], [])
            if m["side"] == g["player_color"]
        ]
        for m in player_moves:
            cls = m["classification"]
            if cls in quality:
                quality[cls] += 1
            total += 1

    # Add percentages
    result = {}
    for cls, count in quality.items():
        result[cls] = {
            "count": count,
            "pct": round(count / total * 100, 1) if total else 0,
        }
    result["total_moves"] = total
    return result


def _compute_time_class_stats(games: list[dict]) -> dict:
    """Win rate by time class."""
    classes = defaultdict(lambda: {"games": 0, "wins": 0, "losses": 0, "draws": 0})
    for g in games:
        tc = g["time_class"] or "unknown"
        classes[tc]["games"] += 1
        if g["result"] == "win":
            classes[tc]["wins"] += 1
        elif g["result"] == "loss":
            classes[tc]["losses"] += 1
        else:
            classes[tc]["draws"] += 1

    result = {}
    for tc, data in classes.items():
        data["win_rate"] = round(data["wins"] / data["games"] * 100, 1) if data["games"] else 0
        result[tc] = data
    return result


def _compute_accuracy(games: list[dict],
                      moves_by_game: dict[int, list[dict]]) -> dict:
    """Accuracy % — percentage of moves matching the engine's best move.

    A move is considered "best" if the centipawn loss is 0 (played move == engine top choice).
    Also computes per-game accuracy for trend analysis.
    """
    total_moves = 0
    best_moves = 0
    game_accuracies = []

    for g in games:
        player_moves = [
            m for m in moves_by_game.get(g["id"], [])
            if m["side"] == g["player_color"]
        ]
        if not player_moves:
            continue

        game_best = sum(1 for m in player_moves
                        if m["move_played"] == m.get("best_move"))
        game_total = len(player_moves)
        total_moves += game_total
        best_moves += game_best
        game_acc = round(game_best / game_total * 100, 1) if game_total else 0
        game_accuracies.append({
            "game_id": g["id"],
            "date": g["date_played"],
            "accuracy": game_acc,
            "result": g["result"],
        })

    overall = round(best_moves / total_moves * 100, 1) if total_moves else 0

    return {
        "overall_pct": overall,
        "best_moves": best_moves,
        "total_moves": total_moves,
        "per_game": game_accuracies,
    }


def _compute_consistency(games: list[dict],
                         moves_by_game: dict[int, list[dict]]) -> dict:
    """Consistency Score — standard deviation of per-game ACPL.

    Low std dev = steady play; high = wild swings.
    Also includes best/worst game ACPL for context.
    """
    EVAL_CAP = 1000
    game_acpls = []

    for g in games:
        acpl = g.get("acpl")
        if acpl is None:
            # v1.7.4: fallback now matches backfill_acpl_for_games via the
            # shared helper. (Previously had its own inline implementation
            # that lacked the v1.7.1 played-best + per-move-cap rules.)
            player_moves = [
                m for m in moves_by_game.get(g["id"], [])
                if m["side"] == g["player_color"]
            ]
            if not player_moves:
                continue
            losses = [
                _per_move_player_loss(m, m["side"], EVAL_CAP)
                for m in player_moves
            ]
            acpl = round(sum(losses) / len(losses), 1) if losses else None

        if acpl is not None:
            game_acpls.append({
                "game_id": g["id"],
                "date": g["date_played"],
                "acpl": acpl,
                "result": g["result"],
            })

    if len(game_acpls) < 2:
        return {
            "std_dev": 0, "mean_acpl": 0, "best_acpl": 0, "worst_acpl": 0,
            "total_games": len(game_acpls), "rating": "insufficient data",
        }

    values = [g["acpl"] for g in game_acpls]
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std_dev = round(math.sqrt(variance), 1)
    best = min(values)
    worst = max(values)

    # Rate consistency
    if std_dev < 15:
        rating = "Very consistent"
    elif std_dev < 30:
        rating = "Consistent"
    elif std_dev < 50:
        rating = "Variable"
    else:
        rating = "Highly variable"

    return {
        "std_dev": std_dev,
        "mean_acpl": round(mean, 1),
        "best_acpl": round(best, 1),
        "worst_acpl": round(worst, 1),
        "total_games": len(game_acpls),
        "rating": rating,
    }


def _compute_danger_zones(games: list[dict],
                          moves_by_game: dict[int, list[dict]]) -> dict:
    """Move Number Danger Zone — histogram of blunders by move number.

    Identifies which move ranges have the most blunders, revealing
    patterns like opening unfamiliarity, middlegame tactical gaps,
    or endgame fatigue.
    """
    # Bucket by 5-move ranges: 1-5, 6-10, 11-15, etc.
    BUCKET_SIZE = 5
    buckets = defaultdict(lambda: {"blunders": 0, "mistakes": 0, "total_moves": 0})

    for g in games:
        player_moves = [
            m for m in moves_by_game.get(g["id"], [])
            if m["side"] == g["player_color"]
        ]
        for m in player_moves:
            mn = m["move_number"]
            bucket_start = ((mn - 1) // BUCKET_SIZE) * BUCKET_SIZE + 1
            bucket_end = bucket_start + BUCKET_SIZE - 1
            bucket_key = f"{bucket_start}-{bucket_end}"
            buckets[bucket_key]["total_moves"] += 1
            if m["classification"] == "blunder":
                buckets[bucket_key]["blunders"] += 1
            elif m["classification"] == "mistake":
                buckets[bucket_key]["mistakes"] += 1

    # Convert to sorted list and compute rates
    result = []
    for key in sorted(buckets.keys(), key=lambda k: int(k.split("-")[0])):
        data = buckets[key]
        total = data["total_moves"]
        result.append({
            "range": key,
            "blunders": data["blunders"],
            "mistakes": data["mistakes"],
            "total_moves": total,
            "blunder_rate": round(data["blunders"] / total * 100, 1) if total else 0,
            "error_rate": round((data["blunders"] + data["mistakes"]) / total * 100, 1) if total else 0,
        })

    # Find the worst danger zone
    worst_zone = max(result, key=lambda x: x["blunder_rate"]) if result else None

    return {
        "histogram": result,
        "worst_zone": worst_zone,
        "bucket_size": BUCKET_SIZE,
    }


def _compute_endgame_conversion(games: list[dict],
                                moves_by_game: dict[int, list[dict]]) -> dict:
    """Endgame Conversion Rate — how well the player converts advantages.

    Tracks:
    - Won positions entering endgame (>200cp advantage at move 30) → did they win?
    - Lost positions entering endgame → did they hold/draw?
    - Equal endgames → win/draw/loss rate
    """
    EVAL_CAP = 1000
    ENDGAME_MOVE = 30
    ADVANTAGE_THRESHOLD = 200

    stats = {
        "winning_endgames": {"total": 0, "converted": 0, "drawn": 0, "lost": 0},
        "losing_endgames": {"total": 0, "saved": 0, "drawn": 0, "lost": 0},
        "equal_endgames": {"total": 0, "won": 0, "drawn": 0, "lost": 0},
        "games_reaching_endgame": 0,
        "total_analyzed": len(games),
    }

    for g in games:
        player_moves = [
            m for m in moves_by_game.get(g["id"], [])
            if m["side"] == g["player_color"]
        ]
        if not player_moves:
            continue

        # Find eval at move 30 (endgame start)
        endgame_moves = [m for m in player_moves if m["move_number"] >= ENDGAME_MOVE]
        if not endgame_moves:
            continue  # Game didn't reach endgame

        stats["games_reaching_endgame"] += 1
        first_endgame = endgame_moves[0]
        eval_cp = first_endgame.get("eval_before_cp") or 0
        eval_cp = max(-EVAL_CAP, min(EVAL_CAP, eval_cp))

        # Normalize to player's perspective
        if g["player_color"] == "black":
            eval_cp = -eval_cp

        result = g["result"]

        if eval_cp >= ADVANTAGE_THRESHOLD:
            # Player was winning entering endgame
            stats["winning_endgames"]["total"] += 1
            if result == "win":
                stats["winning_endgames"]["converted"] += 1
            elif result == "draw":
                stats["winning_endgames"]["drawn"] += 1
            else:
                stats["winning_endgames"]["lost"] += 1
        elif eval_cp <= -ADVANTAGE_THRESHOLD:
            # Player was losing entering endgame
            stats["losing_endgames"]["total"] += 1
            if result == "win":
                stats["losing_endgames"]["saved"] += 1
            elif result == "draw":
                stats["losing_endgames"]["drawn"] += 1
            else:
                stats["losing_endgames"]["lost"] += 1
        else:
            # Roughly equal
            stats["equal_endgames"]["total"] += 1
            if result == "win":
                stats["equal_endgames"]["won"] += 1
            elif result == "draw":
                stats["equal_endgames"]["drawn"] += 1
            else:
                stats["equal_endgames"]["lost"] += 1

    # Compute conversion rates
    w = stats["winning_endgames"]
    w["conversion_rate"] = round(w["converted"] / w["total"] * 100, 1) if w["total"] else 0

    l = stats["losing_endgames"]
    l["save_rate"] = round((l["saved"] + l["drawn"]) / l["total"] * 100, 1) if l["total"] else 0

    e = stats["equal_endgames"]
    e["win_rate"] = round(e["won"] / e["total"] * 100, 1) if e["total"] else 0

    stats["endgame_reach_pct"] = round(
        stats["games_reaching_endgame"] / len(games) * 100, 1
    ) if games else 0

    return stats


def _compute_time_control_performance(games: list[dict],
                                      moves_by_game: dict[int, list[dict]]) -> dict:
    """Time Control Performance — win rate + ACPL by time class.

    Extends the basic time_class_stats with ACPL per time control,
    revealing whether the player performs better in slower or faster games.
    """
    EVAL_CAP = 1000
    tc_data = defaultdict(lambda: {
        "games": 0, "wins": 0, "losses": 0, "draws": 0,
        "acpl_sum": 0, "acpl_count": 0, "blunders": 0, "total_moves": 0,
    })

    for g in games:
        tc = g["time_class"] or "unknown"
        tc_data[tc]["games"] += 1
        if g["result"] == "win":
            tc_data[tc]["wins"] += 1
        elif g["result"] == "loss":
            tc_data[tc]["losses"] += 1
        else:
            tc_data[tc]["draws"] += 1

        # ACPL per time control. v1.7.4: shared helper for consistency.
        acpl = g.get("acpl")
        if acpl is None:
            player_moves = [
                m for m in moves_by_game.get(g["id"], [])
                if m["side"] == g["player_color"]
            ]
            if player_moves:
                losses = [
                    _per_move_player_loss(m, m["side"], EVAL_CAP)
                    for m in player_moves
                ]
                acpl = round(sum(losses) / len(losses), 1) if losses else None

        if acpl is not None:
            tc_data[tc]["acpl_sum"] += acpl
            tc_data[tc]["acpl_count"] += 1

        # Count blunders per time control
        player_moves = [
            m for m in moves_by_game.get(g["id"], [])
            if m["side"] == g["player_color"]
        ]
        for m in player_moves:
            tc_data[tc]["total_moves"] += 1
            if m["classification"] == "blunder":
                tc_data[tc]["blunders"] += 1

    result = {}
    for tc, data in tc_data.items():
        result[tc] = {
            "games": data["games"],
            "wins": data["wins"],
            "losses": data["losses"],
            "draws": data["draws"],
            "win_rate": round(data["wins"] / data["games"] * 100, 1) if data["games"] else 0,
            "acpl": round(data["acpl_sum"] / data["acpl_count"], 1) if data["acpl_count"] else 0,
            "blunders": data["blunders"],
            "blunder_rate": round(data["blunders"] / data["total_moves"] * 100, 1) if data["total_moves"] else 0,
        }

    return result


def _compute_critical_positions(games: list[dict],
                                moves_by_game: dict[int, list[dict]]) -> dict:
    """Critical Position Success Rate.

    A critical position is where a large eval swing was possible (>200cp
    swing between best move and played move). Measures how often the
    player found a good-enough move in these high-stakes moments.
    """
    CRITICAL_THRESHOLD = 200  # cp swing that makes a position "critical"
    GOOD_ENOUGH_THRESHOLD = 50  # player's loss < 50cp = "handled well"

    total_critical = 0
    handled_well = 0
    critical_details = []  # top examples

    for g in games:
        player_moves = [
            m for m in moves_by_game.get(g["id"], [])
            if m["side"] == g["player_color"]
        ]
        for m in player_moves:
            swing = m.get("swing_cp") or 0
            # A position is critical if the best move existed that could
            # swing eval significantly — we detect this by looking at
            # positions where the player DID lose a lot (they missed it)
            # or positions where a big swing was available but they handled it
            best_existed = m.get("best_move") and m["best_move"] != m.get("move_played")

            # Critical = blunder or mistake (big swing was possible and missed)
            # OR excellent/good in a complex position (swing was possible but handled)
            if swing >= CRITICAL_THRESHOLD or (best_existed and swing >= CRITICAL_THRESHOLD):
                total_critical += 1
                if swing <= GOOD_ENOUGH_THRESHOLD:
                    handled_well += 1
                if len(critical_details) < 20:
                    critical_details.append({
                        "game_id": g["id"],
                        "move_number": m["move_number"],
                        "swing_cp": swing,
                        "classification": m["classification"],
                        "handled": swing <= GOOD_ENOUGH_THRESHOLD,
                        "date": g["date_played"],
                    })

    # Also count positions where the player found good moves under pressure
    # (opponent had just made a mistake creating a tactical opportunity)
    opportunities_found = 0
    opportunities_total = 0
    for g in games:
        player_color = g["player_color"]
        opp_color = "black" if player_color == "white" else "white"
        game_moves = moves_by_game.get(g["id"], [])
        opp_moves = [m for m in game_moves if m["side"] == opp_color]

        for opp_m in opp_moves:
            if (opp_m.get("swing_cp") or 0) >= CRITICAL_THRESHOLD:
                # Opponent blundered — did our player capitalize?
                opportunities_total += 1
                # Find the player's next move
                next_player = [
                    m for m in game_moves
                    if m["side"] == player_color
                    and m["move_number"] == opp_m["move_number"] + (1 if player_color == "black" else 0)
                ]
                if next_player and (next_player[0].get("swing_cp") or 0) <= GOOD_ENOUGH_THRESHOLD:
                    opportunities_found += 1

    return {
        "total_critical": total_critical,
        "handled_well": handled_well,
        "success_rate": round(handled_well / total_critical * 100, 1) if total_critical else 0,
        "opportunities_found": opportunities_found,
        "opportunities_total": opportunities_total,
        "opportunity_rate": round(opportunities_found / opportunities_total * 100, 1) if opportunities_total else 0,
        "examples": critical_details[:10],
    }


def _compute_comeback_collapse(games: list[dict],
                               moves_by_game: dict[int, list[dict]]) -> dict:
    """Comeback and Collapse rates.

    - Comeback: player was losing (>-200cp) at some point but won/drew
    - Collapse: player was winning (>+200cp) at some point but lost/drew
    """
    EVAL_CAP = 1000
    THRESHOLD = 200  # cp advantage/disadvantage

    stats = {
        "comebacks": {"total_losing_games": 0, "recovered": 0, "won": 0, "drawn": 0},
        "collapses": {"total_winning_games": 0, "collapsed": 0, "lost": 0, "drawn": 0},
    }

    for g in games:
        player_moves = [
            m for m in moves_by_game.get(g["id"], [])
            if m["side"] == g["player_color"]
        ]
        if not player_moves:
            continue

        # Track max advantage and max disadvantage during the game
        max_advantage = 0
        max_disadvantage = 0

        for m in player_moves:
            eval_cp = m.get("eval_before_cp") or 0
            eval_cp = max(-EVAL_CAP, min(EVAL_CAP, eval_cp))
            # Normalize to player perspective
            if g["player_color"] == "black":
                eval_cp = -eval_cp
            max_advantage = max(max_advantage, eval_cp)
            max_disadvantage = min(max_disadvantage, eval_cp)

        # Was losing at some point?
        if max_disadvantage <= -THRESHOLD:
            stats["comebacks"]["total_losing_games"] += 1
            if g["result"] == "win":
                stats["comebacks"]["recovered"] += 1
                stats["comebacks"]["won"] += 1
            elif g["result"] == "draw":
                stats["comebacks"]["recovered"] += 1
                stats["comebacks"]["drawn"] += 1

        # Was winning at some point?
        if max_advantage >= THRESHOLD:
            stats["collapses"]["total_winning_games"] += 1
            if g["result"] == "loss":
                stats["collapses"]["collapsed"] += 1
                stats["collapses"]["lost"] += 1
            elif g["result"] == "draw" and max_advantage >= THRESHOLD * 2:
                # Only count draws as collapses if advantage was very large
                stats["collapses"]["collapsed"] += 1
                stats["collapses"]["drawn"] += 1

    cb = stats["comebacks"]
    cb["comeback_rate"] = round(
        cb["recovered"] / cb["total_losing_games"] * 100, 1
    ) if cb["total_losing_games"] else 0

    cl = stats["collapses"]
    cl["collapse_rate"] = round(
        cl["collapsed"] / cl["total_winning_games"] * 100, 1
    ) if cl["total_winning_games"] else 0

    return stats


def _compute_opening_repertoire(games: list[dict],
                                moves_by_game: dict[int, list[dict]]) -> dict:
    """Opening repertoire tracker: trends, ECO distribution, focus areas.

    For each opening, computes win-rate trend (improving/declining/stable),
    ECO code, ACPL, and generates focus-area recommendations.
    """
    EVAL_CAP = 1000

    # Group games by opening name
    opening_games: dict[str, list[dict]] = defaultdict(list)
    for g in games:
        name = _get_opening_name(g["pgn"])
        opening_games[name].append(g)

    # Extract ECO code from PGN
    def _get_eco(pgn_text: str) -> str:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if game is None:
            return ""
        return game.headers.get("ECO", "")

    openings_result = []

    for name, og in opening_games.items():
        if len(og) < 2:
            continue

        wins = sum(1 for g in og if g["result"] == "win")
        losses = sum(1 for g in og if g["result"] == "loss")
        draws = sum(1 for g in og if g["result"] == "draw")
        total = len(og)
        win_rate = round(wins / total * 100, 1)

        # ECO code — use first game that has one
        eco = ""
        for g in og:
            eco = _get_eco(g["pgn"])
            if eco:
                break

        # Color — determine if mainly white, black, or both
        white_count = sum(1 for g in og if g["player_color"] == "white")
        black_count = total - white_count
        if white_count > 0 and black_count == 0:
            color = "white"
        elif black_count > 0 and white_count == 0:
            color = "black"
        else:
            color = "both"

        # Trend — split into older and newer halves by date
        sorted_games = sorted(og, key=lambda g: g["date_played"] or "")
        mid = len(sorted_games) // 2
        if mid >= 1:
            older = sorted_games[:mid]
            newer = sorted_games[mid:]
            older_wr = sum(1 for g in older if g["result"] == "win") / len(older) * 100
            newer_wr = sum(1 for g in newer if g["result"] == "win") / len(newer) * 100
            delta = newer_wr - older_wr
            if delta > 10:
                trend = "improving"
            elif delta < -10:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # ACPL for opening phase (moves 1-15)
        acpl_sum = 0.0
        acpl_games = 0
        for g in og:
            player_moves = [
                m for m in moves_by_game.get(g["id"], [])
                if m["side"] == g["player_color"] and m["move_number"] <= 15
            ]
            if player_moves:
                # v1.7.4: shared helper for consistency with backfill_acpl
                move_losses = [
                    _per_move_player_loss(m, m["side"], EVAL_CAP)
                    for m in player_moves
                ]
                if move_losses:
                    acpl_sum += sum(move_losses) / len(move_losses)
                    acpl_games += 1

        acpl = round(acpl_sum / acpl_games, 1) if acpl_games else 0.0

        openings_result.append({
            "name": name,
            "eco": eco,
            "games": total,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": win_rate,
            "trend": trend,
            "acpl": acpl,
            "color": color,
        })

    # Sort by number of games descending
    openings_result.sort(key=lambda x: -x["games"])

    # ECO distribution — group by first letter
    eco_distribution: dict[str, int] = defaultdict(int)
    for entry in openings_result:
        if entry["eco"]:
            letter = entry["eco"][0].upper()
            eco_distribution[letter] += entry["games"]

    # Focus areas — openings with >= 3 games and poor performance
    focus_areas = []
    for entry in openings_result:
        if entry["games"] < 3:
            continue
        reasons = []
        if entry["win_rate"] < 40:
            reasons.append(f"Low win rate ({entry['win_rate']}%)")
        if entry["acpl"] > 80:
            reasons.append(f"High ACPL ({entry['acpl']})")
        if not reasons:
            continue

        # Generate suggestion based on the issue
        if entry["acpl"] > 80 and entry["win_rate"] < 40:
            suggestion = f"Study the key plans and typical tactics in the {entry['name']}. Consider simplifying your opening play."
        elif entry["acpl"] > 80:
            suggestion = f"Practice the critical positions in the {entry['name']} to reduce mistakes in the opening phase."
        else:
            suggestion = f"Review your {entry['name']} games to understand where you're going wrong. Consider trying a different line."

        focus_areas.append({
            "name": entry["name"],
            "eco": entry["eco"],
            "games": entry["games"],
            "win_rate": entry["win_rate"],
            "acpl": entry["acpl"],
            "reason": " | ".join(reasons),
            "suggestion": suggestion,
        })

    # Sort focus areas by most games first (higher priority = more played)
    focus_areas.sort(key=lambda x: -x["games"])

    return {
        "openings": openings_result[:30],
        "eco_distribution": dict(eco_distribution),
        "focus_areas": focus_areas[:10],
    }


def _compute_opening_acpl(games: list[dict],
                          moves_by_game: dict[int, list[dict]]) -> list[dict]:
    """ACPL per opening — reveals which openings the player handles well vs poorly.

    Only includes openings with 3+ games for statistical relevance.
    """
    EVAL_CAP = 1000
    opening_data = defaultdict(lambda: {
        "acpl_sum": 0, "games": 0, "wins": 0, "losses": 0, "draws": 0,
        "blunders": 0, "total_moves": 0,
    })

    for g in games:
        name = _get_opening_name(g["pgn"])
        opening_data[name]["games"] += 1
        if g["result"] == "win":
            opening_data[name]["wins"] += 1
        elif g["result"] == "loss":
            opening_data[name]["losses"] += 1
        else:
            opening_data[name]["draws"] += 1

        # Compute ACPL for opening phase only (moves 1-15)
        player_moves = [
            m for m in moves_by_game.get(g["id"], [])
            if m["side"] == g["player_color"] and m["move_number"] <= 15
        ]
        if player_moves:
            losses = []
            for m in player_moves:
                # v1.7.4: shared helper. Mate-transition moves in the
                # opening phase no longer inflate per-opening ACPL.
                losses.append(
                    _per_move_player_loss(m, m["side"], EVAL_CAP)
                )
                if m["classification"] == "blunder":
                    opening_data[name]["blunders"] += 1
                opening_data[name]["total_moves"] += 1

            game_acpl = sum(losses) / len(losses) if losses else 0
            opening_data[name]["acpl_sum"] += game_acpl

    # Filter to openings with 3+ games and sort by ACPL
    result = []
    for name, data in opening_data.items():
        if data["games"] >= 3:
            acpl = round(data["acpl_sum"] / data["games"], 1) if data["games"] else 0
            win_rate = round(data["wins"] / data["games"] * 100, 1) if data["games"] else 0
            blunder_rate = round(
                data["blunders"] / data["total_moves"] * 100, 1
            ) if data["total_moves"] else 0

            # Rate the opening for this player
            if acpl < 30 and win_rate >= 60:
                recommendation = "Strong — keep playing"
            elif acpl < 50 and win_rate >= 45:
                recommendation = "Solid — room to improve"
            elif acpl > 80 or win_rate < 35:
                recommendation = "Struggling — study or consider alternatives"
            else:
                recommendation = "Average — needs more games"

            result.append({
                "name": name,
                "games": data["games"],
                "wins": data["wins"],
                "losses": data["losses"],
                "draws": data["draws"],
                "win_rate": win_rate,
                "opening_acpl": acpl,
                "blunder_rate": blunder_rate,
                "recommendation": recommendation,
            })

    # Sort: worst ACPL first (areas needing improvement)
    result.sort(key=lambda x: -x["opening_acpl"])
    return result


# ── v1.15.0 Motif Aggregation ─────────────────────────────────────────────

# Canonical 8 motif identifiers from src/motifs.py. Hard-coded here (not
# imported) to keep patterns.py free of motif-detection imports — the
# detector module is heavy (chess.Board work). Order is alphabetical, NOT
# specificity order — sorts happen downstream by missed-count.
_MOTIF_IDENTIFIERS = (
    "discovered_check",
    "fork",
    "hanging_piece",
    "mate_threat",
    "pin",
    "removing_defender",
    "skewer",
    "trapped_piece",
)


def _compute_motif_summary(games: list[dict],
                           moves_by_game: dict[int, list[dict]],
                           period_days: int = 30) -> dict:
    """Per-motif missed/found counts across the player's recent games.

    Aggregates `move_analysis.motifs_json` (populated for critical moves
    since v1.14.0) into a cross-game view: for each of the 8 motif
    identifiers, how often did the player MISS the theme (their move
    didn't execute it but the engine's best move did) vs. FIND it
    (both the played move and best move executed it).

    Scope:
      - Player-side moves only (`m["side"] == g["player_color"]`).
      - Games within the last ``period_days`` (matches the 30-day
        window stored on player_patterns).
      - Games with NULL `date_played` are excluded as out-of-window
        (defensive — mirrors `_compute_acpl_trend`).
      - Moves without `motifs_json` (non-critical, or pre-v1.14.0
        rows that haven't been rescanned) contribute nothing.

    Counting semantics:
      - `missed`: per-instance count of identifiers appearing in
        `motifs_json["missed"]`. This is the strongest "you didn't
        see it" signal — engine's best move had the theme, yours
        didn't.
      - `found`: per-instance count of identifiers appearing in BOTH
        `motifs_json["played"]` and `motifs_json["best"]`. The player
        executed the same theme the engine wanted.
      - Identifiers appearing only in `played` (not `best`) are
        ignored — the player executed a theme but the engine
        preferred a different idea, so the "credit" is ambiguous.
      - `miss_rate` = missed / (missed + found) * 100.

    Returned dict shape (additive evolution — v1.15.0 fields all
    still present, v1.16.0 adds phase splits and dominant-phase tags):
      {
        "period_days": 30,
        "total_critical_moves": N,         # moves with motifs_json in window
        "by_motif": [                      # sorted: missed desc, then found desc
            {
              "motif": "fork",
              "missed": 8, "found": 3, "miss_rate": 72.7,
              # v1.16.0:
              "missed_by_phase": {"opening": 1, "middlegame": 5, "endgame": 2},
              "found_by_phase":  {"opening": 0, "middlegame": 3, "endgame": 0},
              "dominant_missed_phase": "middlegame",  # or None
            },
            ...
        ],
        "top_missed": "fork" | None,
        "top_missed_count": 8,
        # v1.16.0:
        "top_missed_dominant_phase": "middlegame",  # or None
      }

    Empty/degenerate cases:
      - No games or no motifs_json anywhere → `total_critical_moves: 0`,
        `by_motif` has 8 entries with all-zero counts and
        `dominant_missed_phase = None`. `top_missed*` are None/0.

    v1.15.0+ / v1.16.0 (phase splits)
    """
    cutoff_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

    # v1.16.0: phase-keyed buckets. Each motif tracks
    # {opening: int, middlegame: int, endgame: int} for both missed
    # and found. Total = sum(phase_counts.values()).
    _zero_phases = lambda: {"opening": 0, "middlegame": 0, "endgame": 0}
    missed_by_phase: dict[str, dict[str, int]] = {
        m: _zero_phases() for m in _MOTIF_IDENTIFIERS
    }
    found_by_phase: dict[str, dict[str, int]] = {
        m: _zero_phases() for m in _MOTIF_IDENTIFIERS
    }
    total_critical_moves = 0

    for g in games:
        date_played = g.get("date_played")
        if not date_played or date_played[:10] < cutoff_date:
            # NULL or older than the window → skip.
            continue

        player_color = g.get("player_color")
        if player_color not in ("white", "black"):
            continue

        game_moves = moves_by_game.get(g["id"], [])
        for m in game_moves:
            if m.get("side") != player_color:
                continue
            raw = m.get("motifs_json")
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if not isinstance(parsed, dict):
                continue

            total_critical_moves += 1

            played = parsed.get("played") or []
            best = parsed.get("best") or []
            missed = parsed.get("missed") or []

            if not isinstance(played, list):
                played = []
            if not isinstance(best, list):
                best = []
            if not isinstance(missed, list):
                missed = []

            played_set = set(played)
            best_set = set(best)

            # v1.16.0: classify the move's phase once; bump phase buckets.
            move_no = m.get("move_number")
            try:
                phase = _classify_game_phase(int(move_no))
            except (TypeError, ValueError):
                continue  # malformed move_number — skip this move's counts

            for motif in missed:
                if motif in missed_by_phase:
                    missed_by_phase[motif][phase] += 1
            for motif in best_set & played_set:
                if motif in found_by_phase:
                    found_by_phase[motif][phase] += 1

    by_motif: list[dict] = []
    for motif in _MOTIF_IDENTIFIERS:
        m_phases = missed_by_phase[motif]
        f_phases = found_by_phase[motif]
        m = sum(m_phases.values())
        f = sum(f_phases.values())
        denom = m + f
        miss_rate = round(m / denom * 100, 1) if denom else 0.0
        by_motif.append({
            "motif": motif,
            "missed": m,
            "found": f,
            "miss_rate": miss_rate,
            # v1.16.0: per-phase splits. Always present (each phase is
            # 0 when no instances landed there) so the frontend can
            # rely on the keys existing.
            "missed_by_phase": m_phases,
            "found_by_phase": f_phases,
            "dominant_missed_phase": _dominant_phase(m_phases),
        })

    # Sort: most-missed first, then most-found as tiebreaker.
    by_motif.sort(key=lambda x: (-x["missed"], -x["found"]))

    top = by_motif[0] if by_motif else None
    top_missed = top["motif"] if top and top["missed"] > 0 else None
    top_missed_count = top["missed"] if top and top["missed"] > 0 else 0
    # v1.16.0: pass through the top motif's dominant phase (or None).
    top_missed_dominant_phase = (
        top["dominant_missed_phase"] if top and top["missed"] > 0 else None
    )

    return {
        "period_days": period_days,
        "total_critical_moves": total_critical_moves,
        "by_motif": by_motif,
        "top_missed": top_missed,
        "top_missed_count": top_missed_count,
        # v1.16.0: dominant phase of the top-missed motif. None when the
        # top motif's missed instances are <3 OR no phase has ≥60% share.
        "top_missed_dominant_phase": top_missed_dominant_phase,
    }


def _dominant_phase(phase_counts: dict[str, int]) -> str | None:
    """v1.16.0: return the phase ("opening" / "middlegame" / "endgame")
    that holds ≥60% of `phase_counts.values()`, OR None if no phase
    dominates or the total signal is too small.

    Rules:
      - Total < 3 → None (insufficient signal; one or two missed
        instances aren't a "concentration", they're noise).
      - Phase with max count ≥ 60% of total → that phase.
      - Otherwise → None (counts are too balanced to call dominant).

    The 60% threshold matches "a clear majority but not unanimous":
    4/6 (67%) feels like a real pattern; 3/6 (50%) doesn't.
    """
    total = sum(phase_counts.values())
    if total < 3:
        return None
    top_phase, top_count = max(phase_counts.items(), key=lambda kv: kv[1])
    if top_count / total >= 0.6:
        return top_phase
    return None


def _compute_tactical_misses(games: list[dict],
                             moves_by_game: dict[int, list[dict]]) -> dict:
    """Tactical Miss Rate.

    Positions where a large advantage (>200cp) was available but the
    player missed it (played a move with >100cp loss). Counts how often
    the player fails to capitalize on tactical opportunities.
    """
    EVAL_CAP = 1000
    OPPORTUNITY_THRESHOLD = 200  # cp advantage available
    MISS_THRESHOLD = 100  # cp loss that counts as "missed"

    total_opportunities = 0
    missed = 0
    found = 0
    miss_by_phase = {"opening": 0, "middlegame": 0, "endgame": 0}
    opp_by_phase = {"opening": 0, "middlegame": 0, "endgame": 0}

    for g in games:
        player_color = g["player_color"]
        opp_color = "black" if player_color == "white" else "white"
        game_moves = moves_by_game.get(g["id"], [])

        for m in game_moves:
            if m["side"] != player_color:
                continue

            # v1.7.4: cp_loss now goes through the shared helper. The
            # MISS/OPPORTUNITY thresholds below (100/200) are well below the
            # per-move cap (1000), so behavior is unchanged — just code consistency.
            # (Removed dead `player_eval_before` calculation that was set
            # but never read.)
            cp_loss = _per_move_player_loss(m, player_color, EVAL_CAP)

            # Tactical opportunity: position was good for the player AND
            # best move was significantly better than what was played
            best_move = m.get("best_move")
            played = m.get("move_played")

            if best_move and best_move != played and cp_loss >= MISS_THRESHOLD:
                phase = _classify_game_phase(m["move_number"])
                total_opportunities += 1
                opp_by_phase[phase] += 1

                if cp_loss >= OPPORTUNITY_THRESHOLD:
                    missed += 1
                    miss_by_phase[phase] += 1
                else:
                    found += 1

    return {
        "total_opportunities": total_opportunities,
        "missed": missed,
        "found": found,
        "miss_rate": round(missed / total_opportunities * 100, 1) if total_opportunities else 0,
        "find_rate": round(found / total_opportunities * 100, 1) if total_opportunities else 0,
        "miss_by_phase": miss_by_phase,
        "opportunities_by_phase": opp_by_phase,
    }


def _compute_repertoire_consistency(games: list[dict]) -> dict:
    """Repertoire Consistency — does the player stick to a small set of openings?

    A consistent repertoire aids improvement. Measures:
    - How many unique openings used (as white and black)
    - What % of games use the top 3 openings
    - Consistency score (higher = more focused)
    """
    white_openings = defaultdict(int)
    black_openings = defaultdict(int)

    for g in games:
        name = _get_opening_name(g["pgn"])
        if g["player_color"] == "white":
            white_openings[name] += 1
        else:
            black_openings[name] += 1

    def _analyze_repertoire(opening_counts: dict, total_games: int) -> dict:
        if not opening_counts:
            return {
                "unique_openings": 0, "top_3": [], "top_3_pct": 0,
                "consistency_score": 0, "rating": "No games",
            }

        sorted_openings = sorted(opening_counts.items(), key=lambda x: -x[1])
        top_3 = sorted_openings[:3]
        top_3_games = sum(c for _, c in top_3)
        top_3_pct = round(top_3_games / total_games * 100, 1) if total_games else 0

        # Consistency score: % of games in top 3 openings
        # Penalized by number of unique openings
        unique = len(opening_counts)
        if unique <= 3:
            consistency = top_3_pct
        elif unique <= 6:
            consistency = top_3_pct * 0.9
        else:
            consistency = top_3_pct * 0.75

        consistency = round(min(100, consistency), 1)

        if consistency >= 75:
            rating = "Very focused"
        elif consistency >= 55:
            rating = "Reasonably consistent"
        elif consistency >= 35:
            rating = "Scattered"
        else:
            rating = "No clear repertoire"

        return {
            "unique_openings": unique,
            "top_3": [{"name": n, "games": c, "pct": round(c / total_games * 100, 1)} for n, c in top_3],
            "top_3_pct": top_3_pct,
            "consistency_score": consistency,
            "rating": rating,
        }

    white_games = sum(white_openings.values())
    black_games = sum(black_openings.values())

    return {
        "white": _analyze_repertoire(white_openings, white_games),
        "black": _analyze_repertoire(black_openings, black_games),
        "total_unique": len(set(list(white_openings.keys()) + list(black_openings.keys()))),
    }


def update_patterns(db_path: str | None = None) -> int:
    """Update patterns for all players with analyzed games.

    Returns number of players updated.
    """
    conn = init_db(db_path)
    players = conn.execute(
        """SELECT DISTINCT p.id, p.username FROM players p
        JOIN games g ON g.player_id = p.id
        WHERE g.analysis_status = 'complete'"""
    ).fetchall()
    conn.close()

    logger.info("Updating patterns for %d players", len(players))

    for p in players:
        logger.info("Computing patterns for %s (id=%d)", p["username"], p["id"])
        stats = compute_player_patterns(p["id"], db_path=db_path)
        if stats:
            logger.info(
                "  %s: %d games, %.1f%% win rate, ACPL trend: %d weeks",
                p["username"],
                stats["total_games"],
                stats["results"]["win_rate"],
                len(stats["acpl_trend"]),
            )

    return len(players)


# ---------------------------------------------------------------------------
# LLM-powered cross-game trend summary
# ---------------------------------------------------------------------------

TREND_PROMPT = """You are a professional chess coach reviewing a player's recent performance data.

## Player Info
- Name: {name}
- Age: {age}
- Rating: {rating}
- Tier: {tier_label} {tier_icon}

## Performance Summary (last {total_games} games)
- Win rate: {win_rate}%
- Results: {wins}W / {losses}L / {draws}D
- Average ACPL: {avg_acpl}
- Consistency: {consistency}
- Best game ACPL: {best_acpl}  |  Worst game ACPL: {worst_acpl}

## Phase Analysis
- Opening ACPL: {opening_acpl} ({opening_moves} moves)
- Middlegame ACPL: {middlegame_acpl} ({middlegame_moves} moves)
- Endgame ACPL: {endgame_acpl} ({endgame_moves} moves)
- Weakest phase: {worst_phase}

## Move Quality
- Excellent: {excellent_pct}%  |  Good: {good_pct}%
- Inaccuracies: {inaccuracy_pct}%  |  Mistakes: {mistake_pct}%  |  Blunders: {blunder_pct}%

## Additional Metrics
- Accuracy (best moves played): {accuracy_pct}%
- Endgame conversion rate: {endgame_conversion}%
- Tactical miss rate: {tactical_miss_rate}%
- Comeback rate: {comeback_rate}%  |  Collapse rate: {collapse_rate}%
- Repertoire focus: {repertoire_rating}

## ACPL Trend (weekly)
{acpl_trend_text}

## Recurring Tactical Themes (last 30 days)
{motif_summary_text}

## Output format (REQUIRED — read carefully)
Your reply must be PLAIN TEXT ONLY:
- 3 or 4 paragraphs separated by blank lines (one blank line between paragraphs)
- NO JSON, NO arrays, NO objects. Do not wrap your output in `[...]` or `{{...}}`
- NO markdown headings (no `#`, `##`), NO bullet lists (no `-`, `*`, `1.`), NO code fences
- NO preamble like "Sure," / "Certainly," / "Here is your summary:" — start directly with the first sentence of paragraph 1
- NO trailing commentary

The FIRST CHARACTER of your reply must be a letter — never an opening bracket, brace, hash, code fence, or quotation mark.

## Instructions
Write a 3-4 paragraph coaching summary for {name}. This is a progress review, not a single-game analysis.

Requirements:
- Address {name} by name. Use "you" throughout.
- Paragraph 1: Overall progress and what's going well. Be specific with numbers.
- Paragraph 2: Areas that need improvement. Reference the weakest phase, common mistakes, or tactical misses.
- Paragraph 3: 3 specific, actionable practice recommendations appropriate for a {age}-year-old {tier_label}-level player.
  - v1.15.0: When the Recurring Tactical Themes section shows a clear top miss (>= 5 instances), make ONE of the 3 practice recommendations specifically about that motif (name it: "fork puzzles", "pin exercises", etc.). If no theme has reached 5 instances, ignore this rule and pick 3 general recommendations.
  - v1.16.0: When that motif ALSO has a "X focus" tag in the Recurring Tactical Themes block (concentrated in one phase — opening, middlegame, or endgame), name the phase in the recommendation. Examples: "10 middlegame hanging-piece puzzles every day" instead of just "hanging-piece puzzles"; "spot opening pins in your first 10 moves" instead of "spot pins". If no phase focus is tagged, ignore this rule and keep the recommendation general.
- Paragraph 4: Encouragement and growth mindset message.
- Keep language age-appropriate for {age} years old.
- Be warm but professional. Concrete, not vague.

Respond with ONLY the text paragraphs, no JSON, no headers, no markdown formatting. Begin with the first word of paragraph 1; end with the last word of the final paragraph."""


def _format_motif_summary_for_prompt(motif_summary: dict) -> str:
    """v1.15.0: format the motif_summary aggregate as plain lines for the
    LLM prompt. One line per non-zero motif, sorted missed-desc, plus a
    headline if any motif has reached the ≥5 instance "clear top" bar.

    v1.16.0: each line now includes a per-phase split (opening N,
    middlegame N, endgame N) and a trailing "— X focus" tag when the
    motif is concentrated (≥60%) in a single phase. The Headline also
    grows a "concentrated in X (P of T)" sentence when the top motif
    has a dominant phase.

    Returns "  No motif data yet — coach more games or run rescan-motifs."
    when the aggregate has zero critical moves in the window. The leading
    indentation matches the rest of the prompt's bullet styling.
    """
    if not motif_summary or motif_summary.get("total_critical_moves", 0) == 0:
        return "  No motif data yet — coach more games or run rescan-motifs."

    by_motif = motif_summary.get("by_motif") or []
    nonzero = [e for e in by_motif if (e.get("missed", 0) + e.get("found", 0)) > 0]
    if not nonzero:
        return "  No motif data yet — coach more games or run rescan-motifs."

    lines = []
    top = motif_summary.get("top_missed")
    top_count = motif_summary.get("top_missed_count", 0)
    top_phase = motif_summary.get("top_missed_dominant_phase")
    if top and top_count >= 5:
        headline = (
            f"  Headline: {top} is the most-missed theme "
            f"({top_count} instances in the last 30 days)."
        )
        # v1.16.0: when the top motif has a dominant phase, append a
        # concentration sentence inside the Headline so the LLM can
        # spot the phase-naming signal without scanning bullets.
        if top_phase:
            # Find the phase count for clearer attribution
            top_row = next(
                (e for e in nonzero if e.get("motif") == top),
                None,
            )
            if top_row:
                phase_count = (top_row.get("missed_by_phase") or {}).get(top_phase, 0)
                headline = headline.rstrip(".")
                headline += (
                    f" — concentrated in {top_phase} "
                    f"({phase_count} of {top_count})."
                )
        lines.append(headline)

    for e in nonzero:
        base = (
            f"  - {e['motif']}: missed {e['missed']}× / found {e['found']}× "
            f"({e['miss_rate']}% miss rate)"
        )
        # v1.16.0: append phase split when data is present (always set
        # by the v1.16.0 aggregator; defensive None-check for forward
        # compatibility with pre-v1.16.0 stored stats_json).
        m_phases = e.get("missed_by_phase")
        if isinstance(m_phases, dict):
            base += (
                f"; phase split: opening {m_phases.get('opening', 0)}, "
                f"middlegame {m_phases.get('middlegame', 0)}, "
                f"endgame {m_phases.get('endgame', 0)}"
            )
            # Focus tag when this motif has a dominant phase
            dom = e.get("dominant_missed_phase")
            if dom:
                base += f" — {dom} focus"
        lines.append(base)
    return "\n".join(lines)


def generate_trend_summary(player_id: int, db_path: str | None = None,
                           provider: str = "claude", model: str | None = None) -> str:
    """Generate an LLM-powered trend summary from pattern stats.

    Reads the latest pattern stats, builds a prompt, calls the LLM,
    and stores the result in the player_patterns table.

    Returns the summary text.
    """
    from src.llm_providers import call_provider, resolve_model
    from src.tiers import get_tier

    conn = init_db(db_path)

    # Get player info
    player = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    if not player:
        conn.close()
        raise ValueError(f"Player {player_id} not found")

    # Get latest pattern stats
    row = conn.execute(
        """SELECT * FROM player_patterns WHERE player_id = ?
        ORDER BY updated_at DESC LIMIT 1""",
        (player_id,),
    ).fetchone()

    if not row or not row["stats_json"]:
        conn.close()
        raise ValueError(f"No pattern stats for player {player_id}. Run patterns first.")

    stats = json.loads(row["stats_json"])
    pattern_id = row["id"]

    name = player["display_name"] or player["username"]
    age = player["age"] or 10
    rating = player["rating"] or 1000
    tier = get_tier(rating)

    # Extract stats safely
    results = stats.get("results", {})
    phase = stats.get("phase_analysis", {})
    mq = stats.get("move_quality", {})
    consistency = stats.get("consistency", {})
    accuracy = stats.get("accuracy", {})
    endgame = stats.get("endgame_conversion", {})
    tactical = stats.get("tactical_misses", {})
    comeback = stats.get("comeback_collapse", {})
    repertoire = stats.get("repertoire_consistency", {})

    # Build ACPL trend text
    trend = stats.get("acpl_trend", [])
    if trend:
        trend_lines = [f"  {t['week']}: ACPL {t['acpl']} ({t['games']} games)" for t in trend[-8:]]
        acpl_trend_text = "\n".join(trend_lines)
    else:
        acpl_trend_text = "  No trend data available"

    # v1.15.0: Build motif summary text from the per-motif aggregate.
    motif_summary_text = _format_motif_summary_for_prompt(
        stats.get("motif_summary") or {}
    )

    def _safe_get(d, *keys, default="N/A"):
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k)
            else:
                return default
        return d if d is not None else default

    prompt = TREND_PROMPT.format(
        name=name, age=age, rating=rating,
        tier_label=tier.label, tier_icon=tier.icon,
        total_games=stats.get("total_games", 0),
        win_rate=results.get("win_rate", 0),
        wins=results.get("wins", 0),
        losses=results.get("losses", 0),
        draws=results.get("draws", 0),
        avg_acpl=_safe_get(consistency, "mean_acpl"),
        consistency=_safe_get(consistency, "rating"),
        best_acpl=_safe_get(consistency, "best_acpl"),
        worst_acpl=_safe_get(consistency, "worst_acpl"),
        opening_acpl=_safe_get(phase, "opening", "acpl"),
        opening_moves=_safe_get(phase, "opening", "moves", default=0),
        middlegame_acpl=_safe_get(phase, "middlegame", "acpl"),
        middlegame_moves=_safe_get(phase, "middlegame", "moves", default=0),
        endgame_acpl=_safe_get(phase, "endgame", "acpl"),
        endgame_moves=_safe_get(phase, "endgame", "moves", default=0),
        worst_phase=stats.get("worst_phase", "N/A") if "worst_phase" in stats
                    else _find_worst_phase(phase),
        excellent_pct=_safe_get(mq, "excellent", "pct", default=0),
        good_pct=_safe_get(mq, "good", "pct", default=0),
        inaccuracy_pct=_safe_get(mq, "inaccuracy", "pct", default=0),
        mistake_pct=_safe_get(mq, "mistake", "pct", default=0),
        blunder_pct=_safe_get(mq, "blunder", "pct", default=0),
        accuracy_pct=_safe_get(accuracy, "overall_pct", default=0),
        endgame_conversion=_safe_get(endgame, "winning_endgames", "conversion_rate", default=0),
        tactical_miss_rate=_safe_get(tactical, "miss_rate", default=0),
        comeback_rate=_safe_get(comeback, "comebacks", "comeback_rate", default=0),
        collapse_rate=_safe_get(comeback, "collapses", "collapse_rate", default=0),
        repertoire_rating=_safe_get(repertoire, "white", "rating", default="N/A"),
        acpl_trend_text=acpl_trend_text,
        motif_summary_text=motif_summary_text,
    )

    # Call LLM
    logger.info("Generating trend summary for player %d with %s...", player_id, provider)
    used_model = resolve_model(provider, model)
    summary = call_provider(provider, prompt, model=used_model)

    # Store in DB
    conn.execute(
        "UPDATE player_patterns SET trend_summary = ? WHERE id = ?",
        (summary, pattern_id),
    )
    conn.commit()
    conn.close()

    logger.info("Trend summary generated for player %d (%d chars)", player_id, len(summary))
    return summary


# ---------------------------------------------------------------------------
# v1.9.0: Recent Form Review
# ---------------------------------------------------------------------------
#
# Distinct from `trend_summary` (which is a 30-day stats aggregate written
# without knowledge of specific games). The recent-form review names the
# last 10 coached games by date + opponent + result, synthesizes the
# per-game lessons the coach has already written, and identifies the
# through-line. This is what the user sees when asking "how have my
# last 10 games been, as a unit?"
#
# Triggered manually via the Patterns page "Refresh Review" button or
# `python main.py review --player X`. ~$0.10-0.15 per call with gpt-5.5-pro.

DEFAULT_REVIEW_WINDOW = 10  # games

RECENT_FORM_REVIEW_PROMPT = """You are a chess coach writing a multi-game review for {name}, a {age}-year-old at the {tier_label} {tier_icon} level (rating ~{rating}).

Each of {name}'s recent games has already been coached one-by-one. Your job is the **cross-game review** — what's the through-line across the last {window} games? What's actually changing? What patterns recur?

## Last {window} games
{games_table}

## What the per-game coach has been telling {name}
(Most recent first. Use these to find through-lines — do NOT repeat them verbatim.)
{lessons_block}

## Player Trajectory (last 30 days, measured)
{trajectory_block}

## Output format (REQUIRED — read carefully)
Your reply must be PLAIN TEXT ONLY:
- Exactly 4 paragraphs separated by blank lines (one blank line between paragraphs)
- NO JSON, NO arrays, NO objects. Do not wrap your output in `[...]` or `{{...}}`
- NO markdown headings (no `#`, `##`), NO bullet lists (no `-`, `*`, `1.`), NO code fences
- NO preamble like "Sure," / "Certainly," / "Here is your review:" — start directly with the first sentence of paragraph 1
- NO trailing commentary

The FIRST CHARACTER of your reply must be a letter — never an opening bracket, brace, hash, code fence, or quotation mark.

## Instructions
Write a 4-paragraph review for {name}. Plain text, no headings, no markdown.

1. **The arc** — Recent record (W/L/D) + 2-3 sentences setting the scene. Use language a {age}-year-old at {tier_label} level can follow: {language_level}

2. **Specific games** — Name 2-3 standout games by date + opponent + what happened (e.g. "Your win against sarcasta on 2026-05-24 showed exactly the knight-outpost theme"). Refer to actual moves only when they illustrate the through-line. Mix at least one win and one loss/draw if both exist.

3. **What's working / what's not** — Tie to the measured trajectory above. Be concrete: name the phases, name the measured stats by description (don't read back numbers). Acknowledge real progress where the trajectory shows it; flag recurring weaknesses gently — once, in passing.

4. **Forward guidance** — One concrete coaching mission for the next {window} games. Frame as a challenge, not a lecture. Specific and observable (e.g. "find one knight outpost before move 15"), not abstract ("play more accurately").

Tone: warm, honest, and personal. Address {name} by name in paragraph 1 or 2.

Respond with ONLY the four paragraphs of plain text. No JSON, no markdown headings, no extra commentary. Begin with the first word of paragraph 1; end with the last word of the final paragraph."""


def _build_recent_games_table(games: list[dict]) -> str:
    """Format the last N coached games as a compact table for the prompt."""
    if not games:
        return "  (no coached games found)"
    lines = []
    for g in games:
        opp = g.get("opponent_username") or "?"
        date = (g.get("date_played") or "")[:10]  # YYYY-MM-DD
        color = g.get("player_color", "?")
        result = g.get("result", "?")
        opening = (g.get("opening_name") or "—")[:40]
        tc = g.get("time_class") or "?"
        lines.append(
            f"  - {date} | {color:>5} vs {opp:<20} | {result:<4} | "
            f"{tc:<6} | {opening}"
        )
    return "\n".join(lines)


def _build_recent_lessons_block(games: list[dict]) -> str:
    """Format per-game lessons + practice focus + brief excerpt for the prompt."""
    if not games:
        return "  (no per-game coaching available)"
    parts = []
    for i, g in enumerate(games, 1):
        date = (g.get("date_played") or "")[:10]
        result = g.get("result", "?")
        opp = g.get("opponent_username") or "?"
        lesson = (g.get("key_lesson") or "").strip()
        focus = (g.get("practical_focus") or "").strip()
        feedback = (g.get("player_feedback") or "").strip()
        # Trim long player_feedback to first ~200 chars for context
        feedback_excerpt = feedback[:200].rstrip()
        if len(feedback) > 200:
            feedback_excerpt += "…"
        parts.append(
            f"### Game {i} ({date}, {result} vs {opp})\n"
            f"- Key lesson: {lesson or 'N/A'}\n"
            f"- Practice focus: {focus or 'N/A'}\n"
            f"- Feedback excerpt: {feedback_excerpt or 'N/A'}\n"
        )
    return "\n".join(parts)


def _most_played_platform(conn, player_id: int) -> str:
    """Return the platform the player has the most analyzed games on.

    Used as the default scope for the Recent Form Review when no explicit
    platform is requested. Mirrors the v1.7.2 Rating Progression chart's
    default-platform logic. Falls back to 'chess.com' when there are no
    analyzed games yet.
    """
    row = conn.execute(
        """SELECT platform, COUNT(*) AS n
        FROM games
        WHERE player_id = ? AND analysis_status = 'complete'
        GROUP BY platform
        ORDER BY n DESC
        LIMIT 1""",
        (player_id,),
    ).fetchone()
    return (row["platform"] if row and row["platform"] else "chess.com")


def _parse_referenced_game_ids(
    review_text: str, candidate_games: list[dict]
) -> list[int]:
    """Best-effort scan of the review text to find game IDs the LLM mentioned.

    The review prompt instructs the LLM to name games by date + opponent
    (e.g. "Your win against sarcasta on 2026-05-24"). This helper scans
    the generated text for those markers and resolves them back to game
    IDs from the candidate set we passed in.

    Returns a deduped list of game IDs that were mentioned. Empty list
    when no matches found — not an error condition.
    """
    if not review_text or not candidate_games:
        return []
    found: list[int] = []
    text_lower = review_text.lower()
    for g in candidate_games:
        gid = g.get("id")
        if gid is None or gid in found:
            continue
        opp = (g.get("opponent_username") or "").lower()
        date = (g.get("date_played") or "")[:10]
        # Match either the opponent name OR the YYYY-MM-DD date string.
        # Strong signal: BOTH appear. Weak signal: either one alone.
        # We accept either to keep recall high — false positives are
        # harmless (just a clickable pill).
        if opp and opp in text_lower:
            found.append(gid)
            continue
        if date and date in review_text:
            found.append(gid)
    return found


def compute_recent_form_review(
    player_id: int,
    db_path: str | None = None,
    provider: str = "openai",
    model: str | None = None,
    window: int = DEFAULT_REVIEW_WINDOW,
    config: dict | None = None,
    platform: str | None = None,
) -> str:
    """Generate the LLM-powered Recent Form Review across the last N coached games.

    Pulls the most-recent ``window`` coached games for the player on the
    given ``platform``, builds a prompt that combines the per-game lessons
    + the measured trajectory, calls the LLM, and persists the result.

    v1.10.0 changed the persistence model: each call INSERTS a new row into
    ``journal_entries`` (kind='review') rather than UPDATE-ing a single
    field on ``player_patterns``. Reviews now accumulate chronologically.
    The legacy ``player_patterns.recent_form_review`` column is still
    written for backward-compat but is no longer the source of truth.

    Args:
        platform: Scope the review to one platform ('chess.com' / 'lichess' /
            'tournament' / ...). When None (default), uses the player's
            most-played analyzed platform — same default-selection logic as
            the v1.7.2 Rating Progression chart.

    Returns the review text. Returns "" if no coached games exist on the
    chosen platform. Raises ValueError if the player is not found.

    v1.9.0+ / v1.10.0 platform-aware
    """
    from src.llm_providers import call_provider, resolve_model
    from src.tiers import get_tier

    conn = init_db(db_path)

    player = conn.execute(
        "SELECT * FROM players WHERE id = ?", (player_id,)
    ).fetchone()
    if not player:
        conn.close()
        raise ValueError(f"Player {player_id} not found")

    # v1.10.0: resolve platform default
    if platform is None:
        platform = _most_played_platform(conn, player_id)

    # Fetch last N coached games on this platform (most-recent first)
    rows = conn.execute(
        """SELECT g.id, g.date_played, g.player_color, g.result,
                  g.opponent_username, g.time_class, g.pgn, g.platform,
                  gc.key_lesson, gc.practical_focus, gc.player_feedback
           FROM games g
           JOIN game_coaching gc ON gc.game_id = g.id
           WHERE g.player_id = ?
             AND g.analysis_status = 'complete'
             AND gc.player_feedback IS NOT NULL
             AND g.platform = ?
           ORDER BY g.date_played DESC
           LIMIT ?""",
        (player_id, platform, window),
    ).fetchall()

    if not rows:
        conn.close()
        logger.info(
            "No coached games on platform=%s for player %d — skipping review",
            platform, player_id,
        )
        return ""

    games = []
    for r in rows:
        g = dict(r)
        g["opening_name"] = _get_opening_name(g.get("pgn", "") or "")
        games.append(g)

    # Build the trajectory block (reuses v1.8.0 helper)
    trajectory_block, _diag = build_trajectory_block(conn, player_id)
    if not trajectory_block:
        trajectory_block = (
            "  (no trajectory snapshot yet — run `python main.py patterns` "
            "to enable measured cross-game signals)"
        )

    # Player + tier
    name = player["display_name"] or player["username"]
    age = player["age"] or 10
    rating = player["rating"] or 1000
    tier = get_tier(rating)

    prompt = RECENT_FORM_REVIEW_PROMPT.format(
        name=name,
        age=age,
        rating=rating,
        tier_label=tier.label,
        tier_icon=tier.icon,
        language_level=tier.language_level,
        window=len(games),  # actual count, may be < requested if few games
        games_table=_build_recent_games_table(games),
        lessons_block=_build_recent_lessons_block(games),
        trajectory_block=trajectory_block,
    )

    # Resolve provider config + call LLM
    coaching_config = (config or {}).get("coaching", {}) if config else {}
    used_model = resolve_model(provider, model, coaching_config)
    logger.info(
        "Generating recent form review for player %d (platform=%s, window=%d) with %s:%s...",
        player_id, platform, len(games), provider, used_model,
    )
    review = call_provider(
        provider, prompt, model=used_model, coaching_config=coaching_config
    )

    # v1.10.0: INSERT a new journal entry instead of UPDATE-ing the legacy column
    refs = _parse_referenced_game_ids(review, games)
    provider_model = f"{provider}:{used_model}"
    conn.execute(
        """INSERT INTO journal_entries
        (player_id, kind, platform, body, refs_json, provider,
         metadata_json, created_at)
        VALUES (?, 'review', ?, ?, ?, ?, ?, datetime('now'))""",
        (
            player_id, platform, review,
            json.dumps(refs),
            provider_model,
            json.dumps({"window": window, "model": used_model}),
        ),
    )

    # Keep legacy column populated for backward-compat (any tooling still
    # reading it sees the latest review). Source of truth is journal_entries.
    row = conn.execute(
        """SELECT id FROM player_patterns
        WHERE player_id = ? ORDER BY updated_at DESC LIMIT 1""",
        (player_id,),
    ).fetchone()
    if row:
        conn.execute(
            """UPDATE player_patterns
            SET recent_form_review = ?, recent_form_review_updated_at = datetime('now')
            WHERE id = ?""",
            (review, row["id"]),
        )
    else:
        # No patterns row yet — create a minimal one so legacy reads work
        now = datetime.now()
        conn.execute(
            """INSERT INTO player_patterns
            (player_id, period_start, period_end, stats_json,
             recent_form_review, recent_form_review_updated_at, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (
                player_id,
                (now - timedelta(days=30)).strftime("%Y-%m-%d"),
                now.strftime("%Y-%m-%d"),
                json.dumps({}),
                review,
            ),
        )
    conn.commit()
    conn.close()

    logger.info("Recent form review generated for player %d (%d chars)",
                player_id, len(review))
    return review


def _find_worst_phase(phase_analysis: dict) -> str:
    """Find the phase with the highest ACPL."""
    worst = None
    worst_acpl = 0
    for name in ["opening", "middlegame", "endgame"]:
        acpl = (phase_analysis.get(name) or {}).get("acpl")
        if acpl is not None and acpl > worst_acpl:
            worst_acpl = acpl
            worst = name
    return worst or "N/A"


def _find_best_phase(phase_analysis: dict) -> str:
    """Find the phase with the lowest ACPL (best play)."""
    best = None
    best_acpl = float("inf")
    for name in ["opening", "middlegame", "endgame"]:
        acpl = (phase_analysis.get(name) or {}).get("acpl")
        if acpl is not None and acpl < best_acpl:
            best_acpl = acpl
            best = name
    return best or "N/A"


def _acpl_trend_direction(acpl_trend: list[dict]) -> str:
    """Classify the recent ACPL trend as improving / flat / declining.

    Compares the mean ACPL of the most recent 2 weekly buckets against
    the 2 buckets before that. Lower ACPL = better play, so a drop is
    improvement. Returns "improving" / "declining" / "flat" / "insufficient_data".
    """
    if not acpl_trend or len(acpl_trend) < 4:
        return "insufficient_data"
    recent = acpl_trend[-2:]
    prior = acpl_trend[-4:-2]
    recent_mean = sum(t.get("acpl", 0) or 0 for t in recent) / max(1, len(recent))
    prior_mean = sum(t.get("acpl", 0) or 0 for t in prior) / max(1, len(prior))
    # Use a relative threshold so noise doesn't flip the label
    if prior_mean <= 0:
        return "flat"
    delta_pct = (recent_mean - prior_mean) / prior_mean * 100
    if delta_pct < -5:
        return "improving"
    if delta_pct > 5:
        return "declining"
    return "flat"


def build_trajectory_block(
    conn,
    player_id: int,
) -> tuple[str, dict]:
    """Build a structured per-player trajectory block for prompt injection.

    Returns (formatted_markdown_block, diagnostics_dict).
    - The markdown block goes into the GAME_COACHING_PROMPT under the
      ``## Player Trajectory (last 30 days)`` heading.
    - The diagnostics dict is suitable for storage in
      ``game_coaching.coaching_meta_json``.

    Falls back gracefully when patterns haven't been computed yet:
    returns ("", {trajectory_injected: False, ...}). v1.8.0+
    """
    diag: dict = {
        "trajectory_injected": False,
        "trajectory_age_days": None,
        "weakest_phase": None,
        "trend_direction": None,
    }
    row = conn.execute(
        """SELECT id, stats_json, updated_at, period_end FROM player_patterns
        WHERE player_id = ? ORDER BY updated_at DESC LIMIT 1""",
        (player_id,),
    ).fetchone()
    if not row or not row["stats_json"]:
        return "", diag

    try:
        stats = json.loads(row["stats_json"])
    except (TypeError, ValueError):
        return "", diag

    # Compute the freshness of the pattern row (days since updated_at).
    try:
        updated = datetime.fromisoformat(row["updated_at"])
        age_days = max(0, (datetime.now() - updated).days)
    except (TypeError, ValueError):
        age_days = None

    phase = stats.get("phase_analysis") or {}
    consistency = stats.get("consistency") or {}
    tactical = stats.get("tactical_misses") or {}
    endgame = stats.get("endgame_conversion") or {}
    comeback = stats.get("comeback_collapse") or {}
    repertoire = stats.get("repertoire_consistency") or {}
    acpl_trend = stats.get("acpl_trend") or []
    motif_summary = stats.get("motif_summary") or {}

    worst_phase = _find_worst_phase(phase)
    best_phase = _find_best_phase(phase)
    worst_phase_acpl = (phase.get(worst_phase) or {}).get("acpl")
    best_phase_acpl = (phase.get(best_phase) or {}).get("acpl")
    trend_direction = _acpl_trend_direction(acpl_trend)

    mean_acpl = consistency.get("mean_acpl")
    total_games = consistency.get("total_games") or stats.get("total_games", 0)
    miss_rate = tactical.get("miss_rate")
    winning_endgames = endgame.get("winning_endgames") or {}
    conversion_rate = winning_endgames.get("conversion_rate")
    comeback_rate = (comeback.get("comebacks") or {}).get("comeback_rate")
    collapse_rate = (comeback.get("collapses") or {}).get("collapse_rate")
    white_rep_rating = (repertoire.get("white") or {}).get("rating") or "N/A"
    black_rep_rating = (repertoire.get("black") or {}).get("rating") or "N/A"

    # If essentially nothing is measurable yet, skip rather than emit
    # an empty block that would just waste tokens.
    if worst_phase == "N/A" and mean_acpl is None:
        return "", diag

    # Build the synthesized headline sentence deterministically.
    pieces: list[str] = []
    if trend_direction == "improving":
        pieces.append("ACPL has been improving over the last 4 weeks")
    elif trend_direction == "declining":
        pieces.append("ACPL has been climbing over the last 4 weeks")
    elif trend_direction == "flat":
        pieces.append("ACPL has been steady over the last 4 weeks")
    if worst_phase != "N/A" and worst_phase_acpl is not None:
        pieces.append(
            f"{worst_phase} remains the weakest phase at {worst_phase_acpl:.1f}cp avg loss"
        )
    headline = "; ".join(pieces) + "." if pieces else ""

    lines = [
        "",
        "## Player Trajectory (last 30 days)",
        "Measured cross-game signals for this player. Use these to ground",
        "your feedback in the broader arc — acknowledge real progress where",
        "the numbers show it, and note recurring weaknesses gently.",
        "",
    ]
    if headline:
        lines.append(f"**Headline:** {headline}")
        lines.append("")
    lines.append("**Numeric snapshot:**")
    lines.append(f"- Games analyzed in this window: {total_games}")
    if mean_acpl is not None:
        lines.append(f"- Mean ACPL: {mean_acpl}")
    if worst_phase != "N/A" and worst_phase_acpl is not None:
        lines.append(f"- Weakest phase: {worst_phase} (ACPL {worst_phase_acpl:.1f})")
    if best_phase != "N/A" and best_phase_acpl is not None:
        lines.append(f"- Strongest phase: {best_phase} (ACPL {best_phase_acpl:.1f})")
    if miss_rate is not None:
        lines.append(f"- Tactical miss rate: {miss_rate}%")
    if conversion_rate is not None:
        lines.append(f"- Winning endgame conversion: {conversion_rate}%")
    if comeback_rate is not None and collapse_rate is not None:
        lines.append(
            f"- Comeback rate: {comeback_rate}%  |  Collapse rate: {collapse_rate}%"
        )
    lines.append(
        f"- Repertoire focus: White = {white_rep_rating}; Black = {black_rep_rating}"
    )
    lines.append(f"- ACPL trend direction (last 4 weeks): {trend_direction}")
    lines.append("")

    # v1.15.0: recurring tactical themes block (only when motif data exists).
    # v1.16.0: extended with dominant-phase tag when applicable.
    motif_top = motif_summary.get("top_missed")
    motif_top_count = motif_summary.get("top_missed_count", 0)
    motif_total = motif_summary.get("total_critical_moves", 0)
    motif_top_phase = motif_summary.get("top_missed_dominant_phase")
    if motif_total > 0:
        nonzero_motifs = [
            e for e in (motif_summary.get("by_motif") or [])
            if (e.get("missed", 0) + e.get("found", 0)) > 0
        ]
        if nonzero_motifs:
            lines.append("**Recurring tactical themes (last 30 days):**")
            if motif_top and motif_top_count > 0:
                # v1.16.0: append phase tag when dominant
                line = f"- Most-missed: {motif_top} ({motif_top_count} instances)"
                if motif_top_phase:
                    line += f" — concentrated in {motif_top_phase}"
                lines.append(line)
            also = [
                f"{e['motif']} ({e['missed']})"
                for e in nonzero_motifs
                if e["motif"] != motif_top and e["missed"] > 0
            ]
            if also:
                lines.append(f"- Also recurring: {', '.join(also[:4])}")
            lines.append("")

    diag = {
        "trajectory_injected": True,
        "trajectory_age_days": age_days,
        "weakest_phase": worst_phase if worst_phase != "N/A" else None,
        "trend_direction": trend_direction,
        # v1.15.0: most-missed motif tag (None when no critical moves).
        "motif_top_missed": motif_top if motif_top_count > 0 else None,
        # v1.16.0: dominant phase of the top-missed motif (None when
        # the top motif's misses don't concentrate ≥60% in one phase).
        "motif_top_missed_phase": motif_top_phase if motif_top_count > 0 else None,
    }
    return "\n".join(lines), diag


def _compute_time_pressure(games: list[dict],
                           moves_by_game: dict[int, list[dict]]) -> dict | None:
    """Compute time pressure statistics from clock data.

    Returns None if no clock data is available.
    """
    TIME_TROUBLE_THRESHOLD = 30  # seconds remaining
    LOW_TIME_THRESHOLD = 60  # seconds for "under pressure" comparison

    games_with_clocks = 0
    games_in_time_trouble = 0
    total_moves_with_clock = 0

    # Per-phase time consumption
    phase_time_spent = {"opening": [], "middlegame": [], "endgame": []}
    # Blunder tracking: under pressure vs comfortable
    blunders_under_pressure = 0
    moves_under_pressure = 0
    blunders_comfortable = 0
    moves_comfortable = 0
    # Per-move time tracking
    move_times: list[float] = []

    for g in games:
        game_moves = moves_by_game.get(g["id"], [])
        player_color = g["player_color"]

        player_moves = [m for m in game_moves if m["side"] == player_color]
        clock_data = [m for m in player_moves if m.get("clock_seconds") is not None]

        if len(clock_data) < 2:
            continue  # Not enough clock data for this game

        games_with_clocks += 1

        # Check if player hit time trouble
        min_clock = min(m["clock_seconds"] for m in clock_data)
        if min_clock < TIME_TROUBLE_THRESHOLD:
            games_in_time_trouble += 1

        # Compute per-move times and phase distribution
        prev_clock = None
        for m in clock_data:
            total_moves_with_clock += 1
            clock = m["clock_seconds"]
            phase = _classify_game_phase(m["move_number"])

            if prev_clock is not None and prev_clock >= clock:
                time_spent = prev_clock - clock
                move_times.append(time_spent)
                phase_time_spent[phase].append(time_spent)

            # Blunder tracking by time pressure
            is_under_pressure = clock < LOW_TIME_THRESHOLD
            is_blunder = m.get("classification") == "blunder"
            if is_under_pressure:
                moves_under_pressure += 1
                if is_blunder:
                    blunders_under_pressure += 1
            else:
                moves_comfortable += 1
                if is_blunder:
                    blunders_comfortable += 1

            prev_clock = clock

    if games_with_clocks == 0:
        return None

    # Compute averages
    avg_time_per_move = round(sum(move_times) / len(move_times), 1) if move_times else 0
    phase_avg = {}
    for phase, times in phase_time_spent.items():
        phase_avg[phase] = round(sum(times) / len(times), 1) if times else 0

    blunder_rate_pressure = round(
        blunders_under_pressure / moves_under_pressure * 100, 1
    ) if moves_under_pressure > 0 else 0
    blunder_rate_comfortable = round(
        blunders_comfortable / moves_comfortable * 100, 1
    ) if moves_comfortable > 0 else 0

    time_trouble_rate = round(games_in_time_trouble / games_with_clocks * 100, 1)

    # Time management score (0-100): composite of trouble rate and pressure blunders
    trouble_penalty = min(time_trouble_rate, 50)  # 0-50 points from trouble rate
    blunder_penalty = min(blunder_rate_pressure * 2, 50)  # 0-50 points from pressure blunders
    time_management_score = max(0, round(100 - trouble_penalty - blunder_penalty))

    return {
        "games_with_clocks": games_with_clocks,
        "time_trouble_rate": time_trouble_rate,
        "avg_time_per_move": avg_time_per_move,
        "phase_avg_time": phase_avg,
        "blunder_rate_under_pressure": blunder_rate_pressure,
        "blunder_rate_comfortable": blunder_rate_comfortable,
        "moves_under_pressure": moves_under_pressure,
        "moves_comfortable": moves_comfortable,
        "time_management_score": time_management_score,
    }
