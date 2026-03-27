"""Tests for src/patterns.py"""

import json

import pytest

from src.patterns import (
    _classify_game_phase,
    _compute_results,
    _compute_rating_performance,
    _compute_phase_analysis,
    _compute_move_quality,
    _compute_accuracy,
    _compute_consistency,
    _compute_danger_zones,
    _compute_endgame_conversion,
    _compute_time_control_performance,
    compute_player_patterns,
    update_patterns,
)
from src.models import init_db, ensure_player


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def populated_db(db_path):
    """Create a DB with a player, games, and move analysis."""
    conn = init_db(db_path)
    pid = ensure_player(conn, "testplayer", display_name="TestKid", age=9, rating=1050)

    # Insert 3 games
    games = [
        (pid, "https://chess.com/g/1",
         '[White "testplayer"]\n[Black "opp1"]\n[Opening "Italian Game"]\n\n1. e4 e5 *',
         "white", 1050, 980, "win", "600", "rapid", "2026-03-01", "complete"),
        (pid, "https://chess.com/g/2",
         '[White "opp2"]\n[Black "testplayer"]\n[Opening "Italian Game"]\n\n1. e4 e5 *',
         "black", 1060, 1100, "loss", "600", "rapid", "2026-03-05", "complete"),
        (pid, "https://chess.com/g/3",
         '[White "testplayer"]\n[Black "opp3"]\n[Opening "Sicilian Defense"]\n\n1. e4 c5 *',
         "white", 1070, 1020, "win", "600", "rapid", "2026-03-10", "complete"),
    ]
    game_ids = []
    for g in games:
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, player_rating,
             opponent_rating, result, time_control, time_class, date_played,
             analysis_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            g,
        )
        game_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    # Add move analysis for each game
    for gid, color in zip(game_ids, ["white", "black", "white"]):
        for mn in range(1, 21):
            swing = 5 if mn < 10 else (150 if mn == 15 else 30)
            cls = "excellent" if swing <= 30 else ("mistake" if swing <= 300 else "blunder")
            if swing == 5:
                cls = "excellent"
            elif swing == 30:
                cls = "good"
            else:
                cls = "mistake"
            conn.execute(
                """INSERT INTO move_analysis
                (game_id, move_number, side, move_played, best_move,
                 eval_before_cp, eval_after_cp, swing_cp,
                 win_prob_before, win_prob_after, classification, pv_line)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (gid, mn, color, "e4", "e4", 20, 20 - swing, swing,
                 51.0, 50.0, cls, "e4 e5"),
            )
    conn.commit()
    conn.close()
    return pid


class TestClassifyGamePhase:
    def test_opening(self):
        assert _classify_game_phase(1) == "opening"
        assert _classify_game_phase(15) == "opening"

    def test_middlegame(self):
        assert _classify_game_phase(16) == "middlegame"
        assert _classify_game_phase(30) == "middlegame"

    def test_endgame(self):
        assert _classify_game_phase(31) == "endgame"
        assert _classify_game_phase(50) == "endgame"


class TestComputeResults:
    def test_basic_results(self):
        games = [
            {"result": "win"}, {"result": "win"}, {"result": "loss"}, {"result": "draw"},
        ]
        r = _compute_results(games)
        assert r["wins"] == 2
        assert r["losses"] == 1
        assert r["draws"] == 1
        assert r["win_rate"] == 50.0


class TestComputeRatingPerformance:
    def test_buckets(self):
        games = [
            {"player_rating": 1000, "opponent_rating": 1100, "result": "win"},   # vs_higher
            {"player_rating": 1000, "opponent_rating": 900, "result": "win"},    # vs_lower
            {"player_rating": 1000, "opponent_rating": 1020, "result": "loss"},  # vs_equal
        ]
        r = _compute_rating_performance(games)
        assert r["vs_higher"]["wins"] == 1
        assert r["vs_lower"]["wins"] == 1
        assert r["vs_equal"]["losses"] == 1


class TestComputePlayerPatterns:
    def test_full_computation(self, db_path, populated_db):
        stats = compute_player_patterns(populated_db, db_path=db_path)
        assert stats["total_games"] == 3
        assert stats["results"]["wins"] == 2
        assert stats["results"]["losses"] == 1
        assert len(stats["openings"]) >= 1
        assert "opening" in stats["phase_analysis"]
        assert "middlegame" in stats["phase_analysis"]
        # New Phase 1 metrics
        assert "accuracy" in stats
        assert "consistency" in stats
        assert "danger_zones" in stats
        assert "endgame_conversion" in stats
        assert "time_control_performance" in stats

    def test_stores_in_db(self, db_path, populated_db):
        compute_player_patterns(populated_db, db_path=db_path)
        conn = init_db(db_path)
        row = conn.execute(
            "SELECT * FROM player_patterns WHERE player_id = ?",
            (populated_db,),
        ).fetchone()
        conn.close()
        assert row is not None
        stats = json.loads(row["stats_json"])
        assert stats["total_games"] == 3

    def test_empty_player(self, db_path):
        conn = init_db(db_path)
        pid = ensure_player(conn, "empty_player")
        conn.close()
        stats = compute_player_patterns(pid, db_path=db_path)
        assert stats == {}


class TestComputeAccuracy:
    def test_accuracy_calculation(self):
        games = [{"id": 1, "player_color": "white", "date_played": "2026-03-01", "result": "win"}]
        moves = {1: [
            {"side": "white", "move_played": "e4", "best_move": "e4", "classification": "excellent"},
            {"side": "white", "move_played": "Nf3", "best_move": "Nf3", "classification": "excellent"},
            {"side": "white", "move_played": "d4", "best_move": "Bc4", "classification": "good"},
        ]}
        result = _compute_accuracy(games, moves)
        assert result["overall_pct"] == 66.7  # 2/3 best moves
        assert result["best_moves"] == 2
        assert result["total_moves"] == 3

    def test_empty_games(self):
        result = _compute_accuracy([], {})
        assert result["overall_pct"] == 0


class TestComputeConsistency:
    def test_consistency_with_stable_play(self):
        games = [
            {"id": 1, "player_color": "white", "acpl": 50, "date_played": "2026-03-01", "result": "win"},
            {"id": 2, "player_color": "white", "acpl": 55, "date_played": "2026-03-02", "result": "loss"},
            {"id": 3, "player_color": "white", "acpl": 48, "date_played": "2026-03-03", "result": "win"},
        ]
        result = _compute_consistency(games, {})
        assert result["std_dev"] < 10  # Very low spread
        assert result["rating"] in ("Very consistent", "Consistent")
        assert result["best_acpl"] == 48
        assert result["worst_acpl"] == 55

    def test_consistency_with_variable_play(self):
        games = [
            {"id": 1, "player_color": "white", "acpl": 20, "date_played": "2026-03-01", "result": "win"},
            {"id": 2, "player_color": "white", "acpl": 200, "date_played": "2026-03-02", "result": "loss"},
            {"id": 3, "player_color": "white", "acpl": 50, "date_played": "2026-03-03", "result": "win"},
        ]
        result = _compute_consistency(games, {})
        assert result["std_dev"] > 30  # High spread
        assert result["rating"] in ("Variable", "Highly variable")

    def test_insufficient_data(self):
        games = [{"id": 1, "player_color": "white", "acpl": 50, "date_played": "2026-03-01", "result": "win"}]
        result = _compute_consistency(games, {})
        assert result["rating"] == "insufficient data"


class TestComputeDangerZones:
    def test_histogram_buckets(self):
        games = [{"id": 1, "player_color": "white"}]
        moves = {1: [
            {"side": "white", "move_number": 3, "classification": "excellent"},
            {"side": "white", "move_number": 5, "classification": "blunder"},
            {"side": "white", "move_number": 8, "classification": "mistake"},
            {"side": "white", "move_number": 12, "classification": "blunder"},
            {"side": "white", "move_number": 15, "classification": "blunder"},
        ]}
        result = _compute_danger_zones(games, moves)
        assert len(result["histogram"]) >= 2
        # Moves 1-5 should have 1 blunder
        first_bucket = result["histogram"][0]
        assert first_bucket["range"] == "1-5"
        assert first_bucket["blunders"] == 1

    def test_worst_zone(self):
        games = [{"id": 1, "player_color": "white"}]
        moves = {1: [
            {"side": "white", "move_number": 1, "classification": "excellent"},
            {"side": "white", "move_number": 2, "classification": "excellent"},
            {"side": "white", "move_number": 10, "classification": "blunder"},
        ]}
        result = _compute_danger_zones(games, moves)
        assert result["worst_zone"]["range"] == "6-10"


class TestComputeEndgameConversion:
    def test_winning_endgame_converted(self):
        games = [{"id": 1, "player_color": "white", "result": "win"}]
        moves = {1: [
            {"side": "white", "move_number": 30, "eval_before_cp": 300, "eval_after_cp": 280, "classification": "good"},
        ]}
        result = _compute_endgame_conversion(games, moves)
        assert result["winning_endgames"]["total"] == 1
        assert result["winning_endgames"]["converted"] == 1
        assert result["winning_endgames"]["conversion_rate"] == 100.0

    def test_game_not_reaching_endgame(self):
        games = [{"id": 1, "player_color": "white", "result": "win"}]
        moves = {1: [
            {"side": "white", "move_number": 15, "eval_before_cp": 100, "eval_after_cp": 80, "classification": "good"},
        ]}
        result = _compute_endgame_conversion(games, moves)
        assert result["games_reaching_endgame"] == 0


class TestComputeTimeControlPerformance:
    def test_multiple_time_controls(self):
        games = [
            {"id": 1, "player_color": "white", "time_class": "rapid", "result": "win", "acpl": 50},
            {"id": 2, "player_color": "white", "time_class": "rapid", "result": "loss", "acpl": 80},
            {"id": 3, "player_color": "white", "time_class": "blitz", "result": "win", "acpl": 100},
        ]
        moves = {
            1: [{"side": "white", "move_number": 1, "classification": "good",
                 "eval_before_cp": 20, "eval_after_cp": 10}],
            2: [{"side": "white", "move_number": 1, "classification": "blunder",
                 "eval_before_cp": 20, "eval_after_cp": -300}],
            3: [{"side": "white", "move_number": 1, "classification": "excellent",
                 "eval_before_cp": 20, "eval_after_cp": 20}],
        }
        result = _compute_time_control_performance(games, moves)
        assert "rapid" in result
        assert "blitz" in result
        assert result["rapid"]["games"] == 2
        assert result["rapid"]["win_rate"] == 50.0
        assert result["blitz"]["games"] == 1
        assert result["blitz"]["win_rate"] == 100.0
        assert result["rapid"]["acpl"] == 65.0  # (50+80)/2


class TestUpdatePatterns:
    def test_updates_all_players(self, db_path, populated_db):
        count = update_patterns(db_path=db_path)
        assert count == 1
