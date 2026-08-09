"""Tests for src/analyzer.py"""

import inspect
from unittest.mock import MagicMock

import pytest

from src.analyzer import (
    cp_to_win_prob, classify_move, score_to_cp, cap_eval, EVAL_CAP,
    analyze_game,
)


class TestAnalyzeGameBestInfoOrdering:
    """v1.16.2 regression lock for the UnboundLocalError bug.

    The v1.14.0 motif wiring put `best_move_obj = best_info["pv"][0]`
    BEFORE `best_info = info` in the per-move loop. On the very first
    iteration of every newly-analyzed game, `best_info` didn't exist
    yet, raising:

        UnboundLocalError: cannot access local variable 'best_info'
        where it is not associated with a value

    The bug only triggered on `analyze_game` (new analyses) — never
    on rescan-motifs (which doesn't call analyze_game). Symptom was
    silent: 'Failed to analyze game N' in the logs, no Stockfish work,
    no stack trace surfaced to the user.

    This static test inspects the source of analyze_game and asserts
    that `best_info = info` appears BEFORE `best_move_obj = best_info`.
    Static-source check (zero-cost, no Stockfish needed) — runs on
    every commit and would have caught the v1.14.0 regression
    instantly.
    """

    def test_best_info_assigned_before_best_move_obj_read(self):
        src = inspect.getsource(analyze_game)
        # Find the two lines of interest
        assign_idx = src.find("best_info = info")
        read_idx = src.find('best_info["pv"][0] if best_info.get("pv")')
        assert assign_idx != -1, (
            "expected `best_info = info` in analyze_game"
        )
        assert read_idx != -1, (
            "expected `best_info[\"pv\"][0] if best_info.get(\"pv\")` "
            "in analyze_game"
        )
        assert assign_idx < read_idx, (
            f"v1.16.2 regression: `best_info = info` (idx {assign_idx}) "
            f"must come BEFORE the line that reads best_info to derive "
            f"best_move_obj (idx {read_idx}). Otherwise the first loop "
            f"iteration raises UnboundLocalError on freshly-analyzed "
            f"games."
        )


class TestCpToWinProb:
    def test_zero_is_fifty_percent(self):
        assert cp_to_win_prob(0) == pytest.approx(50.0)

    def test_positive_cp_above_fifty(self):
        assert cp_to_win_prob(100) > 50.0

    def test_negative_cp_below_fifty(self):
        assert cp_to_win_prob(-100) < 50.0

    def test_symmetry(self):
        """Win prob at +X should mirror 100 - win_prob at -X."""
        wp_pos = cp_to_win_prob(200)
        wp_neg = cp_to_win_prob(-200)
        assert wp_pos == pytest.approx(100.0 - wp_neg, abs=0.01)

    def test_large_advantage(self):
        assert cp_to_win_prob(1000) > 95.0

    def test_large_disadvantage(self):
        assert cp_to_win_prob(-1000) < 5.0


class TestClassifyMove:
    def test_excellent(self):
        assert classify_move(0) == "excellent"
        assert classify_move(30) == "excellent"

    def test_good(self):
        assert classify_move(31) == "good"
        assert classify_move(50) == "good"

    def test_inaccuracy(self):
        assert classify_move(51) == "inaccuracy"
        assert classify_move(100) == "inaccuracy"

    def test_mistake(self):
        assert classify_move(101) == "mistake"
        assert classify_move(300) == "mistake"

    def test_blunder(self):
        assert classify_move(301) == "blunder"
        assert classify_move(1000) == "blunder"


class TestCapEval:
    def test_within_range_passthrough(self):
        assert cap_eval(500) == 500
        assert cap_eval(-500) == -500
        assert cap_eval(0) == 0

    def test_clamps_positive_overflow(self):
        assert cap_eval(2000) == EVAL_CAP
        assert cap_eval(99999) == EVAL_CAP

    def test_clamps_negative_overflow(self):
        assert cap_eval(-2000) == -EVAL_CAP
        assert cap_eval(-99999) == -EVAL_CAP


