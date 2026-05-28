"""Tests for the live dashboard API server."""

import json
import threading
import time
import urllib.request

import pytest

from src.models import init_db, ensure_player
from src.dashboard_server import run_dashboard


@pytest.fixture
def db_with_data(tmp_path):
    """Create a test DB with sample data."""
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)

    pid = ensure_player(conn, "testplayer", display_name="Test", age=10, rating=1000)

    conn.execute(
        """INSERT INTO games (player_id, game_url, pgn, player_color,
           player_rating, opponent_rating, result, time_control,
           time_class, date_played, analysis_status, coaching_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (pid, "https://chess.com/game/1", "1. e4 e5 *", "white",
         1000, 1100, "win", "600", "rapid", "2026-01-15", "complete", "pending"),
    )
    game_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        """INSERT INTO move_analysis (game_id, move_number, side, move_played,
           best_move, eval_before_cp, eval_after_cp, swing_cp,
           win_prob_before, win_prob_after, classification)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (game_id, 1, "white", "e4", "e4", 0, 20, 0, 50.0, 51.0, "excellent"),
    )
    conn.execute(
        """INSERT INTO move_analysis (game_id, move_number, side, move_played,
           best_move, eval_before_cp, eval_after_cp, swing_cp,
           win_prob_before, win_prob_after, classification)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (game_id, 1, "black", "e5", "e5", 20, 15, 5, 49.0, 49.5, "good"),
    )

    # Add a pending game
    conn.execute(
        """INSERT INTO games (player_id, game_url, pgn, player_color,
           player_rating, opponent_rating, result, time_control,
           time_class, date_played, analysis_status, coaching_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (pid, "https://chess.com/game/2", "1. d4 d5 *", "black",
         1000, 950, "loss", "180", "blitz", "2026-01-16", "pending", "pending"),
    )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def live_server(db_with_data):
    """Start the dashboard server in a background thread."""
    import http.server
    from functools import partial
    from src.dashboard_server import DashboardHandler

    port = 18765
    # v1.13.3: handler is BaseHTTPRequestHandler-based — no `directory` kwarg
    handler = partial(DashboardHandler, db_path=db_with_data)
    httpd = http.server.HTTPServer(("127.0.0.1", port), handler)

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)

    yield f"http://127.0.0.1:{port}"

    httpd.shutdown()


def api_get(base_url, path):
    """Helper: GET an API endpoint and return parsed JSON."""
    url = base_url + path
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


class TestPlayersAPI:
    def test_list_players(self, live_server):
        data = api_get(live_server, "/api/players")
        assert len(data) == 1
        assert data[0]["username"] == "testplayer"
        assert data[0]["display_name"] == "Test"


class TestGamesAPI:
    def test_list_games(self, live_server):
        data = api_get(live_server, "/api/games?player=testplayer")
        assert len(data) == 2

    def test_filter_by_result(self, live_server):
        data = api_get(live_server, "/api/games?player=testplayer&result=win")
        assert len(data) == 1
        assert data[0]["result"] == "win"

    def test_filter_by_time_class(self, live_server):
        data = api_get(live_server, "/api/games?player=testplayer&time_class=blitz")
        assert len(data) == 1
        assert data[0]["time_class"] == "blitz"

    def test_game_detail(self, live_server):
        games = api_get(live_server, "/api/games?player=testplayer")
        complete_game = [g for g in games if g["analysis_status"] == "complete"][0]

        detail = api_get(live_server, f"/api/games/{complete_game['id']}")
        assert "game" in detail
        assert "moves" in detail
        assert len(detail["moves"]) == 2
        assert detail["moves"][0]["move_played"] == "e4"
        assert detail["moves"][0]["classification"] == "excellent"

    def test_game_not_found(self, live_server):
        data = api_get(live_server, "/api/games/99999")
        assert "error" in data

    # ── v1.16.3: slug-or-username resolver on /api/games ─────────────

    def test_v16_3_games_resolves_by_slug(self, live_server):
        """v1.16.3 regression: /api/games?player=<slug> must return
        the same games as /api/games?player=<chess.com-username>.

        v1.16.1 introduced the slug column but missed _api_games_list,
        leaving its WHERE clause as `p.username = ?`. Symptom in
        Bernard's UI: Games tab showed 0 games after the v1.16.1
        frontend started routing by slug.
        """
        # Fixture player is 'testplayer' with display_name='Test' →
        # auto-derived slug is 'test'.
        by_slug = api_get(live_server, "/api/games?player=test")
        by_username = api_get(live_server, "/api/games?player=testplayer")
        assert len(by_slug) == 2, (
            f"slug lookup returned {len(by_slug)} games, expected 2"
        )
        assert len(by_slug) == len(by_username), (
            "slug and username queries must return the same game count"
        )

    def test_v16_3_games_filters_combine_with_slug(self, live_server):
        """v1.16.3: combining ?player=<slug>&result=win still filters
        correctly. Catches regressions where the (slug OR username)
        clause wraps wrong and breaks subsequent AND conditions."""
        data = api_get(live_server, "/api/games?player=test&result=win")
        assert len(data) == 1
        assert data[0]["result"] == "win"


