# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Tests for pipeline scheduler (run_full_pipeline)."""

import threading
from unittest.mock import patch, MagicMock, call

import pytest

from src.scheduler import run_full_pipeline


# ── Helpers ──────────────────────────────────────────────

def _make_config(sf_path="/usr/bin/stockfish"):
    """Create a minimal config dict for testing."""
    return {
        "stockfish": {"path": sf_path, "depth": 22, "threads": 6, "hash_mb": 512},
        "analysis": {"months_lookback": 6},
        "coaching": {"default_provider": "claude"},
    }


def _make_mock_conn(players):
    """Create a mock connection that handles all queries from run_full_pipeline.

    The connection must handle:
    1. SELECT * FROM players ... → returns player dicts
    2. SELECT COUNT(*) as c FROM games ... → returns {"c": 0}
    3. SELECT id, username, display_name FROM players ... → returns player rows
    """
    mock_conn = MagicMock()

    # Track calls to route different queries
    call_count = {"n": 0}

    def smart_execute(sql, *args):
        call_count["n"] += 1
        result = MagicMock()

        if "COUNT(*)" in sql:
            row = {"c": 0}
            result.fetchone.return_value = row
        elif "SELECT *" in sql or "SELECT id, username, display_name" in sql:
            result.fetchall.return_value = players
        else:
            result.fetchall.return_value = []
            result.fetchone.return_value = None

        return result

    mock_conn.execute.side_effect = smart_execute
    return mock_conn


# ── Tests ────────────────────────────────────────────────


