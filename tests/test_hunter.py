"""Tests for src/hunter.py — v1.4.1 Hunter Mode (opponent prep).

Mocks the chess.com / lichess HTTP calls; verifies the profile
computation, cache hit/miss/TTL, and platform validation.
"""
import json
from unittest.mock import patch

import pytest

from src.hunter import (
    DEFAULT_TTL_HOURS,
    _normalize_platform,
    compute_opponent_profile,
    fetch_opponent_games,
    get_cached_profile,
    get_or_fetch_profile,
    set_cached_profile,
)
from src.models import init_db


@pytest.fixture
def db_path(tmp_path):
    """A test DB path with all migrations applied (incl. opponent_cache).
    The dashboard server runs init_db() once at startup; tests must do
    the same to ensure the cache table exists before get_or_fetch_profile
    is called."""
    p = str(tmp_path / "hunt.db")
    init_db(p).close()
    return p


@pytest.fixture
def conn(db_path):
    """A test DB connection with the opponent_cache table created."""
    from src.models import get_connection
    c = get_connection(db_path)
    yield c
    c.close()


def _g(color, result, opening="Italian Game"):
    """Build an opponent-game dict (the shape returned by fetch_opponent_games)."""
    return {
        "pgn": (
            f'[White "w"]\n[Black "b"]\n[Opening "{opening}"]\n'
            '\n1. e4 e5 *'
        ),
        "player_color": color,   # opponent's color
        "result": result,        # opponent's outcome
    }


# ── Platform normalization ──────────────────────────────────────────────


class TestNormalizePlatform:
    @pytest.mark.parametrize("raw,expected", [
        ("chess.com", "chess.com"),
        ("Chess.com", "chess.com"),
        ("CHESS.COM", "chess.com"),
        ("chesscom", "chess.com"),
        ("chess_com", "chess.com"),
        ("lichess", "lichess"),
        ("Lichess", "lichess"),
        ("lichess.org", "lichess"),
    ])
    def test_canonicalizes(self, raw, expected):
        assert _normalize_platform(raw) == expected


# ── compute_opponent_profile ────────────────────────────────────────────


class TestComputeOpponentProfile:
    def test_empty_games(self):
        prof = compute_opponent_profile([])
        assert prof["total_games"] == 0
        assert prof["weaknesses"] == {"white": [], "black": []}
        assert prof["strengths"] == {"white": [], "black": []}

    def test_results_summary(self):
        games = [
            _g("white", "win"), _g("white", "win"), _g("white", "loss"),
            _g("black", "draw"),
        ]
        prof = compute_opponent_profile(games)
        assert prof["total_games"] == 4
        assert prof["results"]["wins"] == 2
        assert prof["results"]["losses"] == 1
        assert prof["results"]["draws"] == 1
        assert prof["results"]["win_rate"] == 50.0

    def test_weaknesses_are_their_losses(self):
        # Opponent loses ALL Italian Games as white — pure weakness
        games = [
            _g("white", "loss", "Italian Game"),
            _g("white", "loss", "Italian Game"),
        ]
        prof = compute_opponent_profile(games)
        white_weak = prof["weaknesses"]["white"]
        assert len(white_weak) == 1
        assert white_weak[0]["name"] == "Italian Game"
        assert white_weak[0]["losses"] == 2
        assert white_weak[0]["rate"] == 100.0
        # And not in their strengths (no wins to surface)
        assert prof["strengths"]["white"] == []

    def test_opening_can_appear_in_both_lists_with_different_rates(self):
        """An opening with wins AND losses surfaces in both lists with the
        appropriate rate from each perspective."""
        games = [
            _g("white", "loss", "Italian Game"),
            _g("white", "loss", "Italian Game"),
            _g("white", "win", "Italian Game"),
        ]
        prof = compute_opponent_profile(games)
        weak = prof["weaknesses"]["white"]
        strong = prof["strengths"]["white"]
        assert len(weak) == 1 and weak[0]["rate"] == pytest.approx(66.7, rel=0.01)
        assert len(strong) == 1 and strong[0]["rate"] == pytest.approx(33.3, rel=0.01)

    def test_strengths_are_their_wins(self):
        games = [
            _g("black", "win", "Sicilian Defense"),
            _g("black", "win", "Sicilian Defense"),
        ]
        prof = compute_opponent_profile(games)
        black_strong = prof["strengths"]["black"]
        assert len(black_strong) == 1
        assert black_strong[0]["name"] == "Sicilian Defense"
        assert black_strong[0]["wins"] == 2
        # Not in weaknesses
        assert prof["weaknesses"]["black"] == []

    def test_color_segmentation(self):
        games = [
            _g("white", "loss", "Italian Game"),
            _g("white", "loss", "Italian Game"),
            _g("black", "loss", "French Defense"),
            _g("black", "loss", "French Defense"),
        ]
        prof = compute_opponent_profile(games)
        assert prof["weaknesses"]["white"][0]["name"] == "Italian Game"
        assert prof["weaknesses"]["black"][0]["name"] == "French Defense"


# ── Cache layer ─────────────────────────────────────────────────────────


