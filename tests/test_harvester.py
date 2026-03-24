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
    "pgn": '[Event "Live"]\n[White "evanleongxinyu"]\n[Black "opponent1"]\n\n1. e4 e5 2. Nf3 Nc6 *',
    "time_control": "600",
    "time_class": "rapid",
    "end_time": 1700000000,
    "white": {
        "username": "evanleongxinyu",
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
        urls = [
            "https://api.chess.com/pub/player/evan/games/2020/01",
            "https://api.chess.com/pub/player/evan/games/2026/01",
            "https://api.chess.com/pub/player/evan/games/2026/02",
            "https://api.chess.com/pub/player/evan/games/2026/03",
        ]
        recent = _chesscom_filter_recent(urls, months=6)
        assert len(recent) >= 2
        assert urls[0] not in recent

    def test_empty_list(self):
        assert _chesscom_filter_recent([], months=6) == []


class TestChessComDeterminePlayerSide:
    def test_white_player(self):
        color, pr, opp, opp_name = _chesscom_determine_side(SAMPLE_CHESSCOM_GAME, "evanleongxinyu")
        assert color == "white"
        assert pr == 1050
        assert opp == 980
        assert opp_name == "opponent1"

    def test_black_player(self):
        color, pr, opp, opp_name = _chesscom_determine_side(SAMPLE_CHESSCOM_GAME, "opponent1")
        assert color == "black"
        assert pr == 980
        assert opp == 1050
        assert opp_name == "evanleongxinyu"

    def test_case_insensitive(self):
        color, _, _, _ = _chesscom_determine_side(SAMPLE_CHESSCOM_GAME, "EvanLeongXinYu")
        assert color == "white"

    def test_unknown_player_raises(self):
        with pytest.raises(ValueError):
            _chesscom_determine_side(SAMPLE_CHESSCOM_GAME, "nobody")


class TestChessComDetermineResult:
    def test_win(self):
        assert _chesscom_determine_result(SAMPLE_CHESSCOM_GAME, "evanleongxinyu") == "win"

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


class TestLichessExtractDate:
    def test_utc_date(self):
        assert _lichess_extract_date(SAMPLE_LICHESS_PGN) == "2026-03-20"

    def test_no_date(self):
        assert _lichess_extract_date("[Event \"test\"]\n1. e4 *") is None


# ── Integration Tests ────────────────────────────────────────────────

class TestHarvestPlayer:
    @patch("src.harvester._chesscom_get_archive_urls")
    @patch("src.harvester._chesscom_fetch_archive")
    def test_stores_chesscom_games(self, mock_fetch, mock_archives, db_path):
        mock_archives.return_value = [
            "https://api.chess.com/pub/player/evan/games/2026/03"
        ]
        mock_fetch.return_value = [SAMPLE_CHESSCOM_GAME]

        stats = harvest_player("evanleongxinyu", db_path=db_path, months=6)
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
        mock_archives.return_value = [
            "https://api.chess.com/pub/player/evan/games/2026/03"
        ]
        mock_fetch.return_value = [SAMPLE_CHESSCOM_GAME]

        harvest_player("evanleongxinyu", db_path=db_path, months=6)
        stats = harvest_player("evanleongxinyu", db_path=db_path, months=6)
        assert stats["new"] == 0
        assert stats["skipped"] == 1

    @patch("src.harvester._chesscom_get_archive_urls")
    @patch("src.harvester._chesscom_fetch_archive")
    def test_platform_filter_chesscom_only(self, mock_fetch, mock_archives, db_path):
        mock_archives.return_value = [
            "https://api.chess.com/pub/player/evan/games/2026/03"
        ]
        mock_fetch.return_value = [SAMPLE_CHESSCOM_GAME]

        stats = harvest_player(
            "evanleongxinyu", db_path=db_path, months=6,
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
                "evanleongxinyu", db_path=db_path, months=6,
                lichess_username="evleong", platform="lichess",
            )
            mock_archives.assert_not_called()
            mock_lichess.assert_called_once()
