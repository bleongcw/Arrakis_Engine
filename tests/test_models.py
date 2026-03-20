"""Tests for src/models.py"""

import sqlite3
import tempfile
import os

import pytest

from src.models import init_db, get_connection, ensure_player


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


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
