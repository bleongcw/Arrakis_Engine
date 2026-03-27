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
            date = datetime.strptime(g["date_played"], "%Y-%m-%d")
        except ValueError:
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
