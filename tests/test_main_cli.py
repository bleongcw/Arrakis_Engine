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
