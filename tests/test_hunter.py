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


class TestUsernameLowercasing:
    """v1.4.3: chess.com's API requires lowercase usernames in the URL path —
    mixed-case names return a 301 that requests follows, but at the cost of
    an extra round-trip. Both fetchers normalize input to lowercase up front.
    """

    @patch("src.hunter._chesscom_get_archive_urls")
    def test_chesscom_lowercases_mixed_case_username(self, mock_archives):
        from src.hunter import _fetch_chesscom_opponent_games
        mock_archives.return_value = []  # short-circuit after archive list
        _fetch_chesscom_opponent_games("Cyborg_warrior", lookback_months=1)
        # Assert the archive helper was called with the lowercased username
        mock_archives.assert_called_once_with("cyborg_warrior")

    @patch("requests.get")
    def test_lichess_lowercases_mixed_case_username(self, mock_get):
        from src.hunter import _fetch_lichess_opponent_games
        # `requests` is imported lazily inside the function, so we patch
        # the underlying requests.get and inspect what URL it was called with.
        mock_resp = MockResp("")
        mock_get.return_value = mock_resp
        _fetch_lichess_opponent_games("DrNykterstein", lookback_months=1)
        called_url = mock_get.call_args[0][0]
        assert "drnykterstein" in called_url
        assert "DrNykterstein" not in called_url


class MockResp:
    """Minimal stand-in for requests.Response — only what
    _fetch_lichess_opponent_games actually touches."""
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        pass


# ── v1.4.4: accumulating cache + representative games ────────────────────


def _enriched_g(
    game_url: str,
    color: str,
    result: str,
    opening: str = "Italian Game",
    date: str = "2026-04-01",
    eco: str = "C50",
):
    """Build a game dict in the v1.4.4 enriched shape returned by
    fetch_opponent_games (with game_url + date_played + eco)."""
    return {
        "pgn": (
            f'[White "w"]\n[Black "b"]\n[Opening "{opening}"]\n'
            f'[ECO "{eco}"]\n[Date "{date.replace("-", ".")}"]\n'
            '\n1. e4 e5 *'
        ),
        "player_color": color,
        "result": result,
        "game_url": game_url,
        "date_played": date,
        "opening_name": opening,
        "eco": eco,
    }


