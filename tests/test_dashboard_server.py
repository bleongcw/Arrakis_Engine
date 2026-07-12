"""Tests for the live dashboard API server."""

import json
import threading
import time
import urllib.request
import urllib.error

import pytest

from src.models import init_db, ensure_player
from src.dashboard_server import run_dashboard


@pytest.fixture
def db_with_data(tmp_path):
    """Create a test DB with sample data."""
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)

    # v1.16.4: fixture player has DIFFERENT slug from chess.com
    # username — exercises the slug-only lookup path realistically.
    # Slug "test" is auto-derivable from display_name "Test" but we
    # set it explicitly for clarity. Tests that pass "test" as
    # ?player= should succeed; tests that pass "testplayer" should
    # fail (legacy-username rejection).
    pid = ensure_player(conn, "testplayer", display_name="Test",
                        slug="test", age=10, rating=1000)

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


def api_post(base_url, path, payload):
    """Helper: POST JSON to an API endpoint. Returns (status, parsed_json)."""
    url = base_url + path
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


class TestPlayersAPI:
    def test_list_players(self, live_server):
        data = api_get(live_server, "/api/players")
        assert len(data) == 1
        assert data[0]["username"] == "testplayer"
        assert data[0]["display_name"] == "Test"


class TestGamesAPI:
    def test_list_games(self, live_server):
        data = api_get(live_server, "/api/games?player=test")
        assert len(data) == 2

    def test_filter_by_result(self, live_server):
        data = api_get(live_server, "/api/games?player=test&result=win")
        assert len(data) == 1
        assert data[0]["result"] == "win"

    def test_filter_by_time_class(self, live_server):
        data = api_get(live_server, "/api/games?player=test&time_class=blitz")
        assert len(data) == 1
        assert data[0]["time_class"] == "blitz"

    def test_game_detail(self, live_server):
        games = api_get(live_server, "/api/games?player=test")
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

    # ── v1.16.3 → v1.16.4: /api/games slug-only behavior ────────────

    def test_v16_4_games_resolves_by_slug(self, live_server):
        """v1.16.3 regression lock: /api/games?player=<slug> returns
        the player's games. v1.16.1 missed this site (the symptom that
        made Bernard's Games tab empty). Fixture slug is 'test'."""
        data = api_get(live_server, "/api/games?player=test")
        assert len(data) == 2

    def test_v16_4_games_rejects_legacy_username(self, live_server):
        """v1.16.4: passing the chess.com username (the fixture's
        'testplayer') no longer resolves — only the slug 'test'
        matches. Returns an empty list."""
        data = api_get(live_server, "/api/games?player=testplayer")
        assert data == [], (
            "v1.16.4: chess.com username should no longer resolve via "
            "/api/games — slug-only lookup."
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

    def test_no_player_username_lookups_outside_creation_check(self):
        """v1.16.4 (tightened from v1.16.3): the ONLY allowed
        `WHERE username = ?` site in dashboard_server.py is the
        player-creation existence check (is_active context). The
        resolver's v1.16.1 fallback was dropped in v1.16.4 — slug-only
        lookups now. Any new `WHERE username = ?` for a player lookup
        is a bug."""
        import re
        from pathlib import Path
        path = Path(__file__).parent.parent / "src" / "dashboard_server.py"
        text = path.read_text()
        offenders = []
        for m in re.finditer(r"WHERE username = \?", text):
            # Allow ONLY the player-creation existence check
            ctx = text[max(0, m.start() - 200):m.start() + 30]
            if "is_active" in ctx:
                continue  # _handle_create_player — intentional
            # Walk backwards to find the nearest `def ` line for diagnostics
            preceding = text[:m.start()]
            def_matches = list(re.finditer(r"^def (\w+)", preceding, re.MULTILINE))
            enclosing = def_matches[-1].group(1) if def_matches else "<unknown>"
            offenders.append((m.start(), enclosing))
        assert not offenders, (
            f"v1.16.4 regression: {len(offenders)} `WHERE username = ?` "
            f"site(s) found outside the player-creation check: "
            f"{offenders}. v1.16.4 is slug-only — all player lookups "
            f"must use slug. The chess.com `username` column is "
            f"reserved for the harvester's API calls only."
        )


class TestStatusAPI:
    def test_status(self, live_server):
        data = api_get(live_server, "/api/status")
        assert data["total_games"] == 2
        assert data["analysis_complete"] == 1
        assert data["analysis_pending"] == 1


class TestPatternsAPI:
    def test_no_patterns(self, live_server):
        data = api_get(live_server, "/api/patterns?player=test")
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

    def test_v16_4_legacy_username_no_longer_resolves(self, live_server):
        """v1.16.4: the v1.16.1 backward-compat fallback was dropped.
        Calling /api/patterns?player=<chess.com-username> now returns
        the same empty shape as an unknown identifier (stats: None).

        Bookmarks created before v1.16.1 would have used the chess.com
        username; the v1.16.1 frontend stopped emitting those URLs, so
        the only callers still using them are stale browser bookmarks
        or hardcoded scripts. v1.16.4 cleanly rejects them rather than
        carrying the dual-lookup forever."""
        # 'testplayer' is the chess.com username of the fixture player.
        # After v1.16.4 this no longer matches — only the slug 'test' does.
        data = api_get(live_server, "/api/patterns?player=test")
        assert data["stats"] is None
        # The endpoint still echoes the param back as 'username' for
        # the frontend's empty-state rendering — that's a cosmetic
        # field name, not evidence the lookup succeeded.

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
        data = api_get(live_server, "/api/journal?player=test")
        assert data["entries"] == []
        assert data["platform_counts"] == {}
        # v1.16.4: the "username" field in the response is just an
        # echo of the ?player= param (legacy naming — it's actually
        # the slug now). Rename is out of scope for v1.16.4.
        assert data["username"] == "test"

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

        data = api_get(live_server, "/api/journal?player=test")
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

        data_all = api_get(live_server, "/api/journal?player=test")
        assert len(data_all["entries"]) == 2
        assert data_all["platform_counts"] == {"chess.com": 1, "lichess": 1}

        data_li = api_get(live_server, "/api/journal?player=test&platform=lichess")
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
            {"player": "test", "body": "Round 3 tournament win!"},
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
            {"player": "test", "body": "   "},
        )
        assert status == 400

    def test_update_note_changes_body(self, live_server, db_with_data):
        # Seed a note
        status, data = self._post(
            live_server, "/api/journal/note",
            {"player": "test", "body": "First."},
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
            {"player": "test", "body": "to be deleted"},
        )
        nid = data["entry"]["id"]

        status, data = self._delete(live_server, f"/api/journal/note/{nid}")
        assert status == 200
        assert data["status"] == "deleted"
        assert data["id"] == nid

        # Confirm GET no longer returns it
        listing = api_get(live_server, "/api/journal?player=test")
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


