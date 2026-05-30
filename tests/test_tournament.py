"""v1.21.0: tests for src/tournament.py — Tournament Prep.

Roster CRUD + the combined cross-opponent aggregation
(compute_tournament_prep). Pure — no network, no Stockfish; cached
profiles are seeded directly via hunter.set_cached_profile.
"""

import json
import itertools

import pytest

from src.models import init_db, ensure_player
from src.hunter import set_cached_profile
from src import tournament as T


@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "tourney.db")
    init_db(p).close()
    return p


@pytest.fixture
def player_id(db_path):
    conn = init_db(db_path)
    pid = ensure_player(conn, "evanleongxinyu", display_name="Evan",
                        slug="evanleong", age=9, rating=1100)
    conn.close()
    return pid


def _profile(weak=None, strong=None, results=None):
    return {
        "total_games": 20,
        "results": results or {"wins": 8, "losses": 10, "draws": 2,
                               "win_rate": 40.0},
        "weaknesses": weak or {"white": [], "black": []},
        "strengths": strong or {"white": [], "black": []},
    }


def _opening(name, eco, total, wins, losses):
    return {"name": name, "eco": eco, "total": total, "wins": wins,
            "losses": losses, "draws": total - wins - losses,
            "rate": round((losses if losses else wins) / total * 100, 1)}


class TestRosterCrud:
    def test_create_and_get(self, db_path, player_id):
        t = T.create_tournament(player_id, "Sat Rapid",
                                event_date="2026-06-01", db_path=db_path)
        assert t["name"] == "Sat Rapid"
        assert t["event_date"] == "2026-06-01"
        assert t["opponents"] == []
        got = T.get_tournament(t["id"], db_path=db_path)
        assert got["id"] == t["id"]

    def test_create_requires_name(self, db_path, player_id):
        with pytest.raises(ValueError, match="name"):
            T.create_tournament(player_id, "  ", db_path=db_path)

    def test_create_unknown_player(self, db_path):
        with pytest.raises(ValueError, match="not found"):
            T.create_tournament(99999, "X", db_path=db_path)

    def test_add_and_dedup_opponent(self, db_path, player_id):
        t = T.create_tournament(player_id, "T", db_path=db_path)
        o = T.add_opponent(t["id"], "Hikaru", db_path=db_path)
        assert o["username"] == "hikaru"  # lowercased
        assert o["platform"] == "chess.com"
        with pytest.raises(ValueError, match="already in"):
            T.add_opponent(t["id"], "hikaru", db_path=db_path)

    def test_add_requires_username(self, db_path, player_id):
        t = T.create_tournament(player_id, "T", db_path=db_path)
        with pytest.raises(ValueError, match="username"):
            T.add_opponent(t["id"], "  ", db_path=db_path)

    def test_remove_opponent(self, db_path, player_id):
        t = T.create_tournament(player_id, "T", db_path=db_path)
        o = T.add_opponent(t["id"], "a", db_path=db_path)
        T.remove_opponent(t["id"], o["id"], db_path=db_path)
        assert T.get_tournament(t["id"], db_path=db_path)["opponents"] == []

    def test_remove_unknown_opponent(self, db_path, player_id):
        t = T.create_tournament(player_id, "T", db_path=db_path)
        with pytest.raises(ValueError, match="not found"):
            T.remove_opponent(t["id"], 424242, db_path=db_path)

    def test_list_with_counts(self, db_path, player_id):
        t = T.create_tournament(player_id, "T", db_path=db_path)
        T.add_opponent(t["id"], "a", db_path=db_path)
        T.add_opponent(t["id"], "b", db_path=db_path)
        rows = T.list_tournaments(player_id, db_path=db_path)
        assert len(rows) == 1
        assert rows[0]["opponent_count"] == 2

    def test_update(self, db_path, player_id):
        t = T.create_tournament(player_id, "Old", db_path=db_path)
        T.update_tournament(t["id"], name="New", notes="bring water",
                            db_path=db_path)
        got = T.get_tournament(t["id"], db_path=db_path)
        assert got["name"] == "New"
        assert got["notes"] == "bring water"

    def test_delete_cascades_opponents(self, db_path, player_id):
        t = T.create_tournament(player_id, "T", db_path=db_path)
        T.add_opponent(t["id"], "a", db_path=db_path)
        T.delete_tournament(t["id"], db_path=db_path)
        assert T.list_tournaments(player_id, db_path=db_path) == []
        with pytest.raises(ValueError, match="not found"):
            T.get_tournament(t["id"], db_path=db_path)


