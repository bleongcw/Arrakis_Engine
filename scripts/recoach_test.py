#!/usr/bin/env python3
"""scripts/recoach_test.py — bulk-re-coach evaluation driver

Re-coach the most-recent N analyzed games for a single player using a
specified LLM provider (default: OpenAI gpt-5.5-pro-2026-04-23). Built
for evaluating the v1.8.0 trajectory-aware coaching feedback at scale.

Safety net:
- **Per-call timeout** — 600s (v1.8.1 OpenAI registry value).
- **Spacing** — 15s sleep between calls, matching `coach_pending` for
  OpenAI. Override with `--spacing N`.
- **Retries** — 3 attempts per game with exponential backoff on rate
  limits (30s → 60s → 120s). Non-rate-limit errors get a flat 30s
  retry.
- **Checkpoint** — `data/recoach_<player>.checkpoint.json`. Written
  after every successful game so Ctrl+C / network failure / laptop
  sleep doesn't lose progress. Re-run with `--resume` to skip
  already-completed games.
- **Existing briefs untouched** — `game_coaching` is UNIQUE on
  `(game_id, provider)`. Old Claude briefs stay; new OpenAI briefs
  land alongside under a different provider key.
- **Ctrl+C** — drops the in-flight call, persists the checkpoint, exits
  cleanly. Re-run with `--resume`.

Usage:
    # Dry-run first (no API calls)
    python scripts/recoach_test.py --player evanleongxinyu --limit 20 --dry-run

    # The real thing (this will burn ~$15-25 over ~8 hours for 100 games)
    python scripts/recoach_test.py --player evanleongxinyu --limit 100

    # Resume after interruption
    python scripts/recoach_test.py --player evanleongxinyu --limit 100 --resume

    # A/B comparison: same games without trajectory injection
    python scripts/recoach_test.py --player evanleongxinyu --limit 10 \\
        --no-trajectory --checkpoint data/recoach_evan_no_traj.checkpoint.json

Estimated:
    Cost: $0.10-0.30 per game with gpt-5.5-pro-2026-04-23
    Time: ~5 min per call + 15s spacing → ~9 h for 100 games
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Make 'src' importable when run from anywhere
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import yaml  # noqa: E402

from src.coach import coach_game  # noqa: E402
from src.llm_providers import PROVIDER_REGISTRY  # noqa: E402
from src.models import init_db  # noqa: E402


DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-5.5-pro-2026-04-23"
DEFAULT_SPACING_SECONDS = 15
MAX_RETRIES_PER_GAME = 3
EST_MIN_COST_PER_GAME = 0.10
EST_MAX_COST_PER_GAME = 0.30
EST_MINUTES_PER_CALL = 5.0


def setup_logging(verbose: bool, log_file: Path | None) -> logging.Logger:
    """Configure logging to console + optional file."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(message)s"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(level=level, format=fmt, handlers=handlers)
    return logging.getLogger("recoach_test")


def load_checkpoint(path: Path) -> set[int]:
    """Load completed game ids from a checkpoint file, or {} if missing."""
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
        return set(int(x) for x in data.get("completed_game_ids", []))
    except (json.JSONDecodeError, OSError, ValueError):
        return set()


