"""Shared pytest fixtures for ArrakisEngine test suite."""

import os
import shutil
from datetime import datetime, timedelta

import pytest
import yaml

from src.models import init_db, ensure_player


SAMPLE_PGN = '[White "testplayer"]\n[Black "opponent"]\n\n1. e4 e5 2. Nf3 Nc6 *'

# Scholar's Mate — short, deterministic, white wins with a blunder by black
SCHOLARS_MATE_PGN = (
    '[Event "Test"]\n[White "testplayer"]\n[Black "opponent"]\n'
    '[Result "1-0"]\n\n1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0'
)


# ---------------------------------------------------------------------------
# Integration / Live test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def stockfish_path():
    """Resolve Stockfish binary path. Skips if not found.

    Resolution order: config.yaml → STOCKFISH_PATH env → which stockfish
    """
    # Try config.yaml
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        sf_path = cfg.get("stockfish", {}).get("path")
        if sf_path and os.path.isfile(sf_path):
            return sf_path

    # Try env var
    sf_path = os.getenv("STOCKFISH_PATH")
    if sf_path and os.path.isfile(sf_path):
        return sf_path

    # Try PATH
    sf_path = shutil.which("stockfish")
    if sf_path:
        return sf_path

    pytest.skip("Stockfish binary not found (set STOCKFISH_PATH or install stockfish)")


@pytest.fixture
def llm_provider():
    """Return (provider, model) for whichever LLM API key is available.

    Prefers Claude, falls back to OpenAI. Skips if neither is set.
    """
    if os.getenv("ARRAKIS_ANTHROPIC_API_KEY"):
        return ("claude", None)
    if os.getenv("ARRAKIS_OPENAI_API_KEY"):
        return ("openai", None)
    pytest.skip("No LLM API key configured (set ARRAKIS_ANTHROPIC_API_KEY or ARRAKIS_OPENAI_API_KEY)")


@pytest.fixture
def db_path(tmp_path):
    """Create a fresh test database and return its path."""
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def player_id(db_path):
    """Create a test player and return the player id."""
    conn = init_db(db_path)
    pid = ensure_player(conn, "testplayer", display_name="TestKid", age=9, rating=1050)
    conn.close()
    return pid


@pytest.fixture
def insert_game(db_path):
    """Callable fixture: insert a game row and return game_id.

    Usage:
        game_id = insert_game(player_id, result="win", ...)
    """
    _counter = [0]

    def _insert(player_id, *, game_url=None, pgn=None, player_color="white",
                player_rating=1050, opponent_rating=980, result="win",
                time_control="600", time_class="rapid", date_played=None,
                analysis_status="complete", coaching_status="pending"):
        _counter[0] += 1
        if game_url is None:
            game_url = f"https://chess.com/game/{_counter[0]}"
        if pgn is None:
            pgn = SAMPLE_PGN
        if date_played is None:
            date_played = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

        conn = init_db(db_path)
        conn.execute(
            """INSERT INTO games
            (player_id, game_url, pgn, player_color, player_rating,
             opponent_rating, result, time_control, time_class, date_played,
             analysis_status, coaching_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (player_id, game_url, pgn, player_color, player_rating,
             opponent_rating, result, time_control, time_class, date_played,
             analysis_status, coaching_status),
        )
        conn.commit()
        game_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return game_id

    return _insert


@pytest.fixture
def insert_moves(db_path):
    """Callable fixture: insert move_analysis rows for a game.

    Usage:
        insert_moves(game_id, moves_data)
    where moves_data is a list of dicts with keys:
        move_number, side, move_played, best_move, eval_before_cp,
        eval_after_cp, swing_cp, win_prob_before, win_prob_after, classification
    """
    def _insert(game_id, moves):
        conn = init_db(db_path)
        for m in moves:
            conn.execute(
                """INSERT INTO move_analysis
                (game_id, move_number, side, move_played, best_move,
                 eval_before_cp, eval_after_cp, swing_cp,
                 win_prob_before, win_prob_after, classification)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (game_id, m["move_number"], m["side"], m["move_played"],
                 m.get("best_move", m["move_played"]),
                 m.get("eval_before_cp", 0), m.get("eval_after_cp", 0),
                 m.get("swing_cp", 0),
                 m.get("win_prob_before", 50.0), m.get("win_prob_after", 50.0),
                 m.get("classification", "excellent")),
            )
        conn.commit()
        conn.close()

    return _insert
