#!/usr/bin/env python3
# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""ArrakisEngine CLI — Chess coaching AI."""

import argparse
import logging
import os
import sys
import time

import yaml
from dotenv import load_dotenv

load_dotenv()

import http.server
import functools

from src.harvester import harvest_player
from src.analyzer import analyze_pending
from src.coach import coach_pending
from src.patterns import update_patterns
from src.report import generate_report
from src.models import init_db


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _config_slug(player: dict) -> str:
    """v1.16.5: the URL/CLI slug for a config-loaded player dict.

    Uses the explicit `slug` key if present, else derives it the same
    way src.models._slugify does (lowercase display_name, strip all
    non-alphanumeric). Mirrors the DB-side derivation so CLI --player
    matching is consistent whether or not config.yaml sets slug.
    """
    import re
    if player.get("slug"):
        return player["slug"]
    source = player.get("display_name") or player.get("username") or ""
    return re.sub(r"[^a-z0-9]+", "", source.lower()) or "player"


def _player_matches(player: dict, requested: list[str]) -> bool:
    """v1.16.5: True if a config player matches a --player value by
    slug OR chess.com username. Keeps `--player` consistent with the
    slug-only model the API/URL use, while still accepting the
    chess.com handle for backward-compatible harvest scripts."""
    return (
        _config_slug(player) in requested
        or player.get("username") in requested
    )


def cmd_harvest(args, config):
    """Harvest games from chess.com and/or lichess for configured players."""
    db_path = config["database"]["path"]
    months = config["analysis"]["months_lookback"]
    conn = init_db(db_path)
    conn.close()

    platform_filter = getattr(args, "platform", None)

    players = config["players"]
    if args.player:
        # v1.16.5: --player accepts slug OR chess.com username. Config
        # entries may carry an explicit `slug`; fall back to the
        # auto-derived slug (lowercase display_name, no separator) so
        # `--player evanleong` matches even when slug isn't set in YAML.
        players = [p for p in players if _player_matches(p, args.player)]

    for player in players:
        username = player["username"]
        lichess_username = player.get("lichess_username")
        platforms = []
        if platform_filter is None or platform_filter == "chess.com":
            platforms.append("chess.com")
        if lichess_username and (platform_filter is None or platform_filter == "lichess"):
            platforms.append("lichess")

        logging.info("Harvesting games for %s from %s...", username, ", ".join(platforms))

        # Ensure player record exists with config data
        from src.models import ensure_player
        conn = init_db(db_path)
        ensure_player(
            conn, username,
            display_name=player.get("display_name"),
            age=player.get("age"),
            rating=player.get("rating"),
            fide_id=player.get("fide_id"),
            fide_rating=player.get("fide_rating"),
            lichess_username=player.get("lichess_username"),
            # v1.16.1: optional explicit slug from config.yaml.
            # When omitted, ensure_player auto-derives from display_name.
            slug=player.get("slug"),
        )
        conn.close()

        stats = harvest_player(
            username, db_path=db_path, months=months,
            lichess_username=lichess_username,
            platform=platform_filter,
        )
        print(f"  {username}: {stats['new']} new games "
              f"({stats['skipped']} already stored, "
              f"{stats['errors']} errors)")


def cmd_analyze(args, config):
    """Run Stockfish analysis on pending games."""
    import shutil
    sf_config = config["stockfish"]
    db_path = config["database"]["path"]
    sf_path = sf_config["path"]

    # Validate Stockfish binary exists before starting
    if not os.path.isfile(sf_path):
        # Try to find it on PATH as a fallback
        found = shutil.which("stockfish")
        if found:
            print(f"⚠️  Stockfish not found at '{sf_path}', but found at '{found}'.")
            print(f"   Update stockfish.path in config.yaml to: {found}")
            sf_path = found
        else:
            print(f"❌ Stockfish binary not found at '{sf_path}'.")
            print()
            print("To fix this:")
            print("  1. Install Stockfish:")
            print("     macOS:  brew install stockfish")
            print("     Ubuntu: sudo apt install stockfish")
            print("     Or download from: https://stockfishchess.org/download/")
            print()
            print("  2. Update stockfish.path in config.yaml:")
            print("     stockfish:")
            print(f"       path: /opt/homebrew/bin/stockfish  # or run: which stockfish")
            print()
            print("  3. Verify it works:")
            print("     stockfish <<< 'quit'")
            return

    count = analyze_pending(
        stockfish_path=sf_path,
        depth=sf_config["depth"],
        threads=sf_config["threads"],
        hash_mb=sf_config["hash_mb"],
        move_time_limit=sf_config.get("move_time_limit", 10.0),
        db_path=db_path,
    )
    print(f"Analyzed {count} games.")


