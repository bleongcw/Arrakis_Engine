"""Tests for src/report.py"""

from datetime import datetime, timedelta

import pytest

from src.report import generate_report
from src.models import init_db, ensure_player


@pytest.fixture
def db_with_games(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    # v1.16.4: pin slug to "testplayer" so the rest of the test file
    # (which calls generate_report("testplayer", ...)) keeps working
    # under slug-only lookup. Mirrors how a real config.yaml entry
    # might set slug == username intentionally (Bernard's setup).
    pid = ensure_player(conn, "testplayer", display_name="TestKid",
                        slug="testplayer", age=9, rating=1050)

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
        ensure_player(conn, "testplayer", display_name="TestKid",
                      slug="testplayer")
        conn.close()

        output_dir = str(tmp_path / "reports")
        path = generate_report("testplayer", output_dir=output_dir, db_path=db_path)
        with open(path) as f:
            content = f.read()
        assert "No games played" in content


class TestAcplInterpretation:
    """Test that ACPL thresholds produce correct interpretation text."""

    def _make_db_with_acpl(self, tmp_path, swing_cp):
        """Create a DB where every player move has the given swing_cp."""
        db_path = str(tmp_path / "acpl_test.db")
        conn = init_db(db_path)
        # v1.16.4: pin slug to "testplayer" so generate_report calls
        # below keep working under slug-only lookup.
        pid = ensure_player(conn, "testplayer", display_name="TestKid",
                            slug="testplayer", age=9, rating=1050)

        recent = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, player_rating,
             opponent_rating, result, time_control, time_class, date_played,
             analysis_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, "https://chess.com/g/1", "1. e4 e5 *", "white",
             1050, 980, "win", "600", "rapid", recent, "complete"),
        )
        gid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert moves with uniform swing_cp so ACPL equals swing_cp
        for i in range(10):
            conn.execute(
                """INSERT INTO move_analysis
                (game_id, move_number, side, move_played, best_move,
                 eval_before_cp, eval_after_cp, swing_cp,
                 win_prob_before, win_prob_after, classification)
                VALUES (?, ?, 'white', 'e4', 'e4', 0, 0, ?, 50, 50, 'excellent')""",
                (gid, i + 1, swing_cp),
            )
        conn.commit()
        conn.close()
        return db_path

    def test_excellent_acpl(self, tmp_path):
        db_path = self._make_db_with_acpl(tmp_path, swing_cp=20)
        output_dir = str(tmp_path / "reports")
        path = generate_report("testplayer", output_dir=output_dir, db_path=db_path)
        with open(path) as f:
            content = f.read()
        assert "Excellent accuracy" in content

    def test_good_acpl(self, tmp_path):
        db_path = self._make_db_with_acpl(tmp_path, swing_cp=55)
        output_dir = str(tmp_path / "reports")
        path = generate_report("testplayer", output_dir=output_dir, db_path=db_path)
        with open(path) as f:
            content = f.read()
        assert "Good accuracy" in content

    def test_needs_work_acpl(self, tmp_path):
        db_path = self._make_db_with_acpl(tmp_path, swing_cp=90)
        output_dir = str(tmp_path / "reports")
        path = generate_report("testplayer", output_dir=output_dir, db_path=db_path)
        with open(path) as f:
            content = f.read()
        assert "Higher than ideal" in content


class TestTimeClassTable:
    def test_report_includes_time_control_table(self, db_with_games):
        db_path, tmp_path = db_with_games
        output_dir = str(tmp_path / "reports")
        path = generate_report("testplayer", output_dir=output_dir, db_path=db_path)
        with open(path) as f:
            content = f.read()
        assert "Time Control" in content
        assert "rapid" in content


class TestNoCoachingData:
    def test_report_handles_no_coaching(self, db_with_games):
        """Report should still generate when no coaching data exists."""
        db_path, tmp_path = db_with_games
        output_dir = str(tmp_path / "reports")
        path = generate_report("testplayer", output_dir=output_dir, db_path=db_path)
        with open(path) as f:
            content = f.read()
        # Should have fallback message for critical positions
        assert "coaching data" in content.lower() or "coach" in content.lower()
