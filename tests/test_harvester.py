"""Tests for src/harvester.py — Chess.com and Lichess harvesters."""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.harvester import (
    _chesscom_filter_recent,
    _chesscom_determine_side,
    _chesscom_determine_result,
    _lichess_determine_side,
    _lichess_determine_result,
    _lichess_extract_time_control,
    _lichess_extract_game_url,
    _lichess_extract_date,
    harvest_player,
)
from src.models import init_db


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


# ── Chess.com Test Data ─────────────────────────────────────────────

SAMPLE_CHESSCOM_GAME = {
    "url": "https://www.chess.com/game/live/12345",
    "pgn": '[Event "Live"]\n[White "testplayer1"]\n[Black "opponent1"]\n\n1. e4 e5 2. Nf3 Nc6 *',
    "time_control": "600",
    "time_class": "rapid",
    "end_time": 1700000000,
    "white": {
        "username": "testplayer1",
        "rating": 1050,
        "result": "win",
    },
    "black": {
        "username": "opponent1",
        "rating": 980,
        "result": "checkmated",
    },
}


# ── Lichess Test Data ────────────────────────────────────────────────

SAMPLE_LICHESS_PGN = """[Event "Rated Blitz game"]
[Site "https://lichess.org/abcdef12"]
[Date "2026.03.20"]
[UTCDate "2026.03.20"]
[White "evleong"]
[Black "lichess_opponent"]
[WhiteElo "1200"]
[BlackElo "1150"]
[Result "1-0"]
[TimeControl "300+0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0"""

SAMPLE_LICHESS_PGN_BLACK = """[Event "Rated Rapid game"]
[Site "https://lichess.org/xyz78901"]
[Date "2026.03.21"]
[UTCDate "2026.03.21"]
[White "another_player"]
[Black "evleong"]
[WhiteElo "1300"]
[BlackElo "1200"]
[Result "0-1"]
[TimeControl "900+10"]

1. d4 d5 2. c4 e6 3. Nc3 Nf6 0-1"""

SAMPLE_LICHESS_PGN_DRAW = """[Event "Rated Classical game"]
[Site "https://lichess.org/draw12345"]
[Date "2026.03.22"]
[UTCDate "2026.03.22"]
[White "evleong"]
[Black "draw_opponent"]
[WhiteElo "1200"]
[BlackElo "1250"]
[Result "1/2-1/2"]
[TimeControl "1800+0"]

1. e4 e5 1/2-1/2"""


# ── Chess.com Tests ──────────────────────────────────────────────────

class TestChessComFilterRecent:
    def test_filters_old_archives(self):
        # v1.30.0: build the archive dates RELATIVE to now instead of
        # hardcoding calendar months. The old fixture (2026/01–03) rotted as
        # real time advanced past its 6-month window and started failing.
        from datetime import datetime, timedelta

        def archive_url(dt):
            return (f"https://api.chess.com/pub/player/testplayer1/games/"
                    f"{dt.year}/{dt.month:02d}")

        now = datetime.now()
        this_month = now.replace(day=1)
        last_month = (this_month - timedelta(days=1)).replace(day=1)
        ancient = "https://api.chess.com/pub/player/testplayer1/games/2010/01"
        urls = [ancient, archive_url(last_month), archive_url(this_month)]

        recent = _chesscom_filter_recent(urls, months=6)
        assert len(recent) >= 2          # this month + last month are within 6mo
        assert ancient not in recent      # the 2010 archive is excluded

    def test_empty_list(self):
        assert _chesscom_filter_recent([], months=6) == []


class TestChessComDeterminePlayerSide:
    def test_white_player(self):
        color, pr, opp, opp_name = _chesscom_determine_side(SAMPLE_CHESSCOM_GAME, "testplayer1")
        assert color == "white"
        assert pr == 1050
        assert opp == 980
        assert opp_name == "opponent1"

    def test_black_player(self):
        color, pr, opp, opp_name = _chesscom_determine_side(SAMPLE_CHESSCOM_GAME, "opponent1")
        assert color == "black"
        assert pr == 980
        assert opp == 1050
        assert opp_name == "testplayer1"

    def test_case_insensitive(self):
        color, _, _, _ = _chesscom_determine_side(SAMPLE_CHESSCOM_GAME, "TestPlayer1")
        assert color == "white"

    def test_unknown_player_raises(self):
        with pytest.raises(ValueError):
            _chesscom_determine_side(SAMPLE_CHESSCOM_GAME, "nobody")