def cmd_coach(args, config):
    """Generate LLM coaching insights for analyzed games."""
    from src.llm_providers import resolve_model

    db_path = config["database"]["path"]
    provider = args.provider or config["coaching"]["default_provider"]
    coaching_config = config.get("coaching", {})
    model = resolve_model(provider, None, coaching_config)

    # Optional --history N override; clamps to 1-20 and persists into config
    # for the duration of this run so coach_game() picks it up.
    history_override = getattr(args, "history", None)
    if history_override is not None:
        n = max(1, min(20, int(history_override)))
        config.setdefault("coaching", {})["coaching_history_count"] = n
        print(f"Coaching history depth: {n} (overridden via --history)")

    limit = getattr(args, 'limit', 0) or 0
    dump_prompt_to = getattr(args, "dump_prompt", None)
    if dump_prompt_to:
        print(f"Prompt dump enabled: writing to {dump_prompt_to}")
    # v1.8.0: --no-trajectory disables trajectory injection for this run
    no_trajectory = getattr(args, "no_trajectory", False)
    trajectory_enabled = False if no_trajectory else None  # None = read config
    if no_trajectory:
        print("Trajectory injection: OFF (--no-trajectory)")
    result = coach_pending(
        provider=provider, model=model, db_path=db_path,
        limit=limit, config=config, dump_prompt_to=dump_prompt_to,
        trajectory_enabled=trajectory_enabled,
    )
    print(f"Coached {result['coached']} games with {provider} ({model}). "
          f"Errors: {result['errors']}, Skipped: {result['skipped']}"
          + (f" — Aborted: {result['abort_reason']}" if result.get('aborted') else ""))


def cmd_patterns(args, config):
    """Update pattern tracking for all players."""
    db_path = config["database"]["path"]
    count = update_patterns(db_path=db_path)
    print(f"Updated patterns for {count} players.")


