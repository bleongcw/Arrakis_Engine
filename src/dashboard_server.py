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
from src.tiers import get_tier

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

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/coach":
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length)) if content_length else {}
            self._handle_coach(body)
        else:
            self._send_json({"error": "Not found"}, 404)

    def _handle_coach(self, body):
        """Trigger coaching for a single game via the dashboard."""
        import threading
        from src.coach import coach_game

        game_id = body.get("game_id")
        provider = body.get("provider", "claude")
        model = body.get("model")

        if not game_id:
            self._send_json({"error": "game_id required"}, 400)
            return

        # Check game exists and is analyzed
        conn = self._get_conn()
        try:
            game = conn.execute(
                "SELECT analysis_status, coaching_status FROM games WHERE id = ?",
                (game_id,),
            ).fetchone()
            if not game:
                self._send_json({"error": "Game not found"}, 404)
                return
            if game["analysis_status"] != "complete":
                self._send_json({"error": "Game not yet analyzed"}, 400)
                return
        finally:
            conn.close()

        # Mark as 'pending' so the dashboard poll can detect the transition
        # back to 'complete' when coaching finishes
        conn2 = self._get_conn()
        try:
            conn2.execute(
                "UPDATE games SET coaching_status = 'pending' WHERE id = ?",
                (game_id,),
            )
            conn2.commit()
        finally:
            conn2.close()

        # Run coaching in a background thread so the request doesn't block
        def run_coach():
            try:
                coach_game(game_id, provider=provider, model=model, db_path=self.db_path)
                logger.info("Dashboard coaching complete for game %d (%s)", game_id, provider)
            except Exception as e:
                logger.error("Dashboard coaching failed for game %d: %s", game_id, e)

        thread = threading.Thread(target=run_coach, daemon=True)
        thread.start()

        self._send_json({
            "status": "started",
            "game_id": game_id,
            "provider": provider,
            "message": f"Coaching started for game {game_id} with {provider}. Refresh in ~30s to see results."
        })

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
            players = []
            for r in rows:
                p = dict_from_row(r)
                # Add tier info based on latest game rating
                latest = conn.execute(
                    """SELECT player_rating FROM games
                    WHERE player_id = ? AND player_rating IS NOT NULL
                    ORDER BY date_played DESC LIMIT 1""",
                    (r["id"],),
                ).fetchone()
                rating = latest["player_rating"] if latest else r["rating"]
                tier = get_tier(rating)
                p["tier"] = tier.name
                p["tier_label"] = tier.label
                p["tier_icon"] = tier.icon
                p["tier_description"] = tier.description
                p["latest_rating"] = rating

                # Profile URLs
                p["chesscom_url"] = f"https://www.chess.com/member/{r['username']}"

                # Lichess URL — look up from config or games
                lichess_game = conn.execute(
                    """SELECT game_url FROM games
                    WHERE player_id = ? AND platform = 'lichess' LIMIT 1""",
                    (r["id"],),
                ).fetchone()
                if lichess_game:
                    # Extract lichess username from game URL
                    p["lichess_url"] = "https://lichess.org"
                    # We'll get the actual username from the games data
                    lichess_pgn = conn.execute(
                        """SELECT pgn FROM games
                        WHERE player_id = ? AND platform = 'lichess' LIMIT 1""",
                        (r["id"],),
                    ).fetchone()
                    if lichess_pgn:
                        import re as _re
                        w = _re.search(r'\[White\s+"([^"]+)"\]', lichess_pgn["pgn"])
                        b = _re.search(r'\[Black\s+"([^"]+)"\]', lichess_pgn["pgn"])
                        # Whichever isn't a known chess.com username
                        for name_match in [w, b]:
                            if name_match and name_match.group(1).lower() != r["username"].lower():
                                continue
                            if name_match:
                                p["lichess_username"] = name_match.group(1)
                                p["lichess_url"] = f"https://lichess.org/@/{name_match.group(1)}"
                                break
                else:
                    p["lichess_url"] = None

                # FIDE URL
                if r["fide_id"]:
                    p["fide_url"] = f"https://ratings.fide.com/profile/{r['fide_id']}"
                else:
                    p["fide_url"] = None

                # Game counts by platform
                p["chesscom_games"] = conn.execute(
                    "SELECT COUNT(*) as c FROM games WHERE player_id = ? AND platform = 'chess.com'",
                    (r["id"],),
                ).fetchone()["c"]
                p["lichess_games"] = conn.execute(
                    "SELECT COUNT(*) as c FROM games WHERE player_id = ? AND platform = 'lichess'",
                    (r["id"],),
                ).fetchone()["c"]

                players.append(p)
            return players
        finally:
            conn.close()

    def _api_games_list(self, params):
        conn = self._get_conn()
        try:
            sql = """
                SELECT g.id, g.player_id, g.game_url, g.player_color,
                       g.player_rating, g.opponent_rating, g.opponent_username,
                       g.result, g.time_control, g.time_class, g.date_played,
                       g.analysis_status, g.coaching_status, g.platform,
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
            games = []
            for r in rows:
                g = dict_from_row(r)
                tier = get_tier(r["player_rating"])
                g["tier"] = tier.name
                g["tier_label"] = tier.label
                g["tier_icon"] = tier.icon
                games.append(g)
            return games
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
                "SELECT * FROM game_coaching WHERE game_id = ? ORDER BY id DESC LIMIT 1",
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

            game_data = dict_from_row(game)
            tier = get_tier(game["player_rating"])
            game_data["tier"] = tier.name
            game_data["tier_label"] = tier.label
            game_data["tier_icon"] = tier.icon
            game_data["tier_description"] = tier.description

            return {
                "game": game_data,
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
