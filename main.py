#!/usr/bin/env python3
# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""ArrakisEngine CLI — Chess coaching AI."""

import argparse
import logging
import os
import sys

import yaml
from dotenv import load_dotenv

load_dotenv()

import http.server
import functools

from src.harvester import harvest_player
from src.analyzer import analyze_pending
from src.coach import coach_pending
from src.patterns import update_patterns
from src.export import export_json
from src.report import generate_report
from src.models import init_db


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def cmd_harvest(args, config):
    """Harvest games from chess.com and/or lichess for configured players."""
    db_path = config["database"]["path"]
    months = config["analysis"]["months_lookback"]
    conn = init_db(db_path)
    conn.close()

    platform_filter = getattr(args, "platform", None)

    players = config["players"]
    if args.player:
        players = [p for p in players if p["username"] in args.player]

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
    result = coach_pending(provider=provider, model=model, db_path=db_path, limit=limit, config=config)
    print(f"Coached {result['coached']} games with {provider} ({model}). "
          f"Errors: {result['errors']}, Skipped: {result['skipped']}"
          + (f" — Aborted: {result['abort_reason']}" if result.get('aborted') else ""))


def cmd_patterns(args, config):
    """Update pattern tracking for all players."""
    db_path = config["database"]["path"]
    count = update_patterns(db_path=db_path)
    print(f"Updated patterns for {count} players.")


def cmd_export_json(args, config):
    """Export data to JSON for the dashboard."""
    db_path = config["database"]["path"]
    counts = export_json(output_dir="dashboard/data", db_path=db_path)
    print(f"Exported: {counts['players']} players, {counts['games']} games, "
          f"{counts['patterns']} pattern records.")


def cmd_report(args, config):
    """Generate coaching reports."""
    db_path = config["database"]["path"]
    players = config["players"]
    if args.player:
        players = [p for p in players if p["username"] in args.player]

    period = "monthly" if args.monthly else "weekly"
    output_dir = args.output or "reports"

    for player in players:
        path = generate_report(
            player["username"], period=period,
            output_dir=output_dir, db_path=db_path,
        )
        print(f"  {player['username']}: {path}")


def cmd_dashboard(args, config):
    """Launch the live dashboard server with API endpoints."""
    db_path = config["database"]["path"]
    port = args.port or 8000

    from src.dashboard_server import run_dashboard
    run_dashboard(db_path=db_path, port=port, config=config, static_dir="dashboard")


def cmd_fide_update(args, config):
    """Update FIDE rating for a player."""
    db_path = config["database"]["path"]
    conn = init_db(db_path)

    username = args.player
    rating = args.rating
    fide_id = getattr(args, "fide_id", None)

    # Find the player
    player = conn.execute(
        "SELECT id, username, display_name, fide_id, fide_rating FROM players WHERE username = ?",
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

    print("\n=== Step 3/5: Coaching games ===")
    cmd_coach(args, config)

    print("\n=== Step 4/5: Updating patterns ===")
    cmd_patterns(args, config)

    print("\n=== Step 5/5: Exporting JSON ===")
    cmd_export_json(args, config)

    print("\nPipeline complete! Run 'python main.py dashboard' to view results.")


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

    # patterns
    patterns_parser = subparsers.add_parser("patterns", help="Update pattern tracking")

    # export-json
    export_parser = subparsers.add_parser("export-json", help="Export data to JSON for dashboard")

    # report
    report_parser = subparsers.add_parser("report", help="Generate coaching reports")
    report_parser.add_argument("--player", action="append", help="Username(s) to report on")
    report_parser.add_argument("--weekly", action="store_true", default=True, help="Weekly report (default)")
    report_parser.add_argument("--monthly", action="store_true", help="Monthly report")
    report_parser.add_argument("--output", help="Output directory (default: reports/)")

    # dashboard
    dashboard_parser = subparsers.add_parser("dashboard", help="Launch local dashboard server")
    dashboard_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")

    # fide-update
    fide_parser = subparsers.add_parser("fide-update", help="Update FIDE rating for a player")
    fide_parser.add_argument("--player", required=True, help="Chess.com username of the player")
    fide_parser.add_argument("--rating", type=int, help="New FIDE rating")
    fide_parser.add_argument("--fide-id", help="FIDE player ID (e.g., 1234567)")

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
    elif args.command == "export-json":
        cmd_export_json(args, config)
    elif args.command == "report":
        cmd_report(args, config)
    elif args.command == "dashboard":
        cmd_dashboard(args, config)
    elif args.command == "fide-update":
        cmd_fide_update(args, config)
    elif args.command == "backfill-clocks":
        cmd_backfill_clocks(args, config)
    elif args.command == "run-all":
        cmd_run_all(args, config)


if __name__ == "__main__":
    main()
