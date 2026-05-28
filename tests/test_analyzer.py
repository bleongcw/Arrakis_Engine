"""Tests for src/analyzer.py"""

import inspect
from unittest.mock import MagicMock

import pytest

from src.analyzer import (
    cp_to_win_prob, classify_move, score_to_cp, cap_eval, EVAL_CAP,
    analyze_game,
)


class TestAnalyzeGameBestInfoOrdering:
    """v1.16.2 regression lock for the UnboundLocalError bug.

    The v1.14.0 motif wiring put `best_move_obj = best_info["pv"][0]`
    BEFORE `best_info = info` in the per-move loop. On the very first
    iteration of every newly-analyzed game, `best_info` didn't exist
    yet, raising:

        UnboundLocalError: cannot access local variable 'best_info'
        where it is not associated with a value

    The bug only triggered on `analyze_game` (new analyses) — never
    on rescan-motifs (which doesn't call analyze_game). Symptom was
    silent: 'Failed to analyze game N' in the logs, no Stockfish work,
    no stack trace surfaced to the user.

    This static test inspects the source of analyze_game and asserts
    that `best_info = info` appears BEFORE `best_move_obj = best_info`.
    Static-source check (zero-cost, no Stockfish needed) — runs on
    every commit and would have caught the v1.14.0 regression
    instantly.
    """

    def test_best_info_assigned_before_best_move_obj_read(self):
        src = inspect.getsource(analyze_game)
        # Find the two lines of interest
        assign_idx = src.find("best_info = info")
        read_idx = src.find('best_info["pv"][0] if best_info.get("pv")')
        assert assign_idx != -1, (
            "expected `best_info = info` in analyze_game"
        )
        assert read_idx != -1, (
            "expected `best_info[\"pv\"][0] if best_info.get(\"pv\")` "
            "in analyze_game"
        )
        assert assign_idx < read_idx, (
            f"v1.16.2 regression: `best_info = info` (idx {assign_idx}) "
            f"must come BEFORE the line that reads best_info to derive "
            f"best_move_obj (idx {read_idx}). Otherwise the first loop "
            f"iteration raises UnboundLocalError on freshly-analyzed "
            f"games."
        )


class TestCpToWinProb:
    def test_zero_is_fifty_percent(self):
        assert cp_to_win_prob(0) == pytest.approx(50.0)

    def test_positive_cp_above_fifty(self):
        assert cp_to_win_prob(100) > 50.0

    def test_negative_cp_below_fifty(self):
        assert cp_to_win_prob(-100) < 50.0

    def test_symmetry(self):
        """Win prob at +X should mirror 100 - win_prob at -X."""
        wp_pos = cp_to_win_prob(200)
        wp_neg = cp_to_win_prob(-200)
        assert wp_pos == pytest.approx(100.0 - wp_neg, abs=0.01)

    def test_large_advantage(self):
        assert cp_to_win_prob(1000) > 95.0

    def test_large_disadvantage(self):
        assert cp_to_win_prob(-1000) < 5.0


class TestClassifyMove:
    def test_excellent(self):
        assert classify_move(0) == "excellent"
        assert classify_move(30) == "excellent"

    def test_good(self):
        assert classify_move(31) == "good"
        assert classify_move(50) == "good"

    def test_inaccuracy(self):
        assert classify_move(51) == "inaccuracy"
        assert classify_move(100) == "inaccuracy"

    def test_mistake(self):
        assert classify_move(101) == "mistake"
        assert classify_move(300) == "mistake"

    def test_blunder(self):
        assert classify_move(301) == "blunder"
        assert classify_move(1000) == "blunder"


class TestCapEval:
    def test_within_range_passthrough(self):
        assert cap_eval(500) == 500
        assert cap_eval(-500) == -500
        assert cap_eval(0) == 0

    def test_clamps_positive_overflow(self):
        assert cap_eval(2000) == EVAL_CAP
        assert cap_eval(99999) == EVAL_CAP

    def test_clamps_negative_overflow(self):
        assert cap_eval(-2000) == -EVAL_CAP
        assert cap_eval(-99999) == -EVAL_CAP


class TestScoreToCp:
    """Test PovScore → centipawn conversion using mock objects."""

    def _mock_score(self, cp=None, mate=None):
        """Build a mock PovScore.

        If mate is set, is_mate() returns True.
        """
        pov = MagicMock()
        white = MagicMock()
        pov.white.return_value = white

        if mate is not None:
            white.is_mate.return_value = True
            white.mate.return_value = mate
            white.score.return_value = None
        else:
            white.is_mate.return_value = False
            white.mate.return_value = None
            white.score.return_value = cp
        return pov

    def test_normal_centipawn(self):
        score = self._mock_score(cp=150)
        assert score_to_cp(score, True) == 150

    def test_negative_centipawn(self):
        score = self._mock_score(cp=-200)
        assert score_to_cp(score, True) == -200

    def test_mate_positive(self):
        score = self._mock_score(mate=3)
        assert score_to_cp(score, True) == EVAL_CAP

    def test_mate_negative(self):
        score = self._mock_score(mate=-5)
        assert score_to_cp(score, True) == -EVAL_CAP

    def test_zero_cp(self):
        score = self._mock_score(cp=0)
        assert score_to_cp(score, True) == 0