def cmd_hunt_scan(args, config):
    """v1.20.0: Deep-scan an opponent's recent games for tactical blind spots.

    Runs Stockfish + the 12 motif detectors over the opponent's last N
    accumulated games (from the Hunter Mode cache) and stores a per-game
    motif summary. Slow by design — opt-in only.
    """
    from src.hunter import deep_scan_opponent, compute_opponent_motif_summary

    db_path = config["database"]["path"]
    opponent = args.opponent.strip()
    platform = args.platform
    features = config.get("features") or {}
    limit = args.games or features.get("hunter_scan_games", 20)

    def progress(done, total):
        print(f"  Deep-scanning {opponent}: game {done}/{total}...", flush=True)

    print(f"Deep scan: {opponent} ({platform}), up to {limit} games "
          f"at depth {config.get('stockfish', {}).get('depth', 22)}.")
    try:
        result = deep_scan_opponent(
            opponent, platform, config=config, db_path=db_path,
            limit=limit, progress_cb=progress,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return

    print(f"Analyzed {result['analyzed']} new game(s) "
          f"(skipped {result['skipped']}, {result['candidates']} candidates).")
    summary = compute_opponent_motif_summary(opponent, platform, db_path)
    if not summary or not summary.get("top_missed"):
        print("No tactical blind spots detected yet.")
        return
    print(f"Top blind spot: {summary['top_missed']} "
          f"(missed {summary['top_missed_count']}× across "
          f"{summary['games_analyzed']} games).")


def cmd_note(args, config):
    """v1.12.0: Append a parent-authored note to the player's Journal.

    No LLM call — this is pure user-written text. Use for parent
    observations alongside the LLM-generated reviews:

        python main.py note --player evanleongxinyu \\
            "Round 3 of the Saturday tournament. Evan beat Sarah 4-0."
    """
    from src import journal as journal_mod
    from src.models import init_db

    db_path = config["database"]["path"]
    username = args.player
    body = args.body.strip() if args.body else ""
    platform = args.platform or "chess.com"

    conn = init_db(db_path)
    # v1.16.4: slug-only lookup. chess.com username is harvester-only.
    row = conn.execute(
        "SELECT id FROM players WHERE slug = ?", (username,)
    ).fetchone()
    conn.close()
    if not row:
        print(f"ERROR: player '{username}' not found")
        return

    try:
        entry = journal_mod.create_note(
            row["id"], body, platform=platform, db_path=db_path,
        )
        print(f"Created note id={entry['id']} for {username} "
              f"({len(body)} chars, platform={platform})")
    except ValueError as e:
        print(f"ERROR: {e}")


def cmd_review(args, config):
    """v1.9.0: Generate the Recent Form Review (last N coached games) for a player.

    Distinct from `patterns` (stats aggregate) — this is an LLM-generated
    narrative across the last N coached games. ~$0.10-0.15 per run.
    """
    from src.patterns import compute_recent_form_review, DEFAULT_REVIEW_WINDOW
    from src.models import init_db

    db_path = config["database"]["path"]
    provider = args.provider or config.get("coaching", {}).get("default_provider", "openai")
    window = max(3, min(30, args.window or DEFAULT_REVIEW_WINDOW))
    players_arg = args.player or []

    conn = init_db(db_path)
    if players_arg:
        targets = []
        for username in players_arg:
            # v1.16.4: slug-only lookup.
            row = conn.execute(
                "SELECT id, username, display_name FROM players WHERE slug = ?",
                (username,),
            ).fetchone()
            if not row:
                print(f"WARN: player '{username}' not found — skipping")
                continue
            targets.append(dict(row))
    else:
        # All active players
        rows = conn.execute(
            "SELECT id, username, display_name FROM players WHERE is_active = 1"
        ).fetchall()
        targets = [dict(r) for r in rows]
    conn.close()

    if not targets:
        print("No target players found.")
        return

    print(f"Generating Recent Form Review for {len(targets)} player(s) "
          f"using {provider} (window={window})...")

    for t in targets:
        try:
            review = compute_recent_form_review(
                t["id"], db_path=db_path, provider=provider,
                window=window, config=config,
            )
            if review:
                preview = review.replace("\n", " ")[:120]
                print(f"  ✓ {t['username']} ({len(review)} chars): {preview}…")
            else:
                print(f"  — {t['username']}: no coached games to review yet")
        except Exception as e:
            print(f"  ✗ {t['username']}: ERROR — {e}")


def cmd_trend(args, config):
    """v1.15.2: Regenerate the LLM-powered trend summary for a player.

    Closes the ergonomic gap from v1.9.0 onward: generate_trend_summary
    was only reachable via the POST /api/trend-summary endpoint (or the
    Patterns page "Refresh Summary" button), even though every other
    LLM-generating pipeline (coach / review / patterns / analyze) had a
    matching CLI subcommand. v1.15.2 brings trend in line.

    Mirrors cmd_review's shape — accepts --player (repeatable) plus
    --provider/--model. Calls patterns.generate_trend_summary which
    writes the result to player_patterns.trend_summary.

    Prereq: `python main.py patterns` must have run at least once so
    there's a stats_json row to summarize. ~$0.02-0.05 per call with
    Claude / gpt-5.5-pro; free with ollama.
    """
    from src.patterns import generate_trend_summary
    from src.models import init_db

    db_path = config["database"]["path"]
    provider = args.provider or config.get("coaching", {}).get("default_provider", "claude")
    players_arg = args.player or []

    conn = init_db(db_path)
    if players_arg:
        targets = []
        for username in players_arg:
            # v1.16.4: slug-only lookup.
            row = conn.execute(
                "SELECT id, username, display_name FROM players WHERE slug = ?",
                (username,),
            ).fetchone()
            if not row:
                print(f"WARN: player '{username}' not found — skipping")
                continue
            targets.append(dict(row))
    else:
        # All active players
        rows = conn.execute(
            "SELECT id, username, display_name FROM players WHERE is_active = 1"
        ).fetchall()
        targets = [dict(r) for r in rows]
    conn.close()

    if not targets:
        print("No target players found.")
        return

    print(f"Generating trend summary for {len(targets)} player(s) using {provider}...")

    for t in targets:
        try:
            summary = generate_trend_summary(
                t["id"], db_path=db_path, provider=provider, model=args.model,
            )
            if summary:
                preview = summary.replace("\n", " ")[:120]
                print(f"  ✓ {t['username']} ({len(summary)} chars): {preview}…")
            else:
                print(f"  — {t['username']}: empty summary returned")
        except ValueError as e:
            # Most common: "No pattern stats for player N. Run patterns first."
            print(f"  ✗ {t['username']}: {e}")
        except Exception as e:
            print(f"  ✗ {t['username']}: ERROR — {e}")


# v1.13.3: cmd_export_json removed — the Next.js frontend reads live
# from /api/* instead of static JSON exports.


def cmd_report(args, config):
    """Generate coaching reports."""
    db_path = config["database"]["path"]
    players = config["players"]
    if args.player:
        # v1.16.5: accept slug OR chess.com username
        players = [p for p in players if _player_matches(p, args.player)]

    period = "monthly" if args.monthly else "weekly"
    output_dir = args.output or "reports"

    for player in players:
        path = generate_report(
            player["username"], period=period,
            output_dir=output_dir, db_path=db_path,
        )
        print(f"  {player['username']}: {path}")


def cmd_dashboard(args, config):
    """Launch the live dashboard server with API endpoints (API-only mode).

    For the unified backend + frontend experience, see `cmd_serve`.
    """
    db_path = config["database"]["path"]
    port = args.port or 8000

    from src.dashboard_server import run_dashboard
    run_dashboard(db_path=db_path, port=port, config=config)


def cmd_serve(args, config):
    """Launch BOTH the API backend AND the Next.js frontend with one command.

    v1.5.0 — the recommended end-user entry point. Spawns `pnpm dev` as a
    child process group, waits for it to be ready, prints a unified banner,
    then runs the API server in the foreground. Ctrl+C stops both cleanly.

    Pre-flight checks: `pnpm` resolvable, `frontend/node_modules` exists.
    Use `--install` to auto-run `pnpm install --frozen-lockfile` first.
    """
    import threading

    from src.dev_runner import (
        DevRunnerError,
        check_node_modules,
        find_pnpm,
        print_unified_banner,
        run_pnpm_install,
        spawn_frontend,
        tail_with_prefix,
        terminate_process_group,
        wait_for_ready,
    )

    db_path = config["database"]["path"]
    api_port = args.port or 8000
    frontend_port_arg = getattr(args, "frontend_port", None)

    # Pre-flight: pnpm + node_modules
    try:
        pnpm_cmd = find_pnpm()
    except DevRunnerError as e:
        print(f"❌ {e}")
        return 1

    if not check_node_modules("frontend"):
        if getattr(args, "install", False):
            print("\U0001f4e6 Running `pnpm install --frozen-lockfile`...")
            try:
                run_pnpm_install(pnpm_cmd, "frontend")
            except DevRunnerError as e:
                print(f"❌ {e}")
                return 1
        else:
            print(
                "❌ frontend/node_modules not found. Run `cd frontend && pnpm install` "
                "first, or pass --install to do it automatically."
            )
            return 1

    # Start the backend in a background thread so we can spawn + wait for the
    # frontend, then keep the main thread free to handle Ctrl+C cleanly.
    from src.dashboard_server import run_dashboard
    backend_thread = threading.Thread(
        target=run_dashboard,
        kwargs={
            "db_path": db_path,
            "port": api_port,
            "config": config,
            "api_only_banner": False,   # we'll print the unified banner ourselves
        },
        daemon=True,
        name="api-backend",
    )
    backend_thread.start()

    # Spawn the frontend
    print("\U0001f680 Starting Arrakis Engine — backend + frontend...")
    print("   (frontend output is prefixed with [frontend])")
    proc = spawn_frontend(pnpm_cmd, "frontend", port=frontend_port_arg)
    ready_event = threading.Event()
    detected_port: dict = {"port": frontend_port_arg or 3000}
    tail_with_prefix(proc, "[frontend]", ready_event, detected_port)

    ready = wait_for_ready(ready_event, proc, timeout_s=60.0)
    if not ready:
        print("❌ Frontend failed to become ready. Exiting.")
        terminate_process_group(proc)
        return 1

    # Both servers up — print the unified banner.
    sched_config = config.get("schedule", {})
    sched_status = "enabled" if sched_config.get("enabled") else "disabled"
    interval = sched_config.get("interval_hours", 6)
    print_unified_banner(
        api_port=api_port,
        frontend_port=detected_port["port"],
        db_path=db_path,
        sched_status=sched_status,
        interval_hours=interval,
    )

    # Block until the user hits Ctrl+C or the frontend dies.
    try:
        while True:
            if proc.poll() is not None:
                print("⚠️ Frontend process exited unexpectedly. Stopping backend.")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\U0001f6d1 Stopping both servers...")
    finally:
        terminate_process_group(proc)
        # Backend is daemon-thread; terminating the process exits it.
        # The scheduler stop is handled inside run_dashboard's KeyboardInterrupt
        # path which won't fire here (different thread). So we exit the process
        # cleanly via os._exit after a brief grace period.
        print("Both servers stopped.")
    return 0


def cmd_fide_update(args, config):
    """Update FIDE rating for a player."""
    db_path = config["database"]["path"]
    conn = init_db(db_path)

    username = args.player
    rating = args.rating
    fide_id = getattr(args, "fide_id", None)

    # Find the player — v1.16.4: slug-only lookup.
    player = conn.execute(
        "SELECT id, username, display_name, fide_id, fide_rating "
        "FROM players WHERE slug = ?",
        (username,),
    ).fetchone()

    if not player:
        print(f"Player '{username}' not found in database.")
        conn.close()
        return

    updates = []
    values = []
    if rating is not None:
        updates.append("fide_rating = ?")
        values.append(rating)
    if fide_id is not None:
        updates.append("fide_id = ?")
        values.append(fide_id)

    if not updates:
        print("Nothing to update. Provide --rating and/or --fide-id.")
        conn.close()
        return

    values.append(player["id"])
    conn.execute(
        f"UPDATE players SET {', '.join(updates)} WHERE id = ?",
        values,
    )
    conn.commit()

    # Show result
    updated = conn.execute("SELECT * FROM players WHERE id = ?", (player["id"],)).fetchone()
    conn.close()

    name = updated["display_name"] or updated["username"]
    fide = updated["fide_rating"] or "—"
    fid = updated["fide_id"] or "—"
    print(f"Updated {name}: FIDE ID={fid}, FIDE rating={fide}")
    if updated["fide_id"]:
        print(f"  Profile: https://ratings.fide.com/profile/{updated['fide_id']}")


def cmd_rescan_motifs(args, config):
    """v1.14.0: backfill tactical motif tags for existing games.

    Re-parses each analyzed game's PGN, walks the moves, and for each
    critical move (|swing_cp| >= MOTIF_DETECTION_THRESHOLD_CP) runs the
    src.motifs detectors using the existing move_analysis row's
    move_played + best_move + pv_line data. Writes the result to the
    motifs_json column.

    No Stockfish call — pure Python. ~1-2s per game.

        python main.py rescan-motifs                          # all analyzed games
        python main.py rescan-motifs --player evanleongxinyu  # one player
        python main.py rescan-motifs --limit 10               # smoke test
    """
    import json
    import time
    import chess
    import chess.pgn
    import io

    from src.analyzer import MOTIF_DETECTION_THRESHOLD_CP
    from src.motifs import detect_motifs
    from src.models import init_db

    db_path = config["database"]["path"]
    conn = init_db(db_path)

    # Resolve target games
    sql = ("SELECT g.id, g.pgn, p.username FROM games g "
           "JOIN players p ON g.player_id = p.id "
           "WHERE g.analysis_status = 'complete'")
    params = []
    if args.player:
        # v1.16.5: accept slug OR chess.com username (this was a
        # v1.16.4 miss — rescan-motifs wasn't in the 4 cmd functions
        # updated, and the static guard only scans dashboard_server.py).
        sql += " AND (p.slug = ? OR p.username = ?)"
        params.append(args.player)
        params.append(args.player)
    sql += " ORDER BY g.date_played DESC"
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    games = conn.execute(sql, params).fetchall()

    if not games:
        print("No analyzed games match. Run `python main.py analyze` first.")
        conn.close()
        return

    print(f"Rescanning {len(games)} games for tactical motifs "
          f"(threshold: |cp_loss| ≥ {MOTIF_DETECTION_THRESHOLD_CP}cp)...")

    total_critical = 0
    total_tagged = 0
    started = time.time()

    for idx, g in enumerate(games, 1):
        game_id = g["id"]
        # Re-parse PGN to walk moves with python-chess
        pgn_game = chess.pgn.read_game(io.StringIO(g["pgn"] or ""))
        if pgn_game is None:
            continue
        board = pgn_game.board()
        moves_iter = list(pgn_game.mainline_moves())

        # Fetch existing rows for this game (move_played, best_move, pv_line, swing_cp)
        rows = conn.execute(
            """SELECT move_number, side, move_played, best_move, pv_line,
                      swing_cp FROM move_analysis WHERE game_id = ?
               ORDER BY move_number,
               CASE side WHEN 'white' THEN 0 ELSE 1 END""",
            (game_id,),
        ).fetchall()
        rows_by_idx = {i: dict(r) for i, r in enumerate(rows)}

        game_tagged = 0
        for i, move in enumerate(moves_iter):
            row = rows_by_idx.get(i)
            if not row:
                board.push(move)
                continue
            swing = row["swing_cp"] or 0
            if abs(swing) < MOTIF_DETECTION_THRESHOLD_CP:
                board.push(move)
                continue
            total_critical += 1

            # Detect motifs on the played move
            board_before = board.copy()
            played_pv: list = []  # not stored; mate_threat may miss, acceptable
            played_motifs = detect_motifs(board_before, move, played_pv)

            # Detect motifs on the best move (if different)
            best_motifs: list[str] = []
            best_san = row.get("best_move")
            if best_san and best_san != row["move_played"]:
                # Parse best_move SAN back into a chess.Move
                try:
                    best_move_obj = board_before.parse_san(best_san)
                except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError):
                    best_move_obj = None
                if best_move_obj is not None:
                    # Reconstruct best_pv from stored pv_line if available
                    best_pv: list = []
                    pv_line = row.get("pv_line") or ""
                    if pv_line:
                        try:
                            pv_board = board_before.copy()
                            for san in pv_line.split():
                                m = pv_board.parse_san(san)
                                best_pv.append(m)
                                pv_board.push(m)
                            # First entry of pv_line is the best_move itself —
                            # detect_motifs wants the continuation AFTER best_move.
                            best_pv = best_pv[1:] if best_pv else []
                        except (ValueError, chess.InvalidMoveError,
                                chess.IllegalMoveError):
                            best_pv = []
                    best_motifs = detect_motifs(board_before, best_move_obj, best_pv)
            else:
                best_motifs = played_motifs

            missed = [m for m in best_motifs if m not in played_motifs]
            motifs_json = None
            if played_motifs or best_motifs:
                motifs_json = json.dumps({
                    "played": played_motifs,
                    "best": best_motifs,
                    "missed": missed,
                })
                game_tagged += 1
                total_tagged += 1

            conn.execute(
                "UPDATE move_analysis SET motifs_json = ? "
                "WHERE game_id = ? AND move_number = ? AND side = ?",
                (motifs_json, game_id, row["move_number"], row["side"]),
            )
            board.push(move)

        if idx % 25 == 0 or idx == len(games):
            elapsed = time.time() - started
            rate = idx / elapsed if elapsed > 0 else 0
            print(f"  [{idx}/{len(games)}] {g['username']} game {game_id}: "
                  f"{game_tagged} tagged. {rate:.1f} games/s")

    conn.commit()
    conn.close()
    elapsed = time.time() - started
    print(f"\nDone. {total_critical} critical moves examined, "
          f"{total_tagged} tagged with motifs. Elapsed: {elapsed:.1f}s.")


