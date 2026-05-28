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


# ─── v1.15.3: trend summary motif-citation compliance ───────────────────


@pytest.fixture
def trend_stats_db(db_path):
    """v1.15.3 compliance fixture — a player_patterns row whose
    motif_summary makes the top-missed motif (hanging_piece) cross
    the ≥5-instance gate that v1.15.0's prompt uses to force the LLM
    to cite the motif by name.

    Returns (player_id, db_path). The player is named 'Evan' so the
    compliance assertion can check for first-name personalization.
    """
    from src.patterns import generate_trend_summary  # noqa: F401 (import sanity)

    conn = init_db(db_path)
    pid = ensure_player(conn, "evan", display_name="Evan", age=9, rating=1100)

    stats = {
        "total_games": 50,
        "results": {"wins": 28, "losses": 20, "draws": 2, "win_rate": 56.0},
        "phase_analysis": {
            "opening": {"acpl": 45.1, "moves": 600},
            "middlegame": {"acpl": 68.1, "moves": 400},
            "endgame": {"acpl": 48.0, "moves": 300},
        },
        "consistency": {
            "mean_acpl": 54.5, "best_acpl": 5.0, "worst_acpl": 220.0,
            "total_games": 50, "rating": "Stable",
        },
        "move_quality": {
            "excellent": {"pct": 60.0}, "good": {"pct": 12.6},
            "inaccuracy": {"pct": 10.5}, "mistake": {"pct": 10.5},
            "blunder": {"pct": 6.4},
        },
        "accuracy": {"overall_pct": 72.5},
        "endgame_conversion": {"winning_endgames": {"conversion_rate": 81.1}},
        "tactical_misses": {"miss_rate": 48.3},
        "comeback_collapse": {
            "comebacks": {"comeback_rate": 30.0},
            "collapses": {"collapse_rate": 25.0},
        },
        "repertoire_consistency": {"white": {"rating": "Focused"}},
        "acpl_trend": [
            {"week": "2026-04-15", "acpl": 60, "games": 5},
            {"week": "2026-04-22", "acpl": 55, "games": 5},
        ],
        # The compliance signal: hanging_piece is far over the 5-instance
        # gate, so the prompt instructs the LLM to make ONE of its 3
        # practice recommendations specifically about this motif.
        "motif_summary": {
            "period_days": 30,
            "total_critical_moves": 15,
            "top_missed": "hanging_piece", "top_missed_count": 13,
            "by_motif": [
                {"motif": "hanging_piece", "missed": 13, "found": 2, "miss_rate": 86.7},
                {"motif": "pin", "missed": 2, "found": 1, "miss_rate": 66.7},
            ],
        },
    }
    conn.execute(
        """INSERT INTO player_patterns
        (player_id, period_start, period_end, stats_json, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))""",
        (pid, "2026-04-15", "2026-05-15", json.dumps(stats)),
    )
    conn.commit()
    conn.close()
    return (pid, db_path)