class TestScoreToCp:
    """Test PovScore → centipawn conversion using mock objects."""

    def _mock_score(self, cp=None, mate=None):
        """Build a mock PovScore.

        If mate is set, is_mate() returns True.
        """
        pov = MagicMock()
        white = MagicMock()
        pov.white.return_value = white

        if mate is not None:
            white.is_mate.return_value = True
            white.mate.return_value = mate
            white.score.return_value = None
        else:
            white.is_mate.return_value = False
            white.mate.return_value = None
            white.score.return_value = cp
        return pov

    def test_normal_centipawn(self):
        score = self._mock_score(cp=150)
        assert score_to_cp(score, True) == 150

    def test_negative_centipawn(self):
        score = self._mock_score(cp=-200)
        assert score_to_cp(score, True) == -200

    def test_mate_positive(self):
        score = self._mock_score(mate=3)
        assert score_to_cp(score, True) == EVAL_CAP

    def test_mate_negative(self):
        score = self._mock_score(mate=-5)
        assert score_to_cp(score, True) == -EVAL_CAP

    def test_zero_cp(self):
        score = self._mock_score(cp=0)
        assert score_to_cp(score, True) == 0


class TestAnalyzePendingCancel:
    """v1.22.4: analyze_pending stops between games when cancel_event is set.

    This is what makes "Run All" / Analyze actually cancellable during the
    (long) analysis phase. We pre-set the event so the loop breaks before the
    first game — no Stockfish is ever spawned (a dummy binary path satisfies
    the existence check, but analyze_game is never reached)."""

    def test_preset_cancel_analyzes_nothing(self, tmp_path):
        import threading
        from src.analyzer import analyze_pending
        from src.models import init_db, ensure_player

        db = str(tmp_path / "a.db")
        conn = init_db(db)
        pid = ensure_player(conn, "p", display_name="P", age=9, rating=1000)
        for i in range(3):
            conn.execute(
                """INSERT INTO games
                (player_id, game_url, pgn, player_color, player_rating,
                 opponent_rating, result, time_control, time_class,
                 date_played, analysis_status)
                VALUES (?, ?, '[White "p"]\n\n1. e4 e5 *', 'white', 1000, 1000,
                        'win', '600', 'rapid', '2026-05-01', 'pending')""",
                (pid, f"https://chess.com/g/{i}"),
            )
        conn.commit()
        conn.close()

        dummy_sf = tmp_path / "stockfish"      # exists; never executed
        dummy_sf.write_text("")

        ev = threading.Event()
        ev.set()
        n = analyze_pending(str(dummy_sf), db_path=db, cancel_event=ev)
        assert n == 0

        # All games remain pending (none were analyzed).
        conn = init_db(db)
        pending = conn.execute(
            "SELECT COUNT(*) FROM games WHERE analysis_status = 'pending'"
        ).fetchone()[0]
        conn.close()
        assert pending == 3


