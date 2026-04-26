"""Tests for v1.4.0 Self-Analysis pattern computations.

Covers _compute_loss_openings, _compute_strong_openings, and the
_aggregate_openings_by_outcome helper that powers both.
"""
import pytest

from src.patterns import (
    _aggregate_openings_by_outcome,
    _compute_loss_openings,
    _compute_strong_openings,
)


def _g(game_id, color, result, opening_name="Italian Game"):
    """Build a minimal game dict suitable for the pattern functions.
    The pgn just needs an `[Opening "..."]` header so _get_opening_name
    can parse it."""
    pgn = (
        f'[White "w"]\n[Black "b"]\n[Opening "{opening_name}"]\n'
        '\n1. e4 e5 2. Nf3 Nc6 *'
    )
    return {
        "id": game_id,
        "pgn": pgn,
        "player_color": color,
        "result": result,
        "date_played": f"2026-04-{game_id:02d}",
    }


class TestLossOpenings:
    def test_empty_returns_empty_buckets(self):
        out = _compute_loss_openings([])
        assert out == {"white": [], "black": []}

    def test_single_loss_below_threshold_filtered(self):
        """Need at least 2 games in an opening to flag a pattern."""
        games = [_g(1, "white", "loss", "French Defense")]
        out = _compute_loss_openings(games)
        assert out["white"] == []
        assert out["black"] == []

    def test_loss_pattern_surfaced(self):
        games = [
            _g(1, "white", "loss", "Italian Game"),
            _g(2, "white", "loss", "Italian Game"),
            _g(3, "white", "win", "Italian Game"),
        ]
        out = _compute_loss_openings(games)
        white = out["white"]
        assert len(white) == 1
        entry = white[0]
        assert entry["name"] == "Italian Game"
        assert entry["losses"] == 2
        assert entry["wins"] == 1
        assert entry["total"] == 3
        assert entry["rate"] == pytest.approx(66.7, rel=0.01)
        assert entry["recent_game_ids"] == [2, 1]  # newest first

    def test_color_segmentation(self):
        games = [
            _g(1, "white", "loss", "Italian Game"),
            _g(2, "white", "loss", "Italian Game"),
            _g(3, "black", "loss", "Sicilian Defense"),
            _g(4, "black", "loss", "Sicilian Defense"),
        ]
        out = _compute_loss_openings(games)
        assert len(out["white"]) == 1 and out["white"][0]["name"] == "Italian Game"
        assert len(out["black"]) == 1 and out["black"][0]["name"] == "Sicilian Defense"

    def test_all_wins_excluded(self):
        """Openings with 100% win-rate must NOT appear in loss list."""
        games = [
            _g(1, "white", "win", "Italian Game"),
            _g(2, "white", "win", "Italian Game"),
        ]
        out = _compute_loss_openings(games)
        assert out["white"] == []

    def test_sorted_by_loss_count_desc(self):
        # Two losing openings: 'Caro-Kann' has 4 losses, 'Italian' has 2.
        games = []
        for i in range(4):
            games.append(_g(i + 1, "white", "loss", "Caro-Kann"))
        for i in range(2):
            games.append(_g(i + 10, "white", "loss", "Italian"))
        out = _compute_loss_openings(games)
        names = [e["name"] for e in out["white"]]
        assert names[0] == "Caro-Kann"
        assert names[1] == "Italian"

    def test_recent_game_ids_capped_at_5(self):
        games = [_g(i + 1, "white", "loss", "Italian Game") for i in range(8)]
        out = _compute_loss_openings(games)
        assert len(out["white"][0]["recent_game_ids"]) == 5


class TestStrongOpenings:
    def test_strong_opening_surfaced(self):
        games = [
            _g(1, "white", "win", "Ruy Lopez"),
            _g(2, "white", "win", "Ruy Lopez"),
            _g(3, "white", "loss", "Ruy Lopez"),
        ]
        out = _compute_strong_openings(games)
        white = out["white"]
        assert len(white) == 1
        entry = white[0]
        assert entry["name"] == "Ruy Lopez"
        assert entry["wins"] == 2
        assert entry["rate"] == pytest.approx(66.7, rel=0.01)

    def test_all_losses_excluded_from_strengths(self):
        games = [
            _g(1, "white", "loss", "Ruy Lopez"),
            _g(2, "white", "loss", "Ruy Lopez"),
        ]
        out = _compute_strong_openings(games)
        assert out["white"] == []


class TestAggregateHelper:
    """_aggregate_openings_by_outcome is the shared engine for both."""

    def test_uses_outcome_filter(self):
        games = [
            _g(1, "white", "win", "X"),
            _g(2, "white", "loss", "X"),
        ]
        loss_view = _aggregate_openings_by_outcome(games, "loss")
        win_view = _aggregate_openings_by_outcome(games, "win")
        # Only 1 game of each outcome — below 2-game threshold for the
        # outcome-filter list... but total is 2 so the entry IS surfaced
        # because the threshold is on TOTAL games in the opening.
        assert any(e["name"] == "X" for e in loss_view["white"])
        assert any(e["name"] == "X" for e in win_view["white"])

    def test_draw_does_not_count_as_loss_or_win(self):
        games = [
            _g(1, "white", "draw", "X"),
            _g(2, "white", "draw", "X"),
        ]
        loss_view = _aggregate_openings_by_outcome(games, "loss")
        win_view = _aggregate_openings_by_outcome(games, "win")
        assert loss_view["white"] == []
        assert win_view["white"] == []
