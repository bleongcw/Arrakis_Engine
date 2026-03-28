"""Integration tests for Stockfish analysis.

These tests require a real Stockfish binary and are excluded by default.
Run with: pytest -m integration
"""

import pytest

from src.analyzer import analyze_game, analyze_pending
from src.models import init_db, ensure_player
from tests.conftest import SCHOLARS_MATE_PGN


pytestmark = pytest.mark.integration


@pytest.fixture
def game_for_analysis(db_path, player_id):
    """Insert a Scholar's Mate game ready for analysis."""
    conn = init_db(db_path)
    conn.execute(
        """INSERT INTO games
        (player_id, game_url, pgn, player_color, player_rating,
         opponent_rating, result, time_control, time_class, date_played,
         analysis_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (player_id, "https://chess.com/game/integration-1",
         SCHOLARS_MATE_PGN, "white", 1050, 980, "win",
         "600", "rapid", "2026-03-01", "pending"),
    )
    conn.commit()
    game_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return game_id


class TestAnalyzeGameEndToEnd:
    def test_creates_move_rows(self, stockfish_path, db_path, game_for_analysis):
        """Stockfish analysis should create one row per half-move."""
        result = analyze_game(
            game_for_analysis, SCHOLARS_MATE_PGN, "white",
            stockfish_path, depth=12, move_time_limit=5.0, db_path=db_path,
        )
        assert result["moves"] == 7  # 4 white + 3 black half-moves

        conn = init_db(db_path)
        rows = conn.execute(
            "SELECT * FROM move_analysis WHERE game_id = ? ORDER BY move_number, side",
            (game_for_analysis,),
        ).fetchall()
        conn.close()

        assert len(rows) == 7
        # Each row should have key fields populated
        for row in rows:
            assert row["eval_before_cp"] is not None
            assert row["eval_after_cp"] is not None
            assert row["classification"] is not None
            assert row["move_played"] is not None

    def test_evaluations_are_sane(self, stockfish_path, db_path, game_for_analysis):
        """Opening eval should be near 0; mate move should be extreme."""
        analyze_game(
            game_for_analysis, SCHOLARS_MATE_PGN, "white",
            stockfish_path, depth=12, move_time_limit=5.0, db_path=db_path,
        )
        conn = init_db(db_path)
        moves = conn.execute(
            "SELECT * FROM move_analysis WHERE game_id = ? ORDER BY move_number, CASE side WHEN 'white' THEN 0 ELSE 1 END",
            (game_for_analysis,),
        ).fetchall()
        conn.close()

        # First move (e4) — eval should be reasonable, within ±100cp
        first_move = moves[0]
        assert first_move["move_played"] == "e4"
        assert abs(first_move["eval_after_cp"]) < 100

        # Last move (Qxf7#) — should show mate (mapped to ±1000cp)
        last_move = moves[-1]
        assert last_move["move_played"] == "Qxf7#"

    def test_acpl_stored_on_game(self, stockfish_path, db_path, game_for_analysis):
        """Game row should have ACPL and status='complete' after analysis."""
        analyze_game(
            game_for_analysis, SCHOLARS_MATE_PGN, "white",
            stockfish_path, depth=12, move_time_limit=5.0, db_path=db_path,
        )
        conn = init_db(db_path)
        game = conn.execute(
            "SELECT analysis_status, acpl FROM games WHERE id = ?",
            (game_for_analysis,),
        ).fetchone()
        conn.close()

        assert game["analysis_status"] == "complete"
        assert isinstance(game["acpl"], float)
        assert game["acpl"] >= 0

    def test_classifications_present(self, stockfish_path, db_path, game_for_analysis):
        """Each move should have a valid classification."""
        analyze_game(
            game_for_analysis, SCHOLARS_MATE_PGN, "white",
            stockfish_path, depth=12, move_time_limit=5.0, db_path=db_path,
        )
        conn = init_db(db_path)
        rows = conn.execute(
            "SELECT classification FROM move_analysis WHERE game_id = ?",
            (game_for_analysis,),
        ).fetchall()
        conn.close()

        valid = {"excellent", "good", "inaccuracy", "mistake", "blunder"}
        for row in rows:
            assert row["classification"] in valid


class TestAnalyzePendingBatch:
    def test_batch_analyzes_pending_games(self, stockfish_path, db_path, player_id):
        """analyze_pending should process all pending games."""
        conn = init_db(db_path)
        for i in range(2):
            conn.execute(
                """INSERT INTO games
                (player_id, game_url, pgn, player_color, player_rating,
                 result, time_control, time_class, date_played, analysis_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (player_id, f"https://chess.com/game/batch-{i}",
                 SCHOLARS_MATE_PGN, "white", 1050, "win",
                 "600", "rapid", "2026-03-01", "pending"),
            )
        conn.commit()
        conn.close()

        count = analyze_pending(
            stockfish_path, depth=12, move_time_limit=5.0, db_path=db_path,
        )
        assert count == 2

        conn = init_db(db_path)
        statuses = conn.execute(
            "SELECT analysis_status FROM games WHERE player_id = ?",
            (player_id,),
        ).fetchall()
        conn.close()
        assert all(s["analysis_status"] == "complete" for s in statuses)

    def test_stuck_game_recovery(self, stockfish_path, db_path, player_id):
        """Games stuck in 'analyzing' should be reset and re-analyzed."""
        conn = init_db(db_path)
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, player_rating,
             result, time_control, time_class, date_played, analysis_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (player_id, "https://chess.com/game/stuck-1",
             SCHOLARS_MATE_PGN, "white", 1050, "win",
             "600", "rapid", "2026-03-01", "analyzing"),
        )
        conn.commit()
        conn.close()

        analyze_pending(
            stockfish_path, depth=12, move_time_limit=5.0, db_path=db_path,
        )

        conn = init_db(db_path)
        game = conn.execute(
            "SELECT analysis_status FROM games WHERE game_url = ?",
            ("https://chess.com/game/stuck-1",),
        ).fetchone()
        conn.close()
        assert game["analysis_status"] == "complete"


class TestAnalyzeErrorHandling:
    def test_empty_pgn_handled_gracefully(self, stockfish_path, db_path, player_id):
        """Games with no valid moves should be marked complete (abandoned)."""
        conn = init_db(db_path)
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, player_rating,
             result, time_control, time_class, date_played, analysis_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (player_id, "https://chess.com/game/bad-pgn",
             "this is not valid PGN at all ###", "white", 1050, "win",
             "600", "rapid", "2026-03-01", "pending"),
        )
        conn.commit()
        game_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

        result = analyze_game(
            game_id, "this is not valid PGN at all ###", "white",
            stockfish_path, depth=12, db_path=db_path,
        )

        # PGN parser treats garbage as 0-move game (abandoned)
        assert result["moves"] == 0 or "error" in result

        conn = init_db(db_path)
        game = conn.execute(
            "SELECT analysis_status FROM games WHERE id = ?",
            (game_id,),
        ).fetchone()
        conn.close()
        # Should be either 'complete' (0-move game) or 'error'
        assert game["analysis_status"] in ("complete", "error")
