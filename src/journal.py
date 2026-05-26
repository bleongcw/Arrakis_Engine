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