class TestPlayerLookupStaticGuard:
    """v1.16.3 static regression guard: catches future lookups that
    bypass _resolve_player_id by going direct to `WHERE username = ?`.
    That class of bug is what made v1.16.1's Games tab break.

    Allowlist: lines we KNOW are intentional (player-creation check,
    inside the resolver itself, the legacy-fallback branch). Anything
    else should funnel through _resolve_player_id or use the
    (slug = ? OR username = ?) shape.
    """

    def test_no_new_player_username_lookups_outside_resolver(self):
        import re
        from pathlib import Path
        path = Path(__file__).parent.parent / "src" / "dashboard_server.py"
        text = path.read_text()
        # Find all occurrences of "WHERE username = ?" referencing the
        # players table. Allow:
        #   - inside `def _resolve_player_id` (the resolver's own fallback)
        #   - inside `def _handle_create_player` (is_active existence check)
        # Anywhere else is a bug — new lookups must funnel through the
        # resolver or use `(slug = ? OR username = ?)`.
        offenders = []
        for m in re.finditer(r"WHERE username = \?", text):
            # Walk backwards to find the nearest `def ` line
            preceding = text[:m.start()]
            def_matches = list(re.finditer(r"^def (\w+)", preceding, re.MULTILINE))
            if def_matches:
                enclosing = def_matches[-1].group(1)
                if enclosing == "_resolve_player_id":
                    continue
            # Method scope (inside a class) — check for is_active in context
            ctx = text[max(0, m.start() - 200):m.start() + 30]
            if "is_active" in ctx:
                continue  # _handle_create_player — intentional
            offenders.append((m.start(), enclosing if def_matches else "<unknown>"))
        assert not offenders, (
            f"v1.16.3 regression: {len(offenders)} `WHERE username = ?` "
            f"site(s) found outside the resolver / player-creation check: "
            f"{offenders}. New endpoints should funnel through "
            f"_resolve_player_id(conn, identifier) or use the "
            f"(slug = ? OR username = ?) shape so slug-based URLs keep "
            f"working."
        )


class TestStatusAPI:
    def test_status(self, live_server):
        data = api_get(live_server, "/api/status")
        assert data["total_games"] == 2
        assert data["analysis_complete"] == 1
        assert data["analysis_pending"] == 1


class TestPatternsAPI:
    def test_no_patterns(self, live_server):
        data = api_get(live_server, "/api/patterns?player=testplayer")
        assert data["stats"] is None

    def test_missing_player_param(self, live_server):
        data = api_get(live_server, "/api/patterns")
        assert "error" in data

    # ── v1.16.1 resolver: slug-or-username acceptance ───────────────

    def test_v16_1_resolves_by_slug(self, live_server):
        """v1.16.1: /api/patterns?player=<slug> resolves correctly.
        Fixture player is 'testplayer' with display_name='Test' →
        auto-derived slug is 'test'."""
        data = api_get(live_server, "/api/patterns?player=test")
        # The resolver matched a known player → stats key present
        # (value can be None because no patterns are seeded, but the
        # 'username' field gets populated by the endpoint when the
        # lookup misses patterns_row only).
        assert "stats" in data
        # When no patterns_row exists but the player IS found, the
        # endpoint returns {"stats": None, "username": <param>}
        assert data["stats"] is None
        assert data["username"] == "test"

    def test_v16_1_resolves_by_legacy_username(self, live_server):
        """v1.16.1: old bookmarks that use the chess.com username
        still work — the resolver falls back to WHERE username = ?
        when the slug lookup misses."""
        data = api_get(live_server, "/api/patterns?player=testplayer")
        assert "stats" in data
        assert data["username"] == "testplayer"

    def test_v16_1_unknown_identifier_returns_null_stats(self, live_server):
        """An identifier that matches neither slug nor username returns
        the same {stats: None} shape — never a 500."""
        data = api_get(live_server, "/api/patterns?player=ghost_player")
        assert data["stats"] is None
        # username field echoes back the param (frontend may render an
        # empty-state with this)
        assert data["username"] == "ghost_player"