class TestAnalyzeGameResourceSafety:
    """v1.29.0 (F3): analyze_game must release the Stockfish engine and the DB
    connection on EVERY path, including a mid-run exception. Before this a raise
    leaked the engine and a connection holding an open write transaction."""

    def test_source_wraps_body_in_try_finally_with_engine_quit(self):
        import inspect
        from src.analyzer import analyze_game
        src = inspect.getsource(analyze_game)
        assert "engine = None" in src
        # engine.quit() lives in a finally, guarded on engine is not None.
        finally_idx = src.rindex("finally:")
        assert "engine.quit()" in src[finally_idx:]
        assert "if engine is not None:" in src[finally_idx:]
        assert "conn.close()" in src[finally_idx:]

    def test_engine_released_and_no_rows_left_on_exception(self, tmp_path):
        from unittest.mock import patch
        from src.analyzer import analyze_game
        from src.models import init_db, ensure_player

        db = str(tmp_path / "a.db")
        conn = init_db(db)
        pid = ensure_player(conn, "p", display_name="P", age=9, rating=1000)
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, result,
             analysis_status, coaching_status)
            VALUES (?, 'u1', '1. e4 e5 2. Nf3 *', 'white', 'win',
                    'analyzing', 'pending')""",
            (pid,),
        )
        conn.commit()
        gid = conn.execute("SELECT id FROM games").fetchone()[0]
        conn.close()

        mock_engine = MagicMock()
        mock_engine.analyse.side_effect = RuntimeError("engine died")

        with patch("chess.engine.SimpleEngine.popen_uci", return_value=mock_engine):
            with pytest.raises(RuntimeError):
                analyze_game(
                    game_id=gid,
                    pgn_text="1. e4 e5 2. Nf3 *",
                    player_color="white",
                    stockfish_path="/fake/stockfish",
                    db_path=db,
                )

        # Engine was quit despite the exception.
        mock_engine.quit.assert_called_once()

        # The failed run left no partial move rows (closing the conn rolled
        # back the open write txn), so the caller's error UPDATE won't contend.
        conn = init_db(db)
        rows = conn.execute(
            "SELECT COUNT(*) FROM move_analysis WHERE game_id = ?", (gid,)
        ).fetchone()[0]
        conn.close()
        assert rows == 0


class TestAnalysisErrorRecovery:
    """v1.29.0 (F2): analysis_status='error' is no longer terminal — the batch
    retries it up to MAX_ANALYSIS_ATTEMPTS, then a manual reset re-arms it."""

    def _seed(self, db, rows):
        """rows: (analysis_status, analysis_attempts). Returns ids."""
        from src.models import init_db, ensure_player
        conn = init_db(db)
        pid = ensure_player(conn, "p", display_name="P", age=9, rating=1000)
        ids = []
        for i, (status, attempts) in enumerate(rows):
            cur = conn.execute(
                """INSERT INTO games
                (player_id, game_url, pgn, player_color, result, date_played,
                 analysis_status, analysis_attempts)
                VALUES (?, ?, '1. e4 e5 *', 'white', 'win', '2026-01-0%d',
                        ?, ?)""" % (i + 1),
                (pid, f"u{i}", status, attempts),
            )
            ids.append(cur.lastrowid)
        conn.commit()
        conn.close()
        return ids

    def test_error_under_cap_is_retried(self, tmp_path):
        from unittest.mock import patch
        from src.analyzer import analyze_pending
        db = str(tmp_path / "a.db")
        ids = self._seed(db, [("error", 1)])
        dummy = tmp_path / "sf"; dummy.write_text("")

        with patch("src.analyzer.analyze_game") as mock_ag:
            analyze_pending(str(dummy), db_path=db)
        assert mock_ag.call_count == 1
        assert mock_ag.call_args.kwargs["game_id"] == ids[0]

    def test_error_at_cap_is_left_alone(self, tmp_path):
        from unittest.mock import patch
        from src.analyzer import analyze_pending, MAX_ANALYSIS_ATTEMPTS
        db = str(tmp_path / "a.db")
        self._seed(db, [("error", MAX_ANALYSIS_ATTEMPTS)])
        dummy = tmp_path / "sf"; dummy.write_text("")

        with patch("src.analyzer.analyze_game") as mock_ag:
            analyze_pending(str(dummy), db_path=db)
        assert mock_ag.call_count == 0

    def test_pending_sorts_ahead_of_error_retries(self, tmp_path):
        from unittest.mock import patch
        from src.analyzer import analyze_pending
        db = str(tmp_path / "a.db")
        # error game seeded FIRST (lower id) so id-order alone would pick it
        # first; the status ordering must still put pending ahead.
        ids = self._seed(db, [("error", 1), ("pending", 0)])
        dummy = tmp_path / "sf"; dummy.write_text("")

        seen = []
        with patch("src.analyzer.analyze_game",
                   side_effect=lambda **kw: seen.append(kw["game_id"])):
            analyze_pending(str(dummy), db_path=db)
        assert seen == [ids[1], ids[0]]  # pending first, then the retry

    def test_failure_increments_attempts(self, tmp_path):
        from unittest.mock import patch
        from src.analyzer import analyze_pending
        from src.models import init_db
        db = str(tmp_path / "a.db")
        ids = self._seed(db, [("pending", 0)])
        dummy = tmp_path / "sf"; dummy.write_text("")

        with patch("src.analyzer.analyze_game", side_effect=RuntimeError("boom")):
            analyze_pending(str(dummy), db_path=db)

        conn = init_db(db)
        row = conn.execute(
            "SELECT analysis_status, analysis_attempts FROM games WHERE id = ?",
            (ids[0],),
        ).fetchone()
        conn.close()
        assert row["analysis_status"] == "error"
        assert row["analysis_attempts"] == 1
