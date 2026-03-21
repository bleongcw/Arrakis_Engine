"""Stockfish analysis engine for ArrakisEngine.

Replays each PGN move-by-move against the local Stockfish binary,
storing per-move evaluations with centipawn scores, win probability,
and move classification.
"""

import io
import logging
import math
import time

import chess
import chess.engine
import chess.pgn

from src.models import get_connection, init_db

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


def score_to_cp(score: chess.engine.PovScore, side: chess.Color) -> int | None:
    """Convert a PovScore to centipawns from white's perspective.

    Mate scores are converted to large centipawn values.
    """
    pov = score.white()
    if pov.is_mate():
        mate_in = pov.mate()
        if mate_in is not None:
            # Positive mate = white winning, negative = black winning
            return 30000 - abs(mate_in) * 10 if mate_in > 0 else -30000 + abs(mate_in) * 10
        return 0
    cp = pov.score()
    return cp if cp is not None else 0


def analyze_game(game_id: int, pgn_text: str, player_color: str,
                 stockfish_path: str, depth: int = 22,
                 threads: int = 6, hash_mb: int = 512,
                 move_time_limit: float = 10.0,
                 db_path: str | None = None) -> dict:
    """Analyze a single game move-by-move with Stockfish.

    Returns a dict with analysis stats.
    """
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

    logger.info("Analyzing game %d: %d moves at depth %d", game_id, total_moves, depth)

    # Use both depth and time limit — whichever is reached first.
    # This prevents hangs on complex endgame positions.
    limit = chess.engine.Limit(depth=depth, time=move_time_limit)

    # Get initial position eval
    info = engine.analyse(board, limit)
    prev_cp = score_to_cp(info["score"], board.turn)

    stats = {"moves": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0}

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

        # Calculate centipawn loss from the moving side's perspective
        if side == "white":
            # White wants positive eval. Loss = before - after (from white POV)
            cp_loss = max(0, (eval_before_cp or 0) - (eval_after_cp or 0))
        else:
            # Black wants negative eval. Loss = after - before (from white POV)
            # i.e., if eval goes from -100 to +50, black lost 150cp
            cp_loss = max(0, (eval_after_cp or 0) - (eval_before_cp or 0))

        swing_cp = cp_loss
        classification = classify_move(cp_loss)

        win_prob_before = cp_to_win_prob(eval_before_cp or 0)
        win_prob_after = cp_to_win_prob(eval_after_cp or 0)

        # Adjust win prob to be from the moving side's perspective
        if side == "black":
            win_prob_before = 100.0 - win_prob_before
            win_prob_after = 100.0 - win_prob_after

        conn.execute(
            """INSERT OR REPLACE INTO move_analysis
            (game_id, move_number, side, move_played, best_move,
             eval_before_cp, eval_after_cp, swing_cp,
             win_prob_before, win_prob_after, classification, pv_line)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (game_id, move_number, side, move_san, best_move_san,
             eval_before_cp, eval_after_cp, swing_cp,
             win_prob_before, win_prob_after, classification, pv_line),
        )

        stats["moves"] += 1
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

    # Mark as complete
    conn.execute(
        "UPDATE games SET analysis_status = 'complete' WHERE id = ?",
        (game_id,),
    )
    conn.commit()

    elapsed = time.time() - start_time
    logger.info(
        "Game %d analysis complete: %d moves in %.1fs (%.1f moves/sec). "
        "Blunders: %d, Mistakes: %d, Inaccuracies: %d",
        game_id, stats["moves"], elapsed, stats["moves"] / elapsed if elapsed > 0 else 0,
        stats["blunders"], stats["mistakes"], stats["inaccuracies"],
    )

    conn.close()
    return stats


def analyze_pending(stockfish_path: str, depth: int = 22,
                    threads: int = 6, hash_mb: int = 512,
                    move_time_limit: float = 10.0,
                    db_path: str | None = None) -> int:
    """Analyze all games with pending analysis status.

    Returns the number of games analyzed.
    """
    conn = init_db(db_path)

    # Reset any games stuck in 'analyzing' from interrupted runs
    stuck = conn.execute(
        "UPDATE games SET analysis_status = 'pending' WHERE analysis_status = 'analyzing'"
    ).rowcount
    if stuck:
        conn.commit()
        logger.info("Reset %d interrupted games back to pending", stuck)

    pending = conn.execute(
        "SELECT id, pgn, player_color FROM games WHERE analysis_status = 'pending'"
    ).fetchall()
    conn.close()

    logger.info("Found %d games pending analysis", len(pending))

    for i, row in enumerate(pending):
        logger.info("Analyzing game %d/%d (id=%d)", i + 1, len(pending), row["id"])
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