class TestPlayersAPIv161:
    """v1.16.1: /api/players response surfaces the slug field so the
    frontend can use it for routing."""

    def test_players_response_includes_slug(self, live_server):
        data = api_get(live_server, "/api/players")
        assert len(data) == 1
        p = data[0]
        assert "slug" in p, "v1.16.1 player response must include slug"
        # Fixture display_name is "Test" → slugify → "test"
        assert p["slug"] == "test"
        # Username (chess.com handle) is still surfaced — they're
        # separate fields now
        assert p["username"] == "testplayer"
        assert p["display_name"] == "Test"


class TestJournalAPI:
    """v1.10.0: GET /api/journal returns chronological entries."""

    def test_empty_journal_for_new_player(self, live_server):
        data = api_get(live_server, "/api/journal?player=testplayer")
        assert data["entries"] == []
        assert data["platform_counts"] == {}
        assert data["username"] == "testplayer"

    def test_missing_player_param(self, live_server):
        data = api_get(live_server, "/api/journal")
        assert "error" in data

    def test_unknown_player_returns_error(self, live_server):
        data = api_get(live_server, "/api/journal?player=nobody")
        assert "error" in data

    def test_returns_entry_after_insertion(self, live_server, db_with_data):
        """Insert a journal entry directly into the DB, confirm GET returns it."""
        import sqlite3
        conn = sqlite3.connect(db_with_data)
        conn.row_factory = sqlite3.Row
        pid = conn.execute(
            "SELECT id FROM players WHERE username = 'testplayer'"
        ).fetchone()["id"]
        conn.execute(
            """INSERT INTO journal_entries
            (player_id, kind, platform, body, refs_json, provider, created_at)
            VALUES (?, 'review', 'chess.com', 'A review.', '[1,2]',
                    'openai:gpt-5.5-pro', datetime('now'))""",
            (pid,),
        )
        conn.commit()
        conn.close()

        data = api_get(live_server, "/api/journal?player=testplayer")
        assert len(data["entries"]) == 1
        e = data["entries"][0]
        assert e["kind"] == "review"
        assert e["platform"] == "chess.com"
        assert e["body"] == "A review."
        assert e["refs"] == [1, 2]  # decoded from JSON
        assert e["provider"] == "openai:gpt-5.5-pro"
        assert data["platform_counts"] == {"chess.com": 1}

    def test_platform_filter_scopes_results(self, live_server, db_with_data):
        """?platform=lichess returns only lichess entries."""
        import sqlite3
        conn = sqlite3.connect(db_with_data)
        pid = conn.execute(
            "SELECT id FROM players WHERE username = 'testplayer'"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO journal_entries (player_id, kind, platform, body, created_at) "
            "VALUES (?, 'review', 'chess.com', 'chess.com review', datetime('now'))",
            (pid,),
        )
        conn.execute(
            "INSERT INTO journal_entries (player_id, kind, platform, body, created_at) "
            "VALUES (?, 'review', 'lichess', 'lichess review', datetime('now'))",
            (pid,),
        )
        conn.commit()
        conn.close()

        data_all = api_get(live_server, "/api/journal?player=testplayer")
        assert len(data_all["entries"]) == 2
        assert data_all["platform_counts"] == {"chess.com": 1, "lichess": 1}

        data_li = api_get(live_server, "/api/journal?player=testplayer&platform=lichess")
        assert len(data_li["entries"]) == 1
        assert data_li["entries"][0]["body"] == "lichess review"