class TestChessComDetermineResult:
    def test_win(self):
        assert _chesscom_determine_result(SAMPLE_CHESSCOM_GAME, "testplayer1") == "win"

    def test_loss(self):
        assert _chesscom_determine_result(SAMPLE_CHESSCOM_GAME, "opponent1") == "loss"

    def test_draw(self):
        draw_game = {
            "white": {"username": "a", "result": "stalemate"},
            "black": {"username": "b", "result": "stalemate"},
        }
        assert _chesscom_determine_result(draw_game, "a") == "draw"


# ── Lichess Tests ────────────────────────────────────────────────────

class TestLichessDetermineSide:
    def test_white_player(self):
        color, pr, opp, opp_name = _lichess_determine_side(SAMPLE_LICHESS_PGN, "evleong")
        assert color == "white"
        assert pr == 1200
        assert opp == 1150
        assert opp_name == "lichess_opponent"

    def test_black_player(self):
        color, pr, opp, opp_name = _lichess_determine_side(SAMPLE_LICHESS_PGN_BLACK, "evleong")
        assert color == "black"
        assert pr == 1200
        assert opp == 1300
        assert opp_name == "another_player"

    def test_case_insensitive(self):
        color, _, _, _ = _lichess_determine_side(SAMPLE_LICHESS_PGN, "EvLeong")
        assert color == "white"

    def test_unknown_player_raises(self):
        with pytest.raises(ValueError):
            _lichess_determine_side(SAMPLE_LICHESS_PGN, "nobody")


class TestLichessDetermineResult:
    def test_white_wins(self):
        assert _lichess_determine_result(SAMPLE_LICHESS_PGN, "evleong") == "win"

    def test_white_loses(self):
        assert _lichess_determine_result(SAMPLE_LICHESS_PGN_BLACK, "another_player") == "loss"

    def test_black_wins(self):
        assert _lichess_determine_result(SAMPLE_LICHESS_PGN_BLACK, "evleong") == "win"

    def test_draw(self):
        assert _lichess_determine_result(SAMPLE_LICHESS_PGN_DRAW, "evleong") == "draw"
        assert _lichess_determine_result(SAMPLE_LICHESS_PGN_DRAW, "draw_opponent") == "draw"


class TestLichessExtractTimeControl:
    def test_blitz(self):
        tc, tc_class = _lichess_extract_time_control(SAMPLE_LICHESS_PGN)
        assert tc == "300+0"
        assert tc_class == "blitz"

    def test_rapid(self):
        tc, tc_class = _lichess_extract_time_control(SAMPLE_LICHESS_PGN_BLACK)
        assert tc == "900+10"
        assert tc_class == "rapid"

    def test_classical(self):
        tc, tc_class = _lichess_extract_time_control(SAMPLE_LICHESS_PGN_DRAW)
        assert tc == "1800+0"
        assert tc_class == "rapid"  # 1800s = 30min = rapid


class TestLichessExtractGameUrl:
    def test_extracts_url(self):
        url = _lichess_extract_game_url(SAMPLE_LICHESS_PGN)
        assert url == "https://lichess.org/abcdef12"

    def test_no_site_header(self):
        assert _lichess_extract_game_url("[Event \"test\"]\n1. e4 *") is None

    # v1.33.2: Lichess moved Site to https://lichess.org/game/<id>, and
    # game_url is the dedup key — 58 games were re-imported as duplicates.

    @pytest.mark.parametrize("site", [
        "https://lichess.org/WS7GBFCF",
        "https://lichess.org/game/WS7GBFCF",
        "https://lichess.org/WS7GBFCF/black",
    ])
    def test_every_site_form_maps_to_one_url(self, site):
        pgn = f'[Site "{site}"]\n\n1. e4 *'
        assert _lichess_extract_game_url(pgn) == "https://lichess.org/WS7GBFCF"

    def test_game_id_header_wins(self):
        pgn = '[Site "https://lichess.org/game/WS7GBFCF"]\n[GameId "WS7GBFCF"]\n\n1. e4 *'
        assert _lichess_extract_game_url(pgn) == "https://lichess.org/WS7GBFCF"

    @patch("src.harvester.requests.get")
    def test_new_site_format_does_not_reimport(self, mock_get, db_path):
        from src.harvester import harvest_lichess
        from src.models import ensure_player
        new_format = SAMPLE_LICHESS_PGN.replace(
            "https://lichess.org/abcdef12", "https://lichess.org/game/abcdef12")
        mock_get.return_value.raise_for_status.return_value = None
        conn = init_db(db_path)
        pid = ensure_player(conn, "testplayer1", display_name="T", age=9,
                            rating=1000)
        mock_get.return_value.text = SAMPLE_LICHESS_PGN
        harvest_lichess("evleong", pid, conn)
        mock_get.return_value.text = new_format
        stats = harvest_lichess("evleong", pid, conn)
        n = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        conn.close()
        assert stats["new"] == 0 and stats["skipped"] == 1
        assert n == 1


