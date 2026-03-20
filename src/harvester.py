"""Chess.com game harvester for ArrakisEngine.

Fetches monthly archives from the chess.com public API,
filters to the configured lookback period, deduplicates
against the database, and stores new games.
"""

import logging
import time
from datetime import datetime, timedelta

import chess.pgn
import io
import requests

from src.models import get_connection, init_db, ensure_player

logger = logging.getLogger(__name__)

CHESS_COM_BASE = "https://api.chess.com/pub/player"
USER_AGENT = "ArrakisEngine/1.0 (contact: bernardleong@dorje.ai)"
REQUEST_HEADERS = {"User-Agent": USER_AGENT}


def get_archive_urls(username: str) -> list[str]:
    """Fetch the list of monthly archive URLs for a player."""
    url = f"{CHESS_COM_BASE}/{username}/games/archives"
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json().get("archives", [])


def filter_recent_archives(archive_urls: list[str], months: int = 6) -> list[str]:
    """Filter archive URLs to only include the last N months."""
    cutoff = datetime.now() - timedelta(days=months * 30)
    recent = []
    for url in archive_urls:
        # URL format: .../games/YYYY/MM
        parts = url.rstrip("/").split("/")
        year, month = int(parts[-2]), int(parts[-1])
        archive_date = datetime(year, month, 1)
        if archive_date >= cutoff.replace(day=1):
            recent.append(url)
    return recent


def fetch_games_from_archive(url: str) -> list[dict]:
    """Fetch all games from a single monthly archive."""
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.json().get("games", [])


def determine_player_side(game: dict, username: str) -> tuple[str, int | None, int | None]:
    """Determine which color the player was and extract ratings.

    Returns (color, player_rating, opponent_rating).
    """
    white = game.get("white", {})
    black = game.get("black", {})
    white_user = white.get("username", "").lower()
    black_user = black.get("username", "").lower()

    if white_user == username.lower():
        return "white", white.get("rating"), black.get("rating")
    elif black_user == username.lower():
        return "black", black.get("rating"), white.get("rating")
    else:
        raise ValueError(f"Player {username} not found in game")


def determine_result(game: dict, username: str) -> str:
    """Determine win/loss/draw from the player's perspective."""
    white = game.get("white", {})
    black = game.get("black", {})
    white_user = white.get("username", "").lower()

    if white_user == username.lower():
        player_result = white.get("result", "")
    else:
        player_result = black.get("result", "")

    if player_result == "win":
        return "win"
    elif player_result in ("checkmated", "timeout", "resigned", "abandoned",
                           "kingofthehill", "threecheck", "timevsinsufficient",
                           "bughousepartnerlose"):
        return "loss"
    else:
        # stalemate, insufficient, 50move, repetition, agreed, etc.
        return "draw"


def harvest_player(username: str, db_path: str | None = None,
                   months: int = 6) -> dict:
    """Harvest games for a single player.

    Returns a dict with counts: {total, new, skipped, errors}.
    """
    conn = init_db(db_path)
    player_id = ensure_player(conn, username)

    archive_urls = get_archive_urls(username)
    recent_urls = filter_recent_archives(archive_urls, months)

    logger.info("Found %d archives for %s (%d within last %d months)",
                len(archive_urls), username, len(recent_urls), months)

    stats = {"total": 0, "new": 0, "skipped": 0, "errors": 0}

    for url in recent_urls:
        logger.info("Fetching archive: %s", url)
        try:
            games = fetch_games_from_archive(url)
        except requests.RequestException as e:
            logger.error("Failed to fetch %s: %s", url, e)
            stats["errors"] += 1
            continue

        for game in games:
            stats["total"] += 1
            game_url = game.get("url", "")
            pgn_text = game.get("pgn", "")

            if not game_url or not pgn_text:
                stats["errors"] += 1
                continue

            # Check for duplicate
            existing = conn.execute(
                "SELECT id FROM games WHERE game_url = ?", (game_url,)
            ).fetchone()
            if existing:
                stats["skipped"] += 1
                continue

            try:
                color, player_rating, opponent_rating = determine_player_side(game, username)
                result = determine_result(game, username)

                # Extract date from game end_time or PGN
                end_time = game.get("end_time")
                if end_time:
                    date_played = datetime.fromtimestamp(end_time).strftime("%Y-%m-%d")
                else:
                    date_played = None

                conn.execute(
                    """INSERT INTO games
                    (player_id, game_url, pgn, player_color, player_rating,
                     opponent_rating, result, time_control, time_class, date_played)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (player_id, game_url, pgn_text, color, player_rating,
                     opponent_rating, result, game.get("time_control"),
                     game.get("time_class"), date_played),
                )
                stats["new"] += 1
            except Exception as e:
                logger.warning("Error processing game %s: %s", game_url, e)
                stats["errors"] += 1

        conn.commit()
        # Be polite — serial requests with small delay
        time.sleep(0.5)

    conn.close()
    logger.info("Harvest complete for %s: %s", username, stats)
    return stats