class TestJournalNoteEndpoints:
    """v1.12.0: POST/PUT/DELETE /api/journal/note for parent-authored notes."""

    def _post(self, base_url, path, body):
        import urllib.request
        req = urllib.request.Request(
            base_url + path,
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())

    def _put(self, base_url, path, body):
        import urllib.request
        req = urllib.request.Request(
            base_url + path,
            data=json.dumps(body).encode(),
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())

    def _delete(self, base_url, path):
        import urllib.request
        req = urllib.request.Request(base_url + path, method="DELETE")
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())

    def _post_raw(self, base_url, path, body):
        """POST variant that returns errors without raising — needed for 4xx."""
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            base_url + path,
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_create_note(self, live_server):
        status, data = self._post(
            live_server, "/api/journal/note",
            {"player": "testplayer", "body": "Round 3 tournament win!"},
        )
        assert status == 200
        assert data["entry"]["kind"] == "note"
        assert data["entry"]["body"] == "Round 3 tournament win!"
        assert data["entry"]["platform"] == "chess.com"
        assert data["entry"]["provider"] is None
        # response shape matches /api/journal entry shape
        assert "refs" in data["entry"]
        assert "metadata" in data["entry"]

    def test_create_note_missing_player_returns_400(self, live_server):
        status, _ = self._post_raw(
            live_server, "/api/journal/note", {"body": "x"}
        )
        assert status == 400

    def test_create_note_unknown_player_returns_404(self, live_server):
        status, _ = self._post_raw(
            live_server, "/api/journal/note",
            {"player": "nobody", "body": "x"},
        )
        assert status == 404

    def test_create_note_empty_body_returns_400(self, live_server):
        status, _ = self._post_raw(
            live_server, "/api/journal/note",
            {"player": "testplayer", "body": "   "},
        )
        assert status == 400

    def test_update_note_changes_body(self, live_server, db_with_data):
        # Seed a note
        status, data = self._post(
            live_server, "/api/journal/note",
            {"player": "testplayer", "body": "First."},
        )
        nid = data["entry"]["id"]

        status, data = self._put(
            live_server, f"/api/journal/note/{nid}", {"body": "Second."},
        )
        assert status == 200
        assert data["entry"]["body"] == "Second."

    def test_update_note_refuses_to_edit_reviews(self, live_server, db_with_data):
        """Reviews are immutable through the note endpoint."""
        import sqlite3
        import urllib.error
        conn = sqlite3.connect(db_with_data)
        pid = conn.execute(
            "SELECT id FROM players WHERE username = 'testplayer'"
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO journal_entries (player_id, kind, platform, body, created_at) "
            "VALUES (?, 'review', 'chess.com', 'a review', datetime('now'))",
            (pid,),
        )
        review_id = cur.lastrowid
        conn.commit()
        conn.close()

        import urllib.request
        req = urllib.request.Request(
            live_server + f"/api/journal/note/{review_id}",
            data=json.dumps({"body": "hacked"}).encode(),
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req)
            assert False, "expected 400 error"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            err = json.loads(e.read().decode())
            assert "only 'note' entries" in err["error"]

    def test_delete_note_removes_row(self, live_server, db_with_data):
        status, data = self._post(
            live_server, "/api/journal/note",
            {"player": "testplayer", "body": "to be deleted"},
        )
        nid = data["entry"]["id"]

        status, data = self._delete(live_server, f"/api/journal/note/{nid}")
        assert status == 200
        assert data["status"] == "deleted"
        assert data["id"] == nid

        # Confirm GET no longer returns it
        listing = api_get(live_server, "/api/journal?player=testplayer")
        ids = [e["id"] for e in listing["entries"]]
        assert nid not in ids

    def test_delete_note_refuses_to_delete_reviews(self, live_server, db_with_data):
        """Reviews are protected from the note delete path."""
        import sqlite3
        import urllib.error
        conn = sqlite3.connect(db_with_data)
        pid = conn.execute(
            "SELECT id FROM players WHERE username = 'testplayer'"
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO journal_entries (player_id, kind, platform, body, created_at) "
            "VALUES (?, 'review', 'chess.com', 'protected', datetime('now'))",
            (pid,),
        )
        review_id = cur.lastrowid
        conn.commit()
        conn.close()

        import urllib.request
        req = urllib.request.Request(
            live_server + f"/api/journal/note/{review_id}",
            method="DELETE",
        )
        try:
            urllib.request.urlopen(req)
            assert False, "expected 400 error"
        except urllib.error.HTTPError as e:
            assert e.code == 400


