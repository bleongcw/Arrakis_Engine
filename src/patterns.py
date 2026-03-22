"""Cross-game pattern detection for ArrakisEngine.

Aggregates analysis across all games per player to find recurring
themes: opening performance, ACPL trends, blunder frequency by
game phase, and performance vs. rated opponents.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import chess.pgn
import io

from src.models import init_db

logger = logging.getLogger(__name__)


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
    }

    # Store patterns
    now = datetime.now()
    period_start = (now - timedelta(days=period_days)).strftime("%Y-%m-%d")
    period_end = now.strftime("%Y-%m-%d")

    conn.execute(
        """INSERT OR REPLACE INTO player_patterns
        (player_id, period_start, period_end, stats_json, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))""",
        (player_id, period_start, period_end, json.dumps(stats)),
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


def _compute_opening_stats(games: list[dict]) -> dict:
    """Win rate by opening name, split by color.

    Returns {"all": [...], "white": [...], "black": [...]}.
    """
    def _aggregate(game_list):
        openings = defaultdict(lambda: {"games": 0, "wins": 0, "losses": 0, "draws": 0})
        for g in game_list:
            name = _get_opening_name(g["pgn"])
            openings[name]["games"] += 1
            if g["result"] == "win":
                openings[name]["wins"] += 1
            elif g["result"] == "loss":
                openings[name]["losses"] += 1
            else:
                openings[name]["draws"] += 1

        result = []
        for name, data in sorted(openings.items(), key=lambda x: x[1]["games"], reverse=True):
            if data["games"] >= 2:
                data["name"] = name
                data["win_rate"] = round(data["wins"] / data["games"] * 100, 1)
                result.append(data)
        return result[:20]

    white_games = [g for g in games if g["player_color"] == "white"]
    black_games = [g for g in games if g["player_color"] == "black"]

    return {
        "all": _aggregate(games),
        "white": _aggregate(white_games),
        "black": _aggregate(black_games),
    }


def _compute_acpl_trend(games: list[dict],
                        moves_by_game: dict[int, list[dict]]) -> list[dict]:
    """ACPL (average centipawn loss) trend in weekly buckets."""
    weekly = defaultdict(lambda: {"total_cp_loss": 0, "total_moves": 0, "games": 0})

    for g in games:
        if not g["date_played"]:
            continue
        # Week bucket
        try:
            date = datetime.strptime(g["date_played"], "%Y-%m-%d")
        except ValueError:
            continue
        week_start = (date - timedelta(days=date.weekday())).strftime("%Y-%m-%d")

        player_moves = [
            m for m in moves_by_game.get(g["id"], [])
            if m["side"] == g["player_color"]
        ]
        if not player_moves:
            continue

        total_loss = sum(m["swing_cp"] or 0 for m in player_moves)
        weekly[week_start]["total_cp_loss"] += total_loss
        weekly[week_start]["total_moves"] += len(player_moves)
        weekly[week_start]["games"] += 1

    trend = []
    for week, data in sorted(weekly.items()):
        if data["total_moves"] > 0:
            trend.append({
                "week": week,
                "acpl": round(data["total_cp_loss"] / data["total_moves"], 1),
                "games": data["games"],
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

    for g in games:
        player_moves = [
            m for m in moves_by_game.get(g["id"], [])
            if m["side"] == g["player_color"]
        ]
        for m in player_moves:
            phase = _classify_game_phase(m["move_number"])
            phases[phase]["moves"] += 1
            phases[phase]["cp_loss"] += m["swing_cp"] or 0
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
