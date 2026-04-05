# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Multi-platform game harvester for ArrakisEngine.

Fetches games from chess.com and lichess.org, deduplicates
against the database, and stores new games.
"""

import io
import logging
import re
import time
from datetime import datetime, timedelta

import chess.pgn
import requests

from src.models import get_connection, init_db, ensure_player

logger = logging.getLogger(__name__)

USER_AGENT = "ArrakisEngine/1.0 (contact: bernardleong@dorje.ai)"
REQUEST_HEADERS = {"User-Agent": USER_AGENT}


# ── Chess.com Harvester ─────────────────────────────────────────────

CHESS_COM_BASE = "https://api.chess.com/pub/player"


def _chesscom_get_archive_urls(username: str) -> list[str]:
    """Fetch the list of monthly archive URLs for a Chess.com player."""
    url = f"{CHESS_COM_BASE}/{username}/games/archives"
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json().get("archives", [])


def _chesscom_filter_recent(archive_urls: list[str], months: int = 6) -> list[str]:
    """Filter archive URLs to only include the last N months."""
    cutoff = datetime.now() - timedelta(days=months * 30)
    recent = []
    for url in archive_urls:
        parts = url.rstrip("/").split("/")
        year, month = int(parts[-2]), int(parts[-1])
        archive_date = datetime(year, month, 1)
        if archive_date >= cutoff.replace(day=1):
            recent.append(url)
    return recent


def _chesscom_fetch_archive(url: str) -> list[dict]:
    """Fetch all games from a single monthly archive."""
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.json().get("games", [])


def _chesscom_determine_side(game: dict, username: str) -> tuple[str, int | None, int | None, str | None]:
    """Determine player color and extract ratings from Chess.com game dict."""
    white = game.get("white", {})
    black = game.get("black", {})
    white_user = white.get("username", "").lower()
    black_user = black.get("username", "").lower()

    if white_user == username.lower():
        return "white", white.get("rating"), black.get("rating"), black.get("username")
    elif black_user == username.lower():
        return "black", black.get("rating"), white.get("rating"), white.get("username")
    else:
        raise ValueError(f"Player {username} not found in game")


def _chesscom_determine_result(game: dict, username: str) -> str:
    """Determine win/loss/draw from Chess.com result codes."""
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
        return "draw"


def harvest_chess_com(username: str, player_id: int, conn,
                      months: int = 6) -> dict:
    """Harvest games from Chess.com for a single player.

    Returns a dict with counts: {total, new, skipped, errors}.
    """
    archive_urls = _chesscom_get_archive_urls(username)
    recent_urls = _chesscom_filter_recent(archive_urls, months)

    logger.info("[chess.com] Found %d archives for %s (%d within last %d months)",
                len(archive_urls), username, len(recent_urls), months)

    stats = {"total": 0, "new": 0, "skipped": 0, "errors": 0}

    for url in recent_urls:
        logger.info("[chess.com] Fetching archive: %s", url)
        try:
            games = _chesscom_fetch_archive(url)
        except requests.RequestException as e:
            logger.error("[chess.com] Failed to fetch %s: %s", url, e)
            stats["errors"] += 1
            continue

        for game in games:
            stats["total"] += 1
            game_url = game.get("url", "")
            pgn_text = game.get("pgn", "")

            if not game_url or not pgn_text:
                stats["errors"] += 1
                continue

            existing = conn.execute(
                "SELECT id FROM games WHERE game_url = ?", (game_url,)
            ).fetchone()
            if existing:
                stats["skipped"] += 1
                continue

            try:
                color, player_rating, opponent_rating, opponent_username = _chesscom_determine_side(game, username)
                result = _chesscom_determine_result(game, username)

                end_time = game.get("end_time")
                if end_time:
                    date_played = datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    date_played = None

                conn.execute(
                    """INSERT INTO games
                    (player_id, game_url, pgn, player_color, player_rating,
                     opponent_rating, opponent_username, result, time_control,
                     time_class, date_played, platform)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'chess.com')""",
                    (player_id, game_url, pgn_text, color, player_rating,
                     opponent_rating, opponent_username, result,
                     game.get("time_control"), game.get("time_class"),
                     date_played),
                )
                stats["new"] += 1
            except Exception as e:
                logger.warning("[chess.com] Error processing game %s: %s", game_url, e)
                stats["errors"] += 1

        conn.commit()
        time.sleep(0.5)

    return stats


# ── Lichess Harvester ────────────────────────────────────────────────

LICHESS_API_BASE = "https://lichess.org/api"


def _lichess_extract_date(pgn_text: str) -> str | None:
    """Extract date+time from PGN [UTCDate]+[UTCTime] or [Date] headers."""
    date_match = re.search(r'\[UTCDate\s+"(\d{4}\.\d{2}\.\d{2})"\]', pgn_text)
    time_match = re.search(r'\[UTCTime\s+"(\d{2}:\d{2}:\d{2})"\]', pgn_text)
    if date_match:
        date_str = date_match.group(1).replace(".", "-")
        if time_match:
            return f"{date_str} {time_match.group(1)}"
        return date_str
    date_match = re.search(r'\[Date\s+"(\d{4}\.\d{2}\.\d{2})"\]', pgn_text)
    if date_match:
        return date_match.group(1).replace(".", "-")
    return None


def _lichess_extract_header(pgn_text: str, header: str) -> str | None:
    """Extract a PGN header value."""
    match = re.search(rf'\[{header}\s+"([^"]+)"\]', pgn_text)
    return match.group(1) if match else None


def _lichess_determine_side(pgn_text: str, username: str) -> tuple[str, int | None, int | None, str | None]:
    """Determine player color, ratings, and opponent from Lichess PGN headers."""
    white = _lichess_extract_header(pgn_text, "White") or ""
    black = _lichess_extract_header(pgn_text, "Black") or ""
    white_elo = _lichess_extract_header(pgn_text, "WhiteElo")
    black_elo = _lichess_extract_header(pgn_text, "BlackElo")

    white_rating = int(white_elo) if white_elo and white_elo.isdigit() else None
    black_rating = int(black_elo) if black_elo and black_elo.isdigit() else None

    if white.lower() == username.lower():
        return "white", white_rating, black_rating, black
    elif black.lower() == username.lower():
        return "black", black_rating, white_rating, white
    else:
        raise ValueError(f"Player {username} not found in Lichess game PGN")


def _lichess_determine_result(pgn_text: str, username: str) -> str:
    """Determine win/loss/draw from PGN Result header and player color."""
    result_str = _lichess_extract_header(pgn_text, "Result") or ""
    white = (_lichess_extract_header(pgn_text, "White") or "").lower()

    is_white = white == username.lower()

    if result_str == "1-0":
        return "win" if is_white else "loss"
    elif result_str == "0-1":
        return "loss" if is_white else "win"
    elif result_str == "1/2-1/2":
        return "draw"
    else:
        return "draw"


def _lichess_extract_time_control(pgn_text: str) -> tuple[str | None, str | None]:
    """Extract time control and classify it.

    Returns (time_control, time_class).
    """
    tc = _lichess_extract_header(pgn_text, "TimeControl")
    event = _lichess_extract_header(pgn_text, "Event") or ""

    # Lichess Event header contains the time class
    time_class = None
    event_lower = event.lower()
    if "ultrabullet" in event_lower:
        time_class = "bullet"
    elif "bullet" in event_lower:
        time_class = "bullet"
    elif "blitz" in event_lower:
        time_class = "blitz"
    elif "rapid" in event_lower:
        time_class = "rapid"
    elif "classical" in event_lower:
        time_class = "rapid"
    elif "correspondence" in event_lower:
        time_class = "daily"
    elif tc:
        # Fallback: parse time control string (e.g., "300+0")
        match = re.match(r"(\d+)\+(\d+)", tc)
        if match:
            base = int(match.group(1))
            if base < 120:
                time_class = "bullet"
            elif base < 600:
                time_class = "blitz"
            elif base <= 1800:
                time_class = "rapid"
            else:
                time_class = "daily"

    return tc, time_class


def _lichess_extract_game_url(pgn_text: str) -> str | None:
    """Extract the game URL from Lichess PGN [Site] header."""
    site = _lichess_extract_header(pgn_text, "Site")
    if site and "lichess.org" in site:
        return site
    return None


def harvest_lichess(username: str, player_id: int, conn,
                    months: int = 6) -> dict:
    """Harvest games from Lichess for a single player.

    Uses the Lichess PGN export API which returns all games as a PGN stream.
    Returns a dict with counts: {total, new, skipped, errors}.
    """
    cutoff = datetime.now() - timedelta(days=months * 30)
    since_ms = int(cutoff.timestamp() * 1000)

    url = f"{LICHESS_API_BASE}/games/user/{username}"
    params = {
        "since": since_ms,
        "pgnInJson": "false",
        "clocks": "true",
        "evals": "false",
        "opening": "true",
    }
    headers = {
        **REQUEST_HEADERS,
        "Accept": "application/x-chess-pgn",
    }

    logger.info("[lichess] Fetching games for %s since %s",
                username, cutoff.strftime("%Y-%m-%d"))

    try:
        resp = requests.get(url, params=params, headers=headers,
                            timeout=120, stream=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error("[lichess] Failed to fetch games for %s: %s", username, e)
        return {"total": 0, "new": 0, "skipped": 0, "errors": 1}

    # Lichess returns a PGN stream — split into individual games
    full_pgn = resp.text
    stats = {"total": 0, "new": 0, "skipped": 0, "errors": 0}

    # Parse PGN stream into individual games
    pgn_io = io.StringIO(full_pgn)
    while True:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break

        stats["total"] += 1
        pgn_text = str(game)

        game_url = _lichess_extract_game_url(pgn_text)
        if not game_url:
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
            color, player_rating, opponent_rating, opponent_username = _lichess_determine_side(pgn_text, username)
            result = _lichess_determine_result(pgn_text, username)
            date_played = _lichess_extract_date(pgn_text)
            time_control, time_class = _lichess_extract_time_control(pgn_text)

            conn.execute(
                """INSERT INTO games
                (player_id, game_url, pgn, player_color, player_rating,
                 opponent_rating, opponent_username, result, time_control,
                 time_class, date_played, platform)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'lichess')""",
                (player_id, game_url, pgn_text, color, player_rating,
                 opponent_rating, opponent_username, result,
                 time_control, time_class, date_played),
            )
            stats["new"] += 1
        except Exception as e:
            logger.warning("[lichess] Error processing game %s: %s", game_url, e)
            stats["errors"] += 1

    conn.commit()

    logger.info("[lichess] Harvest complete for %s: %s", username, stats)
    return stats


# ── Public API (called by main.py) ──────────────────────────────────

def harvest_player(username: str, db_path: str | None = None,
                   months: int = 6, lichess_username: str | None = None,
                   platform: str | None = None) -> dict:
    """Harvest games for a single player from configured platforms.

    Args:
        username: Chess.com username.
        lichess_username: Lichess username (optional).
        platform: Filter to a specific platform ('chess.com' or 'lichess').
                  If None, harvests from all configured platforms.

    Returns a combined dict with counts: {total, new, skipped, errors}.
    """
    conn = init_db(db_path)
    player_id = ensure_player(conn, username)

    combined = {"total": 0, "new": 0, "skipped": 0, "errors": 0}

    # Harvest from Chess.com
    if platform is None or platform == "chess.com":
        logger.info("Harvesting Chess.com games for %s", username)
        try:
            chesscom_stats = harvest_chess_com(username, player_id, conn, months)
            for k in combined:
                combined[k] += chesscom_stats[k]
        except Exception as e:
            logger.error("Chess.com harvest failed for %s: %s", username, e)
            combined["errors"] += 1

    # Harvest from Lichess
    if lichess_username and (platform is None or platform == "lichess"):
        logger.info("Harvesting Lichess games for %s (%s)", username, lichess_username)
        try:
            lichess_stats = harvest_lichess(lichess_username, player_id, conn, months)
            for k in combined:
                combined[k] += lichess_stats[k]
        except Exception as e:
            logger.error("Lichess harvest failed for %s: %s", username, e)
            combined["errors"] += 1

    conn.close()
    logger.info("Harvest complete for %s: %s", username, combined)
    return combined
