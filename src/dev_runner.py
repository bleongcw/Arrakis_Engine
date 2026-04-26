# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Dev-server orchestration for `python main.py serve` (v1.5.0).

This module owns the subprocess plumbing that lets a single `serve`
command spawn the Next.js frontend alongside the Python API:

    find_pnpm()              -> resolves pnpm / corepack pnpm executable
    check_node_modules(cwd)  -> bool for whether `pnpm install` was run
    spawn_frontend(...)      -> subprocess.Popen with the right flags
    tail_with_prefix(...)    -> daemon thread reading + prefixing stdout
    terminate_process_group  -> SIGTERM → wait → SIGKILL on Ctrl+C

The orchestrator (`main.py::cmd_serve`) calls these in order; this module
deliberately stays small and platform-aware so the orchestrator can read
top-to-bottom.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Pattern

logger = logging.getLogger(__name__)

# Default location of the Next.js frontend relative to the repo root.
DEFAULT_FRONTEND_DIR = "frontend"

# Time we'll wait between SIGTERM and SIGKILL during shutdown.
DEFAULT_TERMINATE_GRACE_S = 5.0

# Regex matching the Next.js dev "ready" line — both the historical
# `- Local:    http://localhost:3000` and the v15+ `Local:` variants.
# The capture group pulls the actual port (which auto-bumps to 3001 when
# 3000 is taken).
NEXTJS_READY_PATTERN: Pattern[str] = re.compile(
    r"(?:▲\s+Next\.js[^\n]*\s+)?[-•▲]?\s*(?:Local:\s+)?https?://localhost:(\d+)",
    re.IGNORECASE,
)


# ── Pre-flight checks ────────────────────────────────────────────────────


class DevRunnerError(RuntimeError):
    """Raised for orchestration failures with a user-facing message."""


def find_pnpm() -> list[str]:
    """Resolve the command prefix for invoking pnpm.

    Returns the argv prefix as a list (e.g. `["pnpm"]` or
    `["corepack", "pnpm"]`) so the caller can append `dev`, `install`, etc.
    Raises DevRunnerError with an actionable message if neither path works.
    """
    direct = shutil.which("pnpm")
    if direct:
        return [direct]
    corepack = shutil.which("corepack")
    if corepack:
        # corepack ships with Node 16.10+. It can run `pnpm` even when pnpm
        # isn't installed globally. Verify before returning.
        try:
            subprocess.run(
                [corepack, "pnpm", "--version"],
                check=True, capture_output=True, timeout=10,
            )
            return [corepack, "pnpm"]
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError):
            pass
    raise DevRunnerError(
        "pnpm not found on PATH. Install pnpm (https://pnpm.io/installation) "
        "or enable corepack (`corepack enable`) and try again."
    )


def check_node_modules(frontend_dir: str | Path = DEFAULT_FRONTEND_DIR) -> bool:
    """Return True if frontend/node_modules exists (pnpm install has been run)."""
    return (Path(frontend_dir) / "node_modules").is_dir()


def run_pnpm_install(
    pnpm_cmd: list[str], frontend_dir: str | Path = DEFAULT_FRONTEND_DIR,
) -> None:
    """Run `pnpm install --frozen-lockfile` in the frontend directory.
    Used by the optional `--install` flag on `serve`."""
    cmd = [*pnpm_cmd, "install", "--frozen-lockfile"]
    logger.info("[dev_runner] %s (cwd=%s)", " ".join(cmd), frontend_dir)
    result = subprocess.run(cmd, cwd=str(frontend_dir))
    if result.returncode != 0:
        raise DevRunnerError(
            f"pnpm install failed with exit code {result.returncode}. "
            "See the output above."
        )


# ── Frontend subprocess ──────────────────────────────────────────────────


