"""Live tests for LLM coaching APIs.

These tests require a real API key (Anthropic or OpenAI) and are excluded by default.
Run with: pytest -m live
"""

import os
import json

import pytest

from src.coach import coach_game
from src.models import init_db, ensure_player


pytestmark = pytest.mark.live


@pytest.fixture
def analyzed_game(db_path, player_id):
    """Create a game with pre-populated move_analysis (no Stockfish needed).

    Simulates Scholar's Mate analysis results with realistic eval values.
    """
    conn = init_db(db_path)
    conn.execute(
        """INSERT INTO games
        (player_id, game_url, pgn, player_color, player_rating,
         opponent_rating, result, time_control, time_class, date_played,
         analysis_status, coaching_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (player_id, "https://chess.com/game/live-coach-1",
         '[Event "Test"]\n[White "testplayer"]\n[Black "opponent"]\n'
         '[Result "1-0"]\n\n1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0',
         "white", 1050, 980, "win", "600", "rapid", "2026-03-01",
         "complete", "pending"),
    )
    game_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Hand-crafted move analysis matching Scholar's Mate
    moves = [
        (game_id, 1, "white", "e4", "e4", 0, 20, 0, 50.0, 51.8, "excellent"),
        (game_id, 1, "black", "e5", "e5", 20, 15, 5, 51.8, 51.4, "excellent"),
        (game_id, 2, "white", "Bc4", "Bc4", 15, 40, 0, 51.4, 53.5, "excellent"),
        (game_id, 2, "black", "Nc6", "d5", 40, 80, 40, 53.5, 48.2, "good"),
        (game_id, 3, "white", "Qh5", "Qh5", 80, 200, 0, 58.0, 66.0, "excellent"),
        (game_id, 3, "black", "Nf6", "g6", 200, 900, 700, 66.0, 15.0, "blunder"),
        (game_id, 4, "white", "Qxf7#", "Qxf7#", 900, 1000, 0, 95.0, 100.0, "excellent"),
    ]
    for m in moves:
        conn.execute(
            """INSERT INTO move_analysis
            (game_id, move_number, side, move_played, best_move,
             eval_before_cp, eval_after_cp, swing_cp,
             win_prob_before, win_prob_after, classification)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            m,
        )
    conn.commit()
    conn.close()
    return game_id


class TestCoachGameLive:
    def test_returns_valid_dict(self, llm_provider, db_path, analyzed_game):
        """Live LLM call should return a parsed dict without exceptions."""
        provider, model = llm_provider
        result = coach_game(
            analyzed_game, provider=provider, model=model, db_path=db_path,
        )
        assert isinstance(result, dict)

    def test_has_required_keys(self, llm_provider, db_path, analyzed_game):
        """Coaching response must contain all 7 expected keys."""
        provider, model = llm_provider
        result = coach_game(
            analyzed_game, provider=provider, model=model, db_path=db_path,
        )
        required = [
            "narrative", "key_lesson", "practical_focus",
            "critical_moments", "coach_notes",
        ]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_stores_in_db(self, llm_provider, db_path, analyzed_game):
        """Coaching should be stored in game_coaching table."""
        provider, model = llm_provider
        coach_game(
            analyzed_game, provider=provider, model=model, db_path=db_path,
        )

        conn = init_db(db_path)
        coaching = conn.execute(
            "SELECT * FROM game_coaching WHERE game_id = ?",
            (analyzed_game,),
        ).fetchone()
        game = conn.execute(
            "SELECT coaching_status FROM games WHERE id = ?",
            (analyzed_game,),
        ).fetchone()
        conn.close()

        assert coaching is not None
        assert coaching["narrative"] is not None
        assert len(coaching["narrative"]) > 0
        assert coaching["provider"].startswith(f"{provider}:")
        assert game["coaching_status"] == "complete"


class TestCoachGameLiveEdgeCases:
    def test_missing_api_key_raises(self, db_path, analyzed_game):
        """Should raise ValueError when API key is not set."""
        # Temporarily clear keys
        orig_claude = os.environ.pop("ARRAKIS_ANTHROPIC_API_KEY", None)
        orig_openai = os.environ.pop("ARRAKIS_OPENAI_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="not set"):
                coach_game(analyzed_game, provider="claude", db_path=db_path)
        finally:
            # Restore keys
            if orig_claude:
                os.environ["ARRAKIS_ANTHROPIC_API_KEY"] = orig_claude
            if orig_openai:
                os.environ["ARRAKIS_OPENAI_API_KEY"] = orig_openai

    def test_unknown_provider_raises(self, db_path, analyzed_game):
        """Unknown provider should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            coach_game(analyzed_game, provider="gemini", db_path=db_path)


# ─── v1.13.2: live format-compliance tests per reasoning model ───
#
# These call the actual LLM API and assert that the response contains all 5
# v1.13.0 markdown section headings. Catches format-spec drift at the
# model level — the v1.13.1 incident (gpt-5.4 silently ignoring the spec
# while the frontend's legacy fallback masked it) wouldn't have shipped
# if these had been run.
#
# Cost per run: ~$0.10-0.30 per model. Run with: pytest -m live -k Compliance


class TestStructuredFeedbackCompliance:
    """Per-model real-API tests for v1.13.0 player_feedback structure."""

    REQUIRED_HEADINGS = [
        "## ♟ Opening",
        "## ⚔ Middlegame",
        "## ♔ Endgame",
        "## 🪤 Watch Out For",
        "## 🎯 Top 3 Improvements",
    ]

    def _assert_compliant(self, result: dict, provider: str, model: str):
        """Shared assertion: all 5 required headings must appear in the
        player_feedback string and the validator's compliance flag must
        agree."""
        feedback = result.get("player_feedback") or ""
        missing = [h for h in self.REQUIRED_HEADINGS if h not in feedback]
        assert not missing, (
            f"{provider}:{model} produced non-compliant player_feedback. "
            f"Missing headings: {missing}\n\n"
            f"Actual feedback (first 800 chars):\n{feedback[:800]}"
        )
        # The validator (called inside coach_game) should agree
        meta = result.get("meta") or {}
        assert meta.get("feedback_structure_compliant") is True, (
            f"validator disagrees with raw heading check for {provider}:{model}"
        )
        assert meta.get("feedback_missing_headings") == []

    def test_claude_opus_4_7_compliance(self, db_path, analyzed_game):
        """Claude opus-4-7 should produce all 5 sections reliably."""
        if not os.getenv("ARRAKIS_ANTHROPIC_API_KEY"):
            pytest.skip("ARRAKIS_ANTHROPIC_API_KEY not set")
        model = "claude-opus-4-7"
        result = coach_game(
            analyzed_game, provider="claude", model=model, db_path=db_path,
        )
        self._assert_compliant(result, "claude", model)

    def test_gpt_5_5_pro_compliance(self, db_path, analyzed_game):
        """GPT-5.5-pro should produce all 5 sections reliably.

        This is the test that would have caught the v1.13.1 incident
        (gpt-5.4 silently degrading the output). With this test in place,
        any future regression to a non-compliant model would fail loudly."""
        if not os.getenv("ARRAKIS_OPENAI_API_KEY"):
            pytest.skip("ARRAKIS_OPENAI_API_KEY not set")
        model = "gpt-5.5-pro-2026-04-23"
        result = coach_game(
            analyzed_game, provider="openai", model=model, db_path=db_path,
        )
        self._assert_compliant(result, "openai", model)