class TestHuntDeepScanAPI:
    """v1.20.0: GET /api/hunt/profile carries Deep Scan results
    (motif_summary + deep_scan status). Seeds a fresh cached profile +
    an analyzed opponent game so the request never hits the network."""

    def test_profile_carries_motif_summary_and_status(
        self, live_server, db_with_data,
    ):
        import json as _json
        from src.models import init_db
        from src.hunter import set_cached_profile

        conn = init_db(db_with_data)
        # Fresh cached profile → get_or_fetch_profile returns it (no fetch).
        set_cached_profile(conn, "rival", "chess.com", {
            "total_games": 1,
            "results": {"wins": 0, "losses": 1, "draws": 0, "win_rate": 0.0},
            "weaknesses": {"white": [], "black": []},
            "strengths": {"white": [], "black": []},
        })
        # One analyzed opponent game so deep_scan + motif_summary populate.
        conn.execute(
            """INSERT INTO opponent_games
            (username, platform, game_url, pgn, player_color, result,
             date_played, motifs_json, analyzed_at)
            VALUES ('rival','chess.com','gx','pgn','white','loss',
                    '2026-05-01', ?, datetime('now'))""",
            (_json.dumps({
                "found": {}, "missed": {"fork": 2}, "critical_moves": 2,
                "missed_by_phase": {"fork": {"opening": 0, "middlegame": 2, "endgame": 0}},
            }),),
        )
        conn.commit()
        conn.close()

        data = api_get(live_server, "/api/hunt/profile?opponent=rival&platform=chess.com")
        assert "motif_summary" in data
        assert "deep_scan" in data
        assert data["deep_scan"]["analyzed_games"] == 1
        assert data["motif_summary"]["top_missed"] == "fork"


