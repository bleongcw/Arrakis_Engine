# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Cross-process pipeline task state store.

Tracks the currently running pipeline task (harvest, analyze, patterns, run_all).
Only one task may run at a time. The lock lives in a single `pipeline_lock` DB
row (see src/models.py) so that *independent processes* sharing the same SQLite
DB — e.g. the dashboard server and an external importer — see each other's lock
and never run Stockfish concurrently against the same database.

Acquisition is atomic: a single conditional UPDATE guarded by
`WHERE status != 'running'`. SQLite serializes writers, so two processes racing
to start a task can't both win — the loser's rowcount comes back 0.

A stale lock (heartbeat older than STALE_LOCK_MINUTES) can be reclaimed, mirroring
the analyzer's "reset stuck 'analyzing' games" recovery — this keeps a crashed
holder from wedging the pipeline forever.

The rich progress fields (progress text, detail, result, error) stay in an
in-process mirror; only the lock primitives (start/complete/fail/is_busy/
current_task) are backed by the DB row.
"""

import os
import socket
import sqlite3
import threading
from datetime import datetime, timedelta

from src.models import get_db_path, init_db, get_connection

# A lock held longer than this without a heartbeat is considered abandoned and
# may be reclaimed by another process. Mirrors analyzer.py's stuck-game reset.
STALE_LOCK_MINUTES = 15

_lock = threading.Lock()
_state = {
    "task": None,           # "harvest" | "analyze" | "patterns" | "run_all" | "coach" | None
    "status": "idle",       # "running" | "complete" | "error" | "idle"
    "progress": "",         # Human-readable progress text
    "detail": None,         # { current_step, total_steps, games_processed, games_total }
    "result": None,         # Set on completion
    "error": None,          # Set on error
    "started_at": None,
    "finished_at": None,
    "triggered_by": None,   # "manual" | "schedule" | None
}

# Resolved DB path of the most recent start_task(), reused as the default by the
# other primitives so callers only need to thread db_path through start_task().
_active_db_path: str | None = None


def _holder() -> str:
    """Identify this process for the lock's `holder` column."""
    return f"{socket.gethostname()}:{os.getpid()}"


def _resolve_db_path(db_path: str | None) -> str:
    if db_path is not None:
        return db_path
    return _active_db_path or get_db_path()


def start_task(task_name: str, triggered_by: str = "manual",
               db_path: str | None = None) -> bool:
    """Try to start a new task. Returns False if another (non-stale) task is
    running in *any* process sharing this DB.

    Acquires the lock with a single conditional UPDATE; SQLite serializes
    writers so the acquisition is atomic across processes.
    """
    global _active_db_path
    db_path = _resolve_db_path(db_path)
    _active_db_path = db_path

    now = datetime.now()
    now_iso = now.isoformat()
    stale_cutoff = (now - timedelta(minutes=STALE_LOCK_MINUTES)).isoformat()

    conn = init_db(db_path)
    try:
        cur = conn.execute(
            """UPDATE pipeline_lock
               SET status = 'running', task = ?, holder = ?,
                   started_at = ?, heartbeat_at = ?
               WHERE id = 1
                 AND (status != 'running' OR heartbeat_at IS NULL
                      OR heartbeat_at < ?)""",
            (task_name, _holder(), now_iso, now_iso, stale_cutoff),
        )
        conn.commit()
        acquired = cur.rowcount > 0
    finally:
        conn.close()

    if acquired:
        with _lock:
            _state["task"] = task_name
            _state["status"] = "running"
            _state["progress"] = "Starting..."
            _state["detail"] = None
            _state["result"] = None
            _state["error"] = None
            _state["started_at"] = now_iso
            _state["finished_at"] = None
            _state["triggered_by"] = triggered_by
    return acquired


def update_progress(progress_text: str, detail: dict | None = None,
                    db_path: str | None = None):
    """Update progress for the currently running task.

    Also bumps the DB heartbeat so a long-running task isn't mistaken for a
    stale lock and reclaimed by another process.
    """
    with _lock:
        _state["progress"] = progress_text
        if detail is not None:
            _state["detail"] = detail

    conn = init_db(_resolve_db_path(db_path))
    try:
        conn.execute(
            "UPDATE pipeline_lock SET heartbeat_at = ? WHERE id = 1 AND status = 'running'",
            (datetime.now().isoformat(),),
        )
        conn.commit()
    finally:
        conn.close()


