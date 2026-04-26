"""Tests for v1.4.0 trap library + trap matching.

Covers _load_trap_library, _match_trap, _extract_san_moves,
_compute_trap_falls, _compute_your_arsenal.
"""
import pytest

from src.patterns import (
    _extract_san_moves,
    _frequency_label,
    _load_trap_library,
    _match_trap,
    _compute_trap_falls,
    _compute_your_arsenal,
)


# Hand-built tiny library for unit tests, independent of the vendored file.
TINY_LIB = [
    {
        "eco": "C42",
        "name": "Petrov's Defense: Stafford Gambit",
        "moves": ["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nc6"],
        "depth": 6,
    },
    {
        "eco": "C57",
        "name": "Italian Game: Two Knights Defense, Fried Liver Attack",
        "moves": [
            "e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6",
            "Ng5", "d5", "exd5", "Nxd5", "Nxf7",
        ],
        "depth": 11,
    },
    {
        "eco": "C40",
        "name": "Elephant Gambit",
        "moves": ["e4", "e5", "Nf3", "d5"],
        "depth": 4,
    },
]
# Library should be sorted deepest-first for proper longest-prefix matching.
TINY_LIB_SORTED = sorted(TINY_LIB, key=lambda e: -e["depth"])


class TestLoadTrapLibrary:
    def test_vendored_library_loads(self):
        """The committed traps.json should contain at least the famous beginner traps."""
        lib = _load_trap_library()
        assert isinstance(lib, list)
        assert len(lib) > 0, "Trap library is empty — did you run scripts/build_traps.py?"
        names = [e["name"] for e in lib]
        joined = " | ".join(names)
        # Spot-check coverage of the named traps from the v1.4.0 plan
        assert "Stafford Gambit" in joined
        assert "Fried Liver" in joined
        assert "Elephant Gambit" in joined
        assert "Englund Gambit" in joined
        assert "Halloween Gambit" in joined
        assert "Wayward Queen Attack" in joined

    def test_library_entries_have_required_fields(self):
        lib = _load_trap_library()
        for e in lib[:5]:
            assert "eco" in e
            assert "name" in e
            assert "moves" in e
            assert isinstance(e["moves"], list)
            assert "depth" in e
            assert e["depth"] == len(e["moves"])


class TestMatchTrap:
    def test_no_moves_returns_none(self):
        assert _match_trap([], TINY_LIB_SORTED) is None

    def test_no_library_returns_none(self):
        assert _match_trap(["e4", "e5"], []) is None

    def test_exact_stafford_match(self):
        moves = ["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nc6"]
        m = _match_trap(moves, TINY_LIB_SORTED)
        assert m is not None
        assert "Stafford Gambit" in m["name"]

    def test_stafford_with_continuation(self):
        """Trap signature is a PREFIX of the actual game."""
        moves = ["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nc6", "Nxc6", "dxc6"]
        m = _match_trap(moves, TINY_LIB_SORTED)
        assert m is not None and "Stafford Gambit" in m["name"]

    def test_fried_liver_match(self):
        moves = [
            "e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6",
            "Ng5", "d5", "exd5", "Nxd5", "Nxf7",
        ]
        m = _match_trap(moves, TINY_LIB_SORTED)
        assert m is not None and "Fried Liver" in m["name"]

    def test_elephant_gambit_match(self):
        moves = ["e4", "e5", "Nf3", "d5"]
        m = _match_trap(moves, TINY_LIB_SORTED)
        assert m is not None and "Elephant Gambit" in m["name"]

    def test_no_match_for_unrelated_opening(self):
        # 1.d4 d5 2.c4 — Queen's Gambit, not in our tiny library
        moves = ["d4", "d5", "c4"]
        assert _match_trap(moves, TINY_LIB_SORTED) is None

    def test_partial_signature_does_not_match(self):
        """Library entry requires len(sig) <= len(game). A game with FEWER
        moves than the trap signature must not match."""
        # Stafford signature is 6 plies; game has only 4
        moves = ["e4", "e5", "Nf3", "Nf6"]
        # Should NOT match Stafford (incomplete)
        m = _match_trap(moves, TINY_LIB_SORTED)
        assert m is None or "Stafford" not in m.get("name", "")

    def test_longest_prefix_wins(self):
        """If two library entries share a prefix, deeper match wins (library
        is sorted deepest-first by the build script)."""
        lib = sorted([
            {"eco": "X", "name": "Short", "moves": ["e4", "e5"], "depth": 2},
            {"eco": "X", "name": "Long",  "moves": ["e4", "e5", "Nf3", "Nc6"], "depth": 4},
        ], key=lambda e: -e["depth"])
        m = _match_trap(["e4", "e5", "Nf3", "Nc6"], lib)
        assert m["name"] == "Long"

    def test_real_library_matches_stafford_pgn(self):
        """End-to-end: the vendored library must detect the Stafford."""
        moves = ["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nc6"]
        m = _match_trap(moves, _load_trap_library())
        assert m is not None and "Stafford" in m["name"]


