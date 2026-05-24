"""Tests for src/coach.py"""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.coach import (
    _build_analysis_text,
    _build_critical_moments,
    _fetch_coaching_history,
    _format_single_move,
    _parse_llm_response,
    coach_game,
    coach_pending,
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

    @patch("src.coach.call_provider")
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


class TestCoachingDiagnostics:
    """v1.6.0: Phase 2 diagnostics — log line + --dump-prompt + meta storage."""

    def test_estimate_tokens_roughly_chars_over_four(self):
        from src.coach import _estimate_tokens
        assert _estimate_tokens("") == 1
        assert _estimate_tokens("a" * 4) == 1
        assert _estimate_tokens("a" * 400) == 100
        # Token estimate is intentionally rough — within an order of
        # magnitude is all we need for context-window safety + logging
        assert _estimate_tokens("Hello world") > 0

    def test_count_history_games_handles_empty(self):
        from src.coach import _count_history_games
        assert _count_history_games("") == 0
        assert _count_history_games(None or "") == 0

    def test_count_history_games_counts_headings(self):
        from src.coach import _count_history_games
        sample = """
## Coaching History
### Game 1 (2026-04-01, white, loss)
- Key lesson: foo
### Game 2 (2026-04-02, black, win)
- Key lesson: bar
### Game 3 (2026-04-03, white, draw)
- Key lesson: baz
"""
        assert _count_history_games(sample) == 3

    @patch("src.coach.call_provider")
    def test_coaching_meta_persisted_to_db(self, mock_claude, db_path, game_with_analysis):
        """The coaching_meta_json column should be populated with history
        count, prompt tokens, provider, and model."""
        mock_claude.return_value = json.dumps({
            "narrative": "...", "key_lesson": "...", "practical_focus": "...",
            "critical_moments": [], "coach_notes": "...",
        })
        coach_game(game_with_analysis, provider="claude", db_path=db_path)

        conn = init_db(db_path)
        row = conn.execute(
            "SELECT coaching_meta_json FROM game_coaching WHERE game_id = ?",
            (game_with_analysis,),
        ).fetchone()
        conn.close()
        assert row["coaching_meta_json"], "meta should be populated"
        meta = json.loads(row["coaching_meta_json"])
        assert "history_games_injected" in meta
        assert "prompt_tokens_estimate" in meta
        assert meta["provider"] == "claude"
        assert meta["model"].startswith("claude-")  # whatever the current default is

    @patch("src.coach.call_provider")
    def test_dump_prompt_writes_file(self, mock_claude, tmp_path, db_path, game_with_analysis):
        """dump_prompt_to=<dir> writes one file per game with the full prompt."""
        mock_claude.return_value = json.dumps({
            "narrative": "...", "key_lesson": "...", "practical_focus": "...",
            "critical_moments": [], "coach_notes": "...",
        })
        dump_dir = tmp_path / "prompts"
        coach_game(
            game_with_analysis, provider="claude",
            db_path=db_path, dump_prompt_to=str(dump_dir),
        )
        # File should exist with the expected name pattern
        expected = dump_dir / f"prompt_game_{game_with_analysis}.txt"
        assert expected.exists(), f"expected prompt dump at {expected}"
        content = expected.read_text()
        # Prompt should at minimum contain the player name section and
        # the JSON-output instruction
        assert len(content) > 500  # non-trivial prompt size

    @patch("src.coach.call_provider")
    def test_coaching_response_includes_meta(self, mock_claude, db_path, game_with_analysis):
        """The returned coaching dict (used by API) should include meta."""
        mock_claude.return_value = json.dumps({
            "narrative": "...", "key_lesson": "...", "practical_focus": "...",
            "critical_moments": [], "coach_notes": "...",
        })
        result = coach_game(game_with_analysis, provider="claude", db_path=db_path)
        assert "meta" in result
        assert "history_games_injected" in result["meta"]


class TestBuildAnalysisTextTruncation:
    """Test smart truncation for long games."""

    def _make_moves(self, n, *, blunder_at=None):
        """Generate n half-moves of test data."""
        moves = []
        for i in range(n):
            move_num = (i // 2) + 1
            side = "white" if i % 2 == 0 else "black"
            cls = "excellent"
            swing = 2
            if blunder_at and i in blunder_at:
                cls = "blunder"
                swing = 400
            moves.append({
                "move_number": move_num, "side": side,
                "move_played": "e4", "best_move": "d4" if cls == "blunder" else "e4",
                "eval_before_cp": 20, "eval_after_cp": 20 - swing,
                "swing_cp": swing,
                "win_prob_before": 51.0, "win_prob_after": 51.0,
                "classification": cls,
            })
        return moves

    def test_short_game_returns_all(self):
        moves = self._make_moves(20)
        text = _build_analysis_text(moves)
        # Short game — no gap markers
        assert "omitted" not in text

    def test_long_game_includes_opening_and_blunders(self):
        moves = self._make_moves(100, blunder_at={70, 90})
        text = _build_analysis_text(moves)
        # Should have gap markers for omitted sections
        assert "omitted" in text
        # Blunders should still appear
        assert "??" in text

    def test_long_game_shows_gap_markers(self):
        moves = self._make_moves(100)
        text = _build_analysis_text(moves)
        assert "omitted" in text
        assert "Game summary" in text


class TestFormatSingleMove:
    def test_different_best_move_shown(self):
        move = {
            "move_number": 5, "side": "white", "move_played": "Bb5",
            "best_move": "d4", "eval_before_cp": 30, "eval_after_cp": -120,
            "swing_cp": 150, "win_prob_before": 53.2, "win_prob_after": 37.1,
            "classification": "mistake",
        }
        text = _format_single_move(move)
        assert "[best: d4]" in text
        assert "Bb5?" in text

    def test_same_best_move_not_shown(self):
        move = {
            "move_number": 1, "side": "white", "move_played": "e4",
            "best_move": "e4", "eval_before_cp": 20, "eval_after_cp": 15,
            "swing_cp": 5, "win_prob_before": 51.8, "win_prob_after": 51.4,
            "classification": "excellent",
        }
        text = _format_single_move(move)
        assert "[best:" not in text
        assert "e4!" in text


class TestCoachGameProviderSwitch:
    @patch("src.coach.call_provider")
    def test_claude_provider(self, mock_claude, db_path, game_with_analysis):
        mock_claude.return_value = json.dumps({
            "narrative": "n", "key_lesson": "k", "practical_focus": "p",
            "critical_moments": [], "coach_notes": "c",
        })
        coach_game(game_with_analysis, provider="claude", db_path=db_path)
        mock_claude.assert_called_once()

    @patch("src.coach.call_provider")
    def test_openai_provider(self, mock_openai, db_path, game_with_analysis):
        mock_openai.return_value = json.dumps({
            "narrative": "n", "key_lesson": "k", "practical_focus": "p",
            "critical_moments": [], "coach_notes": "c",
        })
        coach_game(game_with_analysis, provider="openai", db_path=db_path)
        mock_openai.assert_called_once()

    def test_unknown_provider_raises(self, db_path, game_with_analysis):
        with pytest.raises(ValueError, match="Unknown provider"):
            coach_game(game_with_analysis, provider="nonexistent_provider", db_path=db_path)


class TestCoachPendingLimit:
    @patch("src.coach.coach_game")
    def test_limit_respected(self, mock_coach, db_path):
        """coach_pending with limit=1 should only coach 1 game."""
        conn = init_db(db_path)
        pid = ensure_player(conn, "testplayer", display_name="T", age=9, rating=1000)
        for i in range(3):
            conn.execute(
                """INSERT INTO games
                (player_id, game_url, pgn, player_color, result,
                 analysis_status, coaching_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (pid, f"https://chess.com/game/{i+100}", "1. e4 *", "white",
                 "win", "complete", "pending"),
            )
        conn.commit()
        conn.close()

        mock_coach.return_value = {"narrative": "ok"}
        coach_pending(provider="claude", db_path=db_path, limit=1)
        assert mock_coach.call_count == 1


class TestCoachingHistoryDepth:
    """Tests for the configurable coaching_history_count setting (v1.3.0)."""

    def _seed_history(self, db_path, n_history_games: int):
        """Seed `n_history_games` already-coached games + 1 pending game.
        Returns (player_id, pending_game_id, conn). Caller closes conn.
        """
        conn = init_db(db_path)
        pid = ensure_player(conn, "histplayer", display_name="H", age=9, rating=1000)

        for i in range(n_history_games):
            conn.execute(
                """INSERT INTO games
                (player_id, game_url, pgn, player_color, result,
                 analysis_status, coaching_status, date_played)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (pid, f"https://chess.com/h/{i}", "1. e4 *", "white",
                 "win", "complete", "complete", f"2026-03-{i+1:02d}"),
            )
            gid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO game_coaching
                (game_id, provider, narrative, key_lesson, practical_focus, coach_notes)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (gid, "claude", f"narrative-{i}", f"lesson-{i}",
                 f"focus-{i}", f"notes-{i}"),
            )

        # One pending game (the one being coached now, excluded from history)
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, result,
             analysis_status, coaching_status, date_played)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, "https://chess.com/h/current", "1. e4 *", "white",
             "win", "complete", "pending", "2026-04-01"),
        )
        pending_gid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        return pid, pending_gid, conn

    def test_default_limit_is_5(self, db_path):
        """When no limit kwarg is passed, history fetch returns at most 5 games."""
        pid, pending_gid, conn = self._seed_history(db_path, 10)
        try:
            text = _fetch_coaching_history(conn, pid, pending_gid)
            # Default limit=5 → exactly 5 history blocks rendered
            assert text.count("### Game ") == 5
        finally:
            conn.close()

    def test_custom_limit_returns_more(self, db_path):
        """Passing limit=10 returns 10 history games."""
        pid, pending_gid, conn = self._seed_history(db_path, 12)
        try:
            text = _fetch_coaching_history(conn, pid, pending_gid, limit=10)
            assert text.count("### Game ") == 10
        finally:
            conn.close()

    def test_limit_caps_at_available_games(self, db_path):
        """If only 3 history games exist but limit=10, return all 3."""
        pid, pending_gid, conn = self._seed_history(db_path, 3)
        try:
            text = _fetch_coaching_history(conn, pid, pending_gid, limit=10)
            assert text.count("### Game ") == 3
        finally:
            conn.close()

    def test_excludes_current_game(self, db_path):
        """The pending (currently-being-coached) game must not appear in history."""
        pid, pending_gid, conn = self._seed_history(db_path, 3)
        try:
            text = _fetch_coaching_history(conn, pid, pending_gid, limit=10)
            assert f"chess.com/h/current" not in text
        finally:
            conn.close()

    def test_coach_game_wires_history_count_from_config(self):
        """coach_game must read coaching_history_count from config and pass
        it as limit= to _fetch_coaching_history. Guards against accidental
        removal of the config plumbing."""
        from src import coach as coach_mod
        import inspect

        source = inspect.getsource(coach_mod.coach_game)
        assert "coaching_history_count" in source, \
            "coach_game must read coaching_history_count from config"
        assert "limit=history_count" in source, \
            "coach_game must pass history_count as limit= to _fetch_coaching_history"

    def test_history_count_clamps_to_valid_range(self):
        """Out-of-range or invalid values in config should be clamped to 1-20."""
        from src import coach as coach_mod
        import inspect

        source = inspect.getsource(coach_mod.coach_game)
        assert "max(1, min(20" in source, \
            "coach_game must clamp coaching_history_count to [1, 20]"