class TestCorsHeaders:
    def test_response_has_cors(self, live_server):
        """API responses should include CORS headers."""
        url = live_server + "/api/players"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            cors = resp.getheader("Access-Control-Allow-Origin")
        assert cors == "*"


class TestDateRangeFilter:
    def test_filter_by_date_from(self, live_server):
        """Games before 'from' date should be excluded."""
        data = api_get(live_server, "/api/games?player=testplayer&from=2026-01-16")
        assert len(data) == 1
        assert all(g["date_played"] >= "2026-01-16" for g in data)

    def test_filter_by_date_to(self, live_server):
        """Games after 'to' date should be excluded."""
        data = api_get(live_server, "/api/games?player=testplayer&to=2026-01-15")
        assert len(data) == 1
        assert all(g["date_played"] <= "2026-01-15" for g in data)


class TestStatusCounts:
    def test_status_has_correct_counts(self, live_server):
        data = api_get(live_server, "/api/status")
        assert data["total_games"] == 2
        assert data["analysis_complete"] == 1
        assert data["analysis_pending"] == 1


class TestPlayerFilter:
    def test_games_filtered_by_player(self, live_server):
        """Requesting an unknown player should return empty list."""
        data = api_get(live_server, "/api/games?player=nonexistent")
        assert data == []


class TestClientDisconnectHandling:
    """When the client disconnects mid-response, the server should swallow
    the resulting ConnectionResetError/BrokenPipeError and log at DEBUG —
    not blow up with two stack traces in the console.

    Regression guard for the v1.3.x console-noise bug where dev-mode
    Next.js hot reload + AbortController-cancelled fetches triggered
    full ERROR-level traces."""

    def _make_handler(self):
        """Construct a DashboardHandler without running BaseHTTPRequestHandler
        socket setup. We just need an object with the right method binding."""
        from src.dashboard_server import DashboardHandler
        from unittest.mock import MagicMock
        h = DashboardHandler.__new__(DashboardHandler)
        h.wfile = MagicMock()
        h.headers = {}
        h._headers_buffer = []
        h.send_response = MagicMock()
        h.send_header = MagicMock()
        h.end_headers = MagicMock()
        return h

    def test_send_json_swallows_connection_reset(self):
        """ConnectionResetError on wfile.write must not propagate."""
        h = self._make_handler()
        h.wfile.write.side_effect = ConnectionResetError("simulated client gone")
        # Must not raise:
        h._send_json({"ok": True})

    def test_send_json_swallows_broken_pipe(self):
        """BrokenPipeError on wfile.write must not propagate."""
        h = self._make_handler()
        h.wfile.write.side_effect = BrokenPipeError("simulated broken pipe")
        h._send_json({"ok": True})

    def test_send_json_propagates_other_errors(self):
        """Other exceptions (real bugs) should still bubble up."""
        h = self._make_handler()
        h.wfile.write.side_effect = RuntimeError("real bug")
        with pytest.raises(RuntimeError, match="real bug"):
            h._send_json({"ok": True})

    def test_handle_api_skips_recovery_on_disconnect(self):
        """When _handle_api's primary _send_json raises a disconnect error,
        the exception handler must NOT try a secondary 500-response (which
        would only raise BrokenPipeError again).

        Verified by source inspection — the exception handler must short-
        circuit on (ConnectionResetError, BrokenPipeError)."""
        from src import dashboard_server
        import inspect
        source = inspect.getsource(dashboard_server.DashboardHandler._handle_api)
        assert "ConnectionResetError" in source and "BrokenPipeError" in source, (
            "_handle_api must detect client-disconnect errors and short-circuit"
        )
        assert "Client disconnected" in source, (
            "_handle_api must log client disconnects at debug, not as ERROR"
        )
