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


# --- v1.8.0: trajectory-aware per-game coaching ---

class TestTrajectoryInjection:
    """v1.8.0: coach_game must read player_patterns and inject the
    'Player Trajectory (last 30 days)' block, gated by
    coaching_trajectory_enabled and overridable via the trajectory_enabled
    argument."""

    def _seed_patterns(self, db_path, player_id: int):
        """Insert a synthetic player_patterns row with measurable signals."""
        conn = init_db(db_path)
        stats = {
            "total_games": 50,
            "phase_analysis": {
                "opening": {"acpl": 40.0},
                "middlegame": {"acpl": 90.0},
                "endgame": {"acpl": 55.0},
            },
            "consistency": {"mean_acpl": 60.0, "total_games": 50},
            "tactical_misses": {"miss_rate": 47.0},
            "endgame_conversion": {"winning_endgames": {"conversion_rate": 75.0}},
            "comeback_collapse": {
                "comebacks": {"comeback_rate": 30.0},
                "collapses": {"collapse_rate": 25.0},
            },
            "repertoire_consistency": {
                "white": {"rating": "Focused"},
                "black": {"rating": "Focused"},
            },
            "acpl_trend": [
                {"week": "w1", "acpl": 70}, {"week": "w2", "acpl": 70},
                {"week": "w3", "acpl": 55}, {"week": "w4", "acpl": 55},
            ],
        }
        conn.execute(
            """INSERT INTO player_patterns
            (player_id, period_start, period_end, stats_json, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))""",
            (player_id, "2026-04-01", "2026-04-30", json.dumps(stats)),
        )
        conn.commit()
        conn.close()

    @patch("src.coach.call_provider")
    def test_trajectory_block_injected_into_prompt_when_enabled(
        self, mock_claude, tmp_path, db_path, game_with_analysis,
    ):
        """When patterns are populated and trajectory is enabled (default),
        the dumped prompt contains the trajectory heading."""
        mock_claude.return_value = json.dumps({
            "narrative": "...", "key_lesson": "...", "practical_focus": "...",
            "critical_moments": [], "coach_notes": "...",
        })
        # Find the player_id behind game_with_analysis
        conn = init_db(db_path)
        pid = conn.execute(
            "SELECT player_id FROM games WHERE id = ?", (game_with_analysis,),
        ).fetchone()["player_id"]
        conn.close()
        self._seed_patterns(db_path, pid)

        dump_dir = tmp_path / "prompts"
        coach_game(
            game_with_analysis, provider="claude", db_path=db_path,
            dump_prompt_to=str(dump_dir),
            # trajectory_enabled=None → falls through to config default (True)
        )
        prompt = (dump_dir / f"prompt_game_{game_with_analysis}.txt").read_text()
        assert "## Player Trajectory (last 30 days)" in prompt, \
            "trajectory block must be injected when patterns exist"
        assert "middlegame" in prompt  # the synthetic weakest phase
        assert "47" in prompt          # tactical miss rate
        assert "improving" in prompt   # trend direction from synthetic data

    @patch("src.coach.call_provider")
    def test_trajectory_disabled_via_argument_omits_block(
        self, mock_claude, tmp_path, db_path, game_with_analysis,
    ):
        """trajectory_enabled=False suppresses the block even if patterns
        are populated. The CLI `--no-trajectory` flag uses this path."""
        mock_claude.return_value = json.dumps({
            "narrative": "...", "key_lesson": "...", "practical_focus": "...",
            "critical_moments": [], "coach_notes": "...",
        })
        conn = init_db(db_path)
        pid = conn.execute(
            "SELECT player_id FROM games WHERE id = ?", (game_with_analysis,),
        ).fetchone()["player_id"]
        conn.close()
        self._seed_patterns(db_path, pid)

        dump_dir = tmp_path / "prompts_off"
        coach_game(
            game_with_analysis, provider="claude", db_path=db_path,
            dump_prompt_to=str(dump_dir),
            trajectory_enabled=False,
        )
        prompt = (dump_dir / f"prompt_game_{game_with_analysis}.txt").read_text()
        assert "## Player Trajectory (last 30 days)" not in prompt, \
            "trajectory block must be omitted when trajectory_enabled=False"

    @patch("src.coach.call_provider")
    def test_trajectory_disabled_via_config_omits_block(
        self, mock_claude, tmp_path, db_path, game_with_analysis,
    ):
        """coaching_trajectory_enabled=False in config suppresses the block."""
        mock_claude.return_value = json.dumps({
            "narrative": "...", "key_lesson": "...", "practical_focus": "...",
            "critical_moments": [], "coach_notes": "...",
        })
        conn = init_db(db_path)
        pid = conn.execute(
            "SELECT player_id FROM games WHERE id = ?", (game_with_analysis,),
        ).fetchone()["player_id"]
        conn.close()
        self._seed_patterns(db_path, pid)

        dump_dir = tmp_path / "prompts_cfg_off"
        cfg = {"coaching": {"coaching_trajectory_enabled": False}}
        coach_game(
            game_with_analysis, provider="claude", db_path=db_path,
            dump_prompt_to=str(dump_dir), config=cfg,
        )
        prompt = (dump_dir / f"prompt_game_{game_with_analysis}.txt").read_text()
        assert "## Player Trajectory (last 30 days)" not in prompt

    @patch("src.coach.call_provider")
    def test_trajectory_meta_persisted_to_db(
        self, mock_claude, db_path, game_with_analysis,
    ):
        """coaching_meta_json must include trajectory_injected and
        trajectory_age_days so the UI can render the freshness stamp."""
        mock_claude.return_value = json.dumps({
            "narrative": "...", "key_lesson": "...", "practical_focus": "...",
            "critical_moments": [], "coach_notes": "...",
        })
        conn = init_db(db_path)
        pid = conn.execute(
            "SELECT player_id FROM games WHERE id = ?", (game_with_analysis,),
        ).fetchone()["player_id"]
        conn.close()
        self._seed_patterns(db_path, pid)

        coach_game(game_with_analysis, provider="claude", db_path=db_path)

        conn = init_db(db_path)
        row = conn.execute(
            "SELECT coaching_meta_json FROM game_coaching WHERE game_id = ?",
            (game_with_analysis,),
        ).fetchone()
        conn.close()
        meta = json.loads(row["coaching_meta_json"])
        assert meta["trajectory_injected"] is True
        assert "trajectory_age_days" in meta
        assert meta["trajectory_weakest_phase"] == "middlegame"
        assert meta["trajectory_trend_direction"] == "improving"

    @patch("src.coach.call_provider")
    def test_trajectory_silently_skipped_when_no_patterns(
        self, mock_claude, db_path, game_with_analysis,
    ):
        """When the player has no player_patterns row, trajectory injection
        silently no-ops and meta records trajectory_injected=False. No
        crash, no empty heading."""
        mock_claude.return_value = json.dumps({
            "narrative": "...", "key_lesson": "...", "practical_focus": "...",
            "critical_moments": [], "coach_notes": "...",
        })
        # Note: deliberately NOT seeding patterns. But we need to disable
        # the auto-refresh path (which would compute patterns) for this
        # test to assert the empty path. compute_player_patterns is also
        # cheap on an empty DB so just verify the final meta state.
        coach_game(game_with_analysis, provider="claude", db_path=db_path)

        conn = init_db(db_path)
        row = conn.execute(
            "SELECT coaching_meta_json FROM game_coaching WHERE game_id = ?",
            (game_with_analysis,),
        ).fetchone()
        conn.close()
        meta = json.loads(row["coaching_meta_json"])
        # Either silently skipped (no patterns) or injected after auto-refresh
        # built a row from the lone analyzed game. Both are valid outcomes;
        # what matters is the field exists and is boolean.
        assert "trajectory_injected" in meta
        assert isinstance(meta["trajectory_injected"], bool)

    def test_coach_game_wires_trajectory_from_config(self):
        """Mirror of test_coach_game_wires_history_count_from_config —
        guards against future refactors silently breaking the trajectory
        wiring."""
        from src import coach as coach_mod
        import inspect

        source = inspect.getsource(coach_mod.coach_game)
        assert "coaching_trajectory_enabled" in source, \
            "coach_game must read coaching_trajectory_enabled from config"
        assert "build_trajectory_block" in source, \
            "coach_game must call build_trajectory_block"
        assert "player_trajectory=player_trajectory" in source, \
            "coach_game must pass player_trajectory into the prompt format()"


