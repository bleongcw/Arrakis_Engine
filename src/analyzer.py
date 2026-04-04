# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Stockfish analysis engine for ArrakisEngine.

Replays each PGN move-by-move against the local Stockfish binary,
storing per-move evaluations with centipawn scores, win probability,
and move classification.
"""

import io
import logging
import math
import re
import time

import chess
import chess.engine
import chess.pgn

from src.models import get_connection, init_db
from src.tiers import get_tier, classify_move as tier_classify_move, TierConfig

logger = logging.getLogger(__name__)


def cp_to_win_prob(cp: int) -> float:
    """Convert centipawn evaluation to win probability using Lichess formula.

    win% = 50 + 50 × (2 / (1 + exp(-0.00368208 × cp)) - 1)
    """
    return 50.0 + 50.0 * (2.0 / (1.0 + math.exp(-0.00368208 * cp)) - 1.0)


def classify_move(cp_loss: int) -> str:
    """Classify a move based on centipawn loss."""
    if cp_loss <= 30:
        return "excellent"
    elif cp_loss <= 50:
        return "good"
    elif cp_loss <= 100:
        return "inaccuracy"
    elif cp_loss <= 300:
        return "mistake"
    else:
        return "blunder"


EVAL_CAP = 1000  # Cap evaluations at ±1000cp (industry standard: Lichess, Chess.com)


def cap_eval(cp: int) -> int:
    """Cap a centipawn evaluation at ±EVAL_CAP.

    Positions beyond ±10 pawns are effectively won/lost regardless of
    exact value. Capping prevents mate scores and extreme evals from
    distorting ACPL calculations.
    """
    return max(-EVAL_CAP, min(EVAL_CAP, cp))


def score_to_cp(score: chess.engine.PovScore, side: chess.Color) -> int | None:
    """Convert a PovScore to centipawns from white's perspective.

    Mate scores are mapped to ±1000cp (the eval cap).
    """
    pov = score.white()
    if pov.is_mate():
        mate_in = pov.mate()
        if mate_in is not None:
            # Positive mate = white winning, negative = black winning
            return EVAL_CAP if mate_in > 0 else -EVAL_CAP
        return 0
    cp = pov.score()
    return cp if cp is not None else 0


CLK_PATTERN = re.compile(r'\[%clk\s+(\d+):(\d+):(\d+)(?:\.(\d+))?\]')


def extract_clock_seconds(comment: str) -> float | None:
    """Extract clock time in seconds from a PGN move comment.

    Handles formats like {[%clk 0:05:30]} and {[%clk 0:05:30.1]}.
    """
    m = CLK_PATTERN.search(comment)
    if not m:
        return None
    hours, mins, secs = int(m.group(1)), int(m.group(2)), int(m.group(3))
    frac = int(m.group(4)) / (10 ** len(m.group(4))) if m.group(4) else 0
    return hours * 3600 + mins * 60 + secs + frac


def extract_clocks_from_pgn(pgn_text: str) -> list[float | None]:
    """Extract per-move clock data from a PGN string.

    Returns a list of clock_seconds values, one per half-move, in move order.
    """
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return []
    clocks: list[float | None] = []
    node = game
    while node.variations:
        node = node.variations[0]
        comment = node.comment or ""
        clocks.append(extract_clock_seconds(comment))
    return clocks


def analyze_game(game_id: int, pgn_text: str, player_color: str,
                 stockfish_path: str, depth: int = 22,
                 threads: int = 6, hash_mb: int = 512,
                 move_time_limit: float = 10.0,
                 db_path: str | None = None,
                 tier: TierConfig | None = None) -> dict:
    """Analyze a single game move-by-move with Stockfish.

    If tier is provided, uses tier-specific depth, time limit, and
    classification thresholds. Otherwise uses the passed-in defaults.

    Returns a dict with analysis stats.
    """
    # Apply tier overrides if provided
    if tier:
        depth = tier.depth
        move_time_limit = tier.time_limit
        logger.info("  Tier: %s %s (depth=%d, time=%.0fs, blunder>%dcp)",
                     tier.icon, tier.label, depth, move_time_limit, tier.blunder_cp)
    conn = init_db(db_path)

    # Mark as analyzing
    conn.execute(
        "UPDATE games SET analysis_status = 'analyzing' WHERE id = ?",
        (game_id,),
    )
    conn.commit()

    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        conn.execute(
            "UPDATE games SET analysis_status = 'error' WHERE id = ?",
            (game_id,),
        )
        conn.commit()
        conn.close()
        return {"error": "Failed to parse PGN"}

    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    engine.configure({"Threads": threads, "Hash": hash_mb})

    board = game.board()
    moves = list(game.mainline_moves())
    total_moves = len(moves)
    start_time = time.time()

    # Extract per-move clock data from PGN comments
    clocks = extract_clocks_from_pgn(pgn_text)

    # Skip games with no moves (abandoned, etc.)
    if total_moves == 0:
        logger.info("Game %d has no moves (abandoned/forfeit), marking complete", game_id)
        engine.quit()
        conn.execute(
            "UPDATE games SET analysis_status = 'complete' WHERE id = ?",
            (game_id,),
        )
        conn.commit()
        conn.close()
        return {"moves": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0, "skipped": True}

    logger.info("Analyzing game %d: %d moves at depth %d", game_id, total_moves, depth)

    # Use both depth and time limit — whichever is reached first.
    # This prevents hangs on complex endgame positions.
    limit = chess.engine.Limit(depth=depth, time=move_time_limit)

    # Get initial position eval
    info = engine.analyse(board, limit)
    prev_cp = score_to_cp(info["score"], board.turn)

    stats = {"moves": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0}
    player_cp_losses = []  # Track player's capped cp losses for ACPL

    for i, move in enumerate(moves):
        move_number = (i // 2) + 1
        side = "white" if board.turn == chess.WHITE else "black"
        move_san = board.san(move)

        # Get best move before playing
        best_info = info  # reuse previous analysis
        best_move_san = None
        if best_info.get("pv"):
            try:
                best_move_san = board.san(best_info["pv"][0])
            except (ValueError, IndexError):
                pass

        pv_line = None
        if best_info.get("pv"):
            try:
                pv_board = board.copy()
                pv_moves = []
                for pv_move in best_info["pv"][:5]:
                    pv_moves.append(pv_board.san(pv_move))
                    pv_board.push(pv_move)
                pv_line = " ".join(pv_moves)
            except (ValueError, IndexError):
                pass

        eval_before_cp = prev_cp

        # Play the move
        board.push(move)

        # Analyze the new position
        info = engine.analyse(board, limit)
        current_cp = score_to_cp(info["score"], board.turn)

        eval_after_cp = current_cp

        # Cap evaluations at ±1000cp BEFORE computing loss (Lichess/Chess.com standard).
        # This prevents mate scores and extreme positions from distorting ACPL.
        capped_before = cap_eval(eval_before_cp or 0)
        capped_after = cap_eval(eval_after_cp or 0)

        # Calculate centipawn loss from the moving side's perspective
        if side == "white":
            # White wants positive eval. Loss = before - after (from white POV)
            cp_loss = max(0, capped_before - capped_after)
        else:
            # Black wants negative eval. Loss = after - before (from white POV)
            # i.e., if eval goes from -100 to +50, black lost 150cp
            cp_loss = max(0, capped_after - capped_before)

        swing_cp = cp_loss
        classification = tier_classify_move(cp_loss, tier) if tier else classify_move(cp_loss)

        win_prob_before = cp_to_win_prob(eval_before_cp or 0)
        win_prob_after = cp_to_win_prob(eval_after_cp or 0)

        # Adjust win prob to be from the moving side's perspective
        if side == "black":
            win_prob_before = 100.0 - win_prob_before
            win_prob_after = 100.0 - win_prob_after

        # Get clock data for this move (index i = half-move index)
        clock_secs = clocks[i] if i < len(clocks) else None

        conn.execute(
            """INSERT OR REPLACE INTO move_analysis
            (game_id, move_number, side, move_played, best_move,
             eval_before_cp, eval_after_cp, swing_cp,
             win_prob_before, win_prob_after, classification, pv_line,
             clock_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (game_id, move_number, side, move_san, best_move_san,
             eval_before_cp, eval_after_cp, swing_cp,
             win_prob_before, win_prob_after, classification, pv_line,
             clock_secs),
        )

        stats["moves"] += 1
        if side == player_color:
            player_cp_losses.append(cp_loss)
        if classification == "blunder":
            stats["blunders"] += 1
        elif classification == "mistake":
            stats["mistakes"] += 1
        elif classification == "inaccuracy":
            stats["inaccuracies"] += 1

        prev_cp = current_cp

        # Progress logging every 10 moves
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            eta = (total_moves - i - 1) / rate if rate > 0 else 0
            logger.info(
                "  Game %d: %d/%d moves (%.1f moves/sec, ETA %.0fs)",
                game_id, i + 1, total_moves, rate, eta,
            )

    engine.quit()

    # Compute per-game ACPL (capped, player's side only)
    game_acpl = round(sum(player_cp_losses) / len(player_cp_losses), 1) if player_cp_losses else 0

    # Mark as complete and store ACPL
    conn.execute(
        "UPDATE games SET analysis_status = 'complete', acpl = ? WHERE id = ?",
        (game_acpl, game_id),
    )
    conn.commit()

    elapsed = time.time() - start_time
    logger.info(
        "Game %d analysis complete: %d moves in %.1fs (%.1f moves/sec). "
        "ACPL: %.1f, Blunders: %d, Mistakes: %d, Inaccuracies: %d",
        game_id, stats["moves"], elapsed, stats["moves"] / elapsed if elapsed > 0 else 0,
        game_acpl, stats["blunders"], stats["mistakes"], stats["inaccuracies"],
    )

    conn.close()
    return stats