class TestRunFullPipeline:
    """Verify the 4-step pipeline: harvest → analyze → patterns → coach."""

    @patch("src.coach.coach_pending")
    @patch("src.patterns.compute_player_patterns")
    @patch("src.analyzer.analyze_pending")
    @patch("src.harvester.harvest_player")
    @patch("src.llm_providers.resolve_model")
    @patch("src.scheduler.pipeline_state")
    @patch("src.scheduler.get_connection")
    @patch("src.scheduler.Path")
    def test_calls_all_four_steps(
        self, mock_path, mock_get_conn, mock_state, mock_resolve,
        mock_harvest, mock_analyze, mock_patterns, mock_coach,
    ):
        # Setup
        mock_path.return_value.is_file.return_value = True
        player = {"username": "testplayer", "display_name": "Test", "id": 1,
                  "lichess_username": None}
        mock_get_conn.return_value = _make_mock_conn([player])

        mock_harvest.return_value = {"new": 3, "errors": 0}
        mock_analyze.return_value = 3
        mock_resolve.return_value = "claude-opus-4-6"
        mock_coach.return_value = {"coached": 2, "errors": 0, "skipped": 1}

        config = _make_config()
        result = run_full_pipeline(config, "test.db")

        # Verify all steps called
        mock_harvest.assert_called_once()
        mock_analyze.assert_called_once()
        mock_patterns.assert_called()
        mock_coach.assert_called_once()

        # Verify result dict
        assert result["new_games"] == 3
        assert result["games_analyzed"] == 3
        assert result["coached"] == 2
        assert result["skipped"] == 1
        assert "errors" in result

    @patch("src.coach.coach_pending")
    @patch("src.patterns.compute_player_patterns")
    @patch("src.analyzer.analyze_pending")
    @patch("src.harvester.harvest_player")
    @patch("src.llm_providers.resolve_model")
    @patch("src.scheduler.pipeline_state")
    @patch("src.scheduler.get_connection")
    @patch("src.scheduler.Path")
    def test_player_filter_passed_through(
        self, mock_path, mock_get_conn, mock_state, mock_resolve,
        mock_harvest, mock_analyze, mock_patterns, mock_coach,
    ):
        mock_path.return_value.is_file.return_value = True
        player = {"username": "evan", "display_name": "Evan", "id": 1,
                  "lichess_username": None}
        mock_get_conn.return_value = _make_mock_conn([player])

        mock_harvest.return_value = {"new": 0, "errors": 0}
        mock_analyze.return_value = 0
        mock_resolve.return_value = "claude-opus-4-6"
        mock_coach.return_value = {"coached": 0, "errors": 0, "skipped": 0}

        run_full_pipeline(_make_config(), "test.db", player_filter="evan")

        # Verify player filter passed to coach
        _, kwargs = mock_coach.call_args
        assert kwargs.get("player") == "evan"

    @patch("src.coach.coach_pending")
    @patch("src.patterns.compute_player_patterns")
    @patch("src.analyzer.analyze_pending")
    @patch("src.harvester.harvest_player")
    @patch("src.llm_providers.resolve_model")
    @patch("src.scheduler.pipeline_state")
    @patch("src.scheduler.get_connection")
    @patch("src.scheduler.Path")
    def test_cancel_event_passed_to_coach(
        self, mock_path, mock_get_conn, mock_state, mock_resolve,
        mock_harvest, mock_analyze, mock_patterns, mock_coach,
    ):
        mock_path.return_value.is_file.return_value = True
        player = {"username": "test", "display_name": "Test", "id": 1,
                  "lichess_username": None}
        mock_get_conn.return_value = _make_mock_conn([player])

        mock_harvest.return_value = {"new": 0, "errors": 0}
        mock_analyze.return_value = 0
        mock_resolve.return_value = "claude-opus-4-6"
        mock_coach.return_value = {"coached": 0, "errors": 0, "skipped": 0}

        cancel = threading.Event()
        run_full_pipeline(_make_config(), "test.db", cancel_event=cancel)

        _, kwargs = mock_coach.call_args
        assert kwargs.get("cancel_event") is cancel

    @patch("src.coach.coach_pending")
    @patch("src.patterns.compute_player_patterns")
    @patch("src.analyzer.analyze_pending")
    @patch("src.harvester.harvest_player")
    @patch("src.llm_providers.resolve_model")
    @patch("src.scheduler.pipeline_state")
    @patch("src.scheduler.get_connection")
    @patch("src.scheduler.Path")
    def test_provider_passed_to_coach(
        self, mock_path, mock_get_conn, mock_state, mock_resolve,
        mock_harvest, mock_analyze, mock_patterns, mock_coach,
    ):
        mock_path.return_value.is_file.return_value = True
        player = {"username": "test", "display_name": "Test", "id": 1,
                  "lichess_username": None}
        mock_get_conn.return_value = _make_mock_conn([player])

        mock_harvest.return_value = {"new": 0, "errors": 0}
        mock_analyze.return_value = 0
        mock_resolve.return_value = "gpt-5.4"
        mock_coach.return_value = {"coached": 0, "errors": 0, "skipped": 0}

        run_full_pipeline(_make_config(), "test.db", provider="openai")

        _, kwargs = mock_coach.call_args
        assert kwargs.get("provider") == "openai"

    @patch("src.coach.coach_pending")
    @patch("src.patterns.compute_player_patterns")
    @patch("src.analyzer.analyze_pending")
    @patch("src.harvester.harvest_player")
    @patch("src.llm_providers.resolve_model")
    @patch("src.scheduler.pipeline_state")
    @patch("src.scheduler.get_connection")
    @patch("src.scheduler.Path")
    def test_progress_updates_four_steps(
        self, mock_path, mock_get_conn, mock_state, mock_resolve,
        mock_harvest, mock_analyze, mock_patterns, mock_coach,
    ):
        mock_path.return_value.is_file.return_value = True
        player = {"username": "test", "display_name": "Test", "id": 1,
                  "lichess_username": None}
        mock_get_conn.return_value = _make_mock_conn([player])

        mock_harvest.return_value = {"new": 0, "errors": 0}
        mock_analyze.return_value = 0
        mock_resolve.return_value = "claude-opus-4-6"
        mock_coach.return_value = {"coached": 0, "errors": 0, "skipped": 0}

        run_full_pipeline(_make_config(), "test.db")

        # Check that progress updates mention all 4 steps
        progress_messages = [
            str(c) for c in mock_state.update_progress.call_args_list
        ]
        progress_text = " ".join(progress_messages)
        assert "1/4" in progress_text
        assert "2/4" in progress_text
        assert "3/4" in progress_text
        assert "4/4" in progress_text

    @patch("src.scheduler.pipeline_state")
    @patch("src.scheduler.get_connection")
    @patch("shutil.which")
    @patch("src.scheduler.Path")
    def test_stockfish_not_found_raises(
        self, mock_path, mock_which, mock_get_conn, mock_state,
    ):
        mock_path.return_value.is_file.return_value = False
        mock_which.return_value = None
        player = {"username": "test", "display_name": "Test", "id": 1,
                  "lichess_username": None}
        mock_get_conn.return_value = _make_mock_conn([player])

        with pytest.raises(RuntimeError, match="Stockfish not found"):
            run_full_pipeline(_make_config("/nonexistent/stockfish"), "test.db")