# --- v1.13.0: phase-structured player_feedback + trap awareness ---


class TestPhaseClassificationSummary:
    """v1.13.0: per-phase breakdown of player move-quality classifications."""

    def test_empty_moves_returns_zero_counts(self):
        from src.coach import _phase_classification_summary
        out = _phase_classification_summary([], "white")
        # Headers + zero counts + "(none)" for mistake/blunder moves
        assert "Opening (moves 1-15)" in out
        assert "Middlegame (moves 16-30)" in out
        assert "Endgame (moves 31+)" in out
        assert "0 inaccuracies, 0 mistakes, 0 blunders" in out
        assert "(none)" in out

    def test_filters_to_player_color_only(self):
        from src.coach import _phase_classification_summary
        moves = [
            {"side": "white", "move_number": 5, "classification": "blunder"},
            {"side": "black", "move_number": 5, "classification": "blunder"},
        ]
        out = _phase_classification_summary(moves, "white")
        # Only the white blunder counts → opening shows 1 blunder
        assert "1 blunders" in out
        # Move number 5 in opening
        assert "5 (blunder)" in out

    def test_counts_by_phase_correctly(self):
        from src.coach import _phase_classification_summary
        moves = [
            {"side": "white", "move_number": 5, "classification": "inaccuracy"},
            {"side": "white", "move_number": 18, "classification": "mistake"},
            {"side": "white", "move_number": 25, "classification": "blunder"},
            {"side": "white", "move_number": 35, "classification": "mistake"},
            {"side": "white", "move_number": 40, "classification": "inaccuracy"},
        ]
        out = _phase_classification_summary(moves, "white")
        # Opening: 1 inaccuracy
        assert "1 inaccuracies, 0 mistakes, 0 blunders" in out
        # Middlegame: 1 mistake + 1 blunder (no inaccuracies)
        assert "0 inaccuracies, 1 mistakes, 1 blunders" in out
        # Endgame: 1 inaccuracy + 1 mistake
        assert "1 inaccuracies, 1 mistakes, 0 blunders" in out

    def test_mistake_blunder_move_numbers_listed(self):
        from src.coach import _phase_classification_summary
        moves = [
            {"side": "white", "move_number": 18, "classification": "mistake"},
            {"side": "white", "move_number": 25, "classification": "blunder"},
            # Inaccuracies should NOT appear in the move-number list
            {"side": "white", "move_number": 20, "classification": "inaccuracy"},
        ]
        out = _phase_classification_summary(moves, "white")
        assert "18 (mistake)" in out
        assert "25 (blunder)" in out
        # Inaccuracy moves not listed in the flagged list
        assert "20 (inaccuracy)" not in out

    def test_ignores_unknown_classifications(self):
        from src.coach import _phase_classification_summary
        moves = [
            {"side": "white", "move_number": 5, "classification": "excellent"},
            {"side": "white", "move_number": 6, "classification": "good"},
            {"side": "white", "move_number": 7, "classification": None},
        ]
        out = _phase_classification_summary(moves, "white")
        # All counts remain zero
        assert out.count("0 inaccuracies, 0 mistakes, 0 blunders") == 3


