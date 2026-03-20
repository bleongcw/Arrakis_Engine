#!/usr/bin/env python3
"""ArrakisEngine CLI — Chess coaching AI for Evan & Estella."""

import argparse
import logging
import sys

import yaml
from dotenv import load_dotenv

load_dotenv()

from src.harvester import harvest_player
from src.analyzer import analyze_pending
from src.coach import coach_pending
from src.patterns import update_patterns
from src.models import init_db


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def cmd_harvest(args, config):
    """Harvest games from chess.com for all configured players."""
    db_path = config["database"]["path"]
    months = config["analysis"]["months_lookback"]
    conn = init_db(db_path)
    conn.close()

    players = config["players"]
    if args.player:
        players = [p for p in players if p["username"] in args.player]

    for player in players:
        username = player["username"]
        logging.info("Harvesting games for %s...", username)

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

        stats = harvest_player(username, db_path=db_path, months=months)
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

    count = coach_pending(provider=provider, model=model, db_path=db_path)
    print(f"Coached {count} games with {provider} ({model}).")


def cmd_patterns(args, config):
    """Update pattern tracking for all players."""
    db_path = config["database"]["path"]
    count = update_patterns(db_path=db_path)
    print(f"Updated patterns for {count} players.")


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
    harvest_parser = subparsers.add_parser("harvest", help="Fetch games from chess.com")
    harvest_parser.add_argument(
        "--player", action="append",
        help="Username(s) to harvest (default: all configured players)",
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

    # patterns
    patterns_parser = subparsers.add_parser("patterns", help="Update pattern tracking")

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


if __name__ == "__main__":
    main()