class TestCacheRoundtrip:
    def test_miss_returns_none(self, conn):
        assert get_cached_profile(conn, "evanleongxinyu", "chess.com") is None

    def test_set_then_get_returns_profile(self, conn):
        profile = {"weaknesses": {"white": [], "black": []}, "total_games": 5}
        set_cached_profile(conn, "MagnusCarlsen", "chess.com", profile)
        got = get_cached_profile(conn, "magnuscarlsen", "chess.com")  # case-insensitive
        assert got == profile

    def test_normalizes_platform_alias(self, conn):
        profile = {"foo": "bar"}
        set_cached_profile(conn, "x", "chesscom", profile)
        got = get_cached_profile(conn, "x", "chess.com")
        assert got == profile

    def test_upsert_overwrites(self, conn):
        set_cached_profile(conn, "x", "chess.com", {"v": 1})
        set_cached_profile(conn, "x", "chess.com", {"v": 2})
        assert get_cached_profile(conn, "x", "chess.com") == {"v": 2}

    def test_ttl_expiry_returns_none(self, conn):
        # Insert a profile, then artificially backdate fetched_at past TTL
        set_cached_profile(conn, "x", "chess.com", {"v": 1})
        conn.execute(
            "UPDATE opponent_cache SET fetched_at = datetime('now', '-48 hours') "
            "WHERE username = ? AND platform = ?",
            ("x", "chess.com"),
        )
        conn.commit()
        # Default TTL is 24h, so 48h should be stale
        assert get_cached_profile(conn, "x", "chess.com",
                                   ttl_hours=DEFAULT_TTL_HOURS) is None

    def test_ttl_threshold_keeps_fresh(self, conn):
        set_cached_profile(conn, "x", "chess.com", {"v": 1})
        # Backdate by 12h — within the 24h default TTL
        conn.execute(
            "UPDATE opponent_cache SET fetched_at = datetime('now', '-12 hours') "
            "WHERE username = ? AND platform = ?",
            ("x", "chess.com"),
        )
        conn.commit()
        assert get_cached_profile(conn, "x", "chess.com") == {"v": 1}


# ── fetch_opponent_games dispatch ────────────────────────────────────────


class TestFetchDispatch:
    def test_unknown_platform_raises(self):
        with pytest.raises(ValueError, match="Unknown platform"):
            fetch_opponent_games("u", "playstation", lookback_months=1)

    @patch("src.hunter._fetch_chesscom_opponent_games")
    def test_chesscom_dispatched(self, mock_fn):
        mock_fn.return_value = [_g("white", "win")]
        out = fetch_opponent_games("u", "chess.com", lookback_months=1)
        assert mock_fn.called
        assert len(out) == 1

    @patch("src.hunter._fetch_lichess_opponent_games")
    def test_lichess_dispatched(self, mock_fn):
        mock_fn.return_value = [_g("black", "loss")]
        out = fetch_opponent_games("u", "lichess", lookback_months=1)
        assert mock_fn.called
        assert len(out) == 1


# ── get_or_fetch_profile end-to-end ──────────────────────────────────────


class TestGetOrFetchProfile:
    @patch("src.hunter.fetch_opponent_games")
    def test_fresh_fetch_populates_cache(self, mock_fetch, db_path):
        mock_fetch.return_value = [
            _g("white", "loss", "Italian Game"),
            _g("white", "loss", "Italian Game"),
            _g("white", "win", "Italian Game"),
        ]
        profile = get_or_fetch_profile("OpponentX", "chess.com", db_path)

        # Live fetch happened
        assert mock_fetch.call_count == 1
        # Profile populated
        assert profile["total_games"] == 3
        assert profile["weaknesses"]["white"][0]["name"] == "Italian Game"
        # meta marks this as a live fetch
        assert profile["meta"]["cached"] is False
        assert profile["meta"]["platform"] == "chess.com"
        assert profile["meta"]["fetched_at"] is not None

    @patch("src.hunter.fetch_opponent_games")
    def test_second_call_hits_cache(self, mock_fetch, db_path):
        mock_fetch.return_value = [_g("white", "loss", "Italian Game"),
                                   _g("white", "loss", "Italian Game")]
        # First call: live fetch
        get_or_fetch_profile("OpponentX", "chess.com", db_path)
        # Second call (within TTL): should not re-fetch
        profile = get_or_fetch_profile("OpponentX", "chess.com", db_path)
        assert mock_fetch.call_count == 1
        assert profile["meta"]["cached"] is True

    @patch("src.hunter.fetch_opponent_games")
    def test_force_refresh_bypasses_cache(self, mock_fetch, db_path):
        mock_fetch.return_value = [_g("white", "loss", "Italian Game"),
                                   _g("white", "loss", "Italian Game")]
        get_or_fetch_profile("OpponentX", "chess.com", db_path)
        get_or_fetch_profile("OpponentX", "chess.com", db_path,
                             force_refresh=True)
        assert mock_fetch.call_count == 2

    @patch("src.hunter.fetch_opponent_games")
    def test_empty_profile_when_fetch_returns_nothing(self, mock_fetch, db_path):
        mock_fetch.return_value = []
        profile = get_or_fetch_profile("UnknownUser", "chess.com", db_path)
        assert profile["total_games"] == 0
        assert profile["weaknesses"] == {"white": [], "black": []}
        assert profile["meta"]["cached"] is False


# ── opponent_cache schema migration ──────────────────────────────────────


class TestSchemaMigration:
    def test_table_exists_after_init_db(self, db_path):
        conn = init_db(db_path)
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='opponent_cache'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()

    def test_unique_constraint_on_username_platform(self, conn):
        set_cached_profile(conn, "x", "chess.com", {"v": 1})
        # Same username + platform should upsert, not duplicate
        set_cached_profile(conn, "x", "chess.com", {"v": 2})
        rows = conn.execute(
            "SELECT COUNT(*) AS c FROM opponent_cache "
            "WHERE username = ? AND platform = ?",
            ("x", "chess.com"),
        ).fetchone()
        assert rows["c"] == 1
