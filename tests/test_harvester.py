"""Tests for src/harvester.py"""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.harvester import (
    filter_recent_archives,
    determine_player_side,
    determine_result,
    harvest_player,
)
from src.models import init_db


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


SAMPLE_GAME = {
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


class TestFilterRecentArchives:
    def test_filters_old_archives(self):
        urls = [
            "https://api.chess.com/pub/player/evan/games/2020/01",
            "https://api.chess.com/pub/player/evan/games/2026/01",
            "https://api.chess.com/pub/player/evan/games/2026/02",
            "https://api.chess.com/pub/player/evan/games/2026/03",
        ]
        recent = filter_recent_archives(urls, months=6)
        assert len(recent) >= 2
        assert urls[0] not in recent  # 2020 is definitely old

    def test_empty_list(self):
        assert filter_recent_archives([], months=6) == []


class TestDeterminePlayerSide:
    def test_white_player(self):
        color, pr, opp, opp_name = determine_player_side(SAMPLE_GAME, "evanleongxinyu")
        assert color == "white"
        assert pr == 1050
        assert opp == 980
        assert opp_name == "opponent1"

    def test_black_player(self):
        color, pr, opp, opp_name = determine_player_side(SAMPLE_GAME, "opponent1")
        assert color == "black"
        assert pr == 980
        assert opp == 1050
        assert opp_name == "evanleongxinyu"

    def test_case_insensitive(self):
        color, _, _, _ = determine_player_side(SAMPLE_GAME, "EvanLeongXinYu")
        assert color == "white"

    def test_unknown_player_raises(self):
        with pytest.raises(ValueError):
            determine_player_side(SAMPLE_GAME, "nobody")


class TestDetermineResult:
    def test_win(self):
        assert determine_result(SAMPLE_GAME, "evanleongxinyu") == "win"

    def test_loss(self):
        assert determine_result(SAMPLE_GAME, "opponent1") == "loss"

    def test_draw(self):
        draw_game = {
            "white": {"username": "a", "result": "stalemate"},
            "black": {"username": "b", "result": "stalemate"},
        }
        assert determine_result(draw_game, "a") == "draw"


class TestHarvestPlayer:
    @patch("src.harvester.get_archive_urls")
    @patch("src.harvester.fetch_games_from_archive")
    def test_stores_new_games(self, mock_fetch, mock_archives, db_path):
        mock_archives.return_value = [
            "https://api.chess.com/pub/player/evan/games/2026/03"
        ]
        mock_fetch.return_value = [SAMPLE_GAME]

        stats = harvest_player("evanleongxinyu", db_path=db_path, months=6)
        assert stats["new"] == 1
        assert stats["skipped"] == 0

    @patch("src.harvester.get_archive_urls")
    @patch("src.harvester.fetch_games_from_archive")
    def test_deduplicates(self, mock_fetch, mock_archives, db_path):
        mock_archives.return_value = [
            "https://api.chess.com/pub/player/evan/games/2026/03"
        ]
        mock_fetch.return_value = [SAMPLE_GAME]

        harvest_player("evanleongxinyu", db_path=db_path, months=6)
        stats = harvest_player("evanleongxinyu", db_path=db_path, months=6)
        assert stats["new"] == 0
        assert stats["skipped"] == 1