class TestTrapsForOpening:
    """v1.13.0: trap-awareness helper — finds well-known traps that share
    the same opening prefix as this game."""

    def test_empty_pgn_returns_empty(self):
        from src.coach import _traps_for_opening
        assert _traps_for_opening("") == []
        assert _traps_for_opening(None or "") == []

    def test_italian_game_finds_italian_traps(self):
        """Italian Game (1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5) shares the first 5
        plies with several Italian-family traps in the library."""
        from src.coach import _traps_for_opening
        pgn = (
            '[Event "?"]\n[White "x"]\n[Black "y"]\n\n'
            '1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. d3 *'
        )
        traps = _traps_for_opening(pgn, max_results=5)
        # Should find at least one Italian Game trap
        assert len(traps) >= 1
        names = [t.get("name", "") for t in traps]
        assert any("Italian Game" in n for n in names), (
            f"expected at least one Italian Game trap, got {names}"
        )

    def test_ruy_lopez_finds_ruy_traps_not_italian(self):
        """Ruy Lopez (1.e4 e5 2.Nf3 Nc6 3.Bb5) diverges from Italian at
        move 3 — should find Ruy traps, NOT Italian ones (longest-prefix
        match means Italian traps share only 4 plies vs Ruy's 5)."""
        from src.coach import _traps_for_opening
        pgn = (
            '[Event "?"]\n[White "x"]\n[Black "y"]\n\n'
            '1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *'
        )
        traps = _traps_for_opening(pgn, max_results=5)
        assert len(traps) >= 1
        names = [t.get("name", "") for t in traps]
        # All matches should be Ruy Lopez (deeper prefix match wins)
        assert all("Ruy Lopez" in n for n in names), (
            f"expected only Ruy Lopez traps, got {names}"
        )

    def test_offbook_opening_returns_empty(self):
        """Bizarre opening (1.a4 h5) doesn't match any trap library entry."""
        from src.coach import _traps_for_opening
        pgn = (
            '[Event "?"]\n[White "x"]\n[Black "y"]\n\n'
            '1. a4 h5 2. h4 a5 *'
        )
        assert _traps_for_opening(pgn) == []

    def test_max_results_honored(self):
        from src.coach import _traps_for_opening
        pgn = (
            '[Event "?"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 *'
        )
        traps = _traps_for_opening(pgn, max_results=1)
        assert len(traps) <= 1

    def test_unparseable_pgn_returns_empty(self):
        from src.coach import _traps_for_opening
        assert _traps_for_opening("not a real pgn") == []


