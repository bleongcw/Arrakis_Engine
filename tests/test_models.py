"""Tests for src/models.py"""

import sqlite3
import tempfile
import os

import pytest

from src.models import (
    init_db, get_connection, ensure_player,
    extract_opponent_from_pgn, get_db_path, _migrate,
)


class TestInitDb:
    def test_creates_all_tables(self, db_path):
        conn = init_db(db_path)
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        conn.close()
        assert "players" in tables
        assert "games" in tables
        assert "move_analysis" in tables
        assert "game_coaching" in tables
        assert "player_patterns" in tables

    def test_idempotent(self, db_path):
        conn1 = init_db(db_path)
        conn1.close()
        conn2 = init_db(db_path)
        tables = conn2.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn2.close()
        assert len(tables) >= 5

    def test_foreign_keys_enabled(self, db_path):
        conn = init_db(db_path)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        conn.close()
        assert fk == 1


class TestEnsurePlayer:
    def test_creates_new_player(self, db_path):
        conn = init_db(db_path)
        pid = ensure_player(conn, "testuser", display_name="Test", age=9, rating=1000)
        assert pid > 0
        row = conn.execute("SELECT * FROM players WHERE id = ?", (pid,)).fetchone()
        assert row["username"] == "testuser"
        assert row["display_name"] == "Test"
        assert row["age"] == 9
        assert row["rating"] == 1000
        conn.close()

    def test_returns_existing_player(self, db_path):
        conn = init_db(db_path)
        pid1 = ensure_player(conn, "testuser", display_name="Test")
        pid2 = ensure_player(conn, "testuser")
        assert pid1 == pid2
        conn.close()

    def test_updates_fields(self, db_path):
        conn = init_db(db_path)
        ensure_player(conn, "testuser", display_name="Old")
        ensure_player(conn, "testuser", display_name="New", rating=1100)
        row = conn.execute(
            "SELECT * FROM players WHERE username = 'testuser'"
        ).fetchone()
        assert row["display_name"] == "New"
        assert row["rating"] == 1100
        conn.close()


class TestGameSchema:
    def test_game_url_unique(self, db_path):
        conn = init_db(db_path)
        pid = ensure_player(conn, "testuser")
        conn.execute(
            """INSERT INTO games (player_id, game_url, pgn, player_color, result)
            VALUES (?, 'http://example.com/1', '1. e4', 'white', 'win')""",
            (pid,),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO games (player_id, game_url, pgn, player_color, result)
                VALUES (?, 'http://example.com/1', '1. d4', 'black', 'loss')""",
                (pid,),
            )
        conn.close()

    def test_valid_color_constraint(self, db_path):
        conn = init_db(db_path)
        pid = ensure_player(conn, "testuser")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO games (player_id, game_url, pgn, player_color, result)
                VALUES (?, 'http://example.com/2', '1. e4', 'red', 'win')""",
                (pid,),
            )
        conn.close()

    def test_valid_result_constraint(self, db_path):
        conn = init_db(db_path)
        pid = ensure_player(conn, "testuser")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO games (player_id, game_url, pgn, player_color, result)
                VALUES (?, 'http://example.com/3', '1. e4', 'white', 'stalemate')""",
                (pid,),
            )
        conn.close()


class TestExtractOpponentFromPgn:
    def test_player_is_white_returns_black(self):
        pgn = '[White "me"]\n[Black "opponent"]\n\n1. e4 e5 *'
        assert extract_opponent_from_pgn(pgn, "white") == "opponent"

    def test_player_is_black_returns_white(self):
        pgn = '[White "opponent"]\n[Black "me"]\n\n1. e4 e5 *'
        assert extract_opponent_from_pgn(pgn, "black") == "opponent"

    def test_missing_header_returns_none(self):
        pgn = "1. e4 e5 *"
        assert extract_opponent_from_pgn(pgn, "white") is None

    def test_malformed_pgn(self):
        pgn = '[White "broken'
        assert extract_opponent_from_pgn(pgn, "white") is None


class TestGetDbPath:
    def test_creates_directory(self, tmp_path):
        nested = str(tmp_path / "a" / "b" / "test.db")
        result = get_db_path(nested)
        assert os.path.isdir(os.path.dirname(result))

    def test_returns_string_path(self, tmp_path):
        result = get_db_path(str(tmp_path / "test.db"))
        assert isinstance(result, str)
        assert result.endswith("test.db")


class TestMigrations:
    def test_adds_expected_columns(self, db_path):
        """Verify migration adds columns to a freshly-init'd DB."""
        conn = init_db(db_path)
        # Check that migrated columns exist on games
        game_cols = {r[1] for r in conn.execute("PRAGMA table_info(games)").fetchall()}
        assert "opponent_username" in game_cols
        assert "platform" in game_cols
        assert "acpl" in game_cols

        # Check migrated columns on game_coaching
        coaching_cols = {r[1] for r in conn.execute("PRAGMA table_info(game_coaching)").fetchall()}
        assert "opening_analysis_json" in coaching_cols
        assert "player_feedback" in coaching_cols

        # Check migrated columns on players
        player_cols = {r[1] for r in conn.execute("PRAGMA table_info(players)").fetchall()}
        assert "fide_id" in player_cols
        assert "fide_rating" in player_cols
        assert "lichess_username" in player_cols
        conn.close()


