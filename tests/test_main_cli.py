"""CLI subcommand dispatch tests for main.py.

v1.15.3: started this module to add coverage for cmd_trend (v1.15.2).
Future CLI subcommands should slot in here alongside instead of
sprawling test_main.py / test_cli.py / etc.

Pattern: build an argparse.Namespace manually, patch the heavy
collaborator (LLM call, network call, etc.) at its lazy-import
target, invoke the cmd_* function, assert on dispatch + stdout.
Fast, no LLM, no Stockfish.
"""

import argparse

import pytest

from src.models import init_db, ensure_player

import main as main_module


def _config(db_path: str) -> dict:
    """Minimal config dict matching what main.py's cmd_* functions read."""
    return {
        "database": {"path": db_path},
        "coaching": {"default_provider": "claude"},
    }


def _args(**overrides) -> argparse.Namespace:
    """Build a trend-subcommand-shaped Namespace with sane defaults."""
    base = {"player": None, "provider": None, "model": None}
    base.update(overrides)
    return argparse.Namespace(**base)


class TestCmdTrend:
    """v1.15.3: regression locks for the v1.15.2 trend CLI subcommand."""

    def test_dispatches_to_generate_trend_summary(
        self, db_path, monkeypatch, capsys,
    ):
        """`python main.py trend --player evan --provider openai` must
        call generate_trend_summary(player_id, db_path, provider, model)
        exactly once with the resolved player_id."""
        conn = init_db(db_path)
        # v1.16.4: slug "evan" auto-derived from display_name "Evan".
        # CLI --player now requires slug, not chess.com username.
        pid = ensure_player(
            conn, "evanleongxinyu", display_name="Evan", age=9, rating=1100,
        )
        conn.close()

        calls = []
        def fake_generate(player_id, db_path=None, provider="claude", model=None):
            calls.append({
                "player_id": player_id, "db_path": db_path,
                "provider": provider, "model": model,
            })
            return "fake summary text"

        monkeypatch.setattr(
            "src.patterns.generate_trend_summary", fake_generate,
        )

        args = _args(player=["evan"], provider="openai")
        main_module.cmd_trend(args, _config(db_path))

        assert len(calls) == 1
        c = calls[0]
        assert c["player_id"] == pid
        assert c["provider"] == "openai"
        assert c["model"] is None
        assert c["db_path"] == db_path

        out = capsys.readouterr().out
        assert "✓ evanleongxinyu" in out

    def test_model_override_passes_through(
        self, db_path, monkeypatch, capsys,
    ):
        """--model flag must reach generate_trend_summary unchanged."""
        conn = init_db(db_path)
        ensure_player(conn, "evan", display_name="Evan", age=9, rating=1100)
        conn.close()

        captured = {}
        def fake_generate(player_id, db_path=None, provider="claude", model=None):
            captured["model"] = model
            return "ok"

        monkeypatch.setattr(
            "src.patterns.generate_trend_summary", fake_generate,
        )

        args = _args(
            player=["evan"], provider="openai",
            model="gpt-5.5-pro-2026-04-23",
        )
        main_module.cmd_trend(args, _config(db_path))

        assert captured.get("model") == "gpt-5.5-pro-2026-04-23"

    def test_skips_missing_player_with_warn(
        self, db_path, monkeypatch, capsys,
    ):
        """Unknown username must print a WARN line and exit cleanly —
        never propagate an exception, never crash."""
        # Patch generate_trend_summary defensively so a bug-induced
        # call would be caught (we expect ZERO calls here).
        called = []
        monkeypatch.setattr(
            "src.patterns.generate_trend_summary",
            lambda *a, **kw: called.append(1),
        )

        args = _args(player=["ghost_player"])
        # Must not raise
        main_module.cmd_trend(args, _config(db_path))

        out = capsys.readouterr().out
        assert "WARN" in out
        assert "ghost_player" in out
        assert "No target players found" in out
        assert called == [], "generate_trend_summary should not be invoked for unknown players"

    def test_reports_no_pattern_stats_per_target(
        self, db_path, monkeypatch, capsys,
    ):
        """If generate_trend_summary raises ValueError ('No pattern
        stats for player ...'), the CLI must catch it, mark the
        target ✗, and continue — not propagate."""
        conn = init_db(db_path)
        ensure_player(conn, "evan", display_name="Evan", age=9, rating=1100)
        conn.close()

        def fake_generate(*args, **kwargs):
            raise ValueError("No pattern stats for player 1. Run patterns first.")

        monkeypatch.setattr(
            "src.patterns.generate_trend_summary", fake_generate,
        )

        args = _args(player=["evan"], provider="claude")
        # Must not raise
        main_module.cmd_trend(args, _config(db_path))

        out = capsys.readouterr().out
        assert "✗ evan" in out
        assert "No pattern stats" in out

    def test_no_player_flag_iterates_active_players(
        self, db_path, monkeypatch, capsys,
    ):
        """Without --player, cmd_trend iterates all active players."""
        conn = init_db(db_path)
        ensure_player(conn, "evan", display_name="Evan", age=9, rating=1100)
        ensure_player(conn, "estella", display_name="Estella", age=7, rating=850)
        conn.close()

        seen = []
        def fake_generate(player_id, db_path=None, provider="claude", model=None):
            seen.append(player_id)
            return "ok"

        monkeypatch.setattr(
            "src.patterns.generate_trend_summary", fake_generate,
        )

        args = _args(player=None, provider="openai")
        main_module.cmd_trend(args, _config(db_path))

        assert len(seen) == 2, f"expected 2 players, got {seen}"


