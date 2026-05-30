# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Tournament Prep (v1.21.0) — multi-opponent Hunter Mode.

A `tournament` is a player-scoped, named roster of opponents for an
upcoming event. This module owns the roster CRUD (mirrors the
`src/journal.py` pattern: ValueError for client errors so the HTTP layer
can map to 400/404) and `compute_tournament_prep`, which aggregates the
Hunter Mode opponent profiles across the whole roster into a combined
view — opening targets/cautions + a field-wide tactical blind-spots
summary.

No opponent data is duplicated here: the roster references usernames; the
opening profiles + Deep Scan motifs live in the Hunter Mode caches
(`opponent_cache` / `opponent_games`). `compute_tournament_prep` reads
those CACHE-ONLY (no network, no Stockfish) — the "Prep Roster" background
job warms the profile cache first.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from src.models import init_db, get_connection
from src.hunter import (
    _normalize_platform,
    get_cached_profile,
    compute_opponent_motif_summary,
    get_deep_scan_status,
)
from src.patterns import _MOTIF_IDENTIFIERS, _dominant_phase

logger = logging.getLogger(__name__)

MAX_NAME_LEN = 200
MAX_NOTES_LEN = 2000

# v1.21.0: only surface an opening in the combined view when at least this
# many distinct opponents share it — keeps single-opponent noise out of the
# tournament headline. Overridable via config (features.tournament_min_shared).
DEFAULT_MIN_SHARED = 2


def _normalize_name(name: str | None) -> str:
    if name is None:
        raise ValueError("name is required")
    name = name.strip()
    if not name:
        raise ValueError("name cannot be empty")
    if len(name) > MAX_NAME_LEN:
        raise ValueError(f"name exceeds {MAX_NAME_LEN} characters")
    return name


def _clean_optional(value: str | None, cap: int, label: str) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > cap:
        raise ValueError(f"{label} exceeds {cap} characters")
    return value


# ── Roster CRUD ─────────────────────────────────────────────────────────


def create_tournament(player_id: int, name: str, *, event_date: str | None = None,
                      notes: str | None = None, db_path: str | None = None) -> dict:
    """Create a new (empty) tournament roster for a player."""
    name = _normalize_name(name)
    event_date = _clean_optional(event_date, 64, "event_date")
    notes = _clean_optional(notes, MAX_NOTES_LEN, "notes")

    conn = init_db(db_path)
    try:
        player = conn.execute(
            "SELECT id FROM players WHERE id = ?", (player_id,)
        ).fetchone()
        if not player:
            raise ValueError(f"Player {player_id} not found")
        cur = conn.execute(
            """INSERT INTO tournaments (player_id, name, event_date, notes)
            VALUES (?, ?, ?, ?)""",
            (player_id, name, event_date, notes),
        )
        new_id = cur.lastrowid
        conn.commit()
        logger.info("Created tournament id=%d for player %d (%s)",
                    new_id, player_id, name)
        return get_tournament(new_id, db_path=db_path)
    finally:
        conn.close()


