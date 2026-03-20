"""JSON export for the web dashboard.

Exports games, analysis, coaching, and patterns to JSON files
that the single-file dashboard can load.
"""

import json
import logging
from pathlib import Path

from src.models import init_db

logger = logging.getLogger(__name__)


def export_json(output_dir: str = "dashboard/data", db_path: str | None = None) -> dict:
    """Export all data to JSON files for the dashboard.

    Returns counts of exported items.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    conn = init_db(db_path)

    # Export players
    players = conn.execute("SELECT * FROM players").fetchall()
    players_data = [dict(p) for p in players]
    _write_json(out / "players.json", players_data)

    # Export games with coaching
    games = conn.execute(
        """SELECT g.*, p.username, p.display_name
        FROM games g JOIN players p ON g.player_id = p.id
        ORDER BY g.date_played DESC"""
    ).fetchall()
    games_data = []
    for g in games:
        gd = dict(g)
        # Remove large PGN from list view (keep in detail)
        gd["pgn_preview"] = (gd["pgn"] or "")[:200]
        games_data.append(gd)
    _write_json(out / "games.json", games_data)

    # Export per-game detail (analysis + coaching) as individual files
    detail_dir = out / "games"
    detail_dir.mkdir(exist_ok=True)

    for g in games:
        game_id = g["id"]

        moves = conn.execute(
            """SELECT * FROM move_analysis WHERE game_id = ?
            ORDER BY move_number, CASE side WHEN 'white' THEN 0 ELSE 1 END""",
            (game_id,),
        ).fetchall()

        coaching = conn.execute(
            "SELECT * FROM game_coaching WHERE game_id = ?",
            (game_id,),
        ).fetchone()

        detail = {
            "game": dict(g),
            "moves": [dict(m) for m in moves],
            "coaching": dict(coaching) if coaching else None,
        }
        _write_json(detail_dir / f"{game_id}.json", detail)

    # Export patterns
    patterns = conn.execute(
        """SELECT pp.*, p.username, p.display_name
        FROM player_patterns pp JOIN players p ON pp.player_id = p.id
        ORDER BY pp.updated_at DESC"""
    ).fetchall()
    patterns_data = []
    for p in patterns:
        pd = dict(p)
        if pd.get("stats_json"):
            pd["stats"] = json.loads(pd["stats_json"])
            del pd["stats_json"]
        patterns_data.append(pd)
    _write_json(out / "patterns.json", patterns_data)

    conn.close()

    counts = {
        "players": len(players_data),
        "games": len(games_data),
        "patterns": len(patterns_data),
    }
    logger.info("Exported to %s: %s", output_dir, counts)
    return counts


def _write_json(path: Path, data):
    """Write data to a JSON file."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