class TestAccumulateOpponentGames:
    """v1.4.4: accumulate_opponent_games merges new fetched games into
    a persistent opponent_games cache rather than replacing snapshot."""

    @patch("src.hunter.fetch_opponent_games")
    def test_first_call_inserts_all(self, mock_fetch, db_path):
        from src.hunter import accumulate_opponent_games
        mock_fetch.return_value = [
            _enriched_g(f"https://chess.com/g/{i}", "white", "loss",
                        date=f"2026-04-{i+1:02d}")
            for i in range(3)
        ]
        out = accumulate_opponent_games("OpX", "chess.com", db_path)
        assert len(out) == 3

    @patch("src.hunter.fetch_opponent_games")
    def test_second_call_dedups_on_game_url(self, mock_fetch, db_path):
        """If the second fetch returns games we already have (same URL),
        they are NOT duplicated — only new ones are added."""
        from src.hunter import accumulate_opponent_games
        # First batch: games 0, 1, 2
        mock_fetch.return_value = [
            _enriched_g(f"https://chess.com/g/{i}", "white", "loss",
                        date=f"2026-04-{i+1:02d}")
            for i in range(3)
        ]
        accumulate_opponent_games("OpX", "chess.com", db_path)

        # Second batch: games 1, 2, 3, 4 (1 and 2 are dups; 3 and 4 are new)
        mock_fetch.return_value = [
            _enriched_g(f"https://chess.com/g/{i}", "white", "loss",
                        date=f"2026-04-{i+1:02d}")
            for i in range(1, 5)
        ]
        out = accumulate_opponent_games("OpX", "chess.com", db_path)
        # Should now have 5 distinct games (0,1,2,3,4) — not 7
        assert len(out) == 5

    @patch("src.hunter.fetch_opponent_games")
    def test_sliding_window_prunes_old(self, mock_fetch, db_path):
        """Games older than lookback_months are pruned on each fetch."""
        from src.hunter import accumulate_opponent_games
        # Insert one ancient game (1 year ago)
        mock_fetch.return_value = [
            _enriched_g("https://chess.com/g/old", "white", "loss",
                        date="2025-01-01"),
            _enriched_g("https://chess.com/g/new", "white", "loss",
                        date="2026-04-01"),
        ]
        out = accumulate_opponent_games("OpX", "chess.com", db_path,
                                         lookback_months=6)
        # Only the recent one should survive; 2025-01-01 is > 6 months old
        assert len(out) == 1
        assert out[0]["game_url"] == "https://chess.com/g/new"

    @patch("src.hunter.fetch_opponent_games")
    def test_max_games_cap_prunes_excess(self, mock_fetch, db_path):
        """When max_games is set, oldest games above the cap are pruned."""
        from src.hunter import accumulate_opponent_games
        mock_fetch.return_value = [
            _enriched_g(f"https://chess.com/g/{i}", "white", "loss",
                        date=f"2026-04-{i+1:02d}")
            for i in range(10)
        ]
        out = accumulate_opponent_games("OpX", "chess.com", db_path,
                                         max_games=3)
        assert len(out) == 3
        # Top-3 should be the most recent (dates 8, 9, 10 → games 7, 8, 9)
        urls = [g["game_url"] for g in out]
        assert "https://chess.com/g/9" in urls
        assert "https://chess.com/g/8" in urls
        assert "https://chess.com/g/7" in urls
        assert "https://chess.com/g/0" not in urls

    @patch("src.hunter.fetch_opponent_games")
    def test_keeps_null_dated_games(self, mock_fetch, db_path):
        """Games with no date_played must NOT be pruned by the sliding
        window — we don't know they're old, so we keep them."""
        from src.hunter import accumulate_opponent_games
        # Game has no date — defensive: should NOT be pruned
        mock_fetch.return_value = [
            {
                "pgn": '[White "w"]\n[Black "b"]\n\n1. e4 *',
                "player_color": "white",
                "result": "loss",
                "game_url": "https://chess.com/g/nodate",
                "date_played": None,
                "opening_name": "Unknown",
                "eco": None,
            }
        ]
        out = accumulate_opponent_games("OpX", "chess.com", db_path,
                                         lookback_months=6)
        assert len(out) == 1


class TestRepresentativeGamesInProfile:
    """v1.4.4: each opening entry should carry up to 5 representative PGNs
    so the UI can render the click-to-expand mini-board."""

    def test_reps_populated_newest_first(self):
        from src.hunter import compute_opponent_profile
        # 3 losses in the same opening, different dates
        games = [
            _enriched_g(f"https://chess.com/g/{i}", "white", "loss",
                        date=f"2026-04-{i:02d}")
            for i in range(1, 4)
        ]
        profile = compute_opponent_profile(games)
        weak = profile["weaknesses"]["white"][0]
        reps = weak["representative_games"]
        assert len(reps) == 3
        # Newest first
        assert reps[0]["date_played"] == "2026-04-03"
        assert reps[1]["date_played"] == "2026-04-02"
        assert reps[2]["date_played"] == "2026-04-01"

    def test_reps_capped_at_five(self):
        from src.hunter import compute_opponent_profile, MAX_REPS_PER_OPENING
        games = [
            _enriched_g(f"https://chess.com/g/{i}", "white", "loss",
                        date=f"2026-04-{i:02d}")
            for i in range(1, 9)
        ]
        profile = compute_opponent_profile(games)
        reps = profile["weaknesses"]["white"][0]["representative_games"]
        assert len(reps) == MAX_REPS_PER_OPENING == 5

    def test_eco_propagated(self):
        from src.hunter import compute_opponent_profile
        games = [
            _enriched_g(f"https://chess.com/g/{i}", "white", "loss",
                        date=f"2026-04-{i:02d}", eco="C57")
            for i in range(1, 3)
        ]
        profile = compute_opponent_profile(games)
        weak = profile["weaknesses"]["white"][0]
        assert weak["eco"] == "C57"

    def test_only_outcome_games_in_reps(self):
        """A loss should only show losing games as reps; not wins/draws."""
        from src.hunter import compute_opponent_profile
        games = [
            _enriched_g("https://chess.com/g/1", "white", "loss",
                        date="2026-04-03"),
            _enriched_g("https://chess.com/g/2", "white", "loss",
                        date="2026-04-02"),
            _enriched_g("https://chess.com/g/3", "white", "win",
                        date="2026-04-04"),  # newest but a WIN
        ]
        profile = compute_opponent_profile(games)
        weak_reps = profile["weaknesses"]["white"][0]["representative_games"]
        # Only the 2 losses, in newest-first order
        assert len(weak_reps) == 2
        assert weak_reps[0]["date_played"] == "2026-04-03"
        assert all(rg["pgn"] for rg in weak_reps)