def spawn_frontend(
    pnpm_cmd: list[str],
    frontend_dir: str | Path = DEFAULT_FRONTEND_DIR,
    port: int | None = None,
) -> subprocess.Popen[str]:
    """Start `pnpm dev` (with optional `--port N`) as a child process.

    The process is placed in its own session/group so we can signal the
    whole tree on shutdown — Next.js dev itself spawns workers that
    don't inherit the same parent on Unix without setsid.

    Returns the Popen handle. stdout + stderr are merged on a single PIPE;
    the caller is responsible for tailing it (use `tail_with_prefix`).
    """
    args = [*pnpm_cmd, "dev"]
    if port is not None:
        # Next.js / pnpm: `pnpm dev -- --port N` forwards to next dev
        args.extend(["--", "--port", str(port)])

    popen_kwargs: dict = {
        "cwd": str(frontend_dir),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "bufsize": 1,                  # line-buffered
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    # Put the child in its own process group / session for clean signal
    # propagation. Cross-platform shape: setsid on Unix,
    # CREATE_NEW_PROCESS_GROUP on Windows.
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True
    else:
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    logger.info("[dev_runner] spawning: %s (cwd=%s)", " ".join(args), frontend_dir)
    return subprocess.Popen(args, **popen_kwargs)


def tail_with_prefix(
    proc: subprocess.Popen[str],
    prefix: str,
    ready_event: threading.Event,
    detected_port: dict,
    ready_pattern: Pattern[str] = NEXTJS_READY_PATTERN,
) -> threading.Thread:
    """Spawn a daemon thread that reads `proc.stdout`, prepends `prefix` to
    every line, re-prints to our stdout, and signals `ready_event` when the
    Next.js ready line is seen.

    `detected_port` is a mutable dict the worker writes the captured port
    into (avoids needing a Value/Queue dance). Caller reads after the event.
    """
    def _worker() -> None:
        if proc.stdout is None:
            return
        for line in proc.stdout:
            stripped = line.rstrip("\n")
            print(f"{prefix} {stripped}", flush=True)
            if not ready_event.is_set():
                m = ready_pattern.search(stripped)
                if m:
                    try:
                        detected_port["port"] = int(m.group(1))
                    except (TypeError, ValueError):
                        pass
                    ready_event.set()
        # On EOF (process exited), make sure waiters don't hang.
        ready_event.set()

    thread = threading.Thread(target=_worker, daemon=True, name="frontend-tail")
    thread.start()
    return thread


def wait_for_ready(
    ready_event: threading.Event,
    proc: subprocess.Popen[str],
    timeout_s: float = 60.0,
) -> bool:
    """Block until the frontend is ready or the process exits / timeout hits.

    Returns True if the ready line was seen, False if the process died first
    or we timed out. Also returns False (with a logged warning) if the
    process exits before becoming ready.
    """
    deadline = time.monotonic() + timeout_s
    while not ready_event.is_set():
        if proc.poll() is not None:
            logger.warning(
                "[dev_runner] frontend process exited (code=%s) before ready",
                proc.returncode,
            )
            return False
        if time.monotonic() >= deadline:
            logger.warning(
                "[dev_runner] timed out after %.0fs waiting for frontend ready",
                timeout_s,
            )
            return False
        time.sleep(0.1)
    # ready_event may have been set by EOF in tail_with_prefix on a crashed
    # process; double-check the proc is alive.
    return proc.poll() is None


# ── Shutdown ─────────────────────────────────────────────────────────────


def terminate_process_group(
    proc: subprocess.Popen[str],
    grace_s: float = DEFAULT_TERMINATE_GRACE_S,
) -> None:
    """Send SIGTERM to the process group, wait up to grace_s, then SIGKILL.

    The whole-group approach is essential because `pnpm dev` itself spawns
    Next.js workers; signalling only the pnpm pid leaves the workers
    orphaned + still listening on port 3000.
    """
    if proc.poll() is not None:
        return  # already exited

    try:
        if os.name == "posix":
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
        else:
            proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
    except ProcessLookupError:
        return
    except Exception as e:
        logger.warning("[dev_runner] SIGTERM failed: %s", e)

    try:
        proc.wait(timeout=grace_s)
        return
    except subprocess.TimeoutExpired:
        pass

    logger.warning("[dev_runner] frontend didn't exit after %.0fs; sending SIGKILL",
                   grace_s)
    try:
        if os.name == "posix":
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, OSError):
        return


# ── Banners ──────────────────────────────────────────────────────────────


def print_unified_banner(
    api_port: int,
    frontend_port: int,
    db_path: str,
    sched_status: str,
    interval_hours: int,
    out=sys.stdout,
) -> None:
    """Print the v1.5.0 unified banner — both URLs in one place.

    Used by `cmd_serve` after both servers are up. The `out` parameter is
    for testability; defaults to stdout.
    """
    print("", file=out)
    print(f"\U0001f3f0 Arrakis Engine running", file=out)
    print("", file=out)
    print(f"   \U0001f4e1 Frontend UI:    http://localhost:{frontend_port}   "
          f"← open this", file=out)
    print(f"   \U0001f50c API backend:    http://localhost:{api_port}", file=out)
    print(f"   \U0001f4ca Live data from: {db_path}", file=out)
    print(f"   \U0001f552 Auto-updates:   {sched_status} (every {interval_hours}h)",
          file=out)
    print("", file=out)
    print("Press Ctrl+C to stop both servers.", file=out)
    print("", file=out)
    out.flush()
