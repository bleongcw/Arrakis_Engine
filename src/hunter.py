# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Hunter Mode — opponent prep.

Fetches a specific opponent's recent public games from chess.com or
lichess (without running Stockfish — too slow for opponent prep) and
computes their opening profile so the player can prepare against them.

Architecture (v1.4.4):
    fetch  → opponent_games (sliding window, dedup on game_url)
          → compute_opponent_profile (aggregate + top-5 reps per opening)
          → opponent_cache (24h profile cache for fast page loads)

Output structure mirrors the v1.4.0 Self-Analysis components but
labels are flipped:
- Their LOSSES become OUR weaknesses-to-exploit ("target these")
- Their WINS become lines to AVOID ("don't walk into these")

Each opening entry now includes up to 5 representative PGNs so the UI
can render a step-through mini-board of actual games where the
opponent had that outcome.
"""
from __future__ import annotations

import io
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import chess.pgn

# Reuse the platform-specific fetch + parse helpers from harvester.
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
    _lichess_extract_header,
    LICHESS_API_BASE,
)
from src.models import get_connection
from src.patterns import _get_opening_name

logger = logging.getLogger(__name__)

# How long the recomputed profile JSON is considered fresh before
# triggering a re-fetch + re-aggregate. Independent of the underlying
# accumulating game cache (which never expires — only prunes).
DEFAULT_TTL_HOURS = 24

# Sliding-window default. Games older than this are pruned on each fetch.
# Configurable via config.yaml `features.hunter_lookback_months`.
DEFAULT_LOOKBACK_MONTHS = 6

# How many representative PGNs to surface per (opening, outcome) for the
# expand-on-click UI in Hunt Mode. 5 is enough to see variety; more would
# bloat the cached profile JSON.
MAX_REPS_PER_OPENING = 5


# ── Platform-specific fetch ────────────────────────────────────────────────


def _extract_pgn_header(pgn_text: str, header: str) -> str | None:
    """Generic PGN header extractor. Returns None if missing."""
    return _lichess_extract_header(pgn_text, header)


def _extract_eco(pgn_text: str) -> str | None:
    """Pull the ECO code out of PGN headers. Both chess.com and lichess
    set this on most modern games."""
    eco = _extract_pgn_header(pgn_text, "ECO")
    return eco.strip().upper() if eco else None


def _normalize_date(raw: str | None) -> str | None:
    """Normalize a date string to ISO `YYYY-MM-DD`. Accepts chess.com's
    `2026.04.20` and lichess's `2026.04.20` and ISO already-formatted
    inputs. Returns None on failure."""
    if not raw:
        return None
    raw = raw.strip()
    if not raw or raw == "?":
        return None
    # chess.com / lichess use dots as separators
    raw = raw.replace(".", "-")
    # Some games have just a year-month
    parts = raw.split(" ")[0].split("-")
    if len(parts) != 3:
        return None
    try:
        y, m, d = parts[0], parts[1].zfill(2), parts[2].zfill(2)
        return f"{y}-{m}-{d}"
    except Exception:
        return None


def _fetch_chesscom_opponent_games(
    username: str, lookback_months: int
) -> list[dict]:
    """Pull the opponent's recent chess.com games as enriched dicts.

    chess.com's API requires lowercase usernames in the URL path —
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
            game_url = g.get("url")
            date_played = _normalize_date(_extract_pgn_header(pgn, "Date"))
            opening_name = _get_opening_name(pgn)
            eco = _extract_eco(pgn)
            games.append({
                "pgn": pgn,
                "player_color": color,
                "result": result,
                "game_url": game_url,
                "date_played": date_played,
                "opening_name": opening_name,
                "eco": eco,
            })
    return games


def _fetch_lichess_opponent_games(
    username: str, lookback_months: int
) -> list[dict]:
    """Pull the opponent's recent lichess games. Same enriched dict shape
    as the chess.com path."""
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
            "game_url": _lichess_extract_game_url(pgn_text),
            "date_played": _lichess_extract_date(pgn_text),
            "opening_name": _get_opening_name(pgn_text),
            "eco": _extract_eco(pgn_text),
        })
    return games


