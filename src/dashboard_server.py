# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Live dashboard HTTP server with SQLite API endpoints.

Serves the dashboard static files AND provides /api/* endpoints
that query the SQLite database directly. Safe to run while the
analyzer is writing — SQLite WAL mode supports concurrent readers.
"""

import http.server
import json
import logging
import os
import re
import shutil
import threading
import time
from functools import partial
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import yaml

from src.models import get_connection, update_player
from src.tiers import get_tier

logger = logging.getLogger(__name__)

# Module-level scheduler manager, set by run_dashboard()
_scheduler_manager = None

# ── Route registry (v1.22.0) ─────────────────────────────────────────
# HTTP dispatch is table-driven so out-of-tree code (e.g. the commercial
# Atreides PGN-import module) can register routes into the core dashboard
# before serve() starts, instead of running a separate sidecar process.
#
# Exact-match dicts map a path string -> handler. Regex lists hold
# (compiled_pattern, handler) pairs tried in order after exact matches miss.
#
# Handler signatures:
#   GET    handler(self, params) -> data            (data is JSON-serialized by caller)
#   GET    regex: handler(self, params, *groups) -> data
#   mutate handler(self, body)                      (handler sends its own response)
#   mutate regex: handler(self, body, *groups)
_GET_ROUTES: dict = {}
_GET_REGEX_ROUTES: list = []
_POST_ROUTES: dict = {}
_POST_REGEX_ROUTES: list = []
_PUT_ROUTES: dict = {}
_PUT_REGEX_ROUTES: list = []
_DELETE_ROUTES: dict = {}
_DELETE_REGEX_ROUTES: list = []

_EXACT_ROUTES = {
    "GET": _GET_ROUTES,
    "POST": _POST_ROUTES,
    "PUT": _PUT_ROUTES,
    "DELETE": _DELETE_ROUTES,
}
_REGEX_ROUTES = {
    "GET": _GET_REGEX_ROUTES,
    "POST": _POST_REGEX_ROUTES,
    "PUT": _PUT_REGEX_ROUTES,
    "DELETE": _DELETE_REGEX_ROUTES,
}


def register_route(method: str, path: str, handler):
    """Register an exact-match route handler.

    `method` is one of GET/POST/PUT/DELETE. `handler` receives
    (self, params) for GET (returning the data to serialize) or
    (self, body) for mutations (sending its own response).
    """
    _EXACT_ROUTES[method.upper()][path] = handler


def register_regex_route(method: str, pattern, handler):
    """Register a regex route handler, tried after exact matches.

    `pattern` may be a string (compiled here) or a precompiled pattern.
    `handler` receives the matched groups as trailing args:
    (self, params, *groups) for GET or (self, body, *groups) for mutations.
    """
    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
    _REGEX_ROUTES[method.upper()].append((compiled, handler))


def dict_from_row(row):
    """Convert sqlite3.Row to dict."""
    return dict(row) if row else None


def _resolve_player_id(conn, identifier: str) -> int | None:
    """v1.16.4: slug-only player lookup.

    The chess.com `username` column is reserved exclusively for the
    harvester's API calls — it never appears in URLs, the API
    `?player=` param, the CLI `--player` flag, or any user-facing
    surface. v1.16.4 dropped the v1.16.1 backward-compat fallback
    that accepted username here; old bookmarks using the chess.com
    handle now 404 (frontend has been emitting slug-only URLs since
    v1.16.1, so the practical impact is just stale browser
    bookmarks).

    Returns None if no player matches — callers should 404.
    """
    if not identifier:
        return None
    row = conn.execute(
        "SELECT id FROM players WHERE slug = ?", (identifier,)
    ).fetchone()
    return row["id"] if row else None


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that routes /api/* to SQLite queries.

    v1.13.3: switched from SimpleHTTPRequestHandler to BaseHTTPRequestHandler
    — the backend is API-only. The Next.js frontend on port 3000 serves
    every UI asset; this server only ever needs to answer /api/* paths.
    Non-/api paths return 404."""

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
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        self._dispatch_mutation(_POST_ROUTES, _POST_REGEX_ROUTES, path, body)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        self._dispatch_mutation(_PUT_ROUTES, _PUT_REGEX_ROUTES, path, body)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        self._dispatch_mutation(_DELETE_ROUTES, _DELETE_REGEX_ROUTES, path, None)

    def _dispatch_mutation(self, routes, regex_routes, path, body):
        """Look up an exact route, then the regex routes, else 404.

        Handlers send their own response (the registry stores them so that
        out-of-tree code can register POST/PUT/DELETE endpoints too)."""
        handler = routes.get(path)
        if handler is not None:
            handler(self, body)
            return
        for pattern, h in regex_routes:
            m = pattern.match(path)
            if m:
                h(self, body, *m.groups())
                return
        self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
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

        config = self.config

        def run_coach():
            try:
                coach_game(game_id, provider=provider, model=model, db_path=self.db_path, config=config)
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
            # v1.16.1: accept slug OR chess.com username
            player_id = _resolve_player_id(conn, player_username)
            if player_id is None:
                self._send_json({"error": f"Player {player_username} not found"}, 404)
                return
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

    def _handle_recent_form_review(self, body):
        """v1.9.0: trigger Recent Form Review (last N games) for a player.
        v1.10.0: now accepts optional `platform` to scope the review."""
        from src.patterns import compute_recent_form_review, DEFAULT_REVIEW_WINDOW

        player_username = body.get("player")
        provider = body.get("provider", "openai")
        window = int(body.get("window", DEFAULT_REVIEW_WINDOW) or DEFAULT_REVIEW_WINDOW)
        window = max(3, min(30, window))  # clamp 3-30
        # v1.10.0: optional platform scope. None → most-played fallback in the helper.
        platform = body.get("platform")
        if platform is not None:
            platform = str(platform).strip() or None

        if not player_username:
            self._send_json({"error": "player required"}, 400)
            return

        conn = self._get_conn()
        try:
            # v1.16.1: accept slug OR chess.com username
            player_id = _resolve_player_id(conn, player_username)
            if player_id is None:
                self._send_json({"error": f"Player {player_username} not found"}, 404)
                return
        finally:
            conn.close()

        # Load coaching config so the provider can resolve its model from yaml
        cfg = None
        try:
            import yaml
            with open("config.yaml") as f:
                cfg = yaml.safe_load(f)
        except Exception:
            pass

        def run_review():
            try:
                compute_recent_form_review(
                    player_id, db_path=self.db_path,
                    provider=provider, window=window, config=cfg,
                    platform=platform,
                )
                logger.info("Recent form review complete for %s (%s, %d games, platform=%s)",
                            player_username, provider, window, platform)
            except Exception as e:
                logger.error("Recent form review failed for %s: %s", player_username, e)

        thread = threading.Thread(target=run_review, daemon=True)
        thread.start()

        self._send_json({
            "status": "started",
            "player": player_username,
            "provider": provider,
            "window": window,
            "platform": platform,
            "message": f"Recent form review started for {player_username} (last {window} games).",
        })

    # ── v1.12.0: Journal Note CRUD ──────────────────────────────

    def _handle_create_note(self, body):
        """POST /api/journal/note — create a parent-authored note entry."""
        from src import journal as journal_mod

        player_username = body.get("player")
        note_body = body.get("body")
        platform = body.get("platform") or "chess.com"

        if not player_username:
            self._send_json({"error": "player required"}, 400)
            return

        conn = self._get_conn()
        try:
            # v1.16.1: accept slug OR chess.com username
            player_id = _resolve_player_id(conn, player_username)
            if player_id is None:
                self._send_json({"error": f"Player {player_username} not found"}, 404)
                return
        finally:
            conn.close()

        try:
            entry = journal_mod.create_note(
                player_id, note_body, platform=platform,
                db_path=self.db_path,
            )
        except ValueError as e:
            self._send_json({"error": str(e)}, 400)
            return

        # Decode refs_json / metadata_json so the response matches the
        # GET /api/journal entry shape the client expects
        if entry.get("refs_json"):
            try:
                entry["refs"] = json.loads(entry["refs_json"])
            except (json.JSONDecodeError, TypeError):
                entry["refs"] = []
        else:
            entry["refs"] = []
        if entry.get("metadata_json"):
            try:
                entry["metadata"] = json.loads(entry["metadata_json"])
            except (json.JSONDecodeError, TypeError):
                entry["metadata"] = {}
        else:
            entry["metadata"] = {}
        entry.pop("refs_json", None)
        entry.pop("metadata_json", None)
        self._send_json({"entry": entry})

    def _handle_update_note(self, entry_id: int, body):
        """PUT /api/journal/note/<id> — update note body (notes only)."""
        from src import journal as journal_mod

        new_body = body.get("body")
        try:
            entry = journal_mod.update_note(
                entry_id, new_body, db_path=self.db_path,
            )
        except ValueError as e:
            msg = str(e)
            status = 404 if "not found" in msg.lower() else 400
            self._send_json({"error": msg}, status)
            return

        if entry.get("refs_json"):
            try:
                entry["refs"] = json.loads(entry["refs_json"])
            except (json.JSONDecodeError, TypeError):
                entry["refs"] = []
        else:
            entry["refs"] = []
        if entry.get("metadata_json"):
            try:
                entry["metadata"] = json.loads(entry["metadata_json"])
            except (json.JSONDecodeError, TypeError):
                entry["metadata"] = {}
        else:
            entry["metadata"] = {}
        entry.pop("refs_json", None)
        entry.pop("metadata_json", None)
        self._send_json({"entry": entry})

    def _handle_delete_note(self, entry_id: int):
        """DELETE /api/journal/note/<id> — delete a note entry (notes only)."""
        from src import journal as journal_mod

        try:
            journal_mod.delete_note(entry_id, db_path=self.db_path)
        except ValueError as e:
            msg = str(e)
            status = 404 if "not found" in msg.lower() else 400
            self._send_json({"error": msg}, status)
            return
        self._send_json({"status": "deleted", "id": entry_id})

    # ── Player CRUD handlers ────────────────────────────────────

    def _handle_create_player(self, body):
        """Create a new player (or reactivate an archived one)."""
        from src.models import ensure_player

        username = (body.get("username") or "").strip().lower()
        if not username:
            self._send_json({"error": "username is required"}, 400)
            return

        conn = self._get_conn()
        try:
            existing = conn.execute(
                "SELECT id, is_active FROM players WHERE username = ?", (username,)
            ).fetchone()

            if existing and existing["is_active"] == 1:
                self._send_json({"error": f"Player '{username}' already exists"}, 409)
                return

            if existing and existing["is_active"] == 0:
                # Reactivate archived player
                conn.execute(
                    "UPDATE players SET is_active = 1 WHERE id = ?", (existing["id"],)
                )
                update_player(
                    conn, existing["id"],
                    display_name=body.get("display_name"),
                    age=body.get("age"),
                    rating=body.get("rating"),
                    fide_id=body.get("fide_id"),
                    fide_rating=body.get("fide_rating"),
                    lichess_username=body.get("lichess_username"),
                )
                conn.commit()
                self._send_json({"status": "reactivated", "id": existing["id"]}, 201)
                return

            player_id = ensure_player(
                conn, username,
                display_name=body.get("display_name"),
                age=body.get("age"),
                rating=body.get("rating"),
                fide_id=body.get("fide_id"),
                fide_rating=body.get("fide_rating"),
                lichess_username=body.get("lichess_username"),
            )
            self._send_json({"status": "created", "id": player_id}, 201)
        finally:
            conn.close()

    def _handle_update_player(self, player_id, body):
        """Update player fields. Username is not editable."""
        conn = self._get_conn()
        try:
            existing = conn.execute(
                "SELECT id FROM players WHERE id = ? AND is_active = 1", (player_id,)
            ).fetchone()
            if not existing:
                self._send_json({"error": "Player not found"}, 404)
                return

            update_player(
                conn, player_id,
                display_name=body.get("display_name"),
                age=body.get("age"),
                rating=body.get("rating"),
                fide_id=body.get("fide_id"),
                fide_rating=body.get("fide_rating"),
                lichess_username=body.get("lichess_username"),
            )
            self._send_json({"status": "updated", "id": player_id})
        finally:
            conn.close()

    def _handle_delete_player(self, player_id):
        """Archive a player (soft delete). Game history is preserved."""
        conn = self._get_conn()
        try:
            existing = conn.execute(
                "SELECT id, username FROM players WHERE id = ? AND is_active = 1",
                (player_id,),
            ).fetchone()
            if not existing:
                self._send_json({"error": "Player not found"}, 404)
                return

            game_count = conn.execute(
                "SELECT COUNT(*) as c FROM games WHERE player_id = ?", (player_id,)
            ).fetchone()["c"]

            conn.execute("UPDATE players SET is_active = 0 WHERE id = ?", (player_id,))
            conn.commit()
            self._send_json({
                "status": "archived",
                "id": player_id,
                "username": existing["username"],
                "games_preserved": game_count,
            })
        finally:
            conn.close()

    # ── Settings handlers ────────────────────────────────────────

    def _handle_settings_get(self):
        """Return current analysis config + API key status."""
        sf = self.config.get("stockfish", {})
        analysis = self.config.get("analysis", {})

        # Mask API keys — coach.py uses the ARRAKIS_ prefix
        def mask_key(env_var):
            key = os.environ.get(env_var, "")
            if not key or len(key) < 8:
                return None
            return key[:6] + "\u2022" * 6 + key[-4:]

        coaching = self.config.get("coaching", {})

        from src.llm_providers import get_available_providers

        return {
            "analysis": {
                "stockfish_path": sf.get("path", shutil.which("stockfish") or "stockfish"),
                "depth": sf.get("depth", 22),
                "threads": sf.get("threads", 6),
                "hash_mb": sf.get("hash_mb", 512),
                "move_time_limit": sf.get("move_time_limit", 10.0),
                "months_lookback": analysis.get("months_lookback", 6),
            },
            "api_keys": {
                "anthropic_configured": bool(os.environ.get("ARRAKIS_ANTHROPIC_API_KEY", "")),
                "anthropic_key_hint": mask_key("ARRAKIS_ANTHROPIC_API_KEY"),
                "openai_configured": bool(os.environ.get("ARRAKIS_OPENAI_API_KEY", "")),
                "openai_key_hint": mask_key("ARRAKIS_OPENAI_API_KEY"),
                "google_configured": bool(os.environ.get("ARRAKIS_GOOGLE_API_KEY", "")),
                "google_key_hint": mask_key("ARRAKIS_GOOGLE_API_KEY"),
                "xai_configured": bool(os.environ.get("ARRAKIS_XAI_API_KEY", "")),
                "xai_key_hint": mask_key("ARRAKIS_XAI_API_KEY"),
                "mistral_configured": bool(os.environ.get("ARRAKIS_MISTRAL_API_KEY", "")),
                "mistral_key_hint": mask_key("ARRAKIS_MISTRAL_API_KEY"),
                "deepseek_configured": bool(os.environ.get("ARRAKIS_DEEPSEEK_API_KEY", "")),
                "deepseek_key_hint": mask_key("ARRAKIS_DEEPSEEK_API_KEY"),
                "qwen_configured": bool(os.environ.get("ARRAKIS_QWEN_API_KEY", "")),
                "qwen_key_hint": mask_key("ARRAKIS_QWEN_API_KEY"),
                "ollama_configured": True,
            },
            "coaching": {
                "default_provider": coaching.get("default_provider", "claude"),
                "anthropic_model": coaching.get("anthropic_model", "claude-opus-4-6"),
                "openai_model": coaching.get("openai_model", "gpt-5.4"),
                "gemini_model": coaching.get("gemini_model", "gemini-2.5-pro"),
                "grok_model": coaching.get("grok_model", "grok-3"),
                "mistral_model": coaching.get("mistral_model", "mistral-medium-latest"),
                "deepseek_model": coaching.get("deepseek_model", "deepseek-reasoner"),
                "qwen_model": coaching.get("qwen_model", "qwen3-235b-a22b"),
                "ollama_model": coaching.get("ollama_model", "deepseek-r1:8b"),
                "ollama_base_url": coaching.get("ollama_base_url", "http://localhost:11434"),
                "tone": coaching.get("tone", "balanced"),
                "detail_level": coaching.get("detail_level", "standard"),
                "focus_areas": coaching.get("focus_areas", [
                    "openings", "tactics", "endgames", "time_management", "positional_play"
                ]),
                "custom_instructions": coaching.get("custom_instructions", ""),
                "coaching_history_count": coaching.get("coaching_history_count", 5),
            },
            "providers": get_available_providers(coaching),
        }

    def _handle_update_analysis_settings(self, body):
        """Update analysis settings in config.yaml and in-memory config."""
        config_path = Path("config.yaml")
        if not config_path.exists():
            self._send_json({"error": "config.yaml not found"}, 500)
            return

        try:
            with open(config_path, "r") as f:
                file_config = yaml.safe_load(f) or {}

            # Update stockfish settings
            sf = file_config.setdefault("stockfish", {})
            if "stockfish_path" in body:
                path_val = body["stockfish_path"]
                if path_val and not Path(path_val).is_file():
                    self._send_json(
                        {"error": f"Stockfish not found at: {path_val}", "field": "stockfish_path"},
                        400,
                    )
                    return
                sf["path"] = path_val
            if "depth" in body:
                sf["depth"] = max(1, min(30, int(body["depth"])))
            if "threads" in body:
                sf["threads"] = max(1, min(32, int(body["threads"])))
            if "hash_mb" in body:
                sf["hash_mb"] = max(64, min(4096, int(body["hash_mb"])))
            if "move_time_limit" in body:
                sf["move_time_limit"] = max(1.0, min(60.0, float(body["move_time_limit"])))

            # Update analysis settings
            analysis = file_config.setdefault("analysis", {})
            if "months_lookback" in body:
                analysis["months_lookback"] = max(1, min(24, int(body["months_lookback"])))

            with open(config_path, "w") as f:
                yaml.safe_dump(file_config, f, default_flow_style=False, sort_keys=False)

            # Update in-memory config
            self.config["stockfish"] = sf
            self.config["analysis"] = analysis

            self._send_json({"status": "saved"})

        except Exception as e:
            logger.exception("Failed to update analysis settings: %s", e)
            self._send_json({"error": str(e)}, 500)

    def _handle_update_api_keys(self, body):
        """Update API keys in .env and os.environ."""
        env_path = Path(".env")
        env_lines = []
        if env_path.exists():
            env_lines = env_path.read_text().splitlines()

        def set_env_line(lines, key, value):
            """Update or add a KEY=value line."""
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={value}"
                    return lines
            lines.append(f"{key}={value}")
            return lines

        updated = []

        # Map of body field → env var name → display label
        key_mappings = [
            ("anthropic_key", "ARRAKIS_ANTHROPIC_API_KEY", "anthropic"),
            ("openai_key", "ARRAKIS_OPENAI_API_KEY", "openai"),
            ("google_key", "ARRAKIS_GOOGLE_API_KEY", "google"),
            ("xai_key", "ARRAKIS_XAI_API_KEY", "xai"),
            ("mistral_key", "ARRAKIS_MISTRAL_API_KEY", "mistral"),
            ("deepseek_key", "ARRAKIS_DEEPSEEK_API_KEY", "deepseek"),
            ("qwen_key", "ARRAKIS_QWEN_API_KEY", "qwen"),
        ]

        for body_field, env_var, label in key_mappings:
            value = (body.get(body_field) or "").strip()
            if value:
                env_lines = set_env_line(env_lines, env_var, value)
                os.environ[env_var] = value
                updated.append(label)

        if not updated:
            self._send_json({"error": "No keys provided"}, 400)
            return

        try:
            env_path.write_text("\n".join(env_lines) + "\n")
            self._send_json({"status": "saved", "updated": updated})
        except Exception as e:
            logger.exception("Failed to write .env: %s", e)
            self._send_json({"error": str(e)}, 500)

    def _handle_update_coaching_settings(self, body):
        """Update coaching settings in config.yaml and in-memory config."""
        config_path = Path("config.yaml")
        if not config_path.exists():
            self._send_json({"error": "config.yaml not found"}, 500)
            return

        VALID_TONES = {"encouraging", "balanced", "technical"}
        VALID_DETAIL = {"concise", "standard", "detailed"}
        VALID_FOCUS = {"openings", "tactics", "endgames", "time_management", "positional_play"}
        from src.llm_providers import VALID_PROVIDERS

        try:
            with open(config_path, "r") as f:
                file_config = yaml.safe_load(f) or {}

            coaching = file_config.setdefault("coaching", {})

            if "default_provider" in body:
                val = str(body["default_provider"]).lower()
                if val not in VALID_PROVIDERS:
                    self._send_json({"error": f"Invalid provider: {val}"}, 400)
                    return
                coaching["default_provider"] = val

            if "anthropic_model" in body:
                coaching["anthropic_model"] = str(body["anthropic_model"]).strip()

            if "openai_model" in body:
                coaching["openai_model"] = str(body["openai_model"]).strip()

            # Additional provider model fields
            for key in ("gemini_model", "grok_model", "mistral_model",
                        "deepseek_model", "qwen_model", "ollama_model",
                        "ollama_base_url"):
                if key in body:
                    coaching[key] = str(body[key]).strip()

            if "tone" in body:
                val = str(body["tone"]).lower()
                if val not in VALID_TONES:
                    self._send_json({"error": f"Invalid tone: {val}"}, 400)
                    return
                coaching["tone"] = val

            if "detail_level" in body:
                val = str(body["detail_level"]).lower()
                if val not in VALID_DETAIL:
                    self._send_json({"error": f"Invalid detail level: {val}"}, 400)
                    return
                coaching["detail_level"] = val

            if "focus_areas" in body:
                areas = body["focus_areas"]
                if not isinstance(areas, list):
                    self._send_json({"error": "focus_areas must be a list"}, 400)
                    return
                invalid = set(areas) - VALID_FOCUS
                if invalid:
                    self._send_json({"error": f"Invalid focus areas: {invalid}"}, 400)
                    return
                coaching["focus_areas"] = areas

            if "custom_instructions" in body:
                text = str(body["custom_instructions"])[:2000]
                coaching["custom_instructions"] = text

            if "coaching_history_count" in body:
                try:
                    n = int(body["coaching_history_count"])
                except (TypeError, ValueError):
                    self._send_json(
                        {"error": "coaching_history_count must be an integer"}, 400
                    )
                    return
                if n < 1 or n > 20:
                    self._send_json(
                        {"error": "coaching_history_count must be between 1 and 20"},
                        400,
                    )
                    return
                coaching["coaching_history_count"] = n

            with open(config_path, "w") as f:
                yaml.safe_dump(file_config, f, default_flow_style=False, sort_keys=False)

            self.config["coaching"] = coaching
            self._send_json({"status": "saved"})

        except Exception as e:
            logger.exception("Failed to update coaching settings: %s", e)
            self._send_json({"error": str(e)}, 500)

    # ── Pipeline handlers ────────────────────────────────────────

    def _handle_pipeline_harvest(self, body):
        """Trigger game harvesting from Chess.com/Lichess."""
        from src import pipeline_state
        from src.harvester import harvest_player

        if not pipeline_state.start_task("harvest", db_path=self.db_path):
            current = pipeline_state.current_task()
            self._send_json(
                {"error": f"Another task is running: {current}"},
                409,
            )
            return

        config = self.config
        db_path = self.db_path
        player_filter = body.get("player")
        months = config.get("analysis", {}).get("months_lookback", 6)

        def run():
            try:
                # Read active players from DB
                conn = get_connection(db_path)
                if player_filter:
                    rows = conn.execute(
                        "SELECT * FROM players WHERE COALESCE(is_active, 1) = 1 AND username = ?",
                        (player_filter,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM players WHERE COALESCE(is_active, 1) = 1"
                    ).fetchall()
                conn.close()
                players = [dict(r) for r in rows]

                total_new = 0
                total_errors = 0
                for i, player in enumerate(players):
                    username = player["username"]
                    display_name = player.get("display_name") or username
                    pipeline_state.update_progress(
                        f"Fetching games for {display_name}...",
                        {"current_step": i + 1, "total_steps": len(players)},
                    )

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

        if not pipeline_state.start_task("analyze", db_path=self.db_path):
            current = pipeline_state.current_task()
            self._send_json(
                {"error": f"Another task is running: {current}"},
                409,
            )
            return

        config = self.config
        db_path = self.db_path
        sf_config = config.get("stockfish", {})
        sf_path = sf_config.get("path", shutil.which("stockfish") or "stockfish")

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

        if not pipeline_state.start_task("patterns", db_path=self.db_path):
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
                        "SELECT id, username, display_name FROM players WHERE COALESCE(is_active, 1) = 1 AND username = ?",
                        (player_filter,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, username, display_name FROM players WHERE COALESCE(is_active, 1) = 1"
                    ).fetchall()
                conn.close()

                players_updated = 0
                for i, row in enumerate(rows):
                    display = row["display_name"] or row["username"]
                    pipeline_state.update_progress(
                        f"Computing insights for {display}...",
                        {"current_step": i + 1, "total_steps": len(rows)},
                    )
                    # v1.19.0: explicit user-driven trigger — fire
                    # priority-weakness Journal alerts (de-duped).
                    compute_player_patterns(
                        row["id"], db_path=db_path, emit_weakness_alerts=True
                    )
                    players_updated += 1

                pipeline_state.complete_task({"players_updated": players_updated})

            except Exception as e:
                logger.exception("Pipeline patterns failed: %s", e)
                pipeline_state.fail_task(str(e))

        threading.Thread(target=run, daemon=True).start()
        self._send_json({"status": "started", "message": "Updating insights..."})

    def _handle_pipeline_run_all(self, body):
        """Chain harvest -> analyze -> patterns -> coach."""
        from src import pipeline_state
        from src.scheduler import run_full_pipeline

        if not pipeline_state.start_task("run_all", db_path=self.db_path):
            current = pipeline_state.current_task()
            self._send_json(
                {"error": f"Another task is running: {current}"},
                409,
            )
            return

        config = self.config
        db_path = self.db_path
        player_filter = body.get("player")
        provider = body.get("provider")

        cancel_event = threading.Event()
        DashboardHandler._coach_cancel_event = cancel_event

        def run():
            try:
                result = run_full_pipeline(
                    config, db_path,
                    player_filter=player_filter,
                    provider=provider,
                    cancel_event=cancel_event,
                )
                pipeline_state.complete_task(result)
            except Exception as e:
                logger.exception("Pipeline run-all failed: %s", e)
                pipeline_state.fail_task(str(e))
            finally:
                DashboardHandler._coach_cancel_event = None

        threading.Thread(target=run, daemon=True).start()
        self._send_json({"status": "started", "message": "Starting full pipeline..."})

    # Module-level cancel event for coaching pipeline
    _coach_cancel_event = None

    def _handle_pipeline_coach(self, body):
        """Trigger LLM coaching on analyzed but uncoached games."""
        from src import pipeline_state
        from src.coach import coach_pending

        if not pipeline_state.start_task("coach", db_path=self.db_path):
            current = pipeline_state.current_task()
            self._send_json(
                {"error": f"Another task is running: {current}"},
                409,
            )
            return

        config = self.config
        db_path = self.db_path
        coaching_config = config.get("coaching", {})

        from src.llm_providers import resolve_model

        provider = body.get("provider") or coaching_config.get("default_provider", "claude")
        player_filter = body.get("player")
        model = resolve_model(provider, None, coaching_config)

        cancel_event = threading.Event()
        DashboardHandler._coach_cancel_event = cancel_event

        def progress_cb(coached, errors, total, message):
            pipeline_state.update_progress(
                message,
                {
                    "games_processed": coached + errors,
                    "games_total": total,
                },
            )

        def run():
            try:
                result = coach_pending(
                    provider=provider,
                    model=model,
                    db_path=db_path,
                    config=config,
                    cancel_event=cancel_event,
                    progress_callback=progress_cb,
                    player=player_filter,
                )
                pipeline_state.complete_task({
                    "coached": result.get("coached", 0),
                    "errors": result.get("errors", 0),
                    "skipped": result.get("skipped", 0),
                })
            except Exception as e:
                logger.exception("Pipeline coach failed: %s", e)
                pipeline_state.fail_task(str(e))
            finally:
                DashboardHandler._coach_cancel_event = None

        threading.Thread(target=run, daemon=True).start()
        self._send_json({"status": "started", "message": "Generating coaching briefs..."})

    def _handle_pipeline_cancel(self):
        """Cancel the currently running coaching pipeline (standalone or within run_all)."""
        from src import pipeline_state

        current = pipeline_state.current_task()
        if current not in ("coach", "run_all"):
            self._send_json(
                {"error": "No cancellable task is running." if not current else f"Task '{current}' cannot be cancelled."},
                400,
            )
            return

        cancel_event = DashboardHandler._coach_cancel_event
        if cancel_event:
            cancel_event.set()
            self._send_json({"status": "cancelling", "message": "Cancellation requested..."})
        else:
            self._send_json({"error": "No cancel event available."}, 400)

    # ── API routing ──────────────────────────────────────────────

    def _handle_api(self, path, params):
        """Route API requests to handler functions via the GET registry."""
        try:
            handler = _GET_ROUTES.get(path)
            if handler is not None:
                data = handler(self, params)
            else:
                for pattern, h in _GET_REGEX_ROUTES:
                    m = pattern.match(path)
                    if m:
                        data = h(self, params, *m.groups())
                        break
                else:
                    self._send_json({"error": "Not found"}, 404)
                    return

            self._send_json(data)

        except Exception as e:
            import sqlite3 as _sqlite3
            if isinstance(e, (ConnectionResetError, BrokenPipeError)):
                # Client closed the connection before we finished. Common
                # in dev (Next.js hot reload, page navigation, AbortController
                # cancelling in-flight fetches). Not a server bug — log
                # quietly and skip the recovery response (it would only
                # raise BrokenPipeError again).
                logger.debug("Client disconnected during %s: %s", path, e)
                return
            if isinstance(e, _sqlite3.OperationalError) and "locked" in str(e):
                logger.warning("API request hit DB lock: %s %s", path, e)
                self._send_json(
                    {"error": "Database is busy (analysis in progress). Please try again in a moment."},
                    503,
                )
            else:
                logger.exception("API error: %s", e)
                self._send_json({"error": str(e)}, 500)

    def _send_json(self, data, status=200):
        """Send a JSON response.

        Silently swallows client-disconnect errors (ConnectionResetError,
        BrokenPipeError). These mean the browser closed the connection
        before we finished writing — normal during hot reload or page
        navigation, not a server-side problem.
        """
        body = json.dumps(data, default=str).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionResetError, BrokenPipeError) as e:
            logger.debug("Client disconnected while writing response: %s", e)

    def _get_conn(self):
        """Open a read-only DB connection for this request."""
        return get_connection(self.db_path)

    # ── API Handlers ──────────────────────────────────────────────

    def _api_players(self):
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM players WHERE COALESCE(is_active, 1) = 1"
            ).fetchall()
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
                # v1.16.4: slug-only lookup. chess.com username is
                # harvester-only since v1.16.4.
                conditions.append("p.slug = ?")
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
            # v1.6.0: surface coaching meta (history depth, prompt size,
            # model) so the UI can show a "based on N recent games" stamp
            if coaching_data and coaching_data.get("coaching_meta_json"):
                try:
                    coaching_data["meta"] = json.loads(
                        coaching_data["coaching_meta_json"]
                    )
                except (json.JSONDecodeError, TypeError):
                    coaching_data["meta"] = None

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

            # v1.16.1: resolve slug-or-username to id first, then fetch
            # the latest patterns row. Two-step lookup avoids a JOIN
            # against the deprecated WHERE-by-username pattern.
            player_id = _resolve_player_id(conn, player)
            if player_id is None:
                return {"stats": None, "username": player}
            row = conn.execute(
                """SELECT pp.*, p.username, p.slug, p.display_name
                FROM player_patterns pp JOIN players p ON pp.player_id = p.id
                WHERE pp.player_id = ?
                ORDER BY pp.updated_at DESC LIMIT 1""",
                (player_id,),
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

    def _api_journal(self, params):
        """v1.10.0: list journal entries for a player, newest first.

        Query params:
          player    — required username
          platform  — optional scope (chess.com / lichess / tournament / ...).
                      When omitted, returns ALL platforms.
          kind      — optional filter (review / note).
                      When omitted, returns ALL kinds.
          limit     — optional cap on the number of returned entries (default 50).
        """
        player = params.get("player", [None])[0]
        if not player:
            return {"error": "player parameter required"}
        platform = params.get("platform", [None])[0]
        kind = params.get("kind", [None])[0]
        try:
            limit = max(1, min(500, int(params.get("limit", ["50"])[0])))
        except (ValueError, TypeError):
            limit = 50

        conn = self._get_conn()
        try:
            # v1.16.1: accept slug OR chess.com username
            player_id = _resolve_player_id(conn, player)
            if player_id is None:
                return {"error": f"Player {player} not found"}

            sql = (
                "SELECT id, player_id, kind, platform, body, refs_json, provider, "
                "metadata_json, created_at "
                "FROM journal_entries WHERE player_id = ?"
            )
            args: list = [player_id]
            if platform:
                sql += " AND platform = ?"
                args.append(platform)
            if kind:
                sql += " AND kind = ?"
                args.append(kind)
            sql += " ORDER BY created_at DESC LIMIT ?"
            args.append(limit)

            rows = conn.execute(sql, args).fetchall()

            entries = []
            for r in rows:
                d = dict_from_row(r)
                # Decode JSON columns for the client
                if d.get("refs_json"):
                    try:
                        d["refs"] = json.loads(d["refs_json"])
                    except (json.JSONDecodeError, TypeError):
                        d["refs"] = []
                else:
                    d["refs"] = []
                if d.get("metadata_json"):
                    try:
                        d["metadata"] = json.loads(d["metadata_json"])
                    except (json.JSONDecodeError, TypeError):
                        d["metadata"] = {}
                else:
                    d["metadata"] = {}
                # Strip raw JSON keys — clients use the decoded forms
                d.pop("refs_json", None)
                d.pop("metadata_json", None)
                entries.append(d)

            # Also report what platforms exist for this player so the UI
            # can render the chip row in v1.10.1 without a second round-trip.
            platform_counts = {}
            for r in conn.execute(
                "SELECT platform, COUNT(*) AS n FROM journal_entries "
                "WHERE player_id = ? GROUP BY platform",
                (player_id,),
            ).fetchall():
                platform_counts[r["platform"]] = r["n"]

            return {
                "username": player,
                "entries": entries,
                "platform_counts": platform_counts,
            }
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
        return pipeline_state.get_state(db_path=self.db_path)

    def _api_schedule_status(self):
        if hasattr(self, '_scheduler_manager') and self._scheduler_manager:
            return self._scheduler_manager.get_state()
        # Fallback: read from module-level manager stored during run_dashboard
        from src.scheduler import get_schedule_state
        return get_schedule_state()

    def _handle_schedule_toggle(self, body):
        enabled = body.get("enabled")
        if enabled is None:
            self._send_json({"error": "enabled field required"}, 400)
            return
        manager = _scheduler_manager
        if not manager:
            self._send_json({"error": "Scheduler not initialized"}, 500)
            return
        if enabled:
            manager.enable()
        else:
            manager.disable()
        self._send_json(manager.get_state())

    def _handle_schedule_interval(self, body):
        hours = body.get("hours")
        if not hours or not isinstance(hours, (int, float)) or hours < 1:
            self._send_json({"error": "hours must be >= 1"}, 400)
            return
        manager = _scheduler_manager
        if not manager:
            self._send_json({"error": "Scheduler not initialized"}, 500)
            return
        manager.update_interval(int(hours))
        self._send_json(manager.get_state())

    # ── v1.4.1 Hunter Mode handlers ─────────────────────────────────────

    def _hunter_enabled(self) -> bool:
        """Hunter Mode is on by default; disable via config:
            features:
              hunter_mode: false
        """
        features = (self.config or {}).get("features") or {}
        return features.get("hunter_mode", True)

    def _hunter_config(self) -> dict:
        """Pull Hunter Mode tuning knobs from config.yaml `features`."""
        features = (self.config or {}).get("features") or {}
        return {
            "lookback_months": features.get("hunter_lookback_months", 6),
            "max_games": features.get("hunter_max_games_per_opponent"),
            # v1.20.0: how many recent games a Deep Scan analyzes.
            "scan_games": features.get("hunter_scan_games", 20),
            # v1.21.0: Tournament Prep knobs.
            "tournament_max_opponents": features.get("tournament_max_opponents", 32),
            "tournament_min_shared": features.get("tournament_min_shared", 2),
        }

    def _api_hunt_profile(self, params):
        """GET /api/hunt/profile?opponent=<username>&platform=<chess.com|lichess>

        Returns the opponent's profile, served from cache if fresh
        (within 24h) or fetched live otherwise.
        """
        if not self._hunter_enabled():
            return {"error": "Hunter Mode is disabled in config.yaml"}
        opponent = (params.get("opponent") or [""])[0].strip()
        platform = (params.get("platform") or ["chess.com"])[0].strip()
        if not opponent:
            return {"error": "opponent query param is required"}

        from src.hunter import (
            get_or_fetch_profile,
            compute_opponent_motif_summary,
            get_deep_scan_status,
        )
        cfg = self._hunter_config()
        try:
            profile = get_or_fetch_profile(
                opponent, platform, self.db_path,
                lookback_months=cfg["lookback_months"],
                max_games=cfg["max_games"],
            )
        except ValueError as e:
            return {"error": str(e)}
        # v1.20.0: attach Deep Scan results (Tactical Blind Spots) when the
        # opponent has been scanned; otherwise null + a status block so the
        # UI can render the "Run Deep Scan" affordance.
        if isinstance(profile, dict):
            profile["motif_summary"] = compute_opponent_motif_summary(
                opponent, platform, self.db_path,
            )
            profile["deep_scan"] = get_deep_scan_status(
                opponent, platform, self.db_path,
            )
        return profile

    def _handle_hunt_refresh(self, body):
        """POST /api/hunt/refresh — body: {opponent, platform}
        Forces a re-fetch (bypasses the 24h cache TTL)."""
        if not self._hunter_enabled():
            self._send_json(
                {"error": "Hunter Mode is disabled in config.yaml"}, 403,
            )
            return
        opponent = (body or {}).get("opponent", "").strip()
        platform = (body or {}).get("platform", "chess.com").strip()
        if not opponent:
            self._send_json({"error": "opponent is required"}, 400)
            return

        from src.hunter import get_or_fetch_profile
        cfg = self._hunter_config()
        try:
            profile = get_or_fetch_profile(
                opponent, platform, self.db_path, force_refresh=True,
                lookback_months=cfg["lookback_months"],
                max_games=cfg["max_games"],
            )
        except ValueError as e:
            self._send_json({"error": str(e)}, 400)
            return
        self._send_json(profile)

    def _handle_hunt_scan(self, body):
        """POST /api/pipeline/hunt-scan — body: {opponent, platform}

        v1.20.0 Deep Scan: run Stockfish + the 12 motif detectors over the
        opponent's last N accumulated games (background job), so the
        Tactical Blind Spots card can surface the themes they miss. Opt-in
        only — never runs automatically. Reuses the single-task
        pipeline_state lock so it can't collide with harvest/analyze.
        """
        if not self._hunter_enabled():
            self._send_json(
                {"error": "Hunter Mode is disabled in config.yaml"}, 403,
            )
            return
        opponent = (body or {}).get("opponent", "").strip()
        platform = (body or {}).get("platform", "chess.com").strip()
        if not opponent:
            self._send_json({"error": "opponent is required"}, 400)
            return

        from src import pipeline_state
        from src.hunter import deep_scan_opponent

        if not pipeline_state.start_task("hunt_scan", db_path=self.db_path):
            current = pipeline_state.current_task()
            self._send_json({"error": f"Another task is running: {current}"}, 409)
            return

        db_path = self.db_path
        config = self.config
        scan_games = self._hunter_config().get("scan_games", 20)

        def run():
            try:
                def progress(done, total):
                    pipeline_state.update_progress(
                        f"Deep-scanning {opponent}: game {done} of {total}...",
                        {"games_processed": done, "games_total": total},
                    )
                result = deep_scan_opponent(
                    opponent, platform, config=config, db_path=db_path,
                    limit=scan_games, progress_cb=progress,
                )
                pipeline_state.complete_task(result)
            except FileNotFoundError as e:
                pipeline_state.fail_task(str(e))
            except Exception as e:
                logger.exception("Hunt deep scan failed: %s", e)
                pipeline_state.fail_task(str(e))

        threading.Thread(target=run, daemon=True).start()
        self._send_json({
            "status": "started",
            "message": f"Deep-scanning {opponent}'s last {scan_games} games...",
        })

    # ── v1.21.0 Tournament Prep ──────────────────────────────────────

    def _resolve_tournament_player(self, identifier):
        """slug/username/id → player_id, or None."""
        if not identifier:
            return None
        conn = get_connection(self.db_path)
        try:
            return _resolve_player_id(conn, identifier)
        finally:
            conn.close()

    def _api_tournaments(self, params):
        """GET /api/tournaments?player=<slug> — list a player's rosters."""
        if not self._hunter_enabled():
            return {"error": "Hunter Mode is disabled in config.yaml"}
        player = (params.get("player") or [""])[0].strip()
        pid = self._resolve_tournament_player(player)
        if pid is None:
            return {"error": f"Player '{player}' not found"}
        from src.tournament import list_tournaments
        return {"tournaments": list_tournaments(pid, db_path=self.db_path)}

    def _api_tournament(self, params):
        """GET /api/tournament?id=<n> — full combined prep view (cache-only)."""
        if not self._hunter_enabled():
            return {"error": "Hunter Mode is disabled in config.yaml"}
        raw = (params.get("id") or [""])[0].strip()
        if not raw.isdigit():
            return {"error": "id query param is required"}
        from src.tournament import compute_tournament_prep
        min_shared = self._hunter_config().get("tournament_min_shared", 2)
        try:
            return compute_tournament_prep(
                int(raw), db_path=self.db_path, min_shared=min_shared,
            )
        except ValueError as e:
            return {"error": str(e)}

    def _handle_tournament_create(self, body):
        if not self._hunter_enabled():
            self._send_json({"error": "Hunter Mode is disabled"}, 403)
            return
        body = body or {}
        pid = self._resolve_tournament_player((body.get("player") or "").strip())
        if pid is None:
            self._send_json({"error": "player not found"}, 400)
            return
        from src.tournament import create_tournament
        try:
            t = create_tournament(
                pid, body.get("name"),
                event_date=body.get("event_date"), notes=body.get("notes"),
                db_path=self.db_path,
            )
        except ValueError as e:
            self._send_json({"error": str(e)}, 400)
            return
        self._send_json(t)

    def _handle_tournament_add_opponent(self, body):
        if not self._hunter_enabled():
            self._send_json({"error": "Hunter Mode is disabled"}, 403)
            return
        body = body or {}
        tid = body.get("tournament_id")
        from src.tournament import add_opponent, get_tournament
        # Enforce the per-roster opponent cap.
        cap = self._hunter_config().get("tournament_max_opponents", 32)
        try:
            current = get_tournament(int(tid), db_path=self.db_path)
            if len(current["opponents"]) >= cap:
                self._send_json(
                    {"error": f"Tournament is full (max {cap} opponents)"}, 400)
                return
            row = add_opponent(
                int(tid), body.get("opponent", ""),
                platform=body.get("platform", "chess.com"),
                db_path=self.db_path,
            )
        except (ValueError, TypeError) as e:
            self._send_json({"error": str(e)}, 400)
            return
        self._send_json(row)

    def _handle_tournament_remove_opponent(self, body):
        if not self._hunter_enabled():
            self._send_json({"error": "Hunter Mode is disabled"}, 403)
            return
        body = body or {}
        from src.tournament import remove_opponent
        try:
            remove_opponent(
                int(body.get("tournament_id")),
                int(body.get("opponent_id")),
                db_path=self.db_path,
            )
        except (ValueError, TypeError) as e:
            self._send_json({"error": str(e)}, 400)
            return
        self._send_json({"status": "removed"})

    def _handle_tournament_delete(self, body):
        if not self._hunter_enabled():
            self._send_json({"error": "Hunter Mode is disabled"}, 403)
            return
        from src.tournament import delete_tournament
        try:
            delete_tournament(
                int((body or {}).get("tournament_id")), db_path=self.db_path)
        except (ValueError, TypeError) as e:
            self._send_json({"error": str(e)}, 400)
            return
        self._send_json({"status": "deleted"})

    def _handle_tournament_prep(self, body):
        """POST /api/pipeline/tournament-prep {tournament_id} — warm every
        opponent's opening-profile cache in the background (fast, no
        Stockfish), so the combined view fills in. Reuses the single-task
        pipeline_state lock."""
        if not self._hunter_enabled():
            self._send_json({"error": "Hunter Mode is disabled"}, 403)
            return
        tid = (body or {}).get("tournament_id")
        from src import pipeline_state
        from src.tournament import get_tournament
        from src.hunter import get_or_fetch_profile

        try:
            roster = get_tournament(int(tid), db_path=self.db_path)
        except (ValueError, TypeError) as e:
            self._send_json({"error": str(e)}, 400)
            return

        if not pipeline_state.start_task("tournament_prep", db_path=self.db_path):
            current = pipeline_state.current_task()
            self._send_json({"error": f"Another task is running: {current}"}, 409)
            return

        db_path = self.db_path
        cfg = self._hunter_config()
        opponents = roster["opponents"]
        name = roster["name"]

        def run():
            try:
                warmed = 0
                total = len(opponents)
                for i, opp in enumerate(opponents):
                    pipeline_state.update_progress(
                        f"Prepping {name}: {opp['username']} "
                        f"({i + 1} of {total})...",
                        {"games_processed": i + 1, "games_total": total},
                    )
                    try:
                        get_or_fetch_profile(
                            opp["username"], opp["platform"], db_path,
                            lookback_months=cfg["lookback_months"],
                            max_games=cfg["max_games"],
                        )
                        warmed += 1
                    except Exception as e:  # one bad opponent shouldn't kill the run
                        logger.warning("Tournament prep: %s failed: %s",
                                       opp["username"], e)
                pipeline_state.complete_task(
                    {"warmed": warmed, "total": total})
            except Exception as e:
                logger.exception("Tournament prep failed: %s", e)
                pipeline_state.fail_task(str(e))

        threading.Thread(target=run, daemon=True).start()
        self._send_json({
            "status": "started",
            "message": f"Prepping {len(opponents)} opponents for {name}...",
        })

    def log_message(self, format, *args):
        """Suppress default access logs for cleaner output."""
        if "/api/" in str(args[0]) if args else False:
            logger.debug(format, *args)


# ── Built-in route registrations (v1.22.0) ───────────────────────────
# Registered here, after the class, so DashboardHandler methods exist.
# Mirrors the previous if/elif chains exactly — one entry per endpoint.

# GET — handlers receive (self, params) and return the data to serialize.
register_route("GET", "/api/players", lambda self, params: self._api_players())
register_route("GET", "/api/games", lambda self, params: self._api_games_list(params))
register_regex_route(
    "GET", r"^/api/games/(\d+)$",
    lambda self, params, gid: self._api_game_detail(int(gid)),
)
register_route("GET", "/api/patterns", lambda self, params: self._api_patterns(params))
register_route("GET", "/api/report", lambda self, params: self._api_report(params))
register_route("GET", "/api/status", lambda self, params: self._api_status())
register_route("GET", "/api/pipeline/status", lambda self, params: self._api_pipeline_status())
register_route("GET", "/api/settings", lambda self, params: self._handle_settings_get())
register_route("GET", "/api/schedule/status", lambda self, params: self._api_schedule_status())
register_route("GET", "/api/hunt/profile", lambda self, params: self._api_hunt_profile(params))
register_route("GET", "/api/tournaments", lambda self, params: self._api_tournaments(params))
register_route("GET", "/api/tournament", lambda self, params: self._api_tournament(params))
register_route("GET", "/api/journal", lambda self, params: self._api_journal(params))

# POST — handlers receive (self, body) and send their own response.
register_route("POST", "/api/players", lambda self, body: self._handle_create_player(body))
register_route("POST", "/api/coach", lambda self, body: self._handle_coach(body))
register_route("POST", "/api/trend-summary", lambda self, body: self._handle_trend_summary(body))
# v1.9.0 legacy alias + v1.10.0 canonical endpoint — same handler.
register_route("POST", "/api/recent-form-review", lambda self, body: self._handle_recent_form_review(body))
register_route("POST", "/api/journal/review", lambda self, body: self._handle_recent_form_review(body))
register_route("POST", "/api/pipeline/harvest", lambda self, body: self._handle_pipeline_harvest(body))
register_route("POST", "/api/pipeline/analyze", lambda self, body: self._handle_pipeline_analyze(body))
register_route("POST", "/api/pipeline/patterns", lambda self, body: self._handle_pipeline_patterns(body))
register_route("POST", "/api/pipeline/run-all", lambda self, body: self._handle_pipeline_run_all(body))
register_route("POST", "/api/pipeline/coach", lambda self, body: self._handle_pipeline_coach(body))
register_route("POST", "/api/pipeline/cancel", lambda self, body: self._handle_pipeline_cancel())
register_route("POST", "/api/schedule/toggle", lambda self, body: self._handle_schedule_toggle(body))
register_route("POST", "/api/schedule/interval", lambda self, body: self._handle_schedule_interval(body))
register_route("POST", "/api/hunt/refresh", lambda self, body: self._handle_hunt_refresh(body))
register_route("POST", "/api/pipeline/hunt-scan", lambda self, body: self._handle_hunt_scan(body))
register_route("POST", "/api/tournament/create", lambda self, body: self._handle_tournament_create(body))
register_route("POST", "/api/tournament/add-opponent", lambda self, body: self._handle_tournament_add_opponent(body))
register_route("POST", "/api/tournament/remove-opponent", lambda self, body: self._handle_tournament_remove_opponent(body))
register_route("POST", "/api/tournament/delete", lambda self, body: self._handle_tournament_delete(body))
register_route("POST", "/api/pipeline/tournament-prep", lambda self, body: self._handle_tournament_prep(body))
register_route("POST", "/api/journal/note", lambda self, body: self._handle_create_note(body))

# PUT
register_regex_route(
    "PUT", r"^/api/players/(\d+)$",
    lambda self, body, pid: self._handle_update_player(int(pid), body),
)
register_route("PUT", "/api/settings/analysis", lambda self, body: self._handle_update_analysis_settings(body))
register_route("PUT", "/api/settings/api-keys", lambda self, body: self._handle_update_api_keys(body))
register_route("PUT", "/api/settings/coaching", lambda self, body: self._handle_update_coaching_settings(body))
register_regex_route(
    "PUT", r"^/api/journal/note/(\d+)$",
    lambda self, body, nid: self._handle_update_note(int(nid), body),
)

# DELETE
register_regex_route(
    "DELETE", r"^/api/players/(\d+)$",
    lambda self, body, pid: self._handle_delete_player(int(pid)),
)
register_regex_route(
    "DELETE", r"^/api/journal/note/(\d+)$",
    lambda self, body, nid: self._handle_delete_note(int(nid)),
)


def run_dashboard(db_path: str, port: int = 8000, config: dict | None = None,
                  api_only_banner: bool = True):
    """Start the live dashboard server.

    `api_only_banner` controls the startup banner:
      - True (default, used by `dashboard` command) — print the verbose
        two-terminal message + the v1.5.0 hint about `serve`.
      - False (used by `serve` command) — suppress this banner; the caller
        will print the unified version once the frontend is also ready.
    """
    global _scheduler_manager
    config = config or {}

    # Ensure DB migrations are applied (e.g. is_active column)
    from src.models import init_db
    init_db(db_path)

    # Start the scheduler
    from src.scheduler import SchedulerManager
    _scheduler_manager = SchedulerManager(config, db_path)
    _scheduler_manager.start()

    handler = partial(DashboardHandler, db_path=db_path, config=config)
    with http.server.HTTPServer(("", port), handler) as httpd:
        if api_only_banner:
            sched_config = config.get("schedule", {})
            sched_status = "enabled" if sched_config.get("enabled") else "disabled"
            interval = sched_config.get("interval_hours", 6)

            print(f"\U0001f3f0 Arrakis Engine API running at http://localhost:{port}")
            print(f"\U0001f4ca Live data from: {db_path}")
            print(f"\U0001f552 Auto-updates: {sched_status} (every {interval}h)")
            print("")
            print("\U0001f4cd Open the dashboard UI in a SECOND terminal:")
            print("     cd frontend && pnpm dev")
            print(f"     → then open http://localhost:3000 in your browser")
            print("")
            print("   (This terminal serves the API only. The Next.js frontend on")
            print(f"    port 3000 calls back here on port {port} for data.)")
            print("")
            print("\U0001f4a1 New in v1.5.0: `python main.py serve` starts both backend +")
            print("   frontend with one command (and a single unified banner).")
            print("")
            print("Press Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            _scheduler_manager.stop()
            if api_only_banner:
                print("\nDashboard stopped.")
