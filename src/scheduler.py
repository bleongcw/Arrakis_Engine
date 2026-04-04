# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Automated pipeline scheduler.

Runs the full pipeline (harvest → analyze → patterns) on a configurable
interval using a daemon thread. Integrates with pipeline_state for mutual
exclusion — if a manual run is in progress, the scheduled run skips.
"""

import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path

import schedule as schedule_lib

from src import pipeline_state
from src.models import get_connection

logger = logging.getLogger(__name__)


# ── Shared pipeline runner ────────────────────────────────

def run_full_pipeline(config: dict, db_path: str, player_filter: str | None = None):
    """Execute harvest → analyze → patterns.

    Caller is responsible for pipeline_state.start_task() / complete_task().
    Updates pipeline_state.update_progress() throughout.
    Returns a result dict on success, raises on failure.
    """
    from src.harvester import harvest_player
    from src.analyzer import analyze_pending
    from src.patterns import compute_player_patterns

    months = config.get("analysis", {}).get("months_lookback", 6)
    sf_config = config.get("stockfish", {})
    sf_path = sf_config.get("path", shutil.which("stockfish") or "stockfish")

    # Read active players from DB (single source of truth)
    conn = get_connection(db_path)
    if player_filter:
        player_rows = conn.execute(
            "SELECT * FROM players WHERE COALESCE(is_active, 1) = 1 AND username = ?",
            (player_filter,),
        ).fetchall()
    else:
        player_rows = conn.execute(
            "SELECT * FROM players WHERE COALESCE(is_active, 1) = 1"
        ).fetchall()
    conn.close()
    players = [dict(r) for r in player_rows]

    # Validate stockfish
    if not Path(sf_path).is_file():
        found = shutil.which("stockfish")
        if found:
            sf_path = found
        else:
            raise RuntimeError(
                "Stockfish not found. Install it with: brew install stockfish"
            )

    # Step 1: Harvest
    pipeline_state.update_progress(
        "Step 1/3: Fetching new games...",
        {"current_step": 1, "total_steps": 3},
    )
    total_new = 0
    total_errors = 0
    for player in players:
        username = player["username"]
        display = player.get("display_name") or username
        pipeline_state.update_progress(
            f"Step 1/3: Fetching games for {display}...",
            {"current_step": 1, "total_steps": 3},
        )

        stats = harvest_player(
            username, db_path=db_path, months=months,
            lichess_username=player.get("lichess_username"),
        )
        total_new += stats.get("new", 0)
        total_errors += stats.get("errors", 0)

    # Step 2: Analyze
    conn = get_connection(db_path)
    total_pending = conn.execute(
        "SELECT COUNT(*) as c FROM games WHERE analysis_status = 'pending'"
    ).fetchone()["c"]
    conn.close()

    pipeline_state.update_progress(
        f"Step 2/3: Analyzing {total_pending} games...",
        {"current_step": 2, "total_steps": 3, "games_total": total_pending, "games_processed": 0},
    )

    # Progress polling for analyze
    stop_polling = threading.Event()

    def poll_progress():
        while not stop_polling.is_set():
            try:
                c = get_connection(db_path)
                remaining = c.execute(
                    "SELECT COUNT(*) as c FROM games WHERE analysis_status = 'pending'"
                ).fetchone()["c"]
                c.close()
                done = total_pending - remaining
                pipeline_state.update_progress(
                    f"Step 2/3: Analyzing game {done} of {total_pending}...",
                    {"current_step": 2, "total_steps": 3, "games_total": total_pending, "games_processed": done},
                )
            except Exception:
                pass
            stop_polling.wait(3)

    if total_pending > 0:
        poller = threading.Thread(target=poll_progress, daemon=True)
        poller.start()

    games_analyzed = analyze_pending(
        stockfish_path=sf_path,
        depth=sf_config.get("depth", 22),
        threads=sf_config.get("threads", 6),
        hash_mb=sf_config.get("hash_mb", 512),
        move_time_limit=sf_config.get("move_time_limit", 10.0),
        db_path=db_path,
    )

    if total_pending > 0:
        stop_polling.set()
        poller.join(timeout=5)

    # Step 3: Patterns
    pipeline_state.update_progress(
        "Step 3/3: Updating insights...",
        {"current_step": 3, "total_steps": 3},
    )
    conn = get_connection(db_path)
    player_rows = conn.execute(
        "SELECT id, username, display_name FROM players WHERE COALESCE(is_active, 1) = 1"
    ).fetchall()
    conn.close()

    players_updated = 0
    for row in player_rows:
        display = row["display_name"] or row["username"]
        pipeline_state.update_progress(
            f"Step 3/3: Computing insights for {display}...",
            {"current_step": 3, "total_steps": 3},
        )
        compute_player_patterns(row["id"], db_path=db_path)
        players_updated += 1

    return {
        "new_games": total_new,
        "games_analyzed": games_analyzed,
        "players_updated": players_updated,
        "errors": total_errors,
    }


# ── Schedule state ────────────────────────────────────────

_schedule_lock = threading.Lock()
_schedule_state = {
    "enabled": False,
    "interval_hours": 6,
    "next_run_time": None,
    "last_run_at": None,
    "last_run_status": None,    # "success" | "error" | "skipped" | None
    "last_run_message": None,
}


def _update_schedule_state(**kwargs):
    with _schedule_lock:
        _schedule_state.update(kwargs)


def get_schedule_state() -> dict:
    with _schedule_lock:
        return dict(_schedule_state)


# ── Scheduler manager ────────────────────────────────────

class SchedulerManager:
    """Manages automated pipeline runs on a timer."""

    def __init__(self, config: dict, db_path: str):
        self.config = config
        self.db_path = db_path
        self._scheduler = schedule_lib.Scheduler()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Read schedule config
        sched_config = config.get("schedule", {})
        self._enabled = sched_config.get("enabled", False)
        self._interval_hours = sched_config.get("interval_hours", 6)
        self._run_on_startup = sched_config.get("run_on_startup", False)

        _update_schedule_state(
            enabled=self._enabled,
            interval_hours=self._interval_hours,
        )

    def start(self):
        """Start the scheduler daemon thread."""
        if self._enabled:
            self._configure_job()

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        if self._enabled:
            logger.info(
                "Scheduler started: running every %d hour(s)", self._interval_hours
            )
            if self._run_on_startup:
                logger.info("Scheduler: run_on_startup enabled, triggering initial run")
                threading.Thread(target=self._execute_job, daemon=True).start()
        else:
            logger.info("Scheduler loaded (disabled). Enable via dashboard or config.yaml")

    def stop(self):
        """Signal the scheduler to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def enable(self):
        """Enable scheduling at runtime."""
        self._enabled = True
        self._configure_job()
        _update_schedule_state(enabled=True)
        logger.info("Scheduler enabled: every %d hour(s)", self._interval_hours)

    def disable(self):
        """Disable scheduling at runtime."""
        self._enabled = False
        self._scheduler.clear()
        _update_schedule_state(enabled=False, next_run_time=None)
        logger.info("Scheduler disabled")

    def update_interval(self, hours: int):
        """Change the interval at runtime."""
        self._interval_hours = max(1, hours)
        _update_schedule_state(interval_hours=self._interval_hours)
        if self._enabled:
            self._configure_job()
        logger.info("Scheduler interval updated to %d hour(s)", self._interval_hours)

    def get_state(self) -> dict:
        """Return current schedule state."""
        return get_schedule_state()

    def _configure_job(self):
        """Set up the schedule job with current interval."""
        self._scheduler.clear()
        self._scheduler.every(self._interval_hours).hours.do(self._execute_job)
        # Update next run time
        next_run = self._scheduler.next_run
        _update_schedule_state(
            next_run_time=next_run.isoformat() if next_run else None
        )

    def _run_loop(self):
        """Background loop that checks for pending jobs every 30s."""
        while not self._stop_event.is_set():
            if self._enabled:
                self._scheduler.run_pending()
                # Keep next_run_time fresh
                next_run = self._scheduler.next_run
                _update_schedule_state(
                    next_run_time=next_run.isoformat() if next_run else None
                )
            self._stop_event.wait(30)

    def _execute_job(self):
        """Run the full pipeline as a scheduled job."""
        if pipeline_state.is_busy():
            logger.info("Scheduled run skipped: another task is running")
            _update_schedule_state(
                last_run_at=datetime.now().isoformat(),
                last_run_status="skipped",
                last_run_message="Skipped — another task was already running.",
            )
            return

        if not pipeline_state.start_task("run_all", triggered_by="schedule"):
            _update_schedule_state(
                last_run_at=datetime.now().isoformat(),
                last_run_status="skipped",
                last_run_message="Skipped — could not acquire lock.",
            )
            return

        try:
            result = run_full_pipeline(self.config, self.db_path)
            pipeline_state.complete_task(result)

            # Build friendly message
            parts = []
            if result.get("new_games"):
                parts.append(f"{result['new_games']} new games")
            if result.get("games_analyzed"):
                parts.append(f"{result['games_analyzed']} analyzed")
            if result.get("players_updated"):
                parts.append(f"{result['players_updated']} players updated")
            msg = ", ".join(parts) if parts else "No new data."

            _update_schedule_state(
                last_run_at=datetime.now().isoformat(),
                last_run_status="success",
                last_run_message=msg,
            )
            logger.info("Scheduled pipeline complete: %s", msg)

        except Exception as e:
            logger.exception("Scheduled pipeline failed: %s", e)
            pipeline_state.fail_task(str(e))
            _update_schedule_state(
                last_run_at=datetime.now().isoformat(),
                last_run_status="error",
                last_run_message=str(e),
            )