class TestExtractSanMoves:
    def test_basic_pgn(self):
        pgn = '[White "a"]\n[Black "b"]\n\n1. e4 e5 2. Nf3 Nc6 *'
        moves = _extract_san_moves(pgn)
        assert moves == ["e4", "e5", "Nf3", "Nc6"]

    def test_empty_pgn(self):
        assert _extract_san_moves("") == []

    def test_max_moves_caps(self):
        # 30 plies of 1.e4 e5 2.Nf3 Nc6 ... — but our test PGN is short.
        # Just verify the cap argument doesn't break.
        pgn = '[White "a"]\n[Black "b"]\n\n1. e4 e5 2. Nf3 Nc6 *'
        moves = _extract_san_moves(pgn, max_moves=2)
        assert len(moves) == 2

    def test_malformed_pgn_returns_empty(self):
        assert _extract_san_moves("not a valid pgn at all") == []


class TestFrequencyLabel:
    @pytest.mark.parametrize("count,expected", [
        (1, "Rare"),
        (2, "Rare"),
        (3, "Occasional"),
        (5, "Occasional"),
        (6, "Frequent"),
        (20, "Frequent"),
    ])
    def test_buckets(self, count, expected):
        assert _frequency_label(count) == expected


def _g(game_id, color, result, pgn_moves):
    """Build a game dict with a real PGN move list (so trap matcher can run)."""
    san_pairs = []
    for i, m in enumerate(pgn_moves):
        if i % 2 == 0:
            san_pairs.append(f"{i // 2 + 1}. {m}")
        else:
            san_pairs.append(m)
    pgn = (
        f'[White "w"]\n[Black "b"]\n'
        '\n' + " ".join(san_pairs) + " *"
    )
    return {
        "id": game_id,
        "pgn": pgn,
        "player_color": color,
        "result": result,
        "date_played": f"2026-04-{game_id:02d}",
    }


class TestComputeTrapFalls:
    def test_no_games(self):
        assert _compute_trap_falls([]) == []

    def test_player_loses_to_stafford_three_times(self):
        # Player is White, opponent plays Stafford against them, player loses
        stafford_moves = ["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nc6", "Nxc6", "dxc6"]
        games = [_g(i + 1, "white", "loss", stafford_moves) for i in range(3)]
        out = _compute_trap_falls(games)
        assert len(out) == 1
        entry = out[0]
        assert "Stafford" in entry["name"]
        assert entry["count"] == 3
        assert entry["frequency_label"] == "Occasional"
        assert entry["wins"] == 0
        assert entry["losses"] == 3

    def test_wins_excluded_from_falls(self):
        stafford_moves = ["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nc6"]
        games = [_g(1, "white", "win", stafford_moves)]
        out = _compute_trap_falls(games)
        # Player won — this trap shouldn't appear in 'You Fall For'
        assert all(e["count"] == 0 for e in out) or out == []

    def test_aggregates_across_games(self):
        stafford_moves = ["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nc6"]
        elephant_moves = ["e4", "e5", "Nf3", "d5", "exd5"]
        games = (
            [_g(i + 1, "white", "loss", stafford_moves) for i in range(2)]
            + [_g(i + 10, "white", "loss", elephant_moves) for i in range(4)]
        )
        out = _compute_trap_falls(games)
        names = [e["name"] for e in out]
        # Elephant Gambit lost more — should rank first
        assert "Elephant Gambit" in names[0]


class TestComputeYourArsenal:
    def test_player_wins_with_fried_liver(self):
        fried_moves = [
            "e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6",
            "Ng5", "d5", "exd5", "Nxd5", "Nxf7",
        ]
        games = [_g(i + 1, "white", "win", fried_moves) for i in range(3)]
        out = _compute_your_arsenal(games)
        assert len(out) >= 1
        assert "Fried Liver" in out[0]["name"]
        assert out[0]["count"] == 3
        assert out[0]["wins"] == 3

    def test_losses_excluded_from_arsenal(self):
        fried_moves = [
            "e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6",
            "Ng5", "d5", "exd5", "Nxd5", "Nxf7",
        ]
        games = [_g(i + 1, "white", "loss", fried_moves) for i in range(3)]
        out = _compute_your_arsenal(games)
        # Player only lost — not part of arsenal
        assert all(e["count"] == 0 for e in out) or out == []
