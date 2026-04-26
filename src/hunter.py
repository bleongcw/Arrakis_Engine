# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Hunter Mode — opponent prep (v1.4.1).

Fetches a specific opponent's recent public games from chess.com or
lichess (without running Stockfish — too slow for opponent prep) and
computes their opening profile so the player can prepare against them.

Output structure mirrors the v1.4.0 Self-Analysis components but
labels are flipped:
- Their LOSSES become OUR weaknesses-to-exploit ("Hunt Mode: target these")
- Their WINS become lines to AVOID ("Don't walk into these")

Profiles are cached in the `opponent_cache` table with a 24-hour TTL
to respect the public APIs.
"""
from __future__ import annotations

import io
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import chess.pgn

# Reuse the platform-specific fetch + parse helpers from harvester. They
# are well-isolated and don't write to the games table.
from src.harvester import (
    REQUEST_HEADERS,
    _chesscom_get_archive_urls,
    _chesscom_filter_recent,
    _chesscom_fetch_archive,
    _chesscom_determine_side,
    _chesscom_determine_result,
    _lichess_determine_side,
    _lichess_determine_result,
    _lichess_extract_date,
    _lichess_extract_game_url,
    LICHESS_API_BASE,
)
from src.models import get_connection
from src.patterns import _get_opening_name

logger = logging.getLogger(__name__)

# How long an opponent profile is considered fresh before re-fetching.
DEFAULT_TTL_HOURS = 24

# How many months of history to pull. Shorter than the player harvester's
# default (6 months) — opponent prep cares about CURRENT form, not deep history.
DEFAULT_LOOKBACK_MONTHS = 3


# ── Fetch ──────────────────────────────────────────────────────────────────


def _fetch_chesscom_opponent_games(
    username: str, lookback_months: int
) -> list[dict]:
    """Pull the opponent's recent chess.com games as a list of normalized dicts.

    Each dict: {pgn, color, result, opening_name}, where color and result
    are from the OPPONENT's perspective (we are computing their profile).

    Note: chess.com's API requires lowercase usernames in the URL path —
    mixed-case names return a 301 redirect that `requests` follows but
    that wastes a round-trip. We normalize up front.
    """
    username = username.lower()
    games: list[dict] = []
    try:
        archive_urls = _chesscom_get_archive_urls(username)
    except Exception as e:
        logger.warning("[hunter chess.com] archive list failed for %s: %s",
                       username, e)
        return games

    recent = _chesscom_filter_recent(archive_urls, months=lookback_months)
    logger.info("[hunter chess.com] %s: %d archives in last %d months",
                username, len(recent), lookback_months)

    for url in recent:
        try:
            archive_games = _chesscom_fetch_archive(url)
        except Exception as e:
            logger.warning("[hunter chess.com] archive fetch failed %s: %s",
                           url, e)
            continue

        for g in archive_games:
            pgn = g.get("pgn")
            if not pgn:
                continue
            try:
                color, _r1, _r2, _opp = _chesscom_determine_side(g, username)
                result = _chesscom_determine_result(g, username)
            except Exception:
                continue
            games.append({
                "pgn": pgn,
                "player_color": color,    # opponent's color in this game
                "result": result,         # opponent's outcome
                # Opening name parsed lazily downstream
            })
    return games


def _fetch_lichess_opponent_games(
    username: str, lookback_months: int
) -> list[dict]:
    """Pull the opponent's recent lichess games. Same dict shape as chess.com.

    Lowercased for consistency with the chess.com path. Both side-detection
    helpers in harvester.py do `.lower()` on both sides of the comparison
    so this is safe.
    """
    import requests

    username = username.lower()
    cutoff = datetime.now() - timedelta(days=lookback_months * 30)
    since_ms = int(cutoff.timestamp() * 1000)

    url = f"{LICHESS_API_BASE}/games/user/{username}"
    params = {
        "since": since_ms,
        "pgnInJson": "false",
        "clocks": "false",
        "evals": "false",
        "opening": "true",
    }
    headers = {**REQUEST_HEADERS, "Accept": "application/x-chess-pgn"}

    games: list[dict] = []
    try:
        resp = requests.get(url, params=params, headers=headers,
                            timeout=120, stream=True)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("[hunter lichess] fetch failed for %s: %s", username, e)
        return games

    pgn_io = io.StringIO(resp.text)
    while True:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break
        pgn_text = str(game)
        try:
            color, _r1, _r2, _opp = _lichess_determine_side(pgn_text, username)
            result = _lichess_determine_result(pgn_text, username)
        except Exception:
            continue
        games.append({
            "pgn": pgn_text,
            "player_color": color,
            "result": result,
        })
    return games


def fetch_opponent_games(
    username: str, platform: str,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
) -> list[dict]:
    """Fetch the opponent's recent games from chess.com or lichess.

    `platform` is "chess.com" or "lichess" (case-insensitive).
    Returns a list of normalized game dicts. Empty list on any failure
    (network error, unknown user, etc.) — callers should handle gracefully.
    """
    p = (platform or "").lower().strip()
    if p in ("chess.com", "chesscom", "chess_com"):
        return _fetch_chesscom_opponent_games(username, lookback_months)
    if p in ("lichess", "lichess.org"):
        return _fetch_lichess_opponent_games(username, lookback_months)
    raise ValueError(f"Unknown platform: {platform!r}. "
                     "Expected 'chess.com' or 'lichess'.")


# ── Profile computation ──────────────────────────────────────────────────


def _aggregate(games: list[dict], outcome: str) -> dict:
    """Group opponent games by opening + color, filter to one outcome, return
    {white: [...], black: [...]} structure mirroring v1.4.0 Self-Analysis.

    `outcome` is "loss" (for "their weaknesses — we exploit") or "win"
    (for "their strengths — we avoid").
    """
    def _by_color(game_list: list[dict]) -> list[dict]:
        by_opening: dict[str, dict] = defaultdict(lambda: {
            "total": 0, "wins": 0, "losses": 0, "draws": 0,
        })
        for g in game_list:
            name = _get_opening_name(g["pgn"])
            entry = by_opening[name]
            entry["total"] += 1
            if g["result"] == "win":
                entry["wins"] += 1
            elif g["result"] == "loss":
                entry["losses"] += 1
            else:
                entry["draws"] += 1

        out = []
        for name, e in by_opening.items():
            outcome_count = e["wins"] if outcome == "win" else e["losses"]
            if outcome_count == 0:
                continue
            if e["total"] < 2:
                continue
            rate = round(outcome_count / e["total"] * 100, 1)
            out.append({
                "name": name,
                "total": e["total"],
                "wins": e["wins"],
                "losses": e["losses"],
                "draws": e["draws"],
                "rate": rate,
            })
        sort_key = (
            (lambda x: (-x["losses"], -x["rate"]))
            if outcome == "loss"
            else (lambda x: (-x["wins"], -x["rate"]))
        )
        out.sort(key=sort_key)
        return out[:10]

    white_games = [g for g in games if g["player_color"] == "white"]
    black_games = [g for g in games if g["player_color"] == "black"]
    return {"white": _by_color(white_games), "black": _by_color(black_games)}


def compute_opponent_profile(games: list[dict]) -> dict:
    """Compute the opponent's opening profile.

    Returns:
        {
          "total_games": int,
          "results": {"wins": int, "losses": int, "draws": int, "win_rate": float},
          "weaknesses": {"white": [...], "black": [...]},   # opponent's losses
          "strengths":  {"white": [...], "black": [...]},   # opponent's wins
        }

    "Weaknesses" are openings the opponent loses — these are opportunities
    for the player. "Strengths" are openings the opponent wins — these are
    lines for the player to avoid steering into.
    """
    if not games:
        return {
            "total_games": 0,
            "results": {"wins": 0, "losses": 0, "draws": 0, "win_rate": 0.0},
            "weaknesses": {"white": [], "black": []},
            "strengths": {"white": [], "black": []},
        }

    wins = sum(1 for g in games if g["result"] == "win")
    losses = sum(1 for g in games if g["result"] == "loss")
    draws = sum(1 for g in games if g["result"] == "draw")
    total = len(games)
    win_rate = round(wins / total * 100, 1) if total else 0.0

    return {
        "total_games": total,
        "results": {
            "wins": wins, "losses": losses, "draws": draws,
            "win_rate": win_rate,
        },
        "weaknesses": _aggregate(games, "loss"),
        "strengths": _aggregate(games, "win"),
    }


# ── Cache ──────────────────────────────────────────────────────────────────


def _normalize_platform(platform: str) -> str:
    """Canonicalize platform name for cache key consistency."""
    p = (platform or "").lower().strip()
    if p in ("chess.com", "chesscom", "chess_com"):
        return "chess.com"
    if p in ("lichess", "lichess.org"):
        return "lichess"
    return p


def get_cached_profile(
    conn, username: str, platform: str, ttl_hours: int = DEFAULT_TTL_HOURS,
) -> dict | None:
    """Return the cached profile if fresh, else None."""
    platform = _normalize_platform(platform)
    row = conn.execute(
        "SELECT profile_json, fetched_at FROM opponent_cache "
        "WHERE username = ? AND platform = ?",
        (username.lower(), platform),
    ).fetchone()
    if not row:
        return None

    try:
        fetched = datetime.strptime(row["fetched_at"], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None

    age = datetime.now() - fetched
    if age > timedelta(hours=ttl_hours):
        return None

    try:
        return json.loads(row["profile_json"])
    except json.JSONDecodeError:
        return None


def set_cached_profile(
    conn, username: str, platform: str, profile: dict,
) -> None:
    """Upsert the cached profile."""
    platform = _normalize_platform(platform)
    conn.execute(
        """INSERT INTO opponent_cache (username, platform, profile_json, fetched_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(username, platform) DO UPDATE SET
               profile_json = excluded.profile_json,
               fetched_at   = excluded.fetched_at""",
        (username.lower(), platform, json.dumps(profile)),
    )
    conn.commit()


def get_or_fetch_profile(
    username: str, platform: str,
    db_path: str | None = None,
    force_refresh: bool = False,
    ttl_hours: int = DEFAULT_TTL_HOURS,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
) -> dict:
    """High-level entry point: return a cached profile if fresh, else fetch
    fresh from the platform and update the cache.

    The returned profile dict always includes a top-level `meta` key with
    {cached: bool, fetched_at: str, platform: str, username: str} so the
    UI can show "Last updated …" stamps.
    """
    conn = get_connection(db_path)
    try:
        platform_norm = _normalize_platform(platform)

        if not force_refresh:
            cached = get_cached_profile(conn, username, platform_norm, ttl_hours)
            if cached is not None:
                cached["meta"] = {
                    "cached": True,
                    "platform": platform_norm,
                    "username": username,
                    "fetched_at": _last_fetched_at(conn, username, platform_norm),
                }
                return cached

        logger.info("[hunter] Fetching fresh profile for %s (%s)",
                    username, platform_norm)
        games = fetch_opponent_games(username, platform_norm, lookback_months)
        profile = compute_opponent_profile(games)
        set_cached_profile(conn, username, platform_norm, profile)
        profile["meta"] = {
            "cached": False,
            "platform": platform_norm,
            "username": username,
            "fetched_at": _last_fetched_at(conn, username, platform_norm),
        }
        return profile
    finally:
        conn.close()


def _last_fetched_at(conn, username: str, platform: str) -> str | None:
    row = conn.execute(
        "SELECT fetched_at FROM opponent_cache "
        "WHERE username = ? AND platform = ?",
        (username.lower(), platform),
    ).fetchone()
    return row["fetched_at"] if row else None