class TestLichessExtractDate:
    def test_utc_date(self):
        assert _lichess_extract_date(SAMPLE_LICHESS_PGN) == "2026-03-20"

    def test_no_date(self):
        assert _lichess_extract_date("[Event \"test\"]\n1. e4 *") is None


# ── Integration Tests ────────────────────────────────────────────────

def _recent_archive_url(user="testplayer1"):
    """A chess.com archive URL for the CURRENT month.

    v1.32.1: these fixtures used to hardcode `2026/03`, which silently rotted
    out of the default 6-month lookback as real time advanced (the cutoff
    carries a time-of-day, so a month-boundary archive at 00:00 falls just
    outside). Build it relative to now so the tests can't expire.
    """
    from datetime import datetime
    now = datetime.now()
    return (f"https://api.chess.com/pub/player/{user}/games/"
            f"{now.year}/{now.month:02d}")


class TestHarvestPlayer:
    @patch("src.harvester._chesscom_get_archive_urls")
    @patch("src.harvester._chesscom_fetch_archive")
    def test_stores_chesscom_games(self, mock_fetch, mock_archives, db_path):
        mock_archives.return_value = [_recent_archive_url()]
        mock_fetch.return_value = [SAMPLE_CHESSCOM_GAME]

        stats = harvest_player("testplayer1", db_path=db_path, months=6)
        assert stats["new"] == 1
        assert stats["skipped"] == 0

        # Verify platform is stored
        from src.models import get_connection
        conn = get_connection(db_path)
        game = conn.execute("SELECT platform FROM games LIMIT 1").fetchone()
        assert game["platform"] == "chess.com"
        conn.close()

    @patch("src.harvester._chesscom_get_archive_urls")
    @patch("src.harvester._chesscom_fetch_archive")
    def test_deduplicates(self, mock_fetch, mock_archives, db_path):
        mock_archives.return_value = [_recent_archive_url()]
        mock_fetch.return_value = [SAMPLE_CHESSCOM_GAME]

        harvest_player("testplayer1", db_path=db_path, months=6)
        stats = harvest_player("testplayer1", db_path=db_path, months=6)
        assert stats["new"] == 0
        assert stats["skipped"] == 1

    @patch("src.harvester._chesscom_get_archive_urls")
    @patch("src.harvester._chesscom_fetch_archive")
    def test_platform_filter_chesscom_only(self, mock_fetch, mock_archives, db_path):
        mock_archives.return_value = [_recent_archive_url()]
        mock_fetch.return_value = [SAMPLE_CHESSCOM_GAME]

        stats = harvest_player(
            "testplayer1", db_path=db_path, months=6,
            lichess_username="evleong", platform="chess.com",
        )
        assert stats["new"] == 1
        # Should NOT have tried Lichess

    @patch("src.harvester._chesscom_get_archive_urls")
    @patch("src.harvester._chesscom_fetch_archive")
    def test_platform_filter_lichess_skips_chesscom(self, mock_fetch, mock_archives, db_path):
        """When platform='lichess', chess.com should not be fetched."""
        # We patch lichess to avoid network calls
        with patch("src.harvester.harvest_lichess") as mock_lichess:
            mock_lichess.return_value = {"total": 0, "new": 0, "skipped": 0, "errors": 0}
            stats = harvest_player(
                "testplayer1", db_path=db_path, months=6,
                lichess_username="evleong", platform="lichess",
            )
            mock_archives.assert_not_called()
            mock_lichess.assert_called_once()


# ── v1.33.1: variants are not imported ───────────────────────────────


