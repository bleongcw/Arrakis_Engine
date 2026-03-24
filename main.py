#!/usr/bin/env python3
"""ArrakisEngine CLI — Chess coaching AI for Evan & Estella."""

import argparse
import logging
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
    sf_config = config["stockfish"]
    db_path = config["database"]["path"]

    count = analyze_pending(
        stockfish_path=sf_config["path"],
        depth=sf_config["depth"],
        threads=sf_config["threads"],
        hash_mb=sf_config["hash_mb"],
        move_time_limit=sf_config.get("move_time_limit", 10.0),
        db_path=db_path,
    )
    print(f"Analyzed {count} games.")


def cmd_coach(args, config):
    """Generate LLM coaching insights for analyzed games."""
    db_path = config["database"]["path"]
    provider = args.provider or config["coaching"]["default_provider"]

    model = None
    if provider == "claude":
        model = config["coaching"]["anthropic_model"]
    elif provider == "openai":
        model = config["coaching"]["openai_model"]

    limit = getattr(args, 'limit', 0) or 0
    count = coach_pending(provider=provider, model=model, db_path=db_path, limit=limit)
    print(f"Coached {count} games with {provider} ({model}).")


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
    run_dashboard(db_path=db_path, port=port, static_dir="dashboard")


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
        "--provider", choices=["claude", "openai"],
        help="LLM provider (default: from config)",
    )
    coach_parser.add_argument(
        "--limit", type=int, default=0,
        help="Max games to coach (default: all pending)",
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

    # run-all
    run_all_parser = subparsers.add_parser("run-all", help="Run full pipeline")
    run_all_parser.add_argument("--player", action="append", help="Username(s)")
    run_all_parser.add_argument("--provider", choices=["claude", "openai"], help="LLM provider")

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
    elif args.command == "run-all":
        cmd_run_all(args, config)


if __name__ == "__main__":
    main()