class TestCmdTrendSlugSupport:
    """v1.16.1: --player accepts slug ('evanleong') OR chess.com
    username ('nevergiveupgreatthings'). Same player resolves either
    way; unknown identifier still WARNs cleanly."""

    def test_v16_1_accepts_slug(self, db_path, monkeypatch, capsys):
        """--player evanleong (slug) must resolve to the same id as
        --player nevergiveupgreatthings (chess.com username)."""
        conn = init_db(db_path)
        pid = ensure_player(
            conn, "nevergiveupgreatthings", display_name="Evan Leong",
            age=9, rating=1100,
        )
        conn.close()

        calls = []
        def fake_generate(player_id, db_path=None, provider="claude", model=None):
            calls.append(player_id)
            return "ok"

        monkeypatch.setattr(
            "src.patterns.generate_trend_summary", fake_generate,
        )

        args = _args(player=["evanleong"], provider="openai")
        main_module.cmd_trend(args, _config(db_path))

        assert calls == [pid], (
            f"slug 'evanleong' should resolve to player id {pid}; got {calls}"
        )

    def test_v16_4_legacy_username_rejected(self, db_path, monkeypatch, capsys):
        """v1.16.4: --player <chess.com-username> is no longer
        accepted. The v1.16.1 backward-compat fallback was dropped —
        CLI lookups are slug-only now. Symptom: WARN + skip, no
        generate call."""
        conn = init_db(db_path)
        ensure_player(
            conn, "nevergiveupgreatthings", display_name="Evan Leong",
            age=9, rating=1100,
        )
        conn.close()

        calls = []
        monkeypatch.setattr(
            "src.patterns.generate_trend_summary",
            lambda player_id, **kw: calls.append(player_id) or "ok",
        )

        args = _args(player=["nevergiveupgreatthings"], provider="openai")
        main_module.cmd_trend(args, _config(db_path))

        out = capsys.readouterr().out
        assert "WARN" in out
        assert "nevergiveupgreatthings" in out
        assert calls == [], (
            "v1.16.4: chess.com username should NOT resolve to player_id; "
            "only slug should match."
        )

    def test_v16_1_unknown_identifier_skipped(self, db_path, monkeypatch, capsys):
        """A value matching neither slug nor username gets WARN'd
        and the command continues — no crash, no propagated error."""
        conn = init_db(db_path)
        ensure_player(conn, "nevergiveupgreatthings", display_name="Evan Leong")
        conn.close()

        called = []
        monkeypatch.setattr(
            "src.patterns.generate_trend_summary",
            lambda *a, **kw: called.append(1),
        )

        args = _args(player=["ghost"], provider="openai")
        main_module.cmd_trend(args, _config(db_path))

        out = capsys.readouterr().out
        assert "WARN" in out
        assert "ghost" in out
        assert called == [], "unknown identifier should not invoke generate"