class TestAccumulatedGamesInMeta:
    """v1.4.4: profile.meta.accumulated_games tracks the underlying
    opponent_games cache size, separate from the profile's filtered total."""

    @patch("src.hunter.fetch_opponent_games")
    def test_meta_includes_accumulated_count(self, mock_fetch, db_path):
        from src.hunter import get_or_fetch_profile
        mock_fetch.return_value = [
            _enriched_g(f"https://chess.com/g/{i}", "white", "loss",
                        date=f"2026-04-{i+1:02d}")
            for i in range(5)
        ]
        profile = get_or_fetch_profile("OpX", "chess.com", db_path)
        assert profile["meta"]["accumulated_games"] == 5


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


# ── v1.20.0 Deep Scan: opponent motif analysis ──────────────────────────

import itertools  # noqa: E402
from src.hunter import (  # noqa: E402
    compute_opponent_motif_summary,
    get_deep_scan_status,
    deep_scan_opponent,
    _resolve_opponent_color,
)


def _seed_opponent_game(conn, username, motifs=None, analyzed=True,
                        color="white", pgn="pgn", date="2026-05-01",
                        _counter=itertools.count()):
    """Insert one opponent_games row, optionally pre-analyzed."""
    conn.execute(
        """INSERT INTO opponent_games
        (username, platform, game_url, pgn, player_color, result,
         date_played, motifs_json, analyzed_at)
        VALUES (?, 'chess.com', ?, ?, ?, 'loss', ?, ?, ?)""",
        (username.lower(), f"g{next(_counter)}", pgn, color, date,
         json.dumps(motifs) if motifs is not None else None,
         "datetime('now')" if analyzed else None),
    )
    conn.commit()


class TestComputeOpponentMotifSummary:
    """v1.20.0: aggregate per-game opponent motif data into the
    MotifThemes-compatible shape."""

    def test_none_when_no_analyzed_games(self, conn):
        assert compute_opponent_motif_summary("ghost", "chess.com",
                                              db_path=None) is None

    def test_sums_distinct_games_exactly(self, db_path):
        conn = init_db(db_path)
        _seed_opponent_game(conn, "rival", {
            "found": {"pin": 1}, "missed": {"fork": 2}, "critical_moves": 3,
            "missed_by_phase": {"fork": {"opening": 0, "middlegame": 2, "endgame": 0}},
        })
        _seed_opponent_game(conn, "rival", {
            "found": {}, "missed": {"fork": 1}, "critical_moves": 1,
            "missed_by_phase": {"fork": {"opening": 0, "middlegame": 1, "endgame": 0}},
        })
        _seed_opponent_game(conn, "rival", {
            "found": {"fork": 1}, "missed": {"pin": 1}, "critical_moves": 2,
            "missed_by_phase": {"pin": {"opening": 1, "middlegame": 0, "endgame": 0}},
        })
        conn.close()
        s = compute_opponent_motif_summary("rival", "chess.com", db_path)
        assert s["games_analyzed"] == 3
        assert s["total_critical_moves"] == 6
        assert s["top_missed"] == "fork"
        assert s["top_missed_count"] == 3
        fork = next(e for e in s["by_motif"] if e["motif"] == "fork")
        assert fork["missed"] == 3 and fork["found"] == 1
        assert fork["dominant_missed_phase"] == "middlegame"

    def test_ignores_unanalyzed_rows(self, db_path):
        conn = init_db(db_path)
        _seed_opponent_game(conn, "rival", {
            "found": {}, "missed": {"fork": 5}, "critical_moves": 5,
            "missed_by_phase": {"fork": {"opening": 0, "middlegame": 5, "endgame": 0}},
        })
        _seed_opponent_game(conn, "rival", None, analyzed=False)
        conn.close()
        s = compute_opponent_motif_summary("rival", "chess.com", db_path)
        assert s["games_analyzed"] == 1  # the un-analyzed row is excluded


