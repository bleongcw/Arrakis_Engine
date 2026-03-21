"""Tests for the live dashboard API server."""

import json
import threading
import time
import urllib.request

import pytest

from src.models import init_db, ensure_player
from src.dashboard_server import run_dashboard


@pytest.fixture
def db_with_data(tmp_path):
    """Create a test DB with sample data."""
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)

    pid = ensure_player(conn, "testplayer", display_name="Test", age=10, rating=1000)

    conn.execute(
        """INSERT INTO games (player_id, game_url, pgn, player_color,
           player_rating, opponent_rating, result, time_control,
           time_class, date_played, analysis_status, coaching_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (pid, "https://chess.com/game/1", "1. e4 e5 *", "white",
         1000, 1100, "win", "600", "rapid", "2026-01-15", "complete", "pending"),
    )
    game_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        """INSERT INTO move_analysis (game_id, move_number, side, move_played,
           best_move, eval_before_cp, eval_after_cp, swing_cp,
           win_prob_before, win_prob_after, classification)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (game_id, 1, "white", "e4", "e4", 0, 20, 0, 50.0, 51.0, "excellent"),
    )
    conn.execute(
        """INSERT INTO move_analysis (game_id, move_number, side, move_played,
           best_move, eval_before_cp, eval_after_cp, swing_cp,
           win_prob_before, win_prob_after, classification)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (game_id, 1, "black", "e5", "e5", 20, 15, 5, 49.0, 49.5, "good"),
    )

    # Add a pending game
    conn.execute(
        """INSERT INTO games (player_id, game_url, pgn, player_color,
           player_rating, opponent_rating, result, time_control,
           time_class, date_played, analysis_status, coaching_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (pid, "https://chess.com/game/2", "1. d4 d5 *", "black",
         1000, 950, "loss", "180", "blitz", "2026-01-16", "pending", "pending"),
    )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def live_server(db_with_data):
    """Start the dashboard server in a background thread."""
    import http.server
    from functools import partial
    from src.dashboard_server import DashboardHandler

    port = 18765
    handler = partial(DashboardHandler, directory="dashboard", db_path=db_with_data)
    httpd = http.server.HTTPServer(("127.0.0.1", port), handler)

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)

    yield f"http://127.0.0.1:{port}"

    httpd.shutdown()


def api_get(base_url, path):
    """Helper: GET an API endpoint and return parsed JSON."""
    url = base_url + path
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


class TestPlayersAPI:
    def test_list_players(self, live_server):
        data = api_get(live_server, "/api/players")
        assert len(data) == 1
        assert data[0]["username"] == "testplayer"
        assert data[0]["display_name"] == "Test"


class TestGamesAPI:
    def test_list_games(self, live_server):
        data = api_get(live_server, "/api/games?player=testplayer")
        assert len(data) == 2

    def test_filter_by_result(self, live_server):
        data = api_get(live_server, "/api/games?player=testplayer&result=win")
        assert len(data) == 1
        assert data[0]["result"] == "win"

    def test_filter_by_time_class(self, live_server):
        data = api_get(live_server, "/api/games?player=testplayer&time_class=blitz")
        assert len(data) == 1
        assert data[0]["time_class"] == "blitz"

    def test_game_detail(self, live_server):
        games = api_get(live_server, "/api/games?player=testplayer")
        complete_game = [g for g in games if g["analysis_status"] == "complete"][0]

        detail = api_get(live_server, f"/api/games/{complete_game['id']}")
        assert "game" in detail
        assert "moves" in detail
        assert len(detail["moves"]) == 2
        assert detail["moves"][0]["move_played"] == "e4"
        assert detail["moves"][0]["classification"] == "excellent"

    def test_game_not_found(self, live_server):
        data = api_get(live_server, "/api/games/99999")
        assert "error" in data


class TestStatusAPI:
    def test_status(self, live_server):
        data = api_get(live_server, "/api/status")
        assert data["total_games"] == 2
        assert data["analysis_complete"] == 1
        assert data["analysis_pending"] == 1


class TestPatternsAPI:
    def test_no_patterns(self, live_server):
        data = api_get(live_server, "/api/patterns?player=testplayer")
        assert data["stats"] is None

    def test_missing_player_param(self, live_server):
        data = api_get(live_server, "/api/patterns")
        assert "error" in data