def analyze_pending(stockfish_path: str, depth: int = 22,
                    threads: int = 6, hash_mb: int = 512,
                    move_time_limit: float = 10.0,
                    db_path: str | None = None) -> int:
    """Analyze all games with pending analysis status.

    Returns the number of games analyzed.

    Raises FileNotFoundError if the Stockfish binary doesn't exist.
    """
    import os
    if not os.path.isfile(stockfish_path):
        raise FileNotFoundError(
            f"Stockfish binary not found at '{stockfish_path}'. "
            f"Install Stockfish and update stockfish.path in config.yaml. "
            f"Run 'which stockfish' to find the correct path."
        )

    conn = init_db(db_path)

    # Reset any games stuck in 'analyzing' from interrupted runs
    stuck = conn.execute(
        "UPDATE games SET analysis_status = 'pending' WHERE analysis_status = 'analyzing'"
    ).rowcount
    if stuck:
        conn.commit()
        logger.info("Reset %d interrupted games back to pending", stuck)

    pending = conn.execute(
        """SELECT g.id, g.pgn, g.player_color, g.player_id, g.player_rating,
                  p.rating as profile_rating
           FROM games g
           JOIN players p ON g.player_id = p.id
           WHERE g.analysis_status = 'pending'"""
    ).fetchall()
    conn.close()

    logger.info("Found %d games pending analysis", len(pending))

    for i, row in enumerate(pending):
        # Determine tier from the game's player rating
        game_rating = row["player_rating"] or row["profile_rating"]
        game_tier = get_tier(game_rating)
        logger.info("Analyzing game %d/%d (id=%d) — %s %s (rating %s)",
                     i + 1, len(pending), row["id"],
                     game_tier.icon, game_tier.label, game_rating or "unknown")
        try:
            analyze_game(
                game_id=row["id"],
                pgn_text=row["pgn"],
                player_color=row["player_color"],
                stockfish_path=stockfish_path,
                depth=depth,
                threads=threads,
                hash_mb=hash_mb,
                move_time_limit=move_time_limit,
                db_path=db_path,
                tier=game_tier,
            )
        except Exception as e:
            logger.error("Failed to analyze game %d: %s", row["id"], e)
            err_conn = init_db(db_path)
            err_conn.execute(
                "UPDATE games SET analysis_status = 'error' WHERE id = ?",
                (row["id"],),
            )
            err_conn.commit()
            err_conn.close()

    return len(pending)
