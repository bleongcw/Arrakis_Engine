"""Tests for src/analyzer.py"""

from unittest.mock import MagicMock

import pytest

from src.analyzer import cp_to_win_prob, classify_move, score_to_cp, cap_eval, EVAL_CAP


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
