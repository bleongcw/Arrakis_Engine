"""v1.14.0: tests for src/motifs.py — tactical motif detection.

Each motif gets a positive case (motif present), a near-miss (looks
similar but doesn't qualify), and an unrelated case (quiet move with
no motif). FEN positions are hand-crafted to be minimal and
unambiguous — no extra pieces, just the bare tactical structure.
"""

import chess
import pytest

from src.motifs import (
    detect_motifs,
    detect_mate_threat,
    detect_discovered_check,
    detect_fork,
    detect_pin,
    detect_skewer,
    detect_removing_defender,
    detect_hanging_piece,
    detect_trapped_piece,
    MOTIF_MATE_THREAT,
    MOTIF_DISCOVERED_CHECK,
    MOTIF_FORK,
    MOTIF_PIN,
    MOTIF_SKEWER,
    MOTIF_REMOVING_DEFENDER,
    MOTIF_HANGING_PIECE,
    MOTIF_TRAPPED_PIECE,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _move(board: chess.Board, uci: str) -> chess.Move:
    return chess.Move.from_uci(uci)


# ── Mate threat ─────────────────────────────────────────────────────


class TestMateThreat:
    def test_back_rank_mate_in_1(self):
        # White rook on e1, black king on h8 trapped by own pawns f7/g7/h7.
        # Move Re1-e8 is mate.
        board = chess.Board("6k1/5ppp/8/8/8/8/8/4R2K w - - 0 1")
        assert detect_mate_threat(board, _move(board, "e1e8"), None) == MOTIF_MATE_THREAT

    def test_check_but_not_mate(self):
        # Same back rank but the king has g8 escape (no pawn on g7)
        board = chess.Board("6k1/5p1p/8/8/8/8/8/4R2K w - - 0 1")
        assert detect_mate_threat(board, _move(board, "e1e8"), None) is None

    def test_quiet_move_no_check(self):
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        assert detect_mate_threat(board, _move(board, "e2e4"), None) is None


# ── Discovered check ────────────────────────────────────────────────


class TestDiscoveredCheck:
    def test_classic_discovered_check(self):
        # White rook on e1, white bishop on e4 blocking, black king on e8.
        # Bishop moves away (e.g. Bxh7) → rook delivers check.
        board = chess.Board("4k3/8/8/8/4B3/8/8/4R2K w - - 0 1")
        # Move the bishop off the e-file to unmask rook check
        # Bishop e4 -> b7 (off e-file)
        assert detect_discovered_check(board, _move(board, "e4b7"), None) == MOTIF_DISCOVERED_CHECK

    def test_direct_check_not_discovery(self):
        # Just a queen giving check directly — no discovered attacker
        board = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        # Qd1 -> d8 is direct check
        result = detect_discovered_check(board, _move(board, "d1d8"), None)
        assert result is None

    def test_move_along_pin_line_no_discovery(self):
        # Bishop moves but stays on e-file (doesn't unmask) — Be4-e5
        board = chess.Board("4k3/8/8/8/4B3/8/8/4R2K w - - 0 1")
        # Bishop moves along the e-file → still blocks rook
        assert detect_discovered_check(board, _move(board, "e4e5"), None) is None


# ── Fork ────────────────────────────────────────────────────────────


class TestFork:
    def test_knight_forks_king_and_queen(self):
        # White knight on c3, black king on e1, black queen on a4.
        # Knight d5 → not quite, build a real fork: N on e5 attacks
        # king on g6 and queen on c6.
        # FEN: black king g6, black queen c6, white knight ready to land on e5
        board = chess.Board("8/8/2q3k1/8/3N4/8/8/4K3 w - - 0 1")
        # Nd4 -> e6 forks king g6 and queen c6? Let's check geometry:
        # Knight on e6 attacks: c5, c7, d4, d8, f4, f8, g5, g7.
        # That hits g7 (next to king) but not the king or queen. Bad.
        # Use Nd4 -> c6 captures queen instead. Need a real fork.
        # Simpler: white knight d5, black king e7, black queen b6.
        # From d5, knight attacks c7, e7 (king!), f6, b6 (queen!), b4, c3, e3, f4.
        # Wait — d5 already forks. Need to MOVE INTO that square.
        # White knight on b4 moves to d5 → forks king e7 + queen b6 simultaneously.
        board = chess.Board("8/4k3/1q6/8/1N6/8/8/4K3 w - - 0 1")
        assert detect_fork(board, _move(board, "b4d5"), None) == MOTIF_FORK

    def test_only_one_higher_value_target(self):
        # Knight attacks only the queen (not the king on a far square)
        board = chess.Board("4k3/8/1q6/8/1N6/8/8/4K3 w - - 0 1")
        # Nb4 → d5 attacks queen on b6 but king on e8 is far
        # Knight on d5 attacks: c7, e7, f6, b6 (queen), b4, c3, e3, f4
        # King is on e8 — not attacked. Only one high-value target → not a fork.
        result = detect_fork(board, _move(board, "b4d5"), None)
        assert result is None

    def test_pawn_does_not_count_as_high_value_target(self):
        # Knight attacks queen + pawn — pawn is LOWER value than knight, doesn't count
        board = chess.Board("8/8/8/8/1N6/2p5/8/k2K1q2 w - - 0 1")
        # Knight on b4 -> d3 attacks pawn c5? Let me restructure.
        # The point is: knight attacks queen AND pawn → only 1 higher-value target.
        # Use: white knight, attacks queen + pawn after a move.
        # Skip this specific structure; assert via a clean position:
        # white knight d5, black queen on b6, black pawn on f6
        # Knight attacks pieces — queen (higher) and pawn (lower).
        board = chess.Board("4k3/8/1q3p2/3N4/8/8/8/4K3 w - - 0 1")
        # The knight is already on d5. We need to MOVE INTO this fork.
        # White knight on b4 → d5 attacks queen b6 and pawn f6.
        # Queen is higher value (9 > 3); pawn is lower (1 < 3).
        # Only 1 higher-value target → not a fork.
        board = chess.Board("4k3/8/1q3p2/8/1N6/8/8/4K3 w - - 0 1")
        result = detect_fork(board, _move(board, "b4d5"), None)
        assert result is None


# ── Pin ─────────────────────────────────────────────────────────────


class TestPin:
    def test_bishop_pins_knight_to_king(self):
        # Black king e8, black knight e5, white bishop moves to create pin
        # White bishop on a1, moves to b2? Need bishop on the e-file diagonal.
        # Actually pin against king on the same line: white bishop on h2 pins
        # knight on e5 via h2-b8 diagonal? h2-b8 goes h2,g3,f4,e5,d6,c7,b8 — yes.
        # But e8 not b8. Let me redo: king on b8, knight on e5, bishop moves to h2.
        # White bishop currently on h1, moves Bh1-h2? That's not the move.
        # Cleanest: bishop on a1 → moves to e5 line.
        # Use: White bishop on h6, moves to e3 — pins knight e5 against king on e8.
        # Wait, bishop on e3 attacks along diagonals, not files. A rook would pin
        # along a file.
        # Use a ROOK: white rook on e1, black knight on e5, black king on e8.
        # The rook moves Ra1 -> e1 to create the pin.
        board = chess.Board("4k3/8/8/4n3/8/8/8/R3K3 w - - 0 1")
        # Move Ra1 -> e1. The rook now pins the knight against the king.
        assert detect_pin(board, _move(board, "a1e1"), None) == MOTIF_PIN

    def test_quiet_move_no_pin(self):
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        assert detect_pin(board, _move(board, "g1f3"), None) is None

    def test_pre_existing_pin_not_tagged(self):
        # Pin already exists before the move; the move doesn't create a new pin.
        # White rook e1 already pins knight e5 to king e8. Now white plays Kg1-h1.
        board = chess.Board("4k3/8/8/4n3/8/8/8/4R1K1 w - - 0 1")
        # King move — shouldn't count as creating a pin
        assert detect_pin(board, _move(board, "g1h1"), None) is None


# ── Skewer ──────────────────────────────────────────────────────────


class TestSkewer:
    def test_rook_skewers_king_through_queen(self):
        # Wait — in a skewer the FRONT piece is LESS valuable.
        # So: rook attacks queen, with king behind queen → king moves, queen
        # falls. Front (queen, 9) ≥ back (king, 100)? King=100 is higher.
        # Actually: queen is lower value than king (9 < 100) → skewer applies.
        # Build: white rook on a1, black queen on e1, black king on e8.
        # Wait that's queen in front (on e1 same rank) but king is on e8 (different file).
        # Need them on the SAME line.
        # Try: white rook moves to h1. Black queen on h2, black king on h8.
        # Rook on h1 attacks up the h-file: queen h2 first, king h8 behind. Skewer.
        # Initial: white rook on a1, moves to h1.
        board = chess.Board("7k/7q/8/8/8/8/8/R3K3 w - - 0 1")
        assert detect_skewer(board, _move(board, "a1h1"), None) == MOTIF_SKEWER

    def test_no_back_piece(self):
        # Rook attacks queen but nothing behind it
        board = chess.Board("8/7q/8/8/8/8/k7/R3K3 w - - 0 1")
        # Rook a1 -> h1 attacks queen h7 (via h1-h7 file) but nothing behind h7
        result = detect_skewer(board, _move(board, "a1h1"), None)
        assert result is None

    def test_knight_cannot_skewer(self):
        # Knights can't skewer (not sliding pieces)
        board = chess.Board("7k/7q/8/8/8/8/8/N3K3 w - - 0 1")
        # Knight can't even reach this position; use a valid knight move
        board = chess.Board("8/8/8/8/8/1N6/8/4K3 w - - 0 1")
        result = detect_skewer(board, _move(board, "b3c5"), None)
        assert result is None

    # ── v1.15.1 regression locks: classical-skewer geometry ───────────

    def test_v15_1_queen_attacks_pawn_with_king_behind_is_not_skewer(self):
        """v1.15.1 regression — the bug that prompted the calibration.

        Position is the literal FEN from Evan's game 966 vs Giant_Ro
        (move 27, black to move). Engine's best move was Qxa7 — a
        rook grab. After Qxa7 the black queen sits on a7, attacks
        the white pawn on f2 with the white king on g1 behind along
        the a7-g1 diagonal. The v1.14.0 detector tagged this as a
        skewer (front pawn < back king), inflating the skewer count
        10–18× over other geometric motifs.

        v1.15.1 rejects it: attacker (queen=9) is not less valuable
        than the front piece (pawn=1), so taking the pawn is not a
        meaningful "trade up." The pawn isn't forced to move.
        """
        board = chess.Board(
            "8/Rp2bpkp/3pb1p1/4p3/2PqP3/3P2P1/3Q1PBP/1r2N1K1 b - - 4 27"
        )
        result = detect_skewer(board, _move(board, "d4a7"), None)
        assert result is None, (
            "queen attacks pawn (queen > pawn) is not a classical skewer "
            "— the front piece must be more valuable than the attacker"
        )

    def test_v15_1_bishop_captures_knight_with_queen_behind_is_not_skewer(self):
        """v1.15.1 regression — opening trades should not register.

        White bishop on c4 captures a black knight on c6 (worth 3 vs 3);
        a black queen on c8 happens to be on the c-file behind. The
        v1.14.0 detector tagged this as skewer because front (knight=3)
        < back (queen=9). But the attacker (bishop=3) is not less
        valuable than the front (knight=3) — it's an equal-value
        trade, not a winning skewer. Classical skewer rejects.
        """
        board = chess.Board(
            "r1bqk2r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4"
        )
        # Move: Bxc6 (bishop on c4 takes knight on c6); queen on c8 behind.
        # Wait — board above has queen on d8 not c8. Use a sharper FEN.
        board = chess.Board("r1qk3r/pppp1ppp/2n2n2/4p3/2B1P3/8/PPPP1PPP/4K3 w - - 0 1")
        result = detect_skewer(board, _move(board, "c4c6"), None)
        # Bxc6 captures the knight; on the c-file behind sits a black queen
        # on c8. Equal-value attacker→front trade ⇒ not a real skewer.
        assert result is None, (
            "equal-value attacker → front (bishop=3 vs knight=3) is not "
            "a classical skewer even when a higher-value piece sits behind"
        )

    def test_v15_1_rook_attacks_pawn_with_bishop_behind_is_not_skewer(self):
        """v1.15.1 regression — rook attacking a pawn with a minor piece
        behind is not a forcing skewer (rook=5 > pawn=1).
        """
        # White rook moves from a1 to h1; black pawn h7, black bishop h8.
        # After Rh1: rook on h1, attacks pawn h7 along h-file, bishop h8
        # behind it. Front (pawn=1) < back (bishop=3), but attacker
        # (rook=5) > front (pawn=1). Not a real skewer.
        board = chess.Board("3k3b/7p/8/8/8/8/8/R3K3 w - - 0 1")
        result = detect_skewer(board, _move(board, "a1h1"), None)
        assert result is None, (
            "attacker more valuable than the front piece ⇒ not a forcing skewer"
        )

    def test_v15_1_bishop_skewers_rook_through_queen_still_works(self):
        """v1.15.1 regression — positive case must still fire.

        Classical: bishop attacks queen with rook behind. Wait — that's
        attacker (bishop=3) < front (queen=9) AND front (queen=9) > back
        (rook=5). The current rule requires front < back, so this is
        actually NOT tagged. The correct classical pattern is
        bishop(3) attacks rook(5) with queen(9) behind: attacker(3) <
        front(5) AND front(5) < back(9). Build that.
        """
        # White bishop on a1; black rook on c3, black queen on e5 along
        # the a1-h8 diagonal. White king on h1, black king on h8 (legal
        # but irrelevant). Bxc3 isn't needed — we want the bishop's
        # MOVE to create the geometry. Put bishop on h1 → moves to a8?
        # Cleaner: bishop on a8 (just moved there) attacks rook on c6
        # with queen on e4 behind along a8-h1 diagonal.
        # FEN: bishop just played to a8; before: bishop on b7.
        # Pre-move FEN with bishop on b7: black rook c6, black queen e4.
        board = chess.Board("4k3/1B6/2r5/8/4q3/8/8/4K3 w - - 0 1")
        # Bb7-a8: bishop on a8 sees c6 (rook), then e4 (queen) along a8-h1.
        result = detect_skewer(board, _move(board, "b7a8"), None)
        assert result == MOTIF_SKEWER, (
            "classical attacker(3) < front(5) < back(9) must still tag"
        )


# ── Removing the defender ───────────────────────────────────────────


class TestRemovingDefender:
    def test_capture_removes_sole_defender(self):
        # Setup: White rook on d1 attacks black queen on d6, which is defended
        # by black knight on f5. White bishop on h3 captures the knight.
        # After Bxf5, the queen on d6 is undefended and attacked by the rook —
        # winning the queen for a bishop (a real material gain).
        #
        # Note: a more naive setup (pawn defended by bishop, attacker = rook)
        # doesn't tag because losing a rook for a pawn isn't tactically
        # threatening — the min-SEE heuristic correctly treats that target as
        # still safe. The detector only fires when removing the defender opens
        # a real winning capture.
        board = chess.Board("3k4/8/3q4/5n2/8/7B/8/3RK3 w - - 0 1")
        assert detect_removing_defender(board, _move(board, "h3f5"), None) == MOTIF_REMOVING_DEFENDER

    def test_quiet_capture_no_secondary_target(self):
        # Capture but no other piece becomes hanging
        board = chess.Board("4k3/8/8/8/3p4/2N5/8/4K3 w - - 0 1")
        # Nxd4 — just a capture, no other piece affected
        result = detect_removing_defender(board, _move(board, "c3d4"), None)
        assert result is None

    def test_non_capture_move(self):
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        # Quiet pawn push — not a capture
        assert detect_removing_defender(board, _move(board, "e2e4"), None) is None


# ── Hanging piece ───────────────────────────────────────────────────


class TestHangingPiece:
    def test_capture_undefended_piece(self):
        # White knight captures undefended black bishop
        board = chess.Board("4k3/8/2b5/8/3N4/8/8/4K3 w - - 0 1")
        # Nxc6 — the bishop on c6 has no defenders
        assert detect_hanging_piece(board, _move(board, "d4c6"), None) == MOTIF_HANGING_PIECE

    def test_capture_defended_piece_same_value(self):
        # NxN trade — both knights, mutual capture possible. Not a hanging
        # capture since trade is even.
        board = chess.Board("4k3/8/2n5/3N4/8/8/8/4K3 w - - 0 1")
        # Wait — does this knight on d5 attack c6? Knight moves: b6,b4,c3,c7,e3,e7,f4,f6
        # So d5 -> c6 isn't a knight move. Use:
        # White knight on b4 captures black knight on c6 (legal knight move: b4->c6)
        # But we need the captured piece to be defended.
        # FEN: white knight b4, black king e8, black knight c6, black pawn b7 (defends c6)
        board = chess.Board("4k3/1p6/2n5/8/1N6/8/8/4K3 w - - 0 1")
        # Nxc6: captured value 3 (knight), capturing value 3 (knight), recapture
        # by pawn (worth 1). Pawn recaptures → we lose 3 for 3, no net win, NOT hanging.
        # Actually let me reconsider: after Nxc6, black pawn b7 captures knight on c6.
        # We gave up a knight (3) for a knight (3), break-even. _is_safe_capture
        # checks captured_value >= capturing_value → 3 >= 3 yes, so it IS safe.
        # But "hanging" requires captured > moving OR no defenders. b7 defends c6
        # so there's a defender. Should NOT tag.
        result = detect_hanging_piece(board, _move(board, "b4c6"), None)
        assert result is None

    def test_capture_higher_value_piece(self):
        # Knight captures queen with recapture available — still hanging
        # because captured (9) > moving (3); even after recapture we net +6.
        board = chess.Board("3qk3/8/8/4N3/8/8/8/4K3 w - - 0 1")
        # Nxd8 captures queen, king on e8 can recapture (kxd8)
        # captured_value = 9, moving_value = 3. 9 > 3 → hanging.
        assert detect_hanging_piece(board, _move(board, "e5d7"), None) is None
        # Actually e5d7 isn't a capture. Use a knight that can take the queen:
        # Nf6 captures on d7? No. Nc7 captures queen on a8? Different position.
        # Let me redo with a clear setup: queen on a8, knight on c7 → knight takes queen
        board = chess.Board("q3k3/2N5/8/8/8/8/8/4K3 w - - 0 1")
        # Nxa8 — knight captures queen. King is far on e8, no recapture.
        assert detect_hanging_piece(board, _move(board, "c7a8"), None) == MOTIF_HANGING_PIECE


# ── Trapped piece ───────────────────────────────────────────────────


class TestTrappedPiece:
    def test_quiet_move_no_attack(self):
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        # Quiet development — not attacking anything
        assert detect_trapped_piece(board, _move(board, "g1f3"), None) is None


# ── detect_motifs (top-level) ───────────────────────────────────────


class TestDetectMotifs:
    def test_no_motifs_returns_empty_list(self):
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        # Quiet opening move
        assert detect_motifs(board, _move(board, "e2e4"), None) == []

    def test_returns_list_of_strings(self):
        # Back-rank mate scenario
        board = chess.Board("6k1/5ppp/8/8/8/8/8/4R2K w - - 0 1")
        motifs = detect_motifs(board, _move(board, "e1e8"), None)
        assert isinstance(motifs, list)
        assert all(isinstance(m, str) for m in motifs)
        assert MOTIF_MATE_THREAT in motifs

    def test_specificity_order_preserved(self):
        """Mate threat appears before other tags when multiple apply."""
        # A move that's both mate AND a fork would have mate first.
        # Hard to construct a clean overlap minimally; verify ordering
        # by checking that the _DETECTOR_ORDER constant is used.
        from src.motifs import _DETECTOR_ORDER
        # Sanity: mate_threat comes before fork in the order
        assert _DETECTOR_ORDER.index(MOTIF_MATE_THREAT) < _DETECTOR_ORDER.index(MOTIF_FORK)

    def test_handles_missing_pv(self):
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        # Should not crash with pv=None
        result = detect_motifs(board, _move(board, "e2e4"), None)
        assert result == []
