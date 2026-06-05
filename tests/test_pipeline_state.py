# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Cross-process pipeline lock tests.

The lock is backed by a single `pipeline_lock` DB row so independent processes
sharing one SQLite DB see each other's lock. We simulate two processes with two
explicit db_path values pointing at the same temp DB (the in-memory state mirror
is irrelevant — every assertion goes through the DB-backed primitives).
"""

from datetime import datetime, timedelta

import pytest

from src import models, pipeline_state


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "lock.db")
    models.init_db(path).close()
    # Reset the module-level mirror between tests so leakage from a prior test's
    # in-memory state can't mask a DB-driven result.
    pipeline_state._active_db_path = None
    with pipeline_state._lock:
        pipeline_state._state.update(
            {"task": None, "status": "idle", "result": None, "error": None}
        )
    return path


def test_second_start_blocked_while_held(db_path):
    assert pipeline_state.start_task("analyze", db_path=db_path) is True
    # A second acquisition (simulating another process) must fail.
    assert pipeline_state.start_task("harvest", db_path=db_path) is False
    assert pipeline_state.is_busy(db_path=db_path) is True
    assert pipeline_state.current_task(db_path=db_path) == "analyze"


def test_complete_releases_lock(db_path):
    assert pipeline_state.start_task("analyze", db_path=db_path) is True
    pipeline_state.complete_task({"games_analyzed": 3}, db_path=db_path)
    assert pipeline_state.is_busy(db_path=db_path) is False
    assert pipeline_state.current_task(db_path=db_path) is None
    # Lock is free again.
    assert pipeline_state.start_task("harvest", db_path=db_path) is True


def test_fail_releases_lock(db_path):
    assert pipeline_state.start_task("analyze", db_path=db_path) is True
    pipeline_state.fail_task("boom", db_path=db_path)
    assert pipeline_state.is_busy(db_path=db_path) is False
    assert pipeline_state.start_task("patterns", db_path=db_path) is True


def test_stale_heartbeat_reclaimed(db_path):
    assert pipeline_state.start_task("analyze", db_path=db_path) is True

    # Simulate a crashed holder: backdate the heartbeat well past the stale
    # window without ever releasing the lock.
    stale = (datetime.now()
             - timedelta(minutes=pipeline_state.STALE_LOCK_MINUTES + 5)).isoformat()
    conn = models.init_db(db_path)
    conn.execute(
        "UPDATE pipeline_lock SET heartbeat_at = ? WHERE id = 1", (stale,)
    )
    conn.commit()
    conn.close()

    # The stale lock no longer counts as busy and can be reclaimed.
    assert pipeline_state.is_busy(db_path=db_path) is False
    assert pipeline_state.start_task("harvest", db_path=db_path) is True
    assert pipeline_state.current_task(db_path=db_path) == "harvest"


def test_fresh_heartbeat_keeps_lock(db_path):
    assert pipeline_state.start_task("analyze", db_path=db_path) is True
    # A progress update refreshes the heartbeat; the lock stays held.
    pipeline_state.update_progress("working", db_path=db_path)
    assert pipeline_state.is_busy(db_path=db_path) is True
    assert pipeline_state.start_task("harvest", db_path=db_path) is False


def test_status_poll_does_not_block_under_write_lock(db_path):
    """v1.22.3 regression: /api/pipeline/status (get_state) must stay fast and
    not raise while a heavy task holds the DB write lock.

    Before the fix get_state() called init_db() on every poll — re-running
    executescript(SCHEMA) + CREATE INDEX (schema WRITES). During a running
    analyzer those writes contended for the write lock and blocked the full 30s
    busy_timeout → "database is locked" → the single-threaded server froze
    (socket hang up). A read-only SELECT in WAL mode never waits on the writer.
    """
    import time

    assert pipeline_state.start_task("analyze", db_path=db_path) is True

    # Simulate the analyzer holding the WAL write lock (uncommitted).
    writer = models.init_db(db_path)
    writer.execute("BEGIN IMMEDIATE")
    writer.execute(
        "INSERT INTO players (username, display_name) VALUES ('x', 'X')"
    )
    try:
        t0 = time.time()
        state = pipeline_state.get_state(db_path)  # must not raise / not hang
        elapsed = time.time() - t0
        assert elapsed < 3.0, f"status poll blocked {elapsed:.1f}s under write lock"
        assert state["status"] == "running"
        assert state["task"] == "analyze"
    finally:
        writer.rollback()
        writer.close()
