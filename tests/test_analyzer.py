"""Tests for src/analyzer.py"""

import pytest

from src.analyzer import cp_to_win_prob, classify_move, score_to_cp


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