def list_tournaments(player_id: int, db_path: str | None = None) -> list[dict]:
    """List a player's tournaments (newest first) with opponent counts."""
    conn = init_db(db_path)
    try:
        rows = conn.execute(
            """SELECT t.id, t.player_id, t.name, t.event_date, t.notes,
                      t.created_at, t.updated_at,
                      (SELECT COUNT(*) FROM tournament_opponents o
                       WHERE o.tournament_id = t.id) AS opponent_count
               FROM tournaments t
               WHERE t.player_id = ?
               ORDER BY COALESCE(t.event_date, t.created_at) DESC, t.id DESC""",
            (player_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_tournament(tournament_id: int, db_path: str | None = None) -> dict:
    """Return one tournament + its opponent roster. Raises ValueError if
    the tournament doesn't exist."""
    conn = init_db(db_path)
    try:
        row = conn.execute(
            """SELECT id, player_id, name, event_date, notes,
                      created_at, updated_at
               FROM tournaments WHERE id = ?""",
            (tournament_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Tournament {tournament_id} not found")
        opponents = conn.execute(
            """SELECT id, username, platform, seed, added_at
               FROM tournament_opponents
               WHERE tournament_id = ?
               ORDER BY COALESCE(seed, 999999), id""",
            (tournament_id,),
        ).fetchall()
        result = dict(row)
        result["opponents"] = [dict(o) for o in opponents]
        return result
    finally:
        conn.close()


def update_tournament(tournament_id: int, *, name: str | None = None,
                      event_date: str | None = None, notes: str | None = None,
                      db_path: str | None = None) -> dict:
    """Update mutable fields of a tournament. Only provided fields change."""
    conn = init_db(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM tournaments WHERE id = ?", (tournament_id,)
        ).fetchone()
        if not existing:
            raise ValueError(f"Tournament {tournament_id} not found")

        sets, params = [], []
        if name is not None:
            sets.append("name = ?")
            params.append(_normalize_name(name))
        if event_date is not None:
            sets.append("event_date = ?")
            params.append(_clean_optional(event_date, 64, "event_date"))
        if notes is not None:
            sets.append("notes = ?")
            params.append(_clean_optional(notes, MAX_NOTES_LEN, "notes"))
        if sets:
            sets.append("updated_at = datetime('now')")
            params.append(tournament_id)
            conn.execute(
                f"UPDATE tournaments SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            conn.commit()
        return get_tournament(tournament_id, db_path=db_path)
    finally:
        conn.close()


def delete_tournament(tournament_id: int, db_path: str | None = None) -> None:
    """Delete a tournament and its opponent rows."""
    conn = init_db(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM tournaments WHERE id = ?", (tournament_id,)
        ).fetchone()
        if not existing:
            raise ValueError(f"Tournament {tournament_id} not found")
        conn.execute(
            "DELETE FROM tournament_opponents WHERE tournament_id = ?",
            (tournament_id,),
        )
        conn.execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
        conn.commit()
        logger.info("Deleted tournament id=%d", tournament_id)
    finally:
        conn.close()


def add_opponent(tournament_id: int, username: str, *,
                 platform: str = "chess.com", seed: int | None = None,
                 db_path: str | None = None) -> dict:
    """Add an opponent to a tournament roster. De-dups on
    (tournament_id, username, platform) — re-adding the same opponent
    raises ValueError."""
    username = (username or "").strip()
    if not username:
        raise ValueError("opponent username is required")
    platform = _normalize_platform(platform)

    conn = init_db(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM tournaments WHERE id = ?", (tournament_id,)
        ).fetchone()
        if not existing:
            raise ValueError(f"Tournament {tournament_id} not found")
        dup = conn.execute(
            """SELECT id FROM tournament_opponents
               WHERE tournament_id = ? AND username = ? AND platform = ?""",
            (tournament_id, username.lower(), platform),
        ).fetchone()
        if dup:
            raise ValueError(
                f"{username} ({platform}) is already in this tournament"
            )
        cur = conn.execute(
            """INSERT INTO tournament_opponents
               (tournament_id, username, platform, seed)
               VALUES (?, ?, ?, ?)""",
            (tournament_id, username.lower(), platform, seed),
        )
        conn.execute(
            "UPDATE tournaments SET updated_at = datetime('now') WHERE id = ?",
            (tournament_id,),
        )
        conn.commit()
        row = conn.execute(
            """SELECT id, username, platform, seed, added_at
               FROM tournament_opponents WHERE id = ?""",
            (cur.lastrowid,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def remove_opponent(tournament_id: int, opponent_id: int,
                    db_path: str | None = None) -> None:
    """Remove one opponent row from a tournament."""
    conn = init_db(db_path)
    try:
        row = conn.execute(
            """SELECT id FROM tournament_opponents
               WHERE id = ? AND tournament_id = ?""",
            (opponent_id, tournament_id),
        ).fetchone()
        if not row:
            raise ValueError(
                f"Opponent {opponent_id} not found in tournament {tournament_id}"
            )
        conn.execute(
            "DELETE FROM tournament_opponents WHERE id = ?", (opponent_id,)
        )
        conn.execute(
            "UPDATE tournaments SET updated_at = datetime('now') WHERE id = ?",
            (tournament_id,),
        )
        conn.commit()
    finally:
        conn.close()


# ── Combined analysis ───────────────────────────────────────────────────


def _aggregate_openings(per_opponent: list[tuple[str, list[dict]]],
                        outcome: str, min_shared: int) -> list[dict]:
    """Group opening entries across opponents by (name, color).

    `per_opponent` is a list of (username, opening_entries) where each
    entry is `{name, eco, color, total, wins, losses, ...}`. `outcome` is
    "loss" (targets — openings opponents lose) or "win" (cautions —
    openings opponents win). Returns rows shared by ≥ min_shared opponents,
    sorted by opponent_count desc then aggregate rate desc.
    """
    groups: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "total": 0, "wins": 0, "losses": 0, "eco": None, "opponents": set(),
    })
    for username, entries in per_opponent:
        for e in entries:
            key = (e["name"], e["color"])
            g = groups[key]
            g["total"] += e.get("total", 0)
            g["wins"] += e.get("wins", 0)
            g["losses"] += e.get("losses", 0)
            if g["eco"] is None and e.get("eco"):
                g["eco"] = e["eco"]
            g["opponents"].add(username)

    rows = []
    for (name, color), g in groups.items():
        count = len(g["opponents"])
        if count < min_shared:
            continue
        outcome_n = g["losses"] if outcome == "loss" else g["wins"]
        if outcome_n == 0:
            continue
        rate = round(outcome_n / g["total"] * 100, 1) if g["total"] else 0.0
        rows.append({
            "opening": name,
            "eco": g["eco"],
            "color": color,
            "opponent_count": count,
            "total_games": g["total"],
            "outcome_games": outcome_n,
            "agg_rate": rate,
            "opponents": sorted(g["opponents"]),
        })
    rows.sort(key=lambda r: (-r["opponent_count"], -r["agg_rate"]))
    return rows


def _field_blind_spots(motif_summaries: list[dict]) -> dict | None:
    """Sum per-opponent Deep-Scan motif summaries into a single field-level
    `motif_summary` (same shape `<MotifThemes>` renders). None when no
    opponent has been scanned."""
    if not motif_summaries:
        return None
    missed_by_phase = {m: {"opening": 0, "middlegame": 0, "endgame": 0}
                       for m in _MOTIF_IDENTIFIERS}
    found_total = {m: 0 for m in _MOTIF_IDENTIFIERS}
    total_critical = 0
    for ms in motif_summaries:
        total_critical += ms.get("total_critical_moves", 0)
        for e in ms.get("by_motif", []):
            motif = e.get("motif")
            if motif not in found_total:
                continue
            found_total[motif] += e.get("found", 0)
            for ph in ("opening", "middlegame", "endgame"):
                missed_by_phase[motif][ph] += (e.get("missed_by_phase") or {}).get(ph, 0)

    by_motif = []
    for motif in _MOTIF_IDENTIFIERS:
        m_phases = dict(missed_by_phase[motif])
        m = sum(m_phases.values())
        f = found_total[motif]
        denom = m + f
        by_motif.append({
            "motif": motif,
            "missed": m,
            "found": f,
            "miss_rate": round(m / denom * 100, 1) if denom else 0.0,
            "missed_by_phase": m_phases,
            "dominant_missed_phase": _dominant_phase(m_phases),
        })
    by_motif.sort(key=lambda e: (-e["missed"], -e["found"]))
    top = next((e for e in by_motif if e["missed"] > 0), None)
    return {
        "period_days": None,
        "total_critical_moves": total_critical,
        "by_motif": by_motif,
        "top_missed": top["motif"] if top else None,
        "top_missed_count": top["missed"] if top else 0,
        "top_missed_dominant_phase": top["dominant_missed_phase"] if top else None,
    }


def compute_tournament_prep(tournament_id: int, db_path: str | None = None,
                            min_shared: int = DEFAULT_MIN_SHARED) -> dict:
    """Aggregate the Hunter Mode profiles across a tournament roster.

    CACHE-ONLY: reads each opponent's cached opening profile + Deep-Scan
    motifs (no network, no Stockfish). Opponents without a cached profile
    are marked `pending` — the "Prep Roster" background job warms them.

    Returns the tournament + per-opponent summaries + combined
    `opening_targets` / `opening_cautions` + `field_blind_spots` +
    `scan_coverage`. Raises ValueError if the tournament doesn't exist.
    """
    tournament = get_tournament(tournament_id, db_path=db_path)
    opponents_meta = []
    weakness_rows: list[tuple[str, list[dict]]] = []
    strength_rows: list[tuple[str, list[dict]]] = []
    scanned_summaries: list[dict] = []
    scanned_count = 0

    conn = get_connection(db_path)
    try:
        for opp in tournament["opponents"]:
            username = opp["username"]
            platform = opp["platform"]
            profile = get_cached_profile(conn, username, platform)
            deep_scan = get_deep_scan_status(username, platform, db_path)
            motif_summary = (
                compute_opponent_motif_summary(username, platform, db_path)
                if deep_scan.get("analyzed_games", 0) > 0 else None
            )
            if motif_summary:
                scanned_summaries.append(motif_summary)
                scanned_count += 1

            if profile is None:
                opponents_meta.append({
                    "id": opp["id"], "username": username, "platform": platform,
                    "status": "pending", "summary": None, "deep_scan": deep_scan,
                })
                continue

            # Flatten weaknesses/strengths to per-color entries for aggregation.
            for color in ("white", "black"):
                for e in (profile.get("weaknesses") or {}).get(color, []):
                    weakness_rows.append((username, [{**e, "color": color}]))
                for e in (profile.get("strengths") or {}).get(color, []):
                    strength_rows.append((username, [{**e, "color": color}]))

            results = profile.get("results") or {}
            opponents_meta.append({
                "id": opp["id"], "username": username, "platform": platform,
                "status": "ready",
                "summary": {
                    "total_games": profile.get("total_games", 0),
                    "wins": results.get("wins", 0),
                    "losses": results.get("losses", 0),
                    "draws": results.get("draws", 0),
                    "win_rate": results.get("win_rate", 0.0),
                },
                "deep_scan": deep_scan,
            })
    finally:
        conn.close()

    # Flatten the per-(username, single-entry) tuples for the aggregator.
    def _flatten(rows):
        merged: dict[str, list[dict]] = defaultdict(list)
        for username, entries in rows:
            merged[username].extend(entries)
        return list(merged.items())

    opening_targets = _aggregate_openings(
        _flatten(weakness_rows), "loss", min_shared)
    opening_cautions = _aggregate_openings(
        _flatten(strength_rows), "win", min_shared)

    return {
        "tournament": {
            "id": tournament["id"], "name": tournament["name"],
            "event_date": tournament["event_date"], "notes": tournament["notes"],
        },
        "opponents": opponents_meta,
        "opening_targets": opening_targets,
        "opening_cautions": opening_cautions,
        "field_blind_spots": _field_blind_spots(scanned_summaries),
        "scan_coverage": {
            "scanned": scanned_count, "total": len(tournament["opponents"]),
        },
    }
