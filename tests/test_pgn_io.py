# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Tests for src/pgn_io.py — PGN import (parse + ingest) and export."""

import pytest

from src.models import init_db, get_connection
from src.pgn_io import (
    PgnParseError,
    parse_pgn,
    parse_pgn_multi,
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


# ---------- competition / over-the-board (v1.25.0) ----------

# The user's real OTB game: no TimeControl, no Elo, real names, decided result.
OTB_COMPETITION = """[Event "Checkmate365 Classical"]
[Site "ARC 380, Level 14-06, Singapore"]
[Date "2026.07.12"]
[Round "1"]
[Board "6"]
[White "Evan Leong"]
[Black "Connery Tan"]
[Result "0-1"]

1. e4 c5 2. Nf3 d6 3. g3 Nc6 4. Bg2 Nf6 5. d3 g6 6. O-O Bg7
7. Be3 O-O 8. Qd2 Re8 9. Nc3 Bd7 10. Rfe1 Qa5 11. a3 Rac8
12. Bh6 Nd4 13. Bxg7 Nxf3+ 14. Bxf3 Kxg7 15. e5 Ng4 16. Bxb7 Rb8
17. Bg2 Nxe5 18. f4 Nc6 19. Rab1 e6 20. Ne4 Qxd2 21. Nxd2 Nd4
22. c3 Nb3 23. Nc4 d5 24. Ne5 Ba4 25. c4 d4 26. Nc6 Bxc6
27. Bxc6 Rec8 28. Bd7 Rc7 29. Ba4 Nd2 30. Red1 Nxb1 31. Rxb1 Kf6
32. g4 e5 33. fxe5+ Kxe5 34. Re1+ Kf4 35. Re4+ Kg5 36. b3 f5
37. gxf5 Kxf5 38. Kf2 Rf8 39. Kg3 Kg5 40. Rg4+ Kh6 41. h4 Rf1
42. Kg2 Ra1 43. Kf3 Rxa3 44. Ke2 Re7+ 45. Kd2 Ra2+ 46. Kd1 Rae2
47. Rg1 Ra2 48. Rg4 Ra1+ 49. Kd2 Ree1 50. Rg5 Rh1 {White resigned.} 0-1
"""


def test_time_class_override_wins_over_derived():
    # SCHOLARS_MATE has TimeControl 600+5 (→ 'rapid'); the override wins.
    g = parse_pgn(SCHOLARS_MATE, player_color="white", time_class_override="classical")
    assert g.time_class == "classical"


def test_parse_multi_otb_color_by_display_name():
    games, skipped = parse_pgn_multi(
        OTB_COMPETITION,
        known_usernames=["evanleongxinyu", "Evan Leong"],
        time_class_override="classical",
    )
    assert skipped == []
    assert len(games) == 1
    g = games[0]
    assert g.player_color == "white"          # matched "Evan Leong" (White)
    assert g.result == "loss"                 # 0-1 as White
    assert g.opponent_username == "Connery Tan"
    assert g.time_class == "classical"        # forced; PGN has no TimeControl
    assert g.game_url.startswith("imported:")


def test_parse_multi_splits_and_skips_undecided():
    ongoing = (
        '[White "Evan Leong"]\n[Black "Z"]\n[Result "*"]\n\n1. d4 d5 *\n'
    )
    two = OTB_COMPETITION + "\n\n" + ongoing
    games, skipped = parse_pgn_multi(
        two, known_usernames=["Evan Leong"], time_class_override="blitz"
    )
    assert len(games) == 1                     # the decided game
    assert games[0].time_class == "blitz"
    assert len(skipped) == 1                    # the undecided "*" game
    assert "no decided result" in skipped[0]


def test_parse_multi_empty_rejected():
    with pytest.raises(PgnParseError):
        parse_pgn_multi("   ")


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