def complete_task(result: dict, db_path: str | None = None):
    """Mark the current task as complete and release the lock."""
    with _lock:
        _state["status"] = "complete"
        _state["progress"] = "Done!"
        _state["result"] = result
        _state["finished_at"] = datetime.now().isoformat()
    _release(db_path, "complete")


def fail_task(error_msg: str, db_path: str | None = None):
    """Mark the current task as failed and release the lock."""
    with _lock:
        _state["status"] = "error"
        _state["progress"] = ""
        _state["error"] = error_msg
        _state["finished_at"] = datetime.now().isoformat()
    _release(db_path, "error")


def _release(db_path: str | None, status: str):
    """Set the lock row to a non-running status so it can be re-acquired."""
    conn = init_db(_resolve_db_path(db_path))
    try:
        conn.execute(
            "UPDATE pipeline_lock SET status = ?, heartbeat_at = ? WHERE id = 1",
            (status, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_state(db_path: str | None = None) -> dict:
    """Return a snapshot of the current state.

    Lock fields (status/task/holder/started_at) come from the DB row so the
    snapshot reflects a task running in another process; the rich progress
    fields come from this process's in-memory mirror.
    """
    with _lock:
        snapshot = dict(_state)

    row = _read_row(db_path)

    if row is not None:
        running = _is_running(row["status"], row["heartbeat_at"])
        if running:
            snapshot["status"] = "running"
            snapshot["task"] = row["task"]
            snapshot["started_at"] = row["started_at"]
            snapshot["holder"] = row["holder"]
        elif snapshot["status"] != "running":
            # No live lock anywhere — trust the DB's terminal status only if our
            # mirror has nothing more specific (complete/error with result/error).
            if snapshot["status"] == "idle":
                snapshot["status"] = row["status"] or "idle"
    return snapshot


def is_busy(db_path: str | None = None) -> bool:
    """Check if a task is currently running in any process sharing this DB."""
    row = _read_row(db_path)
    return row is not None and _is_running(row["status"], row["heartbeat_at"])


def current_task(db_path: str | None = None) -> str | None:
    """Return the name of the currently running task, or None."""
    row = _read_row(db_path)
    if row is not None and _is_running(row["status"], row["heartbeat_at"]):
        return row["task"]
    return None


def _read_row(db_path: str | None):
    """Read the lock row with a lightweight READ-ONLY connection.

    Critical perf/robustness fix (v1.22.3): the previous implementation called
    init_db() here — which re-runs executescript(SCHEMA) + CREATE INDEX +
    commits (schema WRITES) on *every* call. Since /api/pipeline/status polls
    this ~once/second, those writes contended with a running analyzer's per-move
    writes and blocked for the full 30s busy_timeout → "database is locked" →
    a single-threaded server froze (socket hang up). A plain SELECT in WAL mode
    never waits on the writer. We also cap the wait at 2s and swallow transient
    OperationalErrors (lock contention OR a not-yet-migrated DB), returning None
    so callers fall back to the in-memory mirror — the status poll must never
    block or raise.
    """
    try:
        conn = get_connection(_resolve_db_path(db_path))
    except sqlite3.OperationalError:
        return None
    try:
        conn.execute("PRAGMA busy_timeout=2000")
        return conn.execute(
            "SELECT task, status, holder, started_at, heartbeat_at "
            "FROM pipeline_lock WHERE id = 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def _is_running(status: str | None, heartbeat_at: str | None) -> bool:
    """A lock counts as running only if status is 'running' AND its heartbeat
    is fresh — a stale heartbeat means the holder crashed and the lock is free."""
    if status != "running":
        return False
    if not heartbeat_at:
        return True
    cutoff = (datetime.now() - timedelta(minutes=STALE_LOCK_MINUTES)).isoformat()
    return heartbeat_at >= cutoff
