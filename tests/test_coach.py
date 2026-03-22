"""Tests for src/coach.py"""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.coach import (
    _build_analysis_text,
    _build_critical_moments,
    _parse_llm_response,
    coach_game,
)
from src.models import init_db, ensure_player


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def game_with_analysis(db_path):
    """Create a game with move analysis in the test DB."""
    conn = init_db(db_path)
    pid = ensure_player(conn, "testplayer", display_name="TestKid", age=9, rating=1050)

    conn.execute(
        """INSERT INTO games
        (player_id, game_url, pgn, player_color, player_rating,
         opponent_rating, result, time_control, time_class, date_played,
         analysis_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (pid, "https://chess.com/game/1",
         '[White "testplayer"]\n[Black "opp"]\n\n1. e4 e5 2. Nf3 Nc6 *',
         "white", 1050, 980, "win", "600", "rapid", "2026-03-01", "complete"),
    )
    game_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Add some move analysis
    moves = [
        (game_id, 1, "white", "e4", "e4", 20, 15, 5, 51.8, 51.4, "excellent", "e4 e5 Nf3"),
        (game_id, 1, "black", "e5", "e5", 15, 20, 5, 51.4, 51.8, "excellent", "e5 Nf3 Nc6"),
        (game_id, 2, "white", "Nf3", "Nf3", 20, 18, 2, 51.8, 51.6, "excellent", "Nf3 Nc6"),
        (game_id, 2, "black", "Nc6", "Nc6", 18, 20, 2, 51.6, 51.8, "excellent", "Nc6 d4"),
    ]
    for m in moves:
        conn.execute(
            """INSERT INTO move_analysis
            (game_id, move_number, side, move_played, best_move,
             eval_before_cp, eval_after_cp, swing_cp,
             win_prob_before, win_prob_after, classification, pv_line)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            m,
        )
    conn.commit()
    conn.close()
    return game_id


SAMPLE_MOVES = [
    {"move_number": 1, "side": "white", "move_played": "e4", "best_move": "e4",
     "eval_before_cp": 20, "eval_after_cp": 15, "swing_cp": 5,
     "win_prob_before": 51.8, "win_prob_after": 51.4, "classification": "excellent"},
    {"move_number": 5, "side": "white", "move_played": "Bb5", "best_move": "d4",
     "eval_before_cp": 30, "eval_after_cp": -120, "swing_cp": 150,
     "win_prob_before": 53.2, "win_prob_after": 37.1, "classification": "mistake"},
    {"move_number": 10, "side": "white", "move_played": "Qh4", "best_move": "Nf3",
     "eval_before_cp": 50, "eval_after_cp": -350, "swing_cp": 400,
     "win_prob_before": 55.5, "win_prob_after": 20.3, "classification": "blunder"},
]


class TestBuildAnalysisText:
    def test_formats_moves(self):
        text = _build_analysis_text(SAMPLE_MOVES)
        assert "1. e4!" in text
        assert "5. Bb5?" in text
        assert "[best: d4]" in text

    def test_blunder_shows_double_question(self):
        text = _build_analysis_text(SAMPLE_MOVES)
        assert "10. Qh4??" in text


class TestBuildCriticalMoments:
    def test_sorts_by_swing(self):
        text = _build_critical_moments(SAMPLE_MOVES, top_n=2)
        lines = text.strip().split("\n")
        assert len(lines) == 2
        assert "Move 10" in lines[0]  # Biggest swing first
        assert "Move 5" in lines[1]


class TestParseLlmResponse:
    def test_parses_clean_json(self):
        data = {"narrative": "Great game!", "key_lesson": "Check before moving"}
        result = _parse_llm_response(json.dumps(data))
        assert result["narrative"] == "Great game!"

    def test_handles_code_fences(self):
        data = {"key_lesson": "Look before you leap"}
        text = f"```json\n{json.dumps(data)}\n```"
        result = _parse_llm_response(text)
        assert result["key_lesson"] == "Look before you leap"

    def test_raises_on_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_response("not json at all")


class TestCoachGame:
    def test_raises_on_missing_game(self, db_path):
        init_db(db_path)
        with pytest.raises(ValueError, match="not found"):
            coach_game(999, db_path=db_path)

    def test_raises_on_unanalyzed_game(self, db_path):
        conn = init_db(db_path)
        pid = ensure_player(conn, "testplayer")
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, result, analysis_status)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (pid, "https://chess.com/game/2", "1. e4 *", "white", "win", "pending"),
        )
        conn.commit()
        gid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        with pytest.raises(ValueError, match="not yet analyzed"):
            coach_game(gid, db_path=db_path)

    @patch("src.coach._call_claude")
    def test_stores_coaching_in_db(self, mock_claude, db_path, game_with_analysis):
        mock_claude.return_value = json.dumps({
            "narrative": "You played a great opening!",
            "key_lesson": "Keep developing pieces early.",
            "practical_focus": "Try to get all your pieces out before move 10.",
            "critical_moments": [
                {"move_number": 1, "side": "white", "what_happened": "Solid start",
                 "what_was_better": "Nothing — great move!", "move_played": "e4",
                 "best_move": "e4"}
            ],
            "coach_notes": "Clean Italian Game opening. Needs work on middlegame planning.",
        })

        result = coach_game(game_with_analysis, provider="claude", db_path=db_path)
        assert result["narrative"] == "You played a great opening!"
        assert result["key_lesson"] == "Keep developing pieces early."

        # Verify stored in DB
        conn = init_db(db_path)
        coaching = conn.execute(
            "SELECT * FROM game_coaching WHERE game_id = ?",
            (game_with_analysis,),
        ).fetchone()
        assert coaching["provider"].startswith("claude:")
        assert "great opening" in coaching["narrative"]

        game = conn.execute(
            "SELECT coaching_status FROM games WHERE id = ?",
            (game_with_analysis,),
        ).fetchone()
        assert game["coaching_status"] == "complete"
        conn.close()
