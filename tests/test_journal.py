"""v1.12.0: tests for src/journal.py — parent note CRUD."""

import pytest

from src.journal import (
    create_note,
    update_note,
    delete_note,
    create_weakness_alert,
    MAX_NOTE_BODY_LEN,
)
from src.models import init_db, ensure_player


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def player_id(db_path):
    conn = init_db(db_path)
    pid = ensure_player(conn, "evan", display_name="Evan", age=9, rating=1100)
    conn.close()
    return pid


def _count_entries(db_path, player_id, kind=None):
    conn = init_db(db_path)
    try:
        if kind:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM journal_entries WHERE player_id = ? AND kind = ?",
                (player_id, kind),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM journal_entries WHERE player_id = ?",
                (player_id,),
            ).fetchone()
        return row["n"]
    finally:
        conn.close()


class TestCreateNote:
    def test_inserts_a_note_row(self, db_path, player_id):
        entry = create_note(player_id, "Round 3 win.", db_path=db_path)
        assert entry["kind"] == "note"
        assert entry["body"] == "Round 3 win."
        assert entry["platform"] == "chess.com"
        assert entry["provider"] is None  # notes have no LLM provider
        assert _count_entries(db_path, player_id, kind="note") == 1

    def test_strips_whitespace(self, db_path, player_id):
        entry = create_note(player_id, "  padded  \n", db_path=db_path)
        assert entry["body"] == "padded"

    def test_accepts_custom_platform(self, db_path, player_id):
        entry = create_note(player_id, "x", platform="lichess", db_path=db_path)
        assert entry["platform"] == "lichess"

    def test_falls_back_to_chess_com_for_empty_platform(self, db_path, player_id):
        entry = create_note(player_id, "x", platform="", db_path=db_path)
        assert entry["platform"] == "chess.com"

    def test_rejects_empty_body(self, db_path, player_id):
        with pytest.raises(ValueError, match="empty"):
            create_note(player_id, "", db_path=db_path)
        with pytest.raises(ValueError, match="empty"):
            create_note(player_id, "   \n  \t  ", db_path=db_path)

    def test_rejects_none_body(self, db_path, player_id):
        with pytest.raises(ValueError, match="required"):
            create_note(player_id, None, db_path=db_path)  # type: ignore[arg-type]

    def test_rejects_oversize_body(self, db_path, player_id):
        with pytest.raises(ValueError, match="exceeds"):
            create_note(player_id, "x" * (MAX_NOTE_BODY_LEN + 1), db_path=db_path)

    def test_rejects_unknown_player(self, db_path):
        init_db(db_path)
        with pytest.raises(ValueError, match="not found"):
            create_note(99999, "x", db_path=db_path)


class TestUpdateNote:
    def test_updates_body(self, db_path, player_id):
        entry = create_note(player_id, "First.", db_path=db_path)
        updated = update_note(entry["id"], "Second.", db_path=db_path)
        assert updated["body"] == "Second."
        assert updated["id"] == entry["id"]

    def test_strips_whitespace_on_update(self, db_path, player_id):
        entry = create_note(player_id, "x", db_path=db_path)
        updated = update_note(entry["id"], "  trimmed  ", db_path=db_path)
        assert updated["body"] == "trimmed"

    def test_rejects_empty_body(self, db_path, player_id):
        entry = create_note(player_id, "x", db_path=db_path)
        with pytest.raises(ValueError, match="empty"):
            update_note(entry["id"], "", db_path=db_path)

    def test_rejects_oversize_body(self, db_path, player_id):
        entry = create_note(player_id, "x", db_path=db_path)
        with pytest.raises(ValueError, match="exceeds"):
            update_note(entry["id"], "x" * (MAX_NOTE_BODY_LEN + 1), db_path=db_path)

    def test_rejects_unknown_entry(self, db_path):
        init_db(db_path)
        with pytest.raises(ValueError, match="not found"):
            update_note(99999, "x", db_path=db_path)

    def test_rejects_non_note_kind(self, db_path, player_id):
        """Reviews are immutable. update_note must refuse to edit them."""
        conn = init_db(db_path)
        cur = conn.execute(
            """INSERT INTO journal_entries
            (player_id, kind, platform, body, created_at)
            VALUES (?, 'review', 'chess.com', 'a review', datetime('now'))""",
            (player_id,),
        )
        rid = cur.lastrowid
        conn.commit()
        conn.close()
        with pytest.raises(ValueError, match="only 'note' entries"):
            update_note(rid, "tampered", db_path=db_path)

        # Confirm the review body is unchanged
        conn = init_db(db_path)
        row = conn.execute(
            "SELECT body, kind FROM journal_entries WHERE id = ?", (rid,)
        ).fetchone()
        conn.close()
        assert row["body"] == "a review"
        assert row["kind"] == "review"