class TestConfigSlugHelpers:
    """v1.16.5: _config_slug + _player_matches for config-dict filtering
    in cmd_harvest / cmd_report. These filter config.yaml player dicts
    (not DB rows), so they need their own slug derivation."""

    def test_config_slug_explicit(self):
        p = {"username": "nevergiveupgreatthings", "slug": "evan",
             "display_name": "Evan Leong"}
        assert main_module._config_slug(p) == "evan"

    def test_config_slug_derived_from_display_name(self):
        p = {"username": "nevergiveupgreatthings", "display_name": "Evan Leong"}
        assert main_module._config_slug(p) == "evanleong"

    def test_config_slug_falls_back_to_username(self):
        p = {"username": "kayaistoast"}
        assert main_module._config_slug(p) == "kayaistoast"

    def test_config_slug_empty_fallback(self):
        assert main_module._config_slug({}) == "player"

    def test_player_matches_by_slug(self):
        p = {"username": "nevergiveupgreatthings", "display_name": "Evan Leong"}
        assert main_module._player_matches(p, ["evanleong"]) is True

    def test_player_matches_by_username(self):
        p = {"username": "nevergiveupgreatthings", "display_name": "Evan Leong"}
        assert main_module._player_matches(p, ["nevergiveupgreatthings"]) is True

    def test_player_matches_rejects_unrelated(self):
        p = {"username": "nevergiveupgreatthings", "display_name": "Evan Leong"}
        assert main_module._player_matches(p, ["estellaleong"]) is False


class TestRescanMotifsSlug:
    """v1.16.5: rescan-motifs --player accepts slug (regression lock
    for the v1.16.4 miss that made `rescan-motifs --player evanleong`
    return 'No analyzed games match')."""

    def _make_args(self, player=None, limit=None):
        return argparse.Namespace(player=player, limit=limit)

    def test_rescan_resolves_by_slug(self, db_path, capsys):
        """A player whose slug differs from username (evanleong vs
        nevergiveupgreatthings) must be found by slug in rescan-motifs.
        Insert a complete game with a motifs-eligible move."""
        from src.models import init_db, ensure_player
        conn = init_db(db_path)
        pid = ensure_player(
            conn, "nevergiveupgreatthings", display_name="Evan Leong",
            slug="evanleong", age=9, rating=1100,
        )
        # Minimal analyzed game so rescan has something to walk.
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, player_rating,
             opponent_rating, result, time_control, time_class,
             date_played, analysis_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, "https://chess.com/g/x",
             '[White "x"]\n[Black "y"]\n\n1. e4 e5 2. Nf3 *',
             "white", 1100, 1050, "win", "600", "rapid",
             "2026-05-01", "complete"),
        )
        conn.commit()
        conn.close()

        # Should NOT print "No analyzed games match" when given the slug.
        main_module.cmd_rescan_motifs(
            self._make_args(player="evanleong"),
            _config(db_path),
        )
        out = capsys.readouterr().out
        assert "No analyzed games match" not in out, (
            "v1.16.5 regression: rescan-motifs --player evanleong (slug) "
            "should resolve, not report zero games."
        )
        assert "Rescanning 1 games" in out or "Rescanning" in out