class TestComputeTournamentPrep:
    def _seed(self, db_path, player_id):
        conn = init_db(db_path)
        # A & B lose to the Italian (White); A & C win with the Najdorf (Black).
        set_cached_profile(conn, "oppa", "chess.com", _profile(
            weak={"white": [_opening("Italian Game", "C50", 6, 1, 5)], "black": []},
            strong={"white": [], "black": [_opening("Sicilian Najdorf", "B90", 8, 6, 2)]},
        ))
        set_cached_profile(conn, "oppb", "chess.com", _profile(
            weak={"white": [_opening("Italian Game", "C50", 4, 1, 3)], "black": []},
        ))
        set_cached_profile(conn, "oppc", "chess.com", _profile(
            strong={"white": [], "black": [_opening("Sicilian Najdorf", "B90", 5, 4, 1)]},
        ))
        conn.close()
        t = T.create_tournament(player_id, "Champs", db_path=db_path)
        for u in ("oppa", "oppb", "oppc", "oppd"):  # oppd has no cached profile
            T.add_opponent(t["id"], u, db_path=db_path)
        return t["id"]

    def test_opening_targets_and_cautions(self, db_path, player_id):
        tid = self._seed(db_path, player_id)
        prep = T.compute_tournament_prep(tid, db_path=db_path)
        targets = prep["opening_targets"]
        assert len(targets) == 1
        assert targets[0]["opening"] == "Italian Game"
        assert targets[0]["color"] == "white"
        assert targets[0]["opponent_count"] == 2
        assert set(targets[0]["opponents"]) == {"oppa", "oppb"}
        cautions = prep["opening_cautions"]
        assert cautions[0]["opening"] == "Sicilian Najdorf"
        assert cautions[0]["opponent_count"] == 2

    def test_min_shared_threshold_excludes_singletons(self, db_path, player_id):
        tid = self._seed(db_path, player_id)
        # With min_shared=3, neither opening (shared by 2) should surface.
        prep = T.compute_tournament_prep(tid, db_path=db_path, min_shared=3)
        assert prep["opening_targets"] == []
        assert prep["opening_cautions"] == []

    def test_pending_opponents_marked(self, db_path, player_id):
        tid = self._seed(db_path, player_id)
        prep = T.compute_tournament_prep(tid, db_path=db_path)
        by_name = {o["username"]: o for o in prep["opponents"]}
        assert by_name["oppd"]["status"] == "pending"
        assert by_name["oppa"]["status"] == "ready"

    def test_scan_coverage_and_field_blind_spots(self, db_path, player_id):
        conn = init_db(db_path)
        set_cached_profile(conn, "oppa", "chess.com", _profile())
        set_cached_profile(conn, "oppb", "chess.com", _profile())
        ctr = itertools.count()

        def scan(u, fork_n):
            conn.execute(
                """INSERT INTO opponent_games
                (username, platform, game_url, pgn, player_color, result,
                 date_played, motifs_json, analyzed_at)
                VALUES (?, 'chess.com', ?, 'pgn', 'white', 'loss',
                        '2026-05-01', ?, datetime('now'))""",
                (u, f"g{next(ctr)}", json.dumps({
                    "found": {}, "missed": {"fork": fork_n},
                    "critical_moves": fork_n,
                    "missed_by_phase": {"fork": {"opening": 0,
                                                 "middlegame": fork_n,
                                                 "endgame": 0}},
                })),
            )
        scan("oppa", 3)
        scan("oppb", 2)
        conn.commit()
        conn.close()
        t = T.create_tournament(player_id, "T", db_path=db_path)
        T.add_opponent(t["id"], "oppa", db_path=db_path)
        T.add_opponent(t["id"], "oppb", db_path=db_path)
        prep = T.compute_tournament_prep(t["id"], db_path=db_path)
        assert prep["scan_coverage"] == {"scanned": 2, "total": 2}
        fbs = prep["field_blind_spots"]
        assert fbs["top_missed"] == "fork"
        assert fbs["top_missed_count"] == 5  # 3 + 2

    def test_unknown_tournament_raises(self, db_path):
        with pytest.raises(ValueError, match="not found"):
            T.compute_tournament_prep(99999, db_path=db_path)