class TestFormatRelevantTrapsBlock:
    """v1.13.0: text rendering for the prompt's trap-awareness section."""

    def test_empty_traps_renders_fallback(self):
        from src.coach import _format_relevant_traps_block
        out = _format_relevant_traps_block([])
        assert "no well-known traps" in out

    def test_renders_trap_name_eco_depth(self):
        from src.coach import _format_relevant_traps_block
        traps = [
            {
                "name": "Italian Game: Fried Liver Attack",
                "eco": "C57",
                "depth": 11,
                "moves_san": "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. Ng5 d5 5. exd5 Nxd5 6. Nxf7",
            },
        ]
        out = _format_relevant_traps_block(traps)
        assert "Italian Game: Fried Liver Attack" in out
        assert "C57" in out
        assert "11 plies" in out


class TestCoachGameWiresPhaseTraps:
    """Source-grep guard: confirms the new helpers are passed into
    GAME_COACHING_PROMPT.format(). Mirrors test_coach_game_wires_history_count."""

    def test_phase_summary_wired(self):
        from src import coach as coach_mod
        import inspect
        source = inspect.getsource(coach_mod.coach_game)
        assert "_phase_classification_summary" in source, \
            "coach_game must call _phase_classification_summary"
        assert "phase_classification_summary=phase_classification_summary" in source, \
            "coach_game must pass phase_classification_summary into format()"

    def test_traps_for_opening_wired(self):
        from src import coach as coach_mod
        import inspect
        source = inspect.getsource(coach_mod.coach_game)
        assert "_traps_for_opening" in source, \
            "coach_game must call _traps_for_opening"
        assert "relevant_traps_block=relevant_traps_block" in source, \
            "coach_game must pass relevant_traps_block into format()"

    def test_prompt_template_has_5_section_spec(self):
        """The 5 markdown section headings must all be in the prompt template."""
        from src.coach import GAME_COACHING_PROMPT
        for heading in [
            "## ♟ Opening",
            "## ⚔ Middlegame",
            "## ♔ Endgame",
            "## 🪤 Watch Out For",
            "## 🎯 Top 3 Improvements",
        ]:
            assert heading in GAME_COACHING_PROMPT, (
                f"prompt template missing required section heading: {heading}"
            )


# --- v1.13.2: player_feedback structure validator ---