class TestDeleteNote:
    def test_removes_the_row(self, db_path, player_id):
        entry = create_note(player_id, "x", db_path=db_path)
        delete_note(entry["id"], db_path=db_path)
        assert _count_entries(db_path, player_id) == 0

    def test_rejects_unknown_entry(self, db_path):
        init_db(db_path)
        with pytest.raises(ValueError, match="not found"):
            delete_note(99999, db_path=db_path)

    def test_rejects_non_note_kind(self, db_path, player_id):
        """Reviews are protected. delete_note must refuse to remove them."""
        conn = init_db(db_path)
        cur = conn.execute(
            """INSERT INTO journal_entries
            (player_id, kind, platform, body, created_at)
            VALUES (?, 'review', 'chess.com', 'a review', datetime('now'))""",
            (player_id,),
        )
        rid = cur.lastrowid
        conn.commit()
        conn.close()
        with pytest.raises(ValueError, match="only 'note' entries"):
            delete_note(rid, db_path=db_path)

        # Confirm the review still exists
        conn = init_db(db_path)
        row = conn.execute(
            "SELECT id FROM journal_entries WHERE id = ?", (rid,)
        ).fetchone()
        conn.close()
        assert row is not None


class TestCreateWeaknessAlert:
    """v1.19.0: auto-filed priority-weakness journal entries with
    fire-once de-dup within the window."""

    def test_inserts_weakness_alert_row(self, db_path, player_id):
        conn = init_db(db_path)
        entry = create_weakness_alert(
            conn, player_id, "fork", "priority", 9, 3, "middlegame",
        )
        conn.close()
        assert entry is not None
        assert entry["kind"] == "weakness_alert"
        assert entry["provider"] is None
        assert "fork" in entry["body"]
        assert "9" in entry["body"]
        import json
        meta = json.loads(entry["metadata_json"])
        assert meta["motif"] == "fork"
        assert meta["tier"] == "priority"
        assert meta["missed_games"] == 9
        assert meta["streak"] == 3
        assert meta["dominant_phase"] == "middlegame"

    def test_body_includes_drill(self, db_path, player_id):
        conn = init_db(db_path)
        entry = create_weakness_alert(
            conn, player_id, "fork", "priority", 9, 3, "middlegame",
        )
        conn.close()
        assert "Drill:" in entry["body"]

    def test_second_call_same_motif_is_noop(self, db_path, player_id):
        conn = init_db(db_path)
        first = create_weakness_alert(
            conn, player_id, "fork", "priority", 9, 3, "middlegame",
        )
        second = create_weakness_alert(
            conn, player_id, "fork", "priority", 10, 4, "middlegame",
        )
        conn.close()
        assert first is not None
        assert second is None  # fire-once within window
        assert _count_entries(db_path, player_id, kind="weakness_alert") == 1

    def test_different_motif_fires_separately(self, db_path, player_id):
        conn = init_db(db_path)
        create_weakness_alert(
            conn, player_id, "fork", "priority", 9, 3, "middlegame",
        )
        other = create_weakness_alert(
            conn, player_id, "pin", "priority", 8, 0, None,
        )
        conn.close()
        assert other is not None
        assert _count_entries(db_path, player_id, kind="weakness_alert") == 2

    def test_entry_past_window_refires(self, db_path, player_id):
        conn = init_db(db_path)
        # Manually insert a fork alert dated 40 days ago (outside 30d window).
        import json
        conn.execute(
            """INSERT INTO journal_entries
            (player_id, kind, platform, body, refs_json, provider,
             metadata_json, created_at)
            VALUES (?, 'weakness_alert', 'chess.com', 'old alert', NULL, NULL,
                    ?, datetime('now', '-40 days'))""",
            (player_id, json.dumps({"motif": "fork", "tier": "priority"})),
        )
        conn.commit()
        # A new run should re-fire since the prior alert is outside the window.
        entry = create_weakness_alert(
            conn, player_id, "fork", "priority", 9, 3, "middlegame",
            period_days=30,
        )
        conn.close()
        assert entry is not None
        assert _count_entries(db_path, player_id, kind="weakness_alert") == 2
