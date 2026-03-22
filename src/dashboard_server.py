"""Live dashboard HTTP server with SQLite API endpoints.

Serves the dashboard static files AND provides /api/* endpoints
that query the SQLite database directly. Safe to run while the
analyzer is writing — SQLite WAL mode supports concurrent readers.
"""

import http.server
import json
import logging
import re
from functools import partial
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from src.models import get_connection

logger = logging.getLogger(__name__)


def dict_from_row(row):
    """Convert sqlite3.Row to dict."""
    return dict(row) if row else None


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that routes /api/* to SQLite queries."""

    def __init__(self, *args, db_path=None, **kwargs):
        self.db_path = db_path
        super().__init__(*args, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self._handle_api(path, parse_qs(parsed.query))
        else:
            super().do_GET()

    def _handle_api(self, path, params):
        """Route API requests to handler functions."""
        try:
            # GET /api/players
            if path == "/api/players":
                data = self._api_players()

            # GET /api/games?player=X&result=Y&time_class=Z&from=D&to=D
            elif path == "/api/games":
                data = self._api_games_list(params)

            # GET /api/games/123
            elif re.match(r"^/api/games/(\d+)$", path):
                game_id = int(re.match(r"^/api/games/(\d+)$", path).group(1))
                data = self._api_game_detail(game_id)

            # GET /api/patterns?player=X
            elif path == "/api/patterns":
                data = self._api_patterns(params)

            # GET /api/status
            elif path == "/api/status":
                data = self._api_status()

            else:
                self._send_json({"error": "Not found"}, 404)
                return

            self._send_json(data)

        except Exception as e:
            logger.exception("API error: %s", e)
            self._send_json({"error": str(e)}, 500)

    def _send_json(self, data, status=200):
        """Send a JSON response."""
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _get_conn(self):
        """Open a read-only DB connection for this request."""
        return get_connection(self.db_path)

    # ── API Handlers ──────────────────────────────────────────────

    def _api_players(self):
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM players").fetchall()
            return [dict_from_row(r) for r in rows]
        finally:
            conn.close()

    def _api_games_list(self, params):
        conn = self._get_conn()
        try:
            sql = """
                SELECT g.id, g.player_id, g.game_url, g.player_color,
                       g.player_rating, g.opponent_rating, g.result,
                       g.time_control, g.time_class, g.date_played,
                       g.analysis_status, g.coaching_status,
                       p.username, p.display_name
                FROM games g JOIN players p ON g.player_id = p.id
            """
            conditions = []
            values = []

            player = params.get("player", [None])[0]
            if player:
                conditions.append("p.username = ?")
                values.append(player)

            result = params.get("result", [None])[0]
            if result:
                conditions.append("g.result = ?")
                values.append(result)

            time_class = params.get("time_class", [None])[0]
            if time_class:
                conditions.append("g.time_class = ?")
                values.append(time_class)

            date_from = params.get("from", [None])[0]
            if date_from:
                conditions.append("g.date_played >= ?")
                values.append(date_from)

            date_to = params.get("to", [None])[0]
            if date_to:
                conditions.append("g.date_played <= ?")
                values.append(date_to)

            if conditions:
                sql += " WHERE " + " AND ".join(conditions)

            sql += " ORDER BY g.date_played DESC"

            rows = conn.execute(sql, values).fetchall()
            return [dict_from_row(r) for r in rows]
        finally:
            conn.close()

    def _api_game_detail(self, game_id):
        conn = self._get_conn()
        try:
            game = conn.execute(
                """SELECT g.*, p.username, p.display_name
                FROM games g JOIN players p ON g.player_id = p.id
                WHERE g.id = ?""",
                (game_id,),
            ).fetchone()

            if not game:
                return {"error": "Game not found"}

            moves = conn.execute(
                """SELECT * FROM move_analysis WHERE game_id = ?
                ORDER BY move_number, CASE side WHEN 'white' THEN 0 ELSE 1 END""",
                (game_id,),
            ).fetchall()

            coaching = conn.execute(
                "SELECT * FROM game_coaching WHERE game_id = ?",
                (game_id,),
            ).fetchone()

            coaching_data = dict_from_row(coaching)
            if coaching_data and coaching_data.get("critical_moments_json"):
                try:
                    coaching_data["critical_moments"] = json.loads(
                        coaching_data["critical_moments_json"]
                    )
                except (json.JSONDecodeError, TypeError):
                    coaching_data["critical_moments"] = []
            if coaching_data and coaching_data.get("opening_analysis_json"):
                try:
                    coaching_data["opening_analysis"] = json.loads(
                        coaching_data["opening_analysis_json"]
                    )
                except (json.JSONDecodeError, TypeError):
                    coaching_data["opening_analysis"] = {}

            return {
                "game": dict_from_row(game),
                "moves": [dict_from_row(m) for m in moves],
                "coaching": coaching_data,
            }
        finally:
            conn.close()

    def _api_patterns(self, params):
        conn = self._get_conn()
        try:
            player = params.get("player", [None])[0]
            if not player:
                return {"error": "player parameter required"}

            row = conn.execute(
                """SELECT pp.*, p.username, p.display_name
                FROM player_patterns pp JOIN players p ON pp.player_id = p.id
                WHERE p.username = ?
                ORDER BY pp.updated_at DESC LIMIT 1""",
                (player,),
            ).fetchone()

            if not row:
                return {"stats": None, "username": player}

            data = dict_from_row(row)
            if data.get("stats_json"):
                try:
                    data["stats"] = json.loads(data["stats_json"])
                except (json.JSONDecodeError, TypeError):
                    data["stats"] = None
                del data["stats_json"]

            return data
        finally:
            conn.close()

    def _api_status(self):
        conn = self._get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) as c FROM games").fetchone()["c"]

            analysis = conn.execute(
                """SELECT analysis_status, COUNT(*) as c
                FROM games GROUP BY analysis_status"""
            ).fetchall()
            analysis_map = {r["analysis_status"]: r["c"] for r in analysis}

            coaching = conn.execute(
                """SELECT coaching_status, COUNT(*) as c
                FROM games GROUP BY coaching_status"""
            ).fetchall()
            coaching_map = {r["coaching_status"]: r["c"] for r in coaching}

            return {
                "total_games": total,
                "analysis_pending": analysis_map.get("pending", 0),
                "analyzing": analysis_map.get("analyzing", 0),
                "analysis_complete": analysis_map.get("complete", 0),
                "analysis_error": analysis_map.get("error", 0),
                "coaching_pending": coaching_map.get("pending", 0),
                "coaching_complete": coaching_map.get("complete", 0),
                "coaching_error": coaching_map.get("error", 0),
            }
        finally:
            conn.close()

    def log_message(self, format, *args):
        """Suppress default access logs for cleaner output."""
        if "/api/" in str(args[0]) if args else False:
            logger.debug(format, *args)


def run_dashboard(db_path: str, port: int = 8000, static_dir: str = "dashboard"):
    """Start the live dashboard server."""
    handler = partial(DashboardHandler, directory=static_dir, db_path=db_path)
    with http.server.HTTPServer(("", port), handler) as httpd:
        print(f"🏰 ArrakisEngine Dashboard running at http://localhost:{port}")
        print(f"📊 Live data from: {db_path}")
        print("Press Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nDashboard stopped.")
