"""Live dashboard HTTP server with SQLite API endpoints.

Serves the dashboard static files AND provides /api/* endpoints
that query the SQLite database directly. Safe to run while the
analyzer is writing — SQLite WAL mode supports concurrent readers.
"""

import http.server
import json
import logging
import re
import shutil
import threading
import time
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

    def __init__(self, *args, db_path=None, config=None, **kwargs):
        self.db_path = db_path
        self.config = config or {}
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

        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        if path == "/api/coach":
            self._handle_coach(body)
        elif path == "/api/trend-summary":
            self._handle_trend_summary(body)
        elif path == "/api/pipeline/harvest":
            self._handle_pipeline_harvest(body)
        elif path == "/api/pipeline/analyze":
            self._handle_pipeline_analyze(body)
        elif path == "/api/pipeline/patterns":
            self._handle_pipeline_patterns(body)
        elif path == "/api/pipeline/run-all":
            self._handle_pipeline_run_all(body)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ── Coaching handlers (existing) ─────────────────────────────

    def _handle_coach(self, body):
        """Trigger coaching for a single game via the dashboard."""
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
        conn2 = self._get_conn()
        try:
            conn2.execute(
                "UPDATE games SET coaching_status = 'pending' WHERE id = ?",
                (game_id,),
            )
            conn2.commit()
        finally:
            conn2.close()

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

    def _handle_trend_summary(self, body):
        """Trigger LLM trend summary generation for a player."""
        from src.patterns import generate_trend_summary

        player_username = body.get("player")
        provider = body.get("provider", "claude")

        if not player_username:
            self._send_json({"error": "player required"}, 400)
            return

        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT id FROM players WHERE username = ?",
                (player_username,),
            ).fetchone()
            if not row:
                self._send_json({"error": f"Player {player_username} not found"}, 404)
                return
            player_id = row["id"]
        finally:
            conn.close()

        def run_summary():
            try:
                generate_trend_summary(player_id, db_path=self.db_path, provider=provider)
                logger.info("Trend summary complete for %s (%s)", player_username, provider)
            except Exception as e:
                logger.error("Trend summary failed for %s: %s", player_username, e)

        thread = threading.Thread(target=run_summary, daemon=True)
        thread.start()

        self._send_json({
            "status": "started",
            "player": player_username,
            "provider": provider,
            "message": f"Trend summary generation started for {player_username}."
        })

    # ── Pipeline handlers ────────────────────────────────────────

    def _handle_pipeline_harvest(self, body):
        """Trigger game harvesting from Chess.com/Lichess."""
        from src import pipeline_state
        from src.harvester import harvest_player
        from src.models import init_db, ensure_player

        if not pipeline_state.start_task("harvest"):
            current = pipeline_state.current_task()
            self._send_json(
                {"error": f"Another task is running: {current}"},
                409,
            )
            return

        config = self.config
        db_path = self.db_path
        player_filter = body.get("player")
        players = config.get("players", [])
        months = config.get("analysis", {}).get("months_lookback", 6)

        if player_filter:
            players = [p for p in players if p["username"] == player_filter]

        def run():
            try:
                total_new = 0
                total_errors = 0
                for i, player in enumerate(players):
                    username = player["username"]
                    display_name = player.get("display_name", username)
                    pipeline_state.update_progress(
                        f"Fetching games for {display_name}...",
                        {"current_step": i + 1, "total_steps": len(players)},
                    )

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
                        lichess_username=player.get("lichess_username"),
                    )
                    total_new += stats.get("new", 0)
                    total_errors += stats.get("errors", 0)

                pipeline_state.complete_task({
                    "players": len(players),
                    "new_games": total_new,
                    "errors": total_errors,
                })
            except Exception as e:
                logger.exception("Pipeline harvest failed: %s", e)
                pipeline_state.fail_task(str(e))

        threading.Thread(target=run, daemon=True).start()
        self._send_json({"status": "started", "message": "Harvesting games..."})

    def _handle_pipeline_analyze(self, body):
        """Trigger Stockfish analysis on pending games."""
        from src import pipeline_state
        from src.analyzer import analyze_pending

        if not pipeline_state.start_task("analyze"):
            current = pipeline_state.current_task()
            self._send_json(
                {"error": f"Another task is running: {current}"},
                409,
            )
            return

        config = self.config
        db_path = self.db_path
        sf_config = config.get("stockfish", {})
        sf_path = sf_config.get("path", "/usr/local/bin/stockfish")

        # Validate Stockfish binary
        if not Path(sf_path).is_file():
            found = shutil.which("stockfish")
            if found:
                sf_path = found
            else:
                pipeline_state.fail_task(
                    "Stockfish not found. Install it with: brew install stockfish"
                )
                self._send_json({"status": "started", "message": "Starting analysis..."})
                return

        def run():
            try:
                # Count pending games for progress tracking
                conn = get_connection(db_path)
                total_pending = conn.execute(
                    "SELECT COUNT(*) as c FROM games WHERE analysis_status = 'pending'"
                ).fetchone()["c"]
                conn.close()

                if total_pending == 0:
                    pipeline_state.complete_task({"games_analyzed": 0})
                    return

                pipeline_state.update_progress(
                    f"Analyzing {total_pending} games with Stockfish...",
                    {"games_total": total_pending, "games_processed": 0},
                )

                # Start a progress-polling sub-thread
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
                                f"Analyzing game {done} of {total_pending}...",
                                {"games_total": total_pending, "games_processed": done},
                            )
                        except Exception:
                            pass
                        stop_polling.wait(3)

                poller = threading.Thread(target=poll_progress, daemon=True)
                poller.start()

                count = analyze_pending(
                    stockfish_path=sf_path,
                    depth=sf_config.get("depth", 22),
                    threads=sf_config.get("threads", 6),
                    hash_mb=sf_config.get("hash_mb", 512),
                    move_time_limit=sf_config.get("move_time_limit", 10.0),
                    db_path=db_path,
                )

                stop_polling.set()
                poller.join(timeout=5)
                pipeline_state.complete_task({"games_analyzed": count})

            except Exception as e:
                logger.exception("Pipeline analyze failed: %s", e)
                pipeline_state.fail_task(str(e))

        threading.Thread(target=run, daemon=True).start()
        self._send_json({"status": "started", "message": "Starting analysis..."})

    def _handle_pipeline_patterns(self, body):
        """Trigger pattern computation."""
        from src import pipeline_state
        from src.patterns import compute_player_patterns

        if not pipeline_state.start_task("patterns"):
            current = pipeline_state.current_task()
            self._send_json(
                {"error": f"Another task is running: {current}"},
                409,
            )
            return

        db_path = self.db_path
        player_filter = body.get("player")

        def run():
            try:
                conn = get_connection(db_path)
                if player_filter:
                    rows = conn.execute(
                        "SELECT id, username, display_name FROM players WHERE username = ?",
                        (player_filter,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, username, display_name FROM players"
                    ).fetchall()
                conn.close()

                players_updated = 0
                for i, row in enumerate(rows):
                    display = row["display_name"] or row["username"]
                    pipeline_state.update_progress(
                        f"Computing insights for {display}...",
                        {"current_step": i + 1, "total_steps": len(rows)},
                    )
                    compute_player_patterns(row["id"], db_path=db_path)
                    players_updated += 1

                pipeline_state.complete_task({"players_updated": players_updated})

            except Exception as e:
                logger.exception("Pipeline patterns failed: %s", e)
                pipeline_state.fail_task(str(e))

        threading.Thread(target=run, daemon=True).start()
        self._send_json({"status": "started", "message": "Updating insights..."})

    def _handle_pipeline_run_all(self, body):
        """Chain harvest -> analyze -> patterns."""
        from src import pipeline_state
        from src.harvester import harvest_player
        from src.analyzer import analyze_pending
        from src.patterns import compute_player_patterns
        from src.models import init_db, ensure_player

        if not pipeline_state.start_task("run_all"):
            current = pipeline_state.current_task()
            self._send_json(
                {"error": f"Another task is running: {current}"},
                409,
            )
            return

        config = self.config
        db_path = self.db_path
        player_filter = body.get("player")
        players = config.get("players", [])
        months = config.get("analysis", {}).get("months_lookback", 6)
        sf_config = config.get("stockfish", {})
        sf_path = sf_config.get("path", "/usr/local/bin/stockfish")

        if player_filter:
            players = [p for p in players if p["username"] == player_filter]

        # Validate stockfish
        if not Path(sf_path).is_file():
            found = shutil.which("stockfish")
            if found:
                sf_path = found
            else:
                pipeline_state.fail_task(
                    "Stockfish not found. Install it with: brew install stockfish"
                )
                self._send_json({"status": "started", "message": "Starting pipeline..."})
                return

        def run():
            try:
                # Step 1: Harvest
                pipeline_state.update_progress(
                    "Step 1/3: Fetching new games...",
                    {"current_step": 1, "total_steps": 3},
                )
                total_new = 0
                total_errors = 0
                for player in players:
                    username = player["username"]
                    display = player.get("display_name", username)
                    pipeline_state.update_progress(
                        f"Step 1/3: Fetching games for {display}...",
                        {"current_step": 1, "total_steps": 3},
                    )

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
                    "SELECT id, username, display_name FROM players"
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

                pipeline_state.complete_task({
                    "new_games": total_new,
                    "games_analyzed": games_analyzed,
                    "players_updated": players_updated,
                    "errors": total_errors,
                })

            except Exception as e:
                logger.exception("Pipeline run-all failed: %s", e)
                pipeline_state.fail_task(str(e))

        threading.Thread(target=run, daemon=True).start()
        self._send_json({"status": "started", "message": "Starting full pipeline..."})

    # ── API routing ──────────────────────────────────────────────

    def _handle_api(self, path, params):
        """Route API requests to handler functions."""
        try:
            if path == "/api/players":
                data = self._api_players()
            elif path == "/api/games":
                data = self._api_games_list(params)
            elif re.match(r"^/api/games/(\d+)$", path):
                game_id = int(re.match(r"^/api/games/(\d+)$", path).group(1))
                data = self._api_game_detail(game_id)
            elif path == "/api/patterns":
                data = self._api_patterns(params)
            elif path == "/api/report":
                data = self._api_report(params)
            elif path == "/api/status":
                data = self._api_status()
            elif path == "/api/pipeline/status":
                data = self._api_pipeline_status()
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
                fide_rating = r["fide_rating"] if "fide_rating" in r.keys() else None
                if fide_rating:
                    rating = fide_rating
                else:
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

                p["chesscom_url"] = f"https://www.chess.com/member/{r['username']}"

                if r["lichess_username"]:
                    p["lichess_url"] = f"https://lichess.org/@/{r['lichess_username']}"
                else:
                    p["lichess_url"] = None

                if r["fide_id"]:
                    p["fide_url"] = f"https://ratings.fide.com/profile/{r['fide_id']}"
                else:
                    p["fide_url"] = None

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

    def _api_report(self, params):
        from src.report import build_report_data

        player = params.get("player", [None])[0]
        if not player:
            return {"error": "player parameter required"}

        period = params.get("period", ["monthly"])[0]
        if period not in ("weekly", "monthly"):
            period = "monthly"

        try:
            data = build_report_data(player, period=period, db_path=self.db_path)
            return data
        except ValueError as e:
            return {"error": str(e)}

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

    def _api_pipeline_status(self):
        from src import pipeline_state
        return pipeline_state.get_state()

    def log_message(self, format, *args):
        """Suppress default access logs for cleaner output."""
        if "/api/" in str(args[0]) if args else False:
            logger.debug(format, *args)


def run_dashboard(db_path: str, port: int = 8000, config: dict | None = None,
                  static_dir: str = "dashboard"):
    """Start the live dashboard server."""
    handler = partial(DashboardHandler, directory=static_dir, db_path=db_path,
                      config=config or {})
    with http.server.HTTPServer(("", port), handler) as httpd:
        print(f"\U0001f3f0 ArrakisEngine Dashboard running at http://localhost:{port}")
        print(f"\U0001f4ca Live data from: {db_path}")
        print("Press Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nDashboard stopped.")
