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
        "repertoire_consistency": _compute_repertoire_consistency(games),
        # Time pressure analysis
        "time_pressure": _compute_time_pressure(games, moves_by_game),
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

        # Fallback: compute from moves with cap if not stored
        if game_acpl is None:
            player_moves = [
                m for m in moves_by_game.get(g["id"], [])
                if m["side"] == g["player_color"]
            ]
            if not player_moves:
                continue
            losses = []
            for m in player_moves:
                before = m.get("eval_before_cp") or 0
                after = m.get("eval_after_cp") or 0
                cb = max(-EVAL_CAP, min(EVAL_CAP, before))
                ca = max(-EVAL_CAP, min(EVAL_CAP, after))
                if m["side"] == "white":
                    losses.append(max(0, cb - ca))
                else:
                    losses.append(max(0, ca - cb))
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
            # Use capped cp_loss for phase ACPL
            before = max(-EVAL_CAP, min(EVAL_CAP, m.get("eval_before_cp") or 0))
            after = max(-EVAL_CAP, min(EVAL_CAP, m.get("eval_after_cp") or 0))
            if m["side"] == "white":
                capped_loss = max(0, before - after)
            else:
                capped_loss = max(0, after - before)
            phases[phase]["cp_loss"] += capped_loss
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
            player_moves = [
                m for m in moves_by_game.get(g["id"], [])
                if m["side"] == g["player_color"]
            ]
            if not player_moves:
                continue
            losses = []
            for m in player_moves:
                before = max(-EVAL_CAP, min(EVAL_CAP, m.get("eval_before_cp") or 0))
                after = max(-EVAL_CAP, min(EVAL_CAP, m.get("eval_after_cp") or 0))
                if m["side"] == "white":
                    losses.append(max(0, before - after))
                else:
                    losses.append(max(0, after - before))
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

        # ACPL per time control
        acpl = g.get("acpl")
        if acpl is None:
            player_moves = [
                m for m in moves_by_game.get(g["id"], [])
                if m["side"] == g["player_color"]
            ]
            if player_moves:
                losses = []
                for m in player_moves:
                    before = max(-EVAL_CAP, min(EVAL_CAP, m.get("eval_before_cp") or 0))
                    after = max(-EVAL_CAP, min(EVAL_CAP, m.get("eval_after_cp") or 0))
                    if m["side"] == "white":
                        losses.append(max(0, before - after))
                    else:
                        losses.append(max(0, after - before))
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
                move_losses = []
                for m in player_moves:
                    before = max(-EVAL_CAP, min(EVAL_CAP, m.get("eval_before_cp") or 0))
                    after = max(-EVAL_CAP, min(EVAL_CAP, m.get("eval_after_cp") or 0))
                    if m["side"] == "white":
                        move_losses.append(max(0, before - after))
                    else:
                        move_losses.append(max(0, after - before))
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
                before = max(-EVAL_CAP, min(EVAL_CAP, m.get("eval_before_cp") or 0))
                after = max(-EVAL_CAP, min(EVAL_CAP, m.get("eval_after_cp") or 0))
                if m["side"] == "white":
                    losses.append(max(0, before - after))
                else:
                    losses.append(max(0, after - before))
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

            # Was there an opportunity? Check if best move gives big advantage
            eval_before = max(-EVAL_CAP, min(EVAL_CAP, m.get("eval_before_cp") or 0))
            eval_after = max(-EVAL_CAP, min(EVAL_CAP, m.get("eval_after_cp") or 0))

            # Player's perspective
            if player_color == "white":
                player_eval_before = eval_before
                cp_loss = max(0, eval_before - eval_after)
            else:
                player_eval_before = -eval_before
                cp_loss = max(0, eval_after - eval_before)

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

## Instructions
Write a 3-4 paragraph coaching summary for {name}. This is a progress review, not a single-game analysis.

Requirements:
- Address {name} by name. Use "you" throughout.
- Paragraph 1: Overall progress and what's going well. Be specific with numbers.
- Paragraph 2: Areas that need improvement. Reference the weakest phase, common mistakes, or tactical misses.
- Paragraph 3: 3 specific, actionable practice recommendations appropriate for a {age}-year-old {tier_label}-level player.
- Paragraph 4: Encouragement and growth mindset message.
- Keep language age-appropriate for {age} years old.
- Be warm but professional. Concrete, not vague.

Respond with ONLY the text paragraphs, no JSON, no headers, no markdown formatting."""


def generate_trend_summary(player_id: int, db_path: str | None = None,
                           provider: str = "claude", model: str | None = None) -> str:
    """Generate an LLM-powered trend summary from pattern stats.

    Reads the latest pattern stats, builds a prompt, calls the LLM,
    and stores the result in the player_patterns table.

    Returns the summary text.
    """
    from src.coach import _call_claude, _call_openai
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
    )

    # Call LLM
    logger.info("Generating trend summary for player %d with %s...", player_id, provider)
    if provider == "claude":
        summary = _call_claude(prompt, model or "claude-opus-4-6")
    elif provider == "openai":
        summary = _call_openai(prompt, model or "chatgpt-5.4-pro")
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Store in DB
    conn.execute(
        "UPDATE player_patterns SET trend_summary = ? WHERE id = ?",
        (summary, pattern_id),
    )
    conn.commit()
    conn.close()

    logger.info("Trend summary generated for player %d (%d chars)", player_id, len(summary))
    return summary


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