class TestTrendSummaryCompliance:
    """v1.15.3: per-model real-API tests for trend summary output style.

    Catches the regression class Bernard worried about — "the LLM
    silently stopped citing the motif by name". The fixture pins a
    motif_summary with top_missed='hanging_piece' at 13 instances
    (well over the ≥5 prompt gate); compliant models MUST mention
    the motif in the generated text.

    Each test costs ~$0.02-0.05 against a real provider. Run via:
        pytest tests/test_coach_live.py -m live -k TrendSummaryCompliance
    """

    # Accept any of these natural-language variants for hanging_piece.
    # Mirrors the motif-id → English mapping documented in src/coach.py's
    # player_feedback section requirements (v1.14.0+).
    MOTIF_VARIANTS = (
        "hanging piece",      # most common
        "hanging pieces",
        "free piece",         # alternate phrasing from coach.py mapping
        "undefended piece",
    )

    # The LLM must NOT start with these — the prompt says
    # "Respond with ONLY the text paragraphs, no JSON, no headers,
    # no markdown formatting."
    FORBIDDEN_PREAMBLE_PREFIXES = (
        "{", "[",            # JSON shapes
        "## ", "# ",         # markdown headings
        "```",               # fenced code blocks
        "Sure,", "Sure!", "Sure ",
        "Certainly,", "Certainly!", "Certainly ",
        "Here's", "Here is",
    )

    def _assert_compliant(self, summary: str, provider: str, model: str):
        """Shared style-check assertion for trend summary output."""
        assert summary, f"{provider}:{model} returned an empty summary"

        # 1. Length proxy for "≥4 paragraphs of real prose"
        assert len(summary) > 600, (
            f"{provider}:{model} returned a suspiciously short summary "
            f"({len(summary)} chars); prompt asks for 3-4 paragraphs.\n"
            f"First 300 chars: {summary[:300]!r}"
        )

        # 2. Player name personalization
        assert "Evan" in summary, (
            f"{provider}:{model} did not address Evan by name — prompt says "
            f"'Address {{name}} by name. Use \"you\" throughout.'\n"
            f"First 300 chars: {summary[:300]!r}"
        )

        # 3. Motif citation (THE regression lock)
        lower = summary.lower()
        if not any(v in lower for v in self.MOTIF_VARIANTS):
            pytest.fail(
                f"{provider}:{model} did NOT cite the top-missed motif "
                f"(hanging_piece, 13 instances) by name. The v1.15.0 "
                f"prompt instructs the LLM to make ONE of its 3 practice "
                f"recommendations specifically about that motif when the "
                f"count is >=5. Accepted variants: {self.MOTIF_VARIANTS!r}.\n\n"
                f"Full summary:\n{summary}"
            )

        # 4. Explicit count reference (the prompt provides "13"; the LLM
        # should echo it). Soft-check — some models paraphrase ("many",
        # "over a dozen"); we accept "13" OR the existence of any 2-digit
        # number in the text as a proxy for grounding.
        import re
        has_thirteen = "13" in summary
        has_double_digit = bool(re.search(r"\b\d{2}\b", summary))
        assert has_thirteen or has_double_digit, (
            f"{provider}:{model} did not reference any numeric count for "
            f"the motif (prompt provides '13 instances'). Likely a "
            f"grounding failure.\n\nSummary:\n{summary[:600]}"
        )

        # 5. No JSON / markdown / preamble leakage
        stripped = summary.lstrip()
        for bad in self.FORBIDDEN_PREAMBLE_PREFIXES:
            assert not stripped.startswith(bad), (
                f"{provider}:{model} summary starts with forbidden preamble "
                f"{bad!r} — prompt says 'ONLY the text paragraphs, no JSON, "
                f"no headers, no markdown formatting.'\n"
                f"First 300 chars: {summary[:300]!r}"
            )

    def test_claude_opus_4_7_cites_top_motif(self, trend_stats_db):
        """Claude opus-4-7 must cite hanging_piece by name in the
        generated trend summary."""
        if not os.getenv("ARRAKIS_ANTHROPIC_API_KEY"):
            pytest.skip("ARRAKIS_ANTHROPIC_API_KEY not set")
        from src.patterns import generate_trend_summary

        pid, db_path = trend_stats_db
        model = "claude-opus-4-7"
        summary = generate_trend_summary(
            pid, db_path=db_path, provider="claude", model=model,
        )
        self._assert_compliant(summary, "claude", model)

    def test_gpt_5_5_pro_cites_top_motif(self, trend_stats_db):
        """GPT-5.5-pro must cite hanging_piece by name. This is the
        test that would have caught the v1.13.1-shape regression on
        the trend summary surface."""
        if not os.getenv("ARRAKIS_OPENAI_API_KEY"):
            pytest.skip("ARRAKIS_OPENAI_API_KEY not set")
        from src.patterns import generate_trend_summary

        pid, db_path = trend_stats_db
        model = "gpt-5.5-pro-2026-04-23"
        summary = generate_trend_summary(
            pid, db_path=db_path, provider="openai", model=model,
        )
        self._assert_compliant(summary, "openai", model)

    def test_zero_motif_data_does_not_crash_live(self, db_path):
        """When motif_summary.total_critical_moves == 0, the prompt
        emits a 'No motif data yet' placeholder and instructs the LLM
        to skip motif-specific recommendations. The LLM must still
        return a usable summary without erroring or going off-format."""
        if not os.getenv("ARRAKIS_OPENAI_API_KEY"):
            pytest.skip("ARRAKIS_OPENAI_API_KEY not set")
        from src.patterns import generate_trend_summary

        conn = init_db(db_path)
        pid = ensure_player(
            conn, "evan", display_name="Evan", age=9, rating=1100,
        )
        stats = {
            "total_games": 5,
            "results": {"wins": 3, "losses": 2, "draws": 0, "win_rate": 60.0},
            "phase_analysis": {
                "opening": {"acpl": 50, "moves": 60},
                "middlegame": {"acpl": 70, "moves": 40},
                "endgame": {"acpl": 55, "moves": 30},
            },
            "consistency": {
                "mean_acpl": 58, "best_acpl": 20, "worst_acpl": 180,
                "total_games": 5, "rating": "Building",
            },
            "move_quality": {
                "excellent": {"pct": 55.0}, "good": {"pct": 15.0},
                "inaccuracy": {"pct": 12.0}, "mistake": {"pct": 12.0},
                "blunder": {"pct": 6.0},
            },
            "accuracy": {"overall_pct": 70.0},
            "endgame_conversion": {"winning_endgames": {"conversion_rate": 75.0}},
            "tactical_misses": {"miss_rate": 50.0},
            "comeback_collapse": {
                "comebacks": {"comeback_rate": 25.0},
                "collapses": {"collapse_rate": 30.0},
            },
            "repertoire_consistency": {"white": {"rating": "Scattered"}},
            "acpl_trend": [],
            "motif_summary": {
                "period_days": 30, "total_critical_moves": 0,
                "top_missed": None, "top_missed_count": 0, "by_motif": [],
            },
        }
        conn.execute(
            """INSERT INTO player_patterns
            (player_id, period_start, period_end, stats_json, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))""",
            (pid, "2026-04-15", "2026-05-15", json.dumps(stats)),
        )
        conn.commit()
        conn.close()

        summary = generate_trend_summary(
            pid, db_path=db_path,
            provider="openai", model="gpt-5.5-pro-2026-04-23",
        )
        assert summary
        assert len(summary) > 400, (
            "even without motif data the LLM should produce a "
            "multi-paragraph summary"
        )
        # Case-insensitive — some models lowercase the first letter
        assert "evan" in summary.lower(), (
            "summary should address the player by name"
        )
        # The real "LLM invented a motif citation" regression we want
        # to catch is a SPECIFIC instance-count claim when no data
        # supports it. Casually mentioning "watch out for hanging
        # pieces" as a generic kid-coaching tip is fine — that's
        # reasonable inference from the other stats (blunder %, etc.).
        # The bad version is "you missed hanging pieces 13 times" with
        # an invented count.
        import re
        bad_count_patterns = [
            r"missed (?:it|hanging\s+pieces?|forks?|pins?|skewers?)\s+\d+\s+times",
            r"\d+\s+missed\s+(?:hanging|forks?|pins?|skewers?)",
            r"top[-\s]missed\s+(?:hanging|forks?|pins?|skewers?).*?\d+",
            r"\d+\s+instances?\s+of",
        ]
        for pat in bad_count_patterns:
            m = re.search(pat, summary, re.IGNORECASE)
            assert m is None, (
                f"LLM invented a specific motif instance count when "
                f"motif_summary was empty — matched pattern {pat!r} on "
                f"text {m.group(0)!r}. The prompt says 'If no theme has "
                f"reached 5 instances, ignore this rule.'\n\nFull summary:\n"
                f"{summary}"
            )