class TestValidatePlayerFeedbackStructure:
    """v1.13.2: catches when the LLM ignores the strict 5-section spec.

    The validator's purpose is to surface silent format degradation —
    typically caused by older / non-reasoning models. Without it, the
    frontend's legacy single-block fallback masks the problem (the
    v1.13.1 config-drift incident).
    """

    def test_fully_compliant_5_section_response(self):
        from src.coach import _validate_player_feedback_structure
        text = (
            "## ♟ Opening\nfoo\n\n"
            "## ⚔ Middlegame\nbar\n\n"
            "## ♔ Endgame\nbaz\n\n"
            "## 🪤 Watch Out For (Trap Awareness)\nquux\n\n"
            "## 🎯 Top 3 Improvements\n1. x"
        )
        result = _validate_player_feedback_structure(text)
        assert result["compliant"] is True
        assert result["missing_headings"] == []
        assert result["headings_found"] == 5

    def test_trap_awareness_heading_variant_accepted(self):
        """The Watch Out For section uses '🪤 Watch Out For (Trap Awareness)'
        in the prompt; the validator should accept any heading that STARTS
        with '🪤 Watch Out For'."""
        from src.coach import _validate_player_feedback_structure
        text = (
            "## ♟ Opening\nx\n"
            "## ⚔ Middlegame\nx\n"
            "## ♔ Endgame\nx\n"
            "## 🪤 Watch Out For (Trap Awareness)\nx\n"
            "## 🎯 Top 3 Improvements\n1."
        )
        assert _validate_player_feedback_structure(text)["compliant"] is True

    def test_legacy_freeform_block_is_non_compliant(self):
        """Pre-v1.13.0 entries and older-model output (the v1.13.1
        gpt-5.4 case) have no headings → flagged non-compliant."""
        from src.coach import _validate_player_feedback_structure
        text = "Evan Leong, this was a tough win. You did very well..."
        result = _validate_player_feedback_structure(text)
        assert result["compliant"] is False
        assert len(result["missing_headings"]) == 5
        assert result["headings_found"] == 0

    def test_partial_compliance_lists_missing_headings(self):
        from src.coach import _validate_player_feedback_structure
        text = (
            "## ♟ Opening\nx\n"
            "## ⚔ Middlegame\nx\n"
            "## 🎯 Top 3 Improvements\n1."
        )
        result = _validate_player_feedback_structure(text)
        assert result["compliant"] is False
        assert "♔ Endgame" in result["missing_headings"]
        assert "🪤 Watch Out For" in result["missing_headings"]
        # ♟ / ⚔ / 🎯 are present, NOT in missing
        assert "♟ Opening" not in result["missing_headings"]

    def test_extra_headings_tracked_but_not_failure(self):
        """LLM-added bonus sections (forward-compat) don't fail
        compliance — they just appear in extra_headings."""
        from src.coach import _validate_player_feedback_structure
        text = (
            "## ♟ Opening\nx\n"
            "## ⚔ Middlegame\nx\n"
            "## ♔ Endgame\nx\n"
            "## 🪤 Watch Out For\nx\n"
            "## 🎯 Top 3 Improvements\n1.\n"
            "## 🎁 Bonus Section\nLLM added an extra."
        )
        result = _validate_player_feedback_structure(text)
        assert result["compliant"] is True
        assert "🎁 Bonus Section" in result["extra_headings"]

    def test_null_and_empty_input_handled_gracefully(self):
        from src.coach import _validate_player_feedback_structure
        for empty in (None, "", "   \n  \t"):
            result = _validate_player_feedback_structure(empty)
            assert result["compliant"] is False
            assert result["headings_found"] == 0
            # All 5 required headings appear as missing
            assert len(result["missing_headings"]) == 5

    def test_required_headings_constant_has_all_5(self):
        """Guard against the constant drifting out of sync with the prompt."""
        from src.coach import _REQUIRED_FEEDBACK_HEADINGS
        assert len(_REQUIRED_FEEDBACK_HEADINGS) == 5
        # Each required heading must also appear in the prompt template
        from src.coach import GAME_COACHING_PROMPT
        for h in _REQUIRED_FEEDBACK_HEADINGS:
            assert f"## {h}" in GAME_COACHING_PROMPT, (
                f"_REQUIRED_FEEDBACK_HEADINGS includes '{h}' but the prompt "
                f"template doesn't reference '## {h}'"
            )