def fetch_opponent_games(
    username: str, platform: str,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
) -> list[dict]:
    """Fetch the opponent's recent games from chess.com or lichess.

    Returns a list of enriched game dicts:
        {pgn, player_color, result, game_url, date_played,
         opening_name, eco}

    Empty list on any failure (network, unknown user, etc.).
    """
    p = (platform or "").lower().strip()
    if p in ("chess.com", "chesscom", "chess_com"):
        return _fetch_chesscom_opponent_games(username, lookback_months)
    if p in ("lichess", "lichess.org"):
        return _fetch_lichess_opponent_games(username, lookback_months)
    raise ValueError(f"Unknown platform: {platform!r}. "
                     "Expected 'chess.com' or 'lichess'.")


# ── Accumulating game cache (v1.4.4) ─────────────────────────────────────


def _normalize_platform(platform: str) -> str:
    p = (platform or "").lower().strip()
    if p in ("chess.com", "chesscom", "chess_com"):
        return "chess.com"
    if p in ("lichess", "lichess.org"):
        return "lichess"
    return p


def _latest_cached_date(conn, username: str, platform: str) -> str | None:
    """The most recent `date_played` we already have for this opponent.
    Used as the fetch-since cutoff so we don't re-pull games we have."""
    row = conn.execute(
        "SELECT MAX(date_played) AS d FROM opponent_games "
        "WHERE username = ? AND platform = ?",
        (username.lower(), platform),
    ).fetchone()
    return row["d"] if row else None