def cmd_backfill_acpl(args, config):
    """Recompute per-game ACPL from existing move_analysis data.

    Without `--force`, only fills games where `acpl IS NULL` (initial
    backfill behavior). With `--force`, recomputes ACPL for ALL analyzed
    games, applying the v1.7.1 fixes (played-best-move zero rule + per-
    move loss cap). Use this once after upgrading from v1.7.0 or earlier
    to correct historical ACPL values distorted by mate-transition bugs.
    """
    from src.models import backfill_acpl_for_games
    db_path = config["database"]["path"]
    conn = init_db(db_path)
    force = getattr(args, "force", False)
    if force:
        print("Recomputing ACPL for ALL analyzed games (v1.7.1 fix)...")
    else:
        print("Backfilling ACPL for games where acpl IS NULL...")
    updated = backfill_acpl_for_games(conn, force=force)
    conn.close()
    print(f"Updated ACPL for {updated} games.")


def cmd_backfill_clocks(args, config):
    """Backfill clock_seconds from PGN annotations for existing games."""
    from src.analyzer import extract_clocks_from_pgn
    db_path = config["database"]["path"]
    conn = init_db(db_path)

    # Find games that have been analyzed but have no clock data
    games = conn.execute(
        """SELECT g.id, g.pgn FROM games g
        WHERE g.analysis_status = 'complete'
        AND EXISTS (SELECT 1 FROM move_analysis m WHERE m.game_id = g.id AND m.clock_seconds IS NULL)"""
    ).fetchall()

    if not games:
        print("No games need clock backfill.")
        conn.close()
        return

    updated_games = 0
    updated_moves = 0
    for game in games:
        clocks = extract_clocks_from_pgn(game["pgn"])
        if not any(c is not None for c in clocks):
            continue  # No clock data in this PGN

        moves = conn.execute(
            """SELECT id, move_number, side FROM move_analysis
            WHERE game_id = ? ORDER BY move_number, CASE side WHEN 'white' THEN 0 ELSE 1 END""",
            (game["id"],),
        ).fetchall()

        for idx, move in enumerate(moves):
            clock_val = clocks[idx] if idx < len(clocks) else None
            if clock_val is not None:
                conn.execute(
                    "UPDATE move_analysis SET clock_seconds = ? WHERE id = ?",
                    (clock_val, move["id"]),
                )
                updated_moves += 1

        updated_games += 1

    conn.commit()
    conn.close()
    print(f"Backfilled clock data: {updated_games} games, {updated_moves} moves updated.")


