# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""In-memory pipeline task state store.

Tracks the currently running pipeline task (harvest, analyze, patterns, run_all).
Only one task may run at a time, enforced by a threading lock.
State is ephemeral — resets on server restart.
"""

import threading
from datetime import datetime

_lock = threading.Lock()
_state = {
    "task": None,           # "harvest" | "analyze" | "patterns" | "run_all" | None
    "status": "idle",       # "running" | "complete" | "error" | "idle"
    "progress": "",         # Human-readable progress text
    "detail": None,         # { current_step, total_steps, games_processed, games_total }
    "result": None,         # Set on completion
    "error": None,          # Set on error
    "started_at": None,
    "finished_at": None,
    "triggered_by": None,   # "manual" | "schedule" | None
}


def start_task(task_name: str, triggered_by: str = "manual") -> bool:
    """Try to start a new task. Returns False if another task is running."""
    with _lock:
        if _state["status"] == "running":
            return False
        _state["task"] = task_name
        _state["status"] = "running"
        _state["progress"] = "Starting..."
        _state["detail"] = None
        _state["result"] = None
        _state["error"] = None
        _state["started_at"] = datetime.now().isoformat()
        _state["finished_at"] = None
        _state["triggered_by"] = triggered_by
        return True


def update_progress(progress_text: str, detail: dict | None = None):
    """Update progress for the currently running task."""
    with _lock:
        _state["progress"] = progress_text
        if detail is not None:
            _state["detail"] = detail


def complete_task(result: dict):
    """Mark the current task as complete."""
    with _lock:
        _state["status"] = "complete"
        _state["progress"] = "Done!"
        _state["result"] = result
        _state["finished_at"] = datetime.now().isoformat()


def fail_task(error_msg: str):
    """Mark the current task as failed."""
    with _lock:
        _state["status"] = "error"
        _state["progress"] = ""
        _state["error"] = error_msg
        _state["finished_at"] = datetime.now().isoformat()


def get_state() -> dict:
    """Return a snapshot of the current state."""
    with _lock:
        return dict(_state)


def is_busy() -> bool:
    """Check if a task is currently running."""
    with _lock:
        return _state["status"] == "running"


def current_task() -> str | None:
    """Return the name of the currently running task, or None."""
    with _lock:
        if _state["status"] == "running":
            return _state["task"]
        return None
