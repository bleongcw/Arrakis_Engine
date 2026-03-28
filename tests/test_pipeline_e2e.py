"""End-to-end pipeline test: Stockfish analysis → LLM coaching.

Requires BOTH Stockfish binary AND an LLM API key.
Run with: pytest -m "integration and live"
"""

import pytest

from src.analyzer import analyze_game
from src.coach import coach_game
from src.models import init_db, ensure_player
from tests.conftest import SCHOLARS_MATE_PGN


@pytest.mark.integration
@pytest.mark.live
class TestFullPipeline:
    def test_analyze_then_coach(self, stockfish_path, llm_provider, db_path, player_id):
        """Full pipeline: insert game → Stockfish analysis → LLM coaching."""
        # 1. Insert a game
        conn = init_db(db_path)
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, player_rating,
             opponent_rating, result, time_control, time_class, date_played,
             analysis_status, coaching_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (player_id, "https://chess.com/game/e2e-1",
             SCHOLARS_MATE_PGN, "white", 1050, 980, "win",
             "600", "rapid", "2026-03-01", "pending", "pending"),
        )
        conn.commit()
        game_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

        # 2. Analyze with real Stockfish
        analysis = analyze_game(
            game_id, SCHOLARS_MATE_PGN, "white",
            stockfish_path, depth=12, move_time_limit=5.0, db_path=db_path,
        )
        assert analysis["moves"] > 0

        # Verify analysis results
        conn = init_db(db_path)
        game = conn.execute(
            "SELECT analysis_status, acpl FROM games WHERE id = ?",
            (game_id,),
        ).fetchone()
        moves = conn.execute(
            "SELECT COUNT(*) as cnt FROM move_analysis WHERE game_id = ?",
            (game_id,),
        ).fetchone()
        conn.close()

        assert game["analysis_status"] == "complete"
        assert game["acpl"] is not None
        assert moves["cnt"] == 7  # Scholar's Mate = 7 half-moves

        # 3. Coach with real LLM
        provider, model = llm_provider
        coaching = coach_game(
            game_id, provider=provider, model=model, db_path=db_path,
        )

        # Verify coaching results
        assert isinstance(coaching, dict)
        assert "narrative" in coaching
        assert "key_lesson" in coaching
        assert len(coaching["narrative"]) > 0

        conn = init_db(db_path)
        game = conn.execute(
            "SELECT coaching_status FROM games WHERE id = ?",
            (game_id,),
        ).fetchone()
        coaching_row = conn.execute(
            "SELECT * FROM game_coaching WHERE game_id = ?",
            (game_id,),
        ).fetchone()
        conn.close()

        assert game["coaching_status"] == "complete"
        assert coaching_row is not None
        assert coaching_row["provider"].startswith(f"{provider}:")
