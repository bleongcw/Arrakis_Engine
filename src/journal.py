# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Journal helpers for parent-authored notes.

The `journal_entries` table was introduced in v1.10.0 for LLM-generated
coaching reviews. v1.12.0 adds parent notes — short text observations
the parent writes alongside the LLM reviews, surfaced in the same
chronological feed.

This module owns the CRUD for `kind='note'` entries. Reviews stay
immutable (managed by `compute_recent_form_review` in patterns.py);
notes can be created, edited, and deleted by the user.

Functions raise ``ValueError`` for client errors (validation failures,
unknown player, attempting to edit a non-note entry) so the HTTP layer
in `dashboard_server.py` can map them to 400/404 responses cleanly.
"""

from __future__ import annotations

import json
import logging

from src.models import init_db

logger = logging.getLogger(__name__)


# Maximum length of a note body, in characters. 4000 covers a generous
# multi-paragraph observation while keeping rows reasonable in SQLite and
# the JSON wire format. The UI enforces this as a soft limit too.
MAX_NOTE_BODY_LEN = 4000


def _normalize_body(body: str | None) -> str:
    """Trim whitespace; validate non-empty + within length cap.

    Raises ValueError with a user-facing message on failure.
    """
    if body is None:
        raise ValueError("body is required")
    body = body.strip()
    if not body:
        raise ValueError("body cannot be empty")
    if len(body) > MAX_NOTE_BODY_LEN:
        raise ValueError(
            f"body exceeds {MAX_NOTE_BODY_LEN} characters "
            f"(got {len(body)})"
        )
    return body


def create_note(
    player_id: int,
    body: str,
    *,
    platform: str = "chess.com",
    db_path: str | None = None,
) -> dict:
    """Insert a new note entry for the player.

    Returns the inserted row as a dict (matches the shape the
    GET /api/journal endpoint returns to clients).

    Raises ValueError on validation failure or unknown player.
    """
    body = _normalize_body(body)
    platform = (platform or "chess.com").strip() or "chess.com"

    conn = init_db(db_path)
    try:
        player = conn.execute(
            "SELECT id FROM players WHERE id = ?", (player_id,)
        ).fetchone()
        if not player:
            raise ValueError(f"Player {player_id} not found")

        cur = conn.execute(
            """INSERT INTO journal_entries
            (player_id, kind, platform, body, refs_json, provider,
             metadata_json, created_at)
            VALUES (?, 'note', ?, ?, NULL, NULL, NULL, datetime('now'))""",
            (player_id, platform, body),
        )
        new_id = cur.lastrowid
        conn.commit()

        row = conn.execute(
            "SELECT id, player_id, kind, platform, body, refs_json, provider, "
            "metadata_json, created_at FROM journal_entries WHERE id = ?",
            (new_id,),
        ).fetchone()
        logger.info("Created note id=%d for player %d (%d chars)",
                    new_id, player_id, len(body))
        return dict(row)
    finally:
        conn.close()


# v1.19.0: short, concrete drill prescriptions keyed by motif. Used by the
# auto-filed "priority weakness" journal alert so the parent sees an
# actionable next step, not just a diagnosis.
_MOTIF_DRILLS = {
    "fork": "before every capture, ask \"what does my knight/queen fork from here?\" — 10 fork puzzles a day",
    "pin": "scan for pins against the king and queen each move — 10 pin puzzles a day",
    "skewer": "look for skewers on the same rank, file, or diagonal — 10 skewer puzzles a day",
    "discovered_check": "spot pieces that unveil a check when they move — 10 discovered-attack puzzles a day",
    "mate_threat": "check for one-move mate threats before and after every move",
    "removing_defender": "ask \"what is defending this piece, and can I take it?\" each capture",
    "hanging_piece": "after every move, count whether each of your pieces is defended — slow down before moving",
    "trapped_piece": "before advancing a piece, check its escape squares so it can't get trapped",
    "back_rank_mate": "watch your back rank — give your king luft and check for back-rank mate every move",
    "deflection": "look for ways to pull a key defender off its square — 10 deflection puzzles a day",
    "overloaded_defender": "spot pieces doing two defensive jobs at once and attack the overload",
    "zugzwang": "in simple endgames, ask whether your opponent would rather not move at all",
}


def _humanize_motif(motif: str) -> str:
    """'hanging_piece' → 'hanging piece' for human-facing journal text."""
    return motif.replace("_", " ")


def _build_weakness_alert_body(motif: str, tier: str, missed_games: int,
                               streak: int, dominant_phase: str | None) -> str:
    """v1.19.0: human paragraph for an auto-filed priority-weakness alert."""
    label = _humanize_motif(motif)
    icon = "🔴" if tier == "priority" else "🟠"
    sentence = f"{icon} New {tier} weakness: {label} — missed in {missed_games} recent games"
    if streak >= 2:
        sentence += f", {streak} in a row"
    if dominant_phase:
        sentence += f", mostly in the {dominant_phase}"
    sentence += "."
    drill = _MOTIF_DRILLS.get(motif)
    if drill:
        sentence += f" Drill: {drill}."
    return sentence


def create_weakness_alert(
    conn,
    player_id: int,
    motif: str,
    tier: str,
    missed_games: int,
    streak: int,
    dominant_phase: str | None,
    *,
    platform: str = "chess.com",
    period_days: int = 30,
) -> dict | None:
    """v1.19.0: file a one-time 'priority weakness' journal entry.

    Reuses the journal_entries table with kind='weakness_alert'. The
    EXISTENCE of an open alert row for this motif within the window IS
    the fire-once state — so an ongoing weakness fires ONE entry per
    episode, not on every patterns run.

    De-dup: if a weakness_alert for the same motif was created within the
    last ``period_days``, this is a no-op and returns None. A different
    motif fires its own entry; an entry older than the window re-fires
    (re-flagging a relapsed weakness is intentional).

    Takes an OPEN connection (the caller — compute_player_patterns — owns
    it and commits/closes). Does not close the connection.
    """
    existing = conn.execute(
        """SELECT id FROM journal_entries
        WHERE player_id = ? AND kind = 'weakness_alert'
          AND json_extract(metadata_json, '$.motif') = ?
          AND created_at >= datetime('now', ?)
        LIMIT 1""",
        (player_id, motif, f"-{period_days} days"),
    ).fetchone()
    if existing:
        logger.info(
            "Weakness alert for player %d motif=%s already open within "
            "%dd window — skipping (fire-once)",
            player_id, motif, period_days,
        )
        return None

    body = _build_weakness_alert_body(
        motif, tier, missed_games, streak, dominant_phase
    )
    metadata = json.dumps({
        "motif": motif,
        "tier": tier,
        "missed_games": missed_games,
        "streak": streak,
        "dominant_phase": dominant_phase,
    })
    platform = (platform or "chess.com").strip() or "chess.com"

    cur = conn.execute(
        """INSERT INTO journal_entries
        (player_id, kind, platform, body, refs_json, provider,
         metadata_json, created_at)
        VALUES (?, 'weakness_alert', ?, ?, NULL, NULL, ?, datetime('now'))""",
        (player_id, platform, body, metadata),
    )
    new_id = cur.lastrowid
    conn.commit()

    row = conn.execute(
        "SELECT id, player_id, kind, platform, body, refs_json, provider, "
        "metadata_json, created_at FROM journal_entries WHERE id = ?",
        (new_id,),
    ).fetchone()
    logger.info("Filed weakness_alert id=%d for player %d (%s, %s)",
                new_id, player_id, motif, tier)
    return dict(row)


def update_note(
    entry_id: int,
    body: str,
    *,
    db_path: str | None = None,
) -> dict:
    """Update the body of a note entry.

    Reviews are immutable — attempting to update a non-note entry raises
    ValueError. Only the body is updatable; kind, platform, provider,
    and created_at stay locked so the timeline order can't be rewritten.

    Returns the updated row as a dict.
    """
    body = _normalize_body(body)

    conn = init_db(db_path)
    try:
        existing = conn.execute(
            "SELECT id, kind FROM journal_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if not existing:
            raise ValueError(f"Journal entry {entry_id} not found")
        if existing["kind"] != "note":
            raise ValueError(
                f"Cannot edit entry {entry_id}: kind is "
                f"'{existing['kind']}', only 'note' entries are editable"
            )

        conn.execute(
            "UPDATE journal_entries SET body = ? WHERE id = ?",
            (body, entry_id),
        )
        conn.commit()

        row = conn.execute(
            "SELECT id, player_id, kind, platform, body, refs_json, provider, "
            "metadata_json, created_at FROM journal_entries WHERE id = ?",
            (entry_id,),
        ).fetchone()
        logger.info("Updated note id=%d (%d chars)", entry_id, len(body))
        return dict(row)
    finally:
        conn.close()


def delete_note(entry_id: int, *, db_path: str | None = None) -> None:
    """Delete a note entry.

    Reviews are protected — attempting to delete a non-note entry raises
    ValueError. The parent should never accidentally delete an LLM
    coaching review through the note delete flow.
    """
    conn = init_db(db_path)
    try:
        existing = conn.execute(
            "SELECT id, kind FROM journal_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if not existing:
            raise ValueError(f"Journal entry {entry_id} not found")
        if existing["kind"] != "note":
            raise ValueError(
                f"Cannot delete entry {entry_id}: kind is "
                f"'{existing['kind']}', only 'note' entries are deletable"
            )

        conn.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
        conn.commit()
        logger.info("Deleted note id=%d", entry_id)
    finally:
        conn.close()