def cmd_run_all(args, config):
    """Run the full pipeline: harvest → analyze → coach → patterns → export."""
    print("=== Step 1/5: Harvesting games ===")
    cmd_harvest(args, config)

    print("\n=== Step 2/5: Analyzing games ===")
    cmd_analyze(args, config)

    print("\n=== Step 3/4: Coaching games ===")
    cmd_coach(args, config)

    print("\n=== Step 4/4: Updating patterns ===")
    cmd_patterns(args, config)

    print("\nPipeline complete! Run 'python main.py serve' to view results.")


def main():
    parser = argparse.ArgumentParser(
        description="ArrakisEngine — Chess Coach AI"
    )
    parser.add_argument(
        "--config", default="config.yaml", help="Path to config file"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )

    subparsers = parser.add_subparsers(dest="command")

    # harvest
    harvest_parser = subparsers.add_parser("harvest", help="Fetch games from chess.com and/or lichess")
    harvest_parser.add_argument(
        "--player", action="append",
        help="Username(s) to harvest (default: all configured players)",
    )
    harvest_parser.add_argument(
        "--platform", choices=["chess.com", "lichess"],
        help="Harvest from a specific platform only (default: all configured)",
    )

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Run Stockfish analysis")
    analyze_parser.add_argument(
        "--pending", action="store_true", default=True,
        help="Analyze pending games (default)",
    )

    # coach
    coach_parser = subparsers.add_parser("coach", help="Generate LLM coaching insights")
    coach_parser.add_argument(
        "--provider", choices=["claude", "openai", "gemini", "grok", "mistral", "deepseek", "qwen", "ollama"],
        help="LLM provider (default: from config)",
    )
    coach_parser.add_argument(
        "--limit", type=int, default=0,
        help="Max games to coach (default: all pending)",
    )
    coach_parser.add_argument(
        "--history", type=int,
        help="Coaching history depth: number of recent coached games to inject "
             "into the LLM prompt (default: from config, range 1-20)",
    )
    coach_parser.add_argument(
        "--dump-prompt", metavar="PATH",
        help="(v1.6.0+) Write the full assembled prompt for each coached game "
             "to PATH. If PATH is a directory, files are written as "
             "prompt_game_<id>.txt. Use to verify history injection.",
    )
    coach_parser.add_argument(
        "--no-trajectory", action="store_true",
        help="(v1.8.0+) Disable per-player trajectory injection for this "
             "run. The prompt will not include the 'Player Trajectory' "
             "section. Useful for A/B comparing coaching output with vs "
             "without trajectory context.",
    )

    # patterns
    patterns_parser = subparsers.add_parser("patterns", help="Update pattern tracking")

    # note (v1.12.0) — quick parent-authored journal entry from the CLI
    note_parser = subparsers.add_parser(
        "note",
        help="(v1.12.0) Append a parent-authored note to the player's Journal",
    )
    note_parser.add_argument(
        "--player", required=True,
        help="Username to attach the note to (e.g. evanleongxinyu)",
    )
    note_parser.add_argument(
        "--platform", default="chess.com",
        help="Platform tag for the note (default: chess.com)",
    )
    note_parser.add_argument(
        "body", help="Note body text (wrap in quotes)",
    )

    # review (v1.9.0) — LLM-generated narrative across the last N coached games
    review_parser = subparsers.add_parser(
        "review",
        help="(v1.9.0) Generate the Recent Form Review for one or all players",
    )
    review_parser.add_argument(
        "--player", action="append",
        help="Username (repeat for multiple). Default: all active players.",
    )
    review_parser.add_argument(
        "--provider", choices=["claude", "openai", "gemini", "grok",
                               "mistral", "deepseek", "qwen", "ollama"],
        help="LLM provider (default: from coaching.default_provider)",
    )
    review_parser.add_argument(
        "--window", type=int, default=10,
        help="Number of recent coached games to include in the review "
             "(default: 10, range 3-30)",
    )

    # trend (v1.15.2) — LLM-powered 30-day stats narrative
    trend_parser = subparsers.add_parser(
        "trend",
        help="(v1.15.2) Regenerate the LLM trend summary for one or all players",
    )
    trend_parser.add_argument(
        "--player", action="append",
        help="Username (repeat for multiple). Default: all active players.",
    )
    trend_parser.add_argument(
        "--provider", choices=["claude", "openai", "gemini", "grok",
                               "mistral", "deepseek", "qwen", "ollama"],
        help="LLM provider (default: from coaching.default_provider)",
    )
    trend_parser.add_argument(
        "--model",
        help="Override the model name (default: provider-specific resolution)",
    )

    # report
    report_parser = subparsers.add_parser("report", help="Generate coaching reports")
    report_parser.add_argument("--player", action="append", help="Username(s) to report on")
    report_parser.add_argument("--weekly", action="store_true", default=True, help="Weekly report (default)")
    report_parser.add_argument("--monthly", action="store_true", help="Monthly report")
    report_parser.add_argument("--output", help="Output directory (default: reports/)")

    # dashboard
    dashboard_parser = subparsers.add_parser("dashboard", help="Launch local dashboard server (API only)")
    dashboard_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")

    # serve (v1.5.0) — launches API + frontend together
    serve_parser = subparsers.add_parser(
        "serve",
        help="Launch API + Next.js frontend together (recommended for end users)",
    )
    serve_parser.add_argument("--port", type=int, default=8000,
                              help="API backend port (default: 8000)")
    serve_parser.add_argument("--frontend-port", type=int, default=None,
                              help="Frontend port (default: Next.js picks 3000)")
    serve_parser.add_argument("--install", action="store_true",
                              help="Run `pnpm install` first if node_modules is missing")

    # fide-update
    fide_parser = subparsers.add_parser("fide-update", help="Update FIDE rating for a player")
    fide_parser.add_argument("--player", required=True, help="Chess.com username of the player")
    fide_parser.add_argument("--rating", type=int, help="New FIDE rating")
    fide_parser.add_argument("--fide-id", help="FIDE player ID (e.g., 1234567)")

    # backfill-acpl (v1.7.1) — recompute ACPL with the mate-transition fix
    backfill_acpl_parser = subparsers.add_parser(
        "backfill-acpl",
        help="Recompute per-game ACPL (v1.7.1 fix for mate-transition bug)",
    )
    backfill_acpl_parser.add_argument(
        "--force", action="store_true",
        help="Recompute ACPL for ALL analyzed games (default: only games "
             "where acpl IS NULL). Use after upgrading to v1.7.1 to "
             "correct historical values.",
    )

    # rescan-motifs (v1.14.0) — backfill tactical motif tags on existing games
    rescan_motifs_parser = subparsers.add_parser(
        "rescan-motifs",
        help="(v1.14.0) Backfill tactical motif tags for analyzed games",
    )
    rescan_motifs_parser.add_argument(
        "--player",
        help="Username to scope to (default: all players)",
    )
    rescan_motifs_parser.add_argument(
        "--limit", type=int, default=0,
        help="Max games to rescan (default: all)",
    )

    # hunt-scan (v1.20.0) — deep-scan an opponent's games for tactical blind spots
    hunt_scan_parser = subparsers.add_parser(
        "hunt-scan",
        help="(v1.20.0) Deep-scan an opponent's recent games for missed tactical motifs",
    )
    hunt_scan_parser.add_argument(
        "--opponent", required=True,
        help="Opponent username to deep-scan (must already be cached via Hunter Mode)",
    )
    hunt_scan_parser.add_argument(
        "--platform", default="chess.com",
        choices=["chess.com", "lichess"],
        help="Platform the opponent plays on (default: chess.com)",
    )
    hunt_scan_parser.add_argument(
        "--games", type=int, default=None,
        help="Number of recent games to scan (default: features.hunter_scan_games or 20)",
    )

    # backfill-clocks
    backfill_parser = subparsers.add_parser("backfill-clocks", help="Backfill clock data from PGN annotations")

    # run-all
    run_all_parser = subparsers.add_parser("run-all", help="Run full pipeline")
    run_all_parser.add_argument("--player", action="append", help="Username(s)")
    run_all_parser.add_argument("--provider", choices=["claude", "openai", "gemini", "grok", "mistral", "deepseek", "qwen", "ollama"], help="LLM provider")
    run_all_parser.add_argument(
        "--history", type=int,
        help="Coaching history depth (default: from config, range 1-20)",
    )
    run_all_parser.add_argument(
        "--dump-prompt", metavar="PATH",
        help="(v1.6.0+) Write the full assembled coaching prompt for each "
             "game to PATH. See `coach --dump-prompt` for details.",
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config(args.config)

    if args.command == "harvest":
        cmd_harvest(args, config)
    elif args.command == "analyze":
        cmd_analyze(args, config)
    elif args.command == "coach":
        cmd_coach(args, config)
    elif args.command == "patterns":
        cmd_patterns(args, config)
    elif args.command == "review":
        cmd_review(args, config)
    elif args.command == "trend":
        cmd_trend(args, config)
    elif args.command == "note":
        cmd_note(args, config)
    elif args.command == "report":
        cmd_report(args, config)
    elif args.command == "dashboard":
        cmd_dashboard(args, config)
    elif args.command == "serve":
        rc = cmd_serve(args, config)
        if rc:
            sys.exit(rc)
    elif args.command == "fide-update":
        cmd_fide_update(args, config)
    elif args.command == "backfill-acpl":
        cmd_backfill_acpl(args, config)
    elif args.command == "rescan-motifs":
        cmd_rescan_motifs(args, config)
    elif args.command == "hunt-scan":
        cmd_hunt_scan(args, config)
    elif args.command == "backfill-clocks":
        cmd_backfill_clocks(args, config)
    elif args.command == "run-all":
        cmd_run_all(args, config)


if __name__ == "__main__":
    main()