def save_checkpoint(
    path: Path, completed: set[int], total: int, args_dict: dict
) -> None:
    """Persist progress after each successful game."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "completed_count": len(completed),
                "total_count": total,
                "completed_game_ids": sorted(completed),
                "run_args": args_dict,
            },
            indent=2,
        )
    )


def fetch_target_games(
    db_path: str, player_username: str, limit: int
) -> list[dict]:
    """Pull the `limit` most-recent ANALYZED game ids for the player."""
    conn = init_db(db_path)
    row = conn.execute(
        "SELECT id FROM players WHERE username = ?", (player_username,)
    ).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Player '{player_username}' not found in DB at {db_path}")
    player_id = row["id"]

    rows = conn.execute(
        """SELECT id, date_played, result, player_color
        FROM games
        WHERE player_id = ? AND analysis_status = 'complete'
        ORDER BY date_played DESC
        LIMIT ?""",
        (player_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_rate_limit_error(exc: Exception) -> bool:
    """Heuristic: detect rate-limit / 429 errors from any provider SDK."""
    msg = str(exc).lower()
    return "429" in msg or "rate_limit" in msg or "rate limit" in msg


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--player", required=True,
                        help="Player username (e.g. evanleongxinyu)")
    parser.add_argument("--limit", type=int, default=100,
                        help="Number of most-recent analyzed games to re-coach (default: 100)")
    parser.add_argument("--provider", default=DEFAULT_PROVIDER,
                        choices=sorted(PROVIDER_REGISTRY.keys()),
                        help=f"LLM provider (default: {DEFAULT_PROVIDER})")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--db", default="data/chess_coach.db",
                        help="Path to SQLite DB (default: data/chess_coach.db)")
    parser.add_argument("--config", default="config.yaml",
                        help="Path to config.yaml (default: config.yaml)")
    parser.add_argument("--checkpoint", default=None,
                        help="Checkpoint JSON path "
                             "(default: data/recoach_<player>.checkpoint.json)")
    parser.add_argument("--log-file", default=None,
                        help="Append run logs to this file "
                             "(default: data/recoach_<player>.log)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from checkpoint (skip already-completed game ids)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be done; no API calls")
    parser.add_argument("--no-trajectory", action="store_true",
                        help="A/B mode: disable trajectory injection for this run")
    parser.add_argument("--spacing", type=int, default=DEFAULT_SPACING_SECONDS,
                        help=f"Seconds to sleep between calls (default: {DEFAULT_SPACING_SECONDS})")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="DEBUG-level logging")
    args = parser.parse_args()

    # Resolve default paths
    checkpoint_path = Path(
        args.checkpoint or f"data/recoach_{args.player}.checkpoint.json"
    )
    log_file = Path(args.log_file or f"data/recoach_{args.player}.log")

    log = setup_logging(args.verbose, log_file)

    # ── Pre-flight ─────────────────────────────────────────────────
    if args.provider != "ollama":  # Ollama needs no API key
        env_var = PROVIDER_REGISTRY[args.provider].get("env_var")
        if env_var and not os.environ.get(env_var):
            log.error("%s not set in environment. Aborting.", env_var)
            return 1

    provider_timeout = PROVIDER_REGISTRY[args.provider]["default_timeout"]
    log.info("Provider: %s | Model: %s | Per-call timeout: %ds",
             args.provider, args.model, int(provider_timeout))
    if args.provider == "openai" and provider_timeout < 600:
        log.warning("OpenAI timeout is %ds — upgrade to v1.8.1+ for 600s headroom.",
                    int(provider_timeout))

    try:
        with open(args.config) as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        log.error("Config file not found: %s", args.config)
        return 1

    traj_cfg = cfg.get("coaching", {}).get("coaching_trajectory_enabled", True)
    if args.no_trajectory:
        log.info("Trajectory injection: OFF (--no-trajectory)")
        trajectory_arg = False
    else:
        log.info("Trajectory injection: %s (from config)",
                 "ON" if traj_cfg else "OFF")
        trajectory_arg = None  # let config drive

    # ── Build the work queue ───────────────────────────────────────
    try:
        games = fetch_target_games(args.db, args.player, args.limit)
    except ValueError as e:
        log.error(str(e))
        return 1

    if not games:
        log.error("No analyzed games found for player '%s'", args.player)
        return 1

    completed = load_checkpoint(checkpoint_path) if args.resume else set()
    pending = [g for g in games if g["id"] not in completed]

    log.info("Target: %d most-recent analyzed games for '%s'",
             len(games), args.player)
    log.info("  Already complete in checkpoint: %d", len(games) - len(pending))
    log.info("  To coach this run: %d", len(pending))

    if not pending:
        log.info("Nothing to do — all target games already in checkpoint.")
        return 0

    # ── Cost + time estimate ───────────────────────────────────────
    est_hours = len(pending) * (EST_MINUTES_PER_CALL + args.spacing / 60.0) / 60.0
    est_low = len(pending) * EST_MIN_COST_PER_GAME
    est_high = len(pending) * EST_MAX_COST_PER_GAME
    log.info("Estimated runtime: ~%.1f hours", est_hours)
    log.info("Estimated %s cost: $%.2f – $%.2f", args.provider, est_low, est_high)
    log.info("Checkpoint: %s", checkpoint_path)
    log.info("Log file:   %s", log_file)

    if args.dry_run:
        log.info("--dry-run set; exiting before any API calls.")
        sample_n = min(10, len(pending))
        log.info("First %d games that would be coached:", sample_n)
        for g in pending[:sample_n]:
            log.info("  • id=%d  %s  %s as %s",
                     g["id"], g["date_played"], g["result"], g["player_color"])
        if len(pending) > sample_n:
            log.info("  … and %d more", len(pending) - sample_n)
        return 0

    args_snapshot = {k: v for k, v in vars(args).items() if k != "checkpoint"}
    args_snapshot["checkpoint"] = str(checkpoint_path)

    # ── Main loop ──────────────────────────────────────────────────
    succeeded = 0
    failed = 0
    rate_limit_retries = 0
    started = datetime.now()

    try:
        for i, g in enumerate(pending, 1):
            game_id = g["id"]
            log.info("[%d/%d] Game %d (%s, %s as %s)...",
                     i, len(pending), game_id, g["date_played"],
                     g["result"], g["player_color"])

            success = False
            for attempt in range(1, MAX_RETRIES_PER_GAME + 1):
                try:
                    result = coach_game(
                        game_id,
                        provider=args.provider,
                        model=args.model,
                        db_path=args.db,
                        config=cfg,
                        trajectory_enabled=trajectory_arg,
                    )
                    meta = result.get("meta", {}) or {}
                    log.info(
                        "  → OK. trajectory_injected=%s weakest=%s trend=%s "
                        "prompt_tokens=%s",
                        meta.get("trajectory_injected"),
                        meta.get("trajectory_weakest_phase"),
                        meta.get("trajectory_trend_direction"),
                        meta.get("prompt_tokens_estimate"),
                    )
                    success = True
                    break
                except KeyboardInterrupt:
                    raise  # bubble up to outer handler
                except Exception as e:
                    if is_rate_limit_error(e):
                        backoff = 30 * (2 ** (attempt - 1))
                        rate_limit_retries += 1
                        log.warning(
                            "  Rate-limit hit (attempt %d/%d). Sleeping %ds…",
                            attempt, MAX_RETRIES_PER_GAME, backoff,
                        )
                        time.sleep(backoff)
                    else:
                        log.error(
                            "  Error (attempt %d/%d): %s",
                            attempt, MAX_RETRIES_PER_GAME, e,
                        )
                        if attempt < MAX_RETRIES_PER_GAME:
                            time.sleep(30)

            if success:
                succeeded += 1
                completed.add(game_id)
                save_checkpoint(checkpoint_path, completed, len(games),
                                args_snapshot)
            else:
                failed += 1
                log.error("  → FAILED after %d attempts. Move on.",
                          MAX_RETRIES_PER_GAME)

            # Spacing between calls (skip after the very last one)
            if i < len(pending):
                time.sleep(args.spacing)

    except KeyboardInterrupt:
        log.warning("Ctrl+C — saving checkpoint and exiting. "
                    "Re-run with --resume to continue.")

    # ── Summary ────────────────────────────────────────────────────
    elapsed = datetime.now() - started
    log.info("=== DONE ===")
    log.info("Succeeded: %d / %d", succeeded, len(pending))
    log.info("Failed:    %d", failed)
    log.info("Rate-limit retries: %d", rate_limit_retries)
    log.info("Elapsed:   %s", elapsed)
    log.info("Checkpoint final: %s (%d / %d games complete overall)",
             checkpoint_path, len(completed), len(games))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