class TestDeepScanStatus:
    def test_counts_analyzed_vs_total(self, db_path):
        conn = init_db(db_path)
        _seed_opponent_game(conn, "rival", {"found": {}, "missed": {},
                                            "critical_moves": 0,
                                            "missed_by_phase": {}})
        _seed_opponent_game(conn, "rival", None, analyzed=False)
        _seed_opponent_game(conn, "rival", None, analyzed=False)
        conn.close()
        status = get_deep_scan_status("rival", "chess.com", db_path)
        assert status["total_cached"] == 3
        assert status["analyzed_games"] == 1


class TestResolveOpponentColor:
    def test_trusts_player_color(self):
        assert _resolve_opponent_color({"player_color": "black"}, "x") == "black"

    def test_falls_back_to_pgn_headers(self):
        pgn = '[White "Rival"]\n[Black "Other"]\n\n1. e4 e5 *'
        assert _resolve_opponent_color({"player_color": None, "pgn": pgn},
                                       "rival") == "white"

    def test_none_when_unresolvable(self):
        pgn = '[White "Someone"]\n[Black "Else"]\n\n1. e4 *'
        assert _resolve_opponent_color({"player_color": "", "pgn": pgn},
                                       "rival") is None


class TestDeepScanIncremental:
    """v1.20.0: deep_scan_opponent skips already-analyzed games. Uses a
    fake engine path is not needed — we pre-mark all games analyzed so the
    Stockfish pass is never reached (engine-free unit test)."""

    def test_all_pre_analyzed_skips_engine(self, db_path):
        conn = init_db(db_path)
        # Two games, both already analyzed → nothing to do, no engine call.
        _seed_opponent_game(conn, "rival", {"found": {}, "missed": {},
                                            "critical_moves": 0,
                                            "missed_by_phase": {}})
        _seed_opponent_game(conn, "rival", {"found": {}, "missed": {},
                                            "critical_moves": 0,
                                            "missed_by_phase": {}})
        conn.close()
        # No stockfish config needed: there are 0 pending games, so the
        # engine is never invoked even though the path resolves a binary.
        result = deep_scan_opponent(
            "rival", "chess.com",
            config={"stockfish": {"path": "stockfish"}},
            db_path=db_path, limit=20,
        )
        assert result["analyzed"] == 0
        assert result["candidates"] == 2


@pytest.mark.integration
class TestAnalyzeOpponentGameEngine:
    """Requires a real Stockfish binary (pytest -m integration)."""

    def test_detects_a_missed_motif(self):
        import shutil
        from src.hunter import analyze_opponent_game
        sf = shutil.which("stockfish") or "/opt/homebrew/bin/stockfish"
        pgn = (
            '[White "goodguy"]\n[Black "rival"]\n\n'
            "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 "
            "6. Rf1 Qxe4+ 7. Be2 Nf3# 0-1"
        )
        res = analyze_opponent_game(pgn, "white", sf, depth=10,
                                    threads=2, hash_mb=128, move_time_limit=3.0)
        assert res["critical_moves"] >= 1
        assert isinstance(res["missed"], dict)