class TestCmdHuntScan:
    """v1.20.0: `python main.py hunt-scan` dispatches to
    deep_scan_opponent with the resolved opponent/platform/limit and
    prints the top blind spot. Patches the engine pass — no Stockfish."""

    def _args(self, opponent="rival", platform="chess.com", games=None):
        return argparse.Namespace(
            opponent=opponent, platform=platform, games=games,
        )

    def test_dispatches_to_deep_scan(self, db_path, monkeypatch, capsys):
        calls = {}

        def fake_scan(username, platform, config=None, db_path=None,
                      limit=20, progress_cb=None):
            calls["username"] = username
            calls["platform"] = platform
            calls["limit"] = limit
            return {"analyzed": 3, "skipped": 0, "candidates": 3}

        def fake_summary(username, platform, db_path=None):
            return {"top_missed": "fork", "top_missed_count": 4,
                    "games_analyzed": 3}

        monkeypatch.setattr("src.hunter.deep_scan_opponent", fake_scan)
        monkeypatch.setattr(
            "src.hunter.compute_opponent_motif_summary", fake_summary,
        )

        cfg = _config(db_path)
        cfg["features"] = {"hunter_scan_games": 12}
        cfg["stockfish"] = {"depth": 22}
        main_module.cmd_hunt_scan(self._args(games=None), cfg)

        assert calls["username"] == "rival"
        assert calls["platform"] == "chess.com"
        assert calls["limit"] == 12  # from features.hunter_scan_games
        out = capsys.readouterr().out
        assert "Top blind spot: fork" in out

    def test_games_flag_overrides_config(self, db_path, monkeypatch, capsys):
        captured = {}

        def fake_scan(u, p, config=None, db_path=None, limit=20, progress_cb=None):
            captured["limit"] = limit
            return {"analyzed": 0, "skipped": 0, "candidates": 0}

        monkeypatch.setattr("src.hunter.deep_scan_opponent", fake_scan)
        monkeypatch.setattr(
            "src.hunter.compute_opponent_motif_summary",
            lambda u, p, db_path=None: None,
        )
        cfg = _config(db_path)
        main_module.cmd_hunt_scan(self._args(games=5), cfg)
        assert captured["limit"] == 5
        out = capsys.readouterr().out
        assert "No tactical blind spots detected yet." in out

    def test_stockfish_missing_is_reported(self, db_path, monkeypatch, capsys):
        def boom(*a, **kw):
            raise FileNotFoundError(
                "Stockfish not found. Install it with: brew install stockfish"
            )
        monkeypatch.setattr("src.hunter.deep_scan_opponent", boom)
        main_module.cmd_hunt_scan(self._args(), _config(db_path))
        out = capsys.readouterr().out
        assert "ERROR" in out and "Stockfish not found" in out


class TestCmdTournamentPrep:
    """v1.21.0: `python main.py tournament-prep --id N` warms the roster
    (patched) + prints the top opening targets."""

    def test_warms_and_prints_targets(self, db_path, monkeypatch, capsys):
        from src.models import init_db, ensure_player
        from src.hunter import set_cached_profile
        from src import tournament as T

        conn = init_db(db_path)
        pid = ensure_player(conn, "evan", display_name="Evan", slug="evanleong")
        prof = {
            "total_games": 6,
            "results": {"wins": 1, "losses": 5, "draws": 0, "win_rate": 16.7},
            "weaknesses": {"white": [{"name": "Kings Gambit", "eco": "C30",
                                      "total": 5, "wins": 1, "losses": 4,
                                      "draws": 0, "rate": 80.0}],
                           "black": []},
            "strengths": {"white": [], "black": []},
        }
        set_cached_profile(conn, "oppa", "chess.com", prof)
        set_cached_profile(conn, "oppb", "chess.com", prof)
        conn.close()

        t = T.create_tournament(pid, "Club", db_path=db_path)
        T.add_opponent(t["id"], "oppa", db_path=db_path)
        T.add_opponent(t["id"], "oppb", db_path=db_path)

        # Patch the network warm so the test never hits chess.com/lichess.
        warmed = []
        monkeypatch.setattr(
            "src.hunter.get_or_fetch_profile",
            lambda u, p, dbp, **kw: warmed.append(u) or {},
        )

        cfg = _config(db_path)
        cfg["features"] = {"tournament_min_shared": 2}
        main_module.cmd_tournament_prep(
            argparse.Namespace(id=t["id"]), cfg,
        )
        out = capsys.readouterr().out
        assert sorted(warmed) == ["oppa", "oppb"]
        assert "Kings Gambit" in out

    def test_unknown_tournament_reports_error(self, db_path, capsys):
        main_module.cmd_tournament_prep(
            argparse.Namespace(id=99999), _config(db_path),
        )
        out = capsys.readouterr().out
        assert "ERROR" in out
