"""Tests for src/report.py"""

from datetime import datetime, timedelta

import pytest

from src.report import generate_report
from src.models import init_db, ensure_player


@pytest.fixture
def db_with_games(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    pid = ensure_player(conn, "testplayer", display_name="TestKid", age=9, rating=1050)

    # Games within last week — use relative dates so test never goes stale
    recent_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    for i in range(3):
        result = ["win", "loss", "win"][i]
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, player_rating,
             opponent_rating, result, time_control, time_class, date_played,
             analysis_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, f"https://chess.com/g/{i}", "1. e4 e5 *", "white",
             1050 + i * 10, 980 + i * 20, result, "600", "rapid",
             recent_date, "complete"),
        )
    conn.commit()
    conn.close()
    return db_path, tmp_path


class TestGenerateReport:
    def test_generates_weekly_report(self, db_with_games):
        db_path, tmp_path = db_with_games
        output_dir = str(tmp_path / "reports")
        path = generate_report("testplayer", period="weekly",
                               output_dir=output_dir, db_path=db_path)
        assert path.endswith(".md")
        with open(path) as f:
            content = f.read()
        assert "TestKid" in content
        assert "Games played:" in content
        assert "3" in content

    def test_generates_monthly_report(self, db_with_games):
        db_path, tmp_path = db_with_games
        output_dir = str(tmp_path / "reports")
        path = generate_report("testplayer", period="monthly",
                               output_dir=output_dir, db_path=db_path)
        with open(path) as f:
            content = f.read()
        assert "TestKid" in content

    def test_unknown_player_raises(self, db_with_games):
        db_path, _ = db_with_games
        with pytest.raises(ValueError, match="not found"):
            generate_report("nobody", db_path=db_path)

    def test_no_games_in_period(self, tmp_path):
        db_path = str(tmp_path / "empty.db")
        conn = init_db(db_path)
        ensure_player(conn, "testplayer", display_name="TestKid")
        conn.close()

        output_dir = str(tmp_path / "reports")
        path = generate_report("testplayer", output_dir=output_dir, db_path=db_path)
        with open(path) as f:
            content = f.read()
        assert "No games played" in content