class TestBackfillAcplMateTransition:
    """v1.7.1 regression: ACPL should NOT count the mate-delivering move as a
    loss, and no single move should contribute more than EVAL_CAP cp.

    Original bug: a Scholar's-Mate game ending in Qxf7# had stored ACPL of
    291.3 because the mate-delivering move (engine's #1 choice, eval
    transition 29990 → -30000) registered as a 2000cp 'loss' after the
    per-eval cap of ±1000. Fix: played-best-move gets zero loss + per-move
    loss cap. See game 419 in the repro DB."""

    def _seed_mate_game(self, conn, player_id):
        cur = conn.execute(
            """INSERT INTO games (player_id, game_url, pgn, player_color,
                                  player_rating, opponent_rating, result,
                                  time_control, time_class, date_played,
                                  platform, analysis_status)
               VALUES (?, ?, ?, 'white', 1100, 1000, 'win', '600',
                       'rapid', '2026-03-06', 'chess.com', 'complete')""",
            (player_id, "https://test.example/g/1",
             '[White "TestKid"]\n[Black "Opp"]\n\n1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# *'),
        )
        game_id = cur.lastrowid
        moves = [
            (1, "white", "e4",    "Nf3",   20,     25),
            (1, "black", "e5",    "e5",    25,     25),
            (2, "white", "Bc4",   "Nf3",   25,     40),
            (2, "black", "Nc6",   "Nc6",   40,     40),
            (3, "white", "Qh5",   "Nf3",   40,    150),
            (3, "black", "Nf6",   "g6",   150,  29990),
            # The bug case: white delivers mate, played==best, eval crosses cap.
            (4, "white", "Qxf7#", "Qxf7#", 29990, -30000),
        ]
        for mv in moves:
            conn.execute(
                """INSERT INTO move_analysis (game_id, move_number, side,
                                              move_played, best_move,
                                              eval_before_cp, eval_after_cp,
                                              swing_cp, classification)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'excellent')""",
                (game_id, mv[0], mv[1], mv[2], mv[3], mv[4], mv[5], 0),
            )
        conn.commit()
        return game_id

    def test_mate_delivering_move_does_not_inflate_acpl(self, db_path):
        from src.models import backfill_acpl_for_games
        conn = init_db(db_path)
        pid = ensure_player(conn, "testkid", display_name="TestKid",
                            age=9, rating=1100)
        game_id = self._seed_mate_game(conn, pid)
        updated = backfill_acpl_for_games(conn, force=True)
        assert updated == 1
        acpl = conn.execute(
            "SELECT acpl FROM games WHERE id = ?", (game_id,),
        ).fetchone()["acpl"]
        # Sanity: no single move can contribute more than EVAL_CAP=1000
        assert acpl <= 1000
        # Expected: (5 + 15 + 110 + 0) / 4 = 32.5. Allow rounding wiggle.
        assert acpl < 50, (
            f"ACPL {acpl} suggests mate-delivering move still inflated it "
            "(should be ~32, was probably ~290 pre-fix)"
        )
        conn.close()

    def test_per_move_loss_cap_applied(self, db_path):
        """A non-best move with a >2000cp swing must be capped at 1000."""
        from src.models import backfill_acpl_for_games
        conn = init_db(db_path)
        pid = ensure_player(conn, "x", age=10, rating=1000)
        cur = conn.execute(
            """INSERT INTO games (player_id, game_url, pgn, player_color,
                                  result, time_class, date_played,
                                  analysis_status)
               VALUES (?, '', '', 'white', 'loss', 'rapid',
                       '2026-04-01', 'complete')""",
            (pid,),
        )
        gid = cur.lastrowid
        conn.execute(
            """INSERT INTO move_analysis (game_id, move_number, side,
                                          move_played, best_move,
                                          eval_before_cp, eval_after_cp,
                                          swing_cp, classification)
               VALUES (?, 1, 'white', 'g4', 'e4', 29990, -30000, 0, 'blunder')""",
            (gid,),
        )
        conn.commit()
        updated = backfill_acpl_for_games(conn, force=True)
        assert updated == 1
        acpl = conn.execute(
            "SELECT acpl FROM games WHERE id = ?", (gid,),
        ).fetchone()["acpl"]
        # Single move, capped at 1000 → ACPL = 1000.0 exactly
        assert acpl == 1000.0

    def test_force_recomputes_existing_acpl(self, db_path):
        """`force=True` should overwrite previously-stored (wrong) values."""
        from src.models import backfill_acpl_for_games
        conn = init_db(db_path)
        pid = ensure_player(conn, "x", age=10, rating=1000)
        cur = conn.execute(
            """INSERT INTO games (player_id, game_url, pgn, player_color,
                                  result, time_class, date_played,
                                  analysis_status, acpl)
               VALUES (?, '', '', 'white', 'win', 'rapid',
                       '2026-04-01', 'complete', 999)""",
            (pid,),
        )
        gid = cur.lastrowid
        conn.execute(
            """INSERT INTO move_analysis (game_id, move_number, side,
                                          move_played, best_move,
                                          eval_before_cp, eval_after_cp,
                                          swing_cp, classification)
               VALUES (?, 1, 'white', 'e4', 'e4', 20, 20, 0, 'excellent')""",
            (gid,),
        )
        conn.commit()
        # Default (no force) skips it because acpl IS NOT NULL
        n = backfill_acpl_for_games(conn, force=False)
        assert n == 0
        # force=True overwrites
        n = backfill_acpl_for_games(conn, force=True)
        assert n == 1
        acpl_fixed = conn.execute(
            "SELECT acpl FROM games WHERE id = ?", (gid,),
        ).fetchone()["acpl"]
        assert acpl_fixed == 0.0
        conn.close()
