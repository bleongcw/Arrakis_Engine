"""Tests for src/export.py"""

import json

import pytest

from src.export import export_json
from src.models import init_db, ensure_player


@pytest.fixture
def db_with_game(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    pid = ensure_player(conn, "testplayer", display_name="Test", age=9, rating=1050)
    conn.execute(
        """INSERT INTO games
        (player_id, game_url, pgn, player_color, player_rating,
         opponent_rating, result, time_control, time_class, date_played,
         analysis_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (pid, "https://chess.com/g/1", "1. e4 e5 *", "white", 1050, 980,
         "win", "600", "rapid", "2026-03-01", "complete"),
    )
    conn.commit()
    conn.close()
    return db_path, tmp_path


class TestExportJson:
    def test_exports_all_files(self, db_with_game):
        db_path, tmp_path = db_with_game
        out_dir = str(tmp_path / "export")
        counts = export_json(output_dir=out_dir, db_path=db_path)

        assert counts["players"] == 1
        assert counts["games"] == 1

        # Verify files exist
        with open(f"{out_dir}/players.json") as f:
            players = json.load(f)
        assert len(players) == 1
        assert players[0]["username"] == "testplayer"

        with open(f"{out_dir}/games.json") as f:
            games = json.load(f)
        assert len(games) == 1

    def test_exports_game_detail(self, db_with_game):
        db_path, tmp_path = db_with_game
        out_dir = str(tmp_path / "export")
        export_json(output_dir=out_dir, db_path=db_path)

        with open(f"{out_dir}/games/1.json") as f:
            detail = json.load(f)
        assert detail["game"]["game_url"] == "https://chess.com/g/1"
        assert detail["moves"] == []  # No analysis yet
        assert detail["coaching"] is None

    def test_empty_db(self, tmp_path):
        db_path = str(tmp_path / "empty.db")
        init_db(db_path)
        out_dir = str(tmp_path / "export")
        counts = export_json(output_dir=out_dir, db_path=db_path)
        assert counts["players"] == 0
        assert counts["games"] == 0


class TestPgnPreviewTruncation:
    def test_long_pgn_truncated(self, tmp_path):
        """PGN preview in games.json should be truncated to 200 chars."""
        db_path = str(tmp_path / "test.db")
        conn = init_db(db_path)
        pid = ensure_player(conn, "testplayer", display_name="Test")
        long_pgn = "1. e4 e5 " * 100  # ~900 chars
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, result, analysis_status)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (pid, "https://chess.com/g/1", long_pgn, "white", "win", "complete"),
        )
        conn.commit()
        conn.close()

        out_dir = str(tmp_path / "export")
        export_json(output_dir=out_dir, db_path=db_path)

        with open(f"{out_dir}/games.json") as f:
            games = json.load(f)
        assert len(games[0]["pgn_preview"]) <= 200


class TestCoachingDataInExport:
    def test_game_with_coaching_includes_data(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = init_db(db_path)
        pid = ensure_player(conn, "testplayer", display_name="Test")
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, result, analysis_status)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (pid, "https://chess.com/g/1", "1. e4 e5 *", "white", "win", "complete"),
        )
        gid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO game_coaching
            (game_id, provider, narrative, key_lesson)
            VALUES (?, ?, ?, ?)""",
            (gid, "claude:test", "Great game!", "Develop pieces"),
        )
        conn.commit()
        conn.close()

        out_dir = str(tmp_path / "export")
        export_json(output_dir=out_dir, db_path=db_path)

        with open(f"{out_dir}/games/{gid}.json") as f:
            detail = json.load(f)
        assert detail["coaching"] is not None
        assert detail["coaching"]["narrative"] == "Great game!"


class TestMissingAnalysisExport:
    def test_game_without_analysis_exports(self, db_with_game):
        """Games without move analysis should export without crashing."""
        db_path, tmp_path = db_with_game
        out_dir = str(tmp_path / "export")
        counts = export_json(output_dir=out_dir, db_path=db_path)
        assert counts["games"] == 1

        with open(f"{out_dir}/games/1.json") as f:
            detail = json.load(f)
        assert detail["moves"] == []


class TestPatternsExport:
    def test_patterns_json_created(self, tmp_path):
        """patterns.json should be created even if empty."""
        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        out_dir = str(tmp_path / "export")
        export_json(output_dir=out_dir, db_path=db_path)

        with open(f"{out_dir}/patterns.json") as f:
            patterns = json.load(f)
        assert isinstance(patterns, list)