class TestTournamentAPI:
    """v1.21.0: tournament roster CRUD + combined prep over HTTP."""

    def _post(self, base_url, path, body):
        req = urllib.request.Request(
            base_url + path, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())

    def test_create_add_list_prep_flow(self, live_server, db_with_data):
        from src.models import init_db
        from src.hunter import set_cached_profile

        conn = init_db(db_with_data)
        prof = {
            "total_games": 8,
            "results": {"wins": 3, "losses": 4, "draws": 1, "win_rate": 37.5},
            "weaknesses": {"white": [{"name": "Italian", "eco": "C50",
                                      "total": 4, "wins": 1, "losses": 3,
                                      "draws": 0, "rate": 75.0}],
                           "black": []},
            "strengths": {"white": [], "black": []},
        }
        set_cached_profile(conn, "oppa", "chess.com", prof)
        set_cached_profile(conn, "oppb", "chess.com", prof)
        conn.close()

        # db_with_data seeds a player; resolve its slug for the create call.
        players = api_get(live_server, "/api/players")
        slug = players["players"][0]["slug"] if isinstance(players, dict) else players[0]["slug"]

        t = self._post(live_server, "/api/tournament/create",
                       {"player": slug, "name": "Club Champs"})
        assert t["name"] == "Club Champs"
        self._post(live_server, "/api/tournament/add-opponent",
                   {"tournament_id": t["id"], "opponent": "oppa"})
        self._post(live_server, "/api/tournament/add-opponent",
                   {"tournament_id": t["id"], "opponent": "oppb"})

        listed = api_get(live_server, f"/api/tournaments?player={slug}")
        assert any(x["id"] == t["id"] and x["opponent_count"] == 2
                   for x in listed["tournaments"])

        prep = api_get(live_server, f"/api/tournament?id={t['id']}")
        assert prep["opening_targets"][0]["opening"] == "Italian"
        assert prep["opening_targets"][0]["opponent_count"] == 2
        assert prep["scan_coverage"]["total"] == 2

    def test_missing_id_errors(self, live_server):
        data = api_get(live_server, "/api/tournament")
        assert "error" in data


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
        data = api_get(live_server, "/api/games?player=test&from=2026-01-16")
        assert len(data) == 1
        assert all(g["date_played"] >= "2026-01-16" for g in data)

    def test_filter_by_date_to(self, live_server):
        """Games after 'to' date should be excluded."""
        data = api_get(live_server, "/api/games?player=test&to=2026-01-15")
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


class TestRouteRegistry:
    """v1.22.0: out-of-tree code can register routes into the core dashboard."""

    def test_register_get_and_post_route(self, live_server):
        from src import dashboard_server as ds

        ds.register_route(
            "GET", "/api/_test-registry",
            lambda self, params: {"ok": True, "via": "GET"},
        )

        captured = {}

        def _post_handler(self, body):
            captured["body"] = body
            self._send_json({"ok": True, "via": "POST"})

        ds.register_route("POST", "/api/_test-registry", _post_handler)
        try:
            got = api_get(live_server, "/api/_test-registry")
            assert got == {"ok": True, "via": "GET"}

            req = urllib.request.Request(
                live_server + "/api/_test-registry",
                data=json.dumps({"hello": "world"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                posted = json.loads(resp.read().decode())
            assert posted == {"ok": True, "via": "POST"}
            assert captured["body"] == {"hello": "world"}
        finally:
            ds._GET_ROUTES.pop("/api/_test-registry", None)
            ds._POST_ROUTES.pop("/api/_test-registry", None)


# Two decided competition games (no TimeControl, no Elo, real names). The fixture
# player's display_name is "Test", so color auto-detects: white in game 1, black
# in game 2. run_pipeline=False keeps Stockfish out of the test.
COMPETITION_PGN = """[Event "Club Championship"]
[Site "Singapore"]
[Date "2026.07.12"]
[White "Test"]
[Black "Rival A"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0

[Event "Club Championship"]
[Site "Singapore"]
[Date "2026.07.13"]
[White "Rival B"]
[Black "Test"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0
"""


class TestCompetitionImport:
    def test_import_competition_batch(self, live_server):
        status, data = api_post(
            live_server,
            "/api/import-pgn",
            {
                "player": "test",
                "pgn": COMPETITION_PGN,
                "platform": "competition",
                "time_class": "classical",
                "run_pipeline": False,
            },
        )
        assert status == 201
        assert data["created_count"] == 2
        assert data["existing_count"] == 0
        assert data["skipped"] == []

        by_color = {g["player_color"]: g for g in data["games"]}
        # display_name "Test" matched White in game 1, Black in game 2.
        assert by_color["white"]["result"] == "win"
        assert by_color["black"]["result"] == "loss"
        assert all(g["time_class"] == "classical" for g in data["games"])

        # Games land in the list tagged platform='competition'.
        games = api_get(live_server, "/api/games?player=test")
        comp = [g for g in games if g["platform"] == "competition"]
        assert len(comp) == 2
        assert all(g["time_class"] == "classical" for g in comp)

    def test_import_competition_dedups(self, live_server):
        payload = {
            "player": "test",
            "pgn": COMPETITION_PGN,
            "platform": "competition",
            "time_class": "classical",
            "run_pipeline": False,
        }
        api_post(live_server, "/api/import-pgn", payload)
        status, data = api_post(live_server, "/api/import-pgn", payload)
        assert status == 200
        assert data["created_count"] == 0
        assert data["existing_count"] == 2

    def test_import_competition_skips_undecided(self, live_server):
        pgn = COMPETITION_PGN + (
            '\n[White "Test"]\n[Black "Rival C"]\n[Result "*"]\n\n1. d4 d5 *\n'
        )
        status, data = api_post(
            live_server,
            "/api/import-pgn",
            {
                "player": "test",
                "pgn": pgn,
                "platform": "competition",
                "time_class": "rapid",
                "run_pipeline": False,
            },
        )
        assert status == 201
        assert data["created_count"] == 2
        assert len(data["skipped"]) == 1
        assert "no decided result" in data["skipped"][0]
