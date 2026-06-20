# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Tests for src/pgn_io.py — PGN import (parse + ingest) and export."""

import pytest

from src.models import init_db, get_connection
from src.pgn_io import (
    PgnParseError,
    parse_pgn,
    ingest_game,
    build_pgn,
    build_bulk_pgn,
)

SCHOLARS_MATE = """[Event "Casual"]
[Site "https://example.org/abc123"]
[Date "2026.05.01"]
[White "alice"]
[Black "bob"]
[Result "1-0"]
[WhiteElo "1450"]
[BlackElo "1400"]
[TimeControl "600+5"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0
"""

# Real OTB scoresheet: undecided "*", only WhiteElo, non-ASCII opponent.
SMU_ONGOING = """[Event "SMU (Section 58)"]
[Site "Singapore"]
[Date "2026.05.30"]
[White "Evan Leong"]
[Black "许诺"]
[Result "*"]
[WhiteElo "1518"]
[TimeControl "900+10"]

1. e4 e5 2. Nf3 Nc6 3. d4 exd4 4. Nxd4 Bc5 5. Be3 Qf6 6. c3 Nge7
7. Bb5 Bxd4 8. cxd4 Qg6 9. Qf3 a6 10. Bxc6 dxc6 *
"""


# ---------- parse ----------

def test_parse_basic_fields():
    g = parse_pgn(SCHOLARS_MATE, player_color="white")
    assert g.result == "win"
    assert g.game_url == "https://example.org/abc123"
    assert g.player_rating == 1450 and g.opponent_rating == 1400
    assert g.time_class == "rapid"
    assert g.move_count == 7


def test_color_inferred_from_usernames():
    g = parse_pgn(SCHOLARS_MATE, known_usernames=["BOB"])
    assert g.player_color == "black" and g.result == "loss"


def test_synthesized_url_stable():
    a = parse_pgn(SMU_ONGOING, player_color="white", result="loss")
    b = parse_pgn(SMU_ONGOING, player_color="white", result="loss")
    assert a.game_url.startswith("imported:") and a.game_url == b.game_url


def test_empty_and_illegal_rejected():
    with pytest.raises(PgnParseError):
        parse_pgn("   ")
    with pytest.raises(PgnParseError):
        parse_pgn('[White "x"]\n[Black "y"]\n[Result "1-0"]\n\n1. e4 e5 2. Ke3 1-0\n',
                  player_color="white")


def test_undecided_requires_result_override():
    with pytest.raises(PgnParseError, match="no decided result"):
        parse_pgn(SMU_ONGOING, player_color="white")
    g = parse_pgn(SMU_ONGOING, player_color="white", result="loss")
    assert g.result == "loss"
    assert g.opponent_username == "许诺"
    assert g.opponent_rating is None


def test_invalid_result_override():
    with pytest.raises(PgnParseError, match="Invalid result override"):
        parse_pgn(SMU_ONGOING, player_color="white", result="1-0")


# ---------- ingest ----------

@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "t.db")
    init_db(path)
    conn = get_connection(path)
    conn.execute("INSERT INTO players (slug, username, display_name) "
                 "VALUES ('alice','alice','Alice')")
    conn.commit()
    conn.close()
    return path


def test_ingest_pending_and_dedup(db):
    conn = get_connection(db)
    pid = conn.execute("SELECT id FROM players WHERE slug='alice'").fetchone()["id"]
    g = parse_pgn(SCHOLARS_MATE, player_color="white")
    first = ingest_game(conn, pid, g)
    second = ingest_game(conn, pid, g)
    conn.commit()
    assert first.created is True and second.created is False
    assert first.game_id == second.game_id
    row = conn.execute("SELECT analysis_status, result, platform FROM games WHERE id=?",
                       (first.game_id,)).fetchone()
    assert row["analysis_status"] == "pending"
    assert row["result"] == "win" and row["platform"] == "import"
    conn.close()


# ---------- export ----------

def test_build_pgn_raw_passthrough():
    game_row = {"pgn": SCHOLARS_MATE}
    out = build_pgn(game_row, annotated=False)
    assert "1. e4 e5" in out
    assert out.endswith("\n")


def test_build_pgn_annotated_adds_eval_and_nag():
    game_row = {"pgn": SCHOLARS_MATE}
    moves = [
        {"move_number": 1, "side": "white", "eval_after_cp": 30, "classification": "good"},
        {"move_number": 2, "side": "black", "eval_after_cp": -260, "classification": "blunder"},
    ]
    out = build_pgn(game_row, moves, annotated=True)
    assert "%eval 0.30" in out          # white move 1 eval comment
    assert "%eval -2.60" in out         # black move 2 eval comment
    assert "$4" in out                  # blunder NAG on the black move


def test_build_pgn_annotated_falls_back_without_moves():
    game_row = {"pgn": SCHOLARS_MATE}
    assert build_pgn(game_row, None, annotated=True).strip() == SCHOLARS_MATE.strip()


def test_build_bulk_pgn_joins_games():
    bulk = build_bulk_pgn(["[Event \"A\"]\n\n1. e4 *", "[Event \"B\"]\n\n1. d4 *"])
    assert bulk.count("[Event") == 2
    assert "\n\n" in bulk


def test_build_bulk_pgn_empty():
    assert build_bulk_pgn([]) == ""