def _insert_games(conn, username: str, platform: str,
                  games: list[dict]) -> int:
    """Insert new games into opponent_games, dedup on game_url.
    Returns the count actually inserted (excludes IGNOREd duplicates)."""
    inserted = 0
    for g in games:
        try:
            cur = conn.execute(
                """INSERT OR IGNORE INTO opponent_games
                   (username, platform, game_url, pgn, player_color, result,
                    opening_name, eco, date_played)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    username.lower(), platform,
                    g.get("game_url"), g["pgn"],
                    g.get("player_color"), g.get("result"),
                    g.get("opening_name"), g.get("eco"),
                    g.get("date_played"),
                ),
            )
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            logger.warning("[hunter] insert failed for game: %s", e)
            continue
    conn.commit()
    return inserted


def _prune_old_games(conn, username: str, platform: str,
                     lookback_months: int) -> int:
    """Delete games older than `lookback_months`. Sliding window.

    Games with NULL date_played are KEPT — pruning them would silently
    discard valid games when a platform omits the Date header (rare
    but happens on some old chess.com PGNs)."""
    cutoff = (datetime.now() - timedelta(days=lookback_months * 30)
              ).strftime("%Y-%m-%d")
    cur = conn.execute(
        "DELETE FROM opponent_games "
        "WHERE username = ? AND platform = ? "
        "  AND date_played IS NOT NULL "
        "  AND date_played < ?",
        (username.lower(), platform, cutoff),
    )
    conn.commit()
    return cur.rowcount


def _apply_cap(conn, username: str, platform: str,
               max_games: int | None) -> int:
    """If `max_games` is set, keep only the most-recent N. Returns deleted."""
    if not max_games or max_games <= 0:
        return 0
    cur = conn.execute(
        """DELETE FROM opponent_games
           WHERE username = ? AND platform = ? AND id NOT IN (
               SELECT id FROM opponent_games
               WHERE username = ? AND platform = ?
               ORDER BY date_played DESC NULLS LAST, id DESC
               LIMIT ?
           )""",
        (username.lower(), platform, username.lower(), platform, max_games),
    )
    conn.commit()
    return cur.rowcount


def _load_cached_games(conn, username: str, platform: str) -> list[dict]:
    """Return all accumulated games for this opponent as dicts."""
    rows = conn.execute(
        "SELECT pgn, player_color, result, game_url, date_played, "
        "       opening_name, eco "
        "FROM opponent_games "
        "WHERE username = ? AND platform = ? "
        "ORDER BY date_played DESC NULLS LAST, id DESC",
        (username.lower(), platform),
    ).fetchall()
    return [dict(r) for r in rows]


def accumulate_opponent_games(
    username: str, platform: str,
    db_path: str | None = None,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
    max_games: int | None = None,
) -> list[dict]:
    """Refresh the opponent_games cache then return all accumulated games.

    Flow:
        1. Determine cutoff = max(latest_cached_date, now - lookback_months)
        2. Fetch games newer than cutoff
        3. Insert with INSERT OR IGNORE (dedup on game_url)
        4. Prune by sliding window
        5. Apply hard cap if configured
        6. Return the full accumulated set
    """
    conn = get_connection(db_path)
    platform = _normalize_platform(platform)
    try:
        # Step 1: compute fetch lookback. If we already have some games,
        # the "since" cutoff is the latest cached date — much cheaper than
        # re-pulling all 6 months.
        latest = _latest_cached_date(conn, username, platform)
        sliding_cutoff = (datetime.now() -
                          timedelta(days=lookback_months * 30))
        if latest:
            try:
                latest_dt = datetime.strptime(latest, "%Y-%m-%d")
                # Fetch from latest if recent enough, else from sliding cutoff
                # Add a 1-day overlap to catch races.
                fetch_since = max(
                    latest_dt - timedelta(days=1),
                    sliding_cutoff,
                )
            except ValueError:
                fetch_since = sliding_cutoff
        else:
            fetch_since = sliding_cutoff

        months_to_fetch = max(
            1,
            int((datetime.now() - fetch_since).days / 30) + 1,
        )

        # Step 2-3: fetch + insert
        fetched = fetch_opponent_games(username, platform,
                                       lookback_months=months_to_fetch)
        inserted = _insert_games(conn, username, platform, fetched)
        logger.info(
            "[hunter] %s/%s: fetched %d games (months=%d), inserted %d new",
            username, platform, len(fetched), months_to_fetch, inserted,
        )

        # Step 4-5: prune
        pruned_window = _prune_old_games(
            conn, username, platform, lookback_months,
        )
        pruned_cap = _apply_cap(conn, username, platform, max_games)
        if pruned_window or pruned_cap:
            logger.info(
                "[hunter] %s/%s: pruned %d (window) + %d (cap)",
                username, platform, pruned_window, pruned_cap,
            )

        # Step 6: return the full accumulated set
        return _load_cached_games(conn, username, platform)
    finally:
        conn.close()


# ── Profile computation ──────────────────────────────────────────────────


def _aggregate(games: list[dict], outcome: str) -> dict:
    """Group opponent games by opening + color, filter to one outcome.
    Each opening entry includes up to MAX_REPS_PER_OPENING representative
    games (most recent first) so the UI can render mini-board step-through.
    """
    def _by_color(game_list: list[dict]) -> list[dict]:
        by_opening: dict[str, dict] = defaultdict(lambda: {
            "total": 0, "wins": 0, "losses": 0, "draws": 0,
            "eco": None,
            "outcome_games": [],   # list of full dicts for the outcome
        })
        for g in game_list:
            name = g.get("opening_name") or _get_opening_name(g["pgn"])
            entry = by_opening[name]
            entry["total"] += 1
            if entry["eco"] is None and g.get("eco"):
                entry["eco"] = g["eco"]
            if g["result"] == "win":
                entry["wins"] += 1
            elif g["result"] == "loss":
                entry["losses"] += 1
            else:
                entry["draws"] += 1
            if g["result"] == outcome:
                entry["outcome_games"].append(g)

        out = []
        for name, e in by_opening.items():
            outcome_count = e["wins"] if outcome == "win" else e["losses"]
            if outcome_count == 0:
                continue
            if e["total"] < 2:
                continue
            rate = round(outcome_count / e["total"] * 100, 1)
            # Sort outcome games newest-first; cap at MAX_REPS_PER_OPENING
            e["outcome_games"].sort(
                key=lambda g: (g.get("date_played") or "", g.get("game_url") or ""),
                reverse=True,
            )
            reps = []
            for rg in e["outcome_games"][:MAX_REPS_PER_OPENING]:
                reps.append({
                    "pgn": rg["pgn"],
                    "date_played": rg.get("date_played"),
                    "opponent_color": rg.get("player_color"),
                    "game_url": rg.get("game_url"),
                })
            out.append({
                "name": name,
                "eco": e["eco"],
                "total": e["total"],
                "wins": e["wins"],
                "losses": e["losses"],
                "draws": e["draws"],
                "rate": rate,
                "representative_games": reps,
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
    """Compute the opponent's opening profile from accumulated games."""
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


# ── Profile cache (24h JSON cache for fast page loads) ───────────────────


def get_cached_profile(
    conn, username: str, platform: str, ttl_hours: int = DEFAULT_TTL_HOURS,
) -> dict | None:
    """Return the cached profile JSON if fresh, else None."""
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

    if datetime.now() - fetched > timedelta(hours=ttl_hours):
        return None

    try:
        return json.loads(row["profile_json"])
    except json.JSONDecodeError:
        return None


def set_cached_profile(
    conn, username: str, platform: str, profile: dict,
) -> None:
    """Upsert the cached profile JSON."""
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


# ── Public API ────────────────────────────────────────────────────────────


def get_or_fetch_profile(
    username: str, platform: str,
    db_path: str | None = None,
    force_refresh: bool = False,
    ttl_hours: int = DEFAULT_TTL_HOURS,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
    max_games: int | None = None,
) -> dict:
    """High-level entry point used by the dashboard API.

    Cache strategy (v1.4.4):
        1. If a fresh profile JSON is in opponent_cache (< 24h old) and
           force_refresh is False, return it directly.
        2. Otherwise: refresh the accumulating game cache (fetch-since +
           prune), recompute the profile from the accumulated set, store
           the JSON in opponent_cache, return.

    Returns the profile with a `meta` key carrying:
        {cached: bool, fetched_at: str|None, platform: str,
         username: str, accumulated_games: int}
    """
    conn = get_connection(db_path)
    platform_norm = _normalize_platform(platform)
    try:
        if not force_refresh:
            cached = get_cached_profile(conn, username, platform_norm, ttl_hours)
            if cached is not None:
                cached["meta"] = {
                    "cached": True,
                    "platform": platform_norm,
                    "username": username,
                    "fetched_at": _last_cache_fetched_at(
                        conn, username, platform_norm,
                    ),
                    "accumulated_games": cached.get("total_games", 0),
                }
                return cached
    finally:
        conn.close()

    # Refresh path: accumulate fresh games then recompute the profile.
    logger.info("[hunter] Refreshing %s (%s) — lookback=%dmo cap=%s",
                username, platform_norm, lookback_months, max_games)
    accumulated = accumulate_opponent_games(
        username, platform_norm, db_path=db_path,
        lookback_months=lookback_months, max_games=max_games,
    )
    profile = compute_opponent_profile(accumulated)

    conn = get_connection(db_path)
    try:
        set_cached_profile(conn, username, platform_norm, profile)
        profile["meta"] = {
            "cached": False,
            "platform": platform_norm,
            "username": username,
            "fetched_at": _last_cache_fetched_at(
                conn, username, platform_norm,
            ),
            "accumulated_games": len(accumulated),
        }
    finally:
        conn.close()
    return profile


def _last_cache_fetched_at(conn, username: str, platform: str) -> str | None:
    row = conn.execute(
        "SELECT fetched_at FROM opponent_cache "
        "WHERE username = ? AND platform = ?",
        (username.lower(), platform),
    ).fetchone()
    return row["fetched_at"] if row else None