class TestVariantsNotImported:
    """Variant games can't be coached: Three-check and friends make
    Stockfish fail with "engine does not support UCI_Variant" (five Lichess
    games stuck at analysis 'error' this way), and Chess960 breaks the
    standard-opening assumptions. The harvester must skip them all."""

    def test_standard_and_headerless_pgn_are_standard(self):
        from src.harvester import _is_standard_chess
        assert _is_standard_chess(SAMPLE_LICHESS_PGN) is True
        assert _is_standard_chess('[Variant "Standard"]\n\n1. e4 *') is True

    @pytest.mark.parametrize("variant", ["Three-check", "Chess960", "Atomic",
                                         "From Position"])
    def test_variant_header_is_not_standard(self, variant):
        from src.harvester import _is_standard_chess
        assert _is_standard_chess(f'[Variant "{variant}"]\n\n1. e4 *') is False

    def test_chesscom_rules_field_is_not_standard(self):
        from src.harvester import _is_standard_chess
        assert _is_standard_chess("1. e4 *", rules="chess960") is False
        assert _is_standard_chess("1. e4 *", rules="chess") is True

    @patch("src.harvester._chesscom_get_archive_urls")
    @patch("src.harvester._chesscom_fetch_archive")
    def test_chesscom_variant_game_is_skipped(self, mock_fetch, mock_archives,
                                              db_path):
        mock_archives.return_value = [_recent_archive_url()]
        variant = {**SAMPLE_CHESSCOM_GAME, "rules": "chess960",
                   "url": "https://www.chess.com/game/live/960"}
        mock_fetch.return_value = [SAMPLE_CHESSCOM_GAME, variant]

        stats = harvest_player("testplayer1", db_path=db_path, months=6)
        assert stats["new"] == 1          # only the standard game
        assert stats["skipped"] == 1

    @patch("src.harvester.requests.get")
    def test_lichess_variant_game_is_skipped(self, mock_get, db_path):
        from src.harvester import harvest_lichess
        from src.models import init_db, ensure_player
        three_check = SAMPLE_LICHESS_PGN.replace(
            '[Event "Rated Blitz game"]',
            '[Event "casual variant:threeCheck game"]\n[Variant "Three-check"]',
        ).replace("lichess.org/", "lichess.org/v")
        mock_get.return_value.text = SAMPLE_LICHESS_PGN + "\n\n" + three_check
        mock_get.return_value.raise_for_status.return_value = None

        conn = init_db(db_path)
        pid = ensure_player(conn, "testplayer1", display_name="T", age=9,
                            rating=1000)
        stats = harvest_lichess("evleong", pid, conn)
        n = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        conn.close()
        assert stats["total"] == 2
        assert stats["new"] == 1
        assert stats["skipped"] == 1
        assert n == 1


# ── v1.30.0: outbound request resilience (_get_json_with_retry) ──────

class TestGetJsonWithRetry:
    """429 / 5xx / non-JSON handling for chess.com + lichess API calls."""

    def _resp(self, status, *, json_data=None, text=None, headers=None):
        r = MagicMock()
        r.status_code = status
        r.headers = headers or {}
        if json_data is not None:
            r.json.return_value = json_data
        else:
            r.json.side_effect = ValueError("no json")
            r.text = text or ""
        r.raise_for_status.side_effect = (
            None if status < 400 else __import__("requests").HTTPError(f"{status}")
        )
        return r

    def test_retries_on_429_then_succeeds(self):
        from src import harvester
        calls = [self._resp(429, headers={"Retry-After": "0"}),
                 self._resp(200, json_data={"archives": ["a"]})]
        with patch("src.harvester.requests.get", side_effect=calls), \
             patch("src.harvester.time.sleep"):
            out = harvester._get_json_with_retry("http://x", timeout=5)
        assert out == {"archives": ["a"]}

    def test_non_json_200_raises_requestexception(self):
        import requests
        from src import harvester
        with patch("src.harvester.requests.get",
                   return_value=self._resp(200, text="<html>bot check</html>")), \
             patch("src.harvester.time.sleep"):
            with pytest.raises(requests.RequestException):
                harvester._get_json_with_retry("http://x", timeout=5)

    def test_gives_up_after_max_retries_on_persistent_429(self):
        import requests
        from src import harvester
        with patch("src.harvester.requests.get",
                   return_value=self._resp(429, headers={"Retry-After": "0"})), \
             patch("src.harvester.time.sleep"):
            with pytest.raises(requests.HTTPError):
                harvester._get_json_with_retry("http://x", timeout=5)


class TestFilterRecentGuards:
    def test_skips_unparseable_archive_url(self):
        # A malformed archive URL must not abort the whole filter.
        urls = [
            "https://api.chess.com/pub/player/x/games/notayear/notamonth",
            "https://api.chess.com/pub/player/x/games/2026/03",
        ]
        # Should not raise; the good one survives (recency depends on clock,
        # so just assert no exception and the bad one is dropped).
        recent = _chesscom_filter_recent(urls, months=600)
        assert all("notayear" not in u for u in recent)