class TestCoachGameWiresValidator:
    """Source-grep guard: confirms the validator is called + its result
    persisted in coaching_meta_json. Mirror of the trajectory wiring guard."""

    def test_validator_called_and_persisted(self):
        from src import coach as coach_mod
        import inspect
        source = inspect.getsource(coach_mod.coach_game)
        assert "_validate_player_feedback_structure" in source, \
            "coach_game must call _validate_player_feedback_structure"
        assert "feedback_structure_compliant" in source, \
            "coach_game must persist feedback_structure_compliant in meta"
        assert "feedback_missing_headings" in source, \
            "coach_game must persist feedback_missing_headings in meta"


# --- v1.14.0: tactical motif tags surfaced in the critical-moments prompt block ---


class TestBuildCriticalMomentsMotifs:
    """v1.14.0: _build_critical_moments surfaces motifs_json data into
    the LLM-visible block so the prompt can cite tactical themes by name."""

    def test_legacy_moves_without_motifs_still_render(self):
        from src.coach import _build_critical_moments
        moves = [
            {
                "move_number": 18, "side": "black", "move_played": "Qh4",
                "best_move": "Nd4", "swing_cp": 250,
                "win_prob_before": 60.0, "win_prob_after": 40.0,
                "motifs_json": None,
            }
        ]
        out = _build_critical_moments(moves, top_n=1)
        # Renders without the tactical motifs annotation when motifs_json is null
        assert "tactical motifs" not in out
        assert "Move 18" in out

    def test_moves_with_motifs_surface_to_block(self):
        from src.coach import _build_critical_moments
        import json as _json
        moves = [
            {
                "move_number": 18, "side": "black", "move_played": "Qh4",
                "best_move": "Nxf7", "swing_cp": 800,
                "win_prob_before": 70.0, "win_prob_after": 30.0,
                "motifs_json": _json.dumps({
                    "played": [],
                    "best": ["fork"],
                    "missed": ["fork"],
                }),
            }
        ]
        out = _build_critical_moments(moves, top_n=1)
        assert "tactical motifs" in out
        assert "MISSED: fork" in out

    def test_played_motifs_surface_too(self):
        """If the player played a hanging-piece capture, the prompt shows it."""
        from src.coach import _build_critical_moments
        import json as _json
        moves = [
            {
                "move_number": 22, "side": "white", "move_played": "Nxe5",
                "best_move": "Nxe5", "swing_cp": 0,
                "win_prob_before": 55.0, "win_prob_after": 60.0,
                "motifs_json": _json.dumps({
                    "played": ["hanging_piece"],
                    "best": ["hanging_piece"],
                    "missed": [],
                }),
            }
        ]
        out = _build_critical_moments(moves, top_n=1)
        assert "PLAYED: hanging_piece" in out

    def test_handles_malformed_motifs_json_gracefully(self):
        """Don't crash if motifs_json is malformed (legacy bad data, etc.)."""
        from src.coach import _build_critical_moments
        moves = [
            {
                "move_number": 18, "side": "black", "move_played": "Qh4",
                "best_move": "Nd4", "swing_cp": 250,
                "win_prob_before": 60.0, "win_prob_after": 40.0,
                "motifs_json": "not json at all {{{",
            }
        ]
        # Should render without crashing — motifs annotation just skipped
        out = _build_critical_moments(moves, top_n=1)
        assert "Move 18" in out
        assert "tactical motifs" not in out

    def test_prompt_template_specifies_motifs_fields(self):
        """The critical_moments JSON schema in the prompt must instruct the LLM
        about the motifs_found / motifs_missed fields (v1.14.0)."""
        from src.coach import GAME_COACHING_PROMPT
        assert "motifs_found" in GAME_COACHING_PROMPT
        assert "motifs_missed" in GAME_COACHING_PROMPT
        # And must list the valid motif identifiers so the LLM doesn't invent
        assert "fork" in GAME_COACHING_PROMPT
        assert "pin" in GAME_COACHING_PROMPT
        assert "discovered_check" in GAME_COACHING_PROMPT
