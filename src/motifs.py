# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Tactical motif detection (v1.14.0).

Given a position and a candidate move, this module classifies the move
with the tactical themes it executes — fork, pin, skewer, discovered
check, removing the defender, hanging-piece capture, mate threat,
trapped piece.

The 8 detectors are pure functions on (board_before, move, pv) and
return either ``None`` (no match) or the motif name string. The
top-level :func:`detect_motifs` runs all detectors and returns the
matched names ordered by specificity (most specific first).

Used by:
  - :mod:`src.analyzer` — calls per critical move (|cp_loss| ≥ 100)
    and persists results to ``move_analysis.motifs_json``.
  - :mod:`src.coach` — surfaces motif tags to the LLM in the
    critical_moments prompt block so feedback can cite themes by name
    ("you missed a knight fork on f7") instead of inferring them
    from raw eval swings.

Design notes:
  - "Sufficient defenders" uses a min-value SEE heuristic (cheap +
    safe-leaning): we tag a capture as a hanging-piece capture only
    when the captured piece had no defenders OR its lowest-valued
    defender was worth less than the captured piece — meaning the
    capture wins material no matter what.
  - All detectors run on the position BEFORE the move is played.
    Inside each detector we ``board.copy()`` and ``push(move)`` to
    look at the position after; we never mutate the caller's board.
  - Detectors are conservative — we'd rather miss a real motif than
    tag a false positive. The coaching prompt explicitly warns the
    LLM not to invent motifs that weren't tagged.
"""

from __future__ import annotations

import chess


# Standard piece values (centipawn-equivalent units). King is given a
# sentinel value of 100 so it always counts as "more valuable than any
# other piece" in skewer / pin logic.
PIECE_VALUES: dict[int, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}


# Motif name constants — kept here so callers (coach.py, frontend type
# union, tests) can refer to them by symbol rather than string literals.
MOTIF_MATE_THREAT = "mate_threat"
MOTIF_DISCOVERED_CHECK = "discovered_check"
MOTIF_FORK = "fork"
MOTIF_PIN = "pin"
MOTIF_SKEWER = "skewer"
MOTIF_REMOVING_DEFENDER = "removing_defender"
MOTIF_HANGING_PIECE = "hanging_piece"
MOTIF_TRAPPED_PIECE = "trapped_piece"


# Order matters: most-specific-first. detect_motifs() preserves this
# order in its returned list so the prompt's "primary motif" reads as
# the most distinctive label when multiple apply.
_DETECTOR_ORDER = (
    MOTIF_MATE_THREAT,
    MOTIF_DISCOVERED_CHECK,
    MOTIF_FORK,
    MOTIF_PIN,
    MOTIF_SKEWER,
    MOTIF_REMOVING_DEFENDER,
    MOTIF_HANGING_PIECE,
    MOTIF_TRAPPED_PIECE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _piece_value(piece: chess.Piece | None) -> int:
    """Return the standard piece value, or 0 for None/empty squares."""
    if piece is None:
        return 0
    return PIECE_VALUES.get(piece.piece_type, 0)


def _min_attacker_value(board: chess.Board, color: bool, square: int) -> int | None:
    """Cheapest piece of ``color`` attacking ``square``, by value.

    Returns ``None`` if no attackers. Used as a min-SEE heuristic: a
    capture by a piece worth more than this is a net loss.
    """
    attackers = board.attackers(color, square)
    if not attackers:
        return None
    return min(
        _piece_value(board.piece_at(sq))
        for sq in attackers
        if board.piece_at(sq) is not None
    )


def _is_safe_capture(board: chess.Board, move: chess.Move) -> bool:
    """Heuristic: would playing ``move`` (a capture) win or trade level material?

    True iff the captured piece's value ≥ the cheapest enemy defender's
    value AFTER the capture. This is a simplified SEE — it ignores the
    full recapture chain but catches the common cases (hanging pieces,
    cheap-takes-expensive) accurately.

    For non-captures, returns True (vacuously — no material is at risk
    from the capture itself).
    """
    if not board.is_capture(move):
        return True
    # The capturing piece's value
    capturing_piece = board.piece_at(move.from_square)
    if capturing_piece is None:
        return True
    captured_value = _piece_value(board.piece_at(move.to_square))
    # For en passant, the captured pawn isn't on to_square
    if board.is_en_passant(move):
        captured_value = PIECE_VALUES[chess.PAWN]
    # Project: after the capture, who attacks the destination square?
    after = board.copy()
    after.push(move)
    # Min enemy attacker (now on the destination) — color is the side
    # that just moved's opponent.
    enemy_color = not capturing_piece.color
    min_defender = _min_attacker_value(after, enemy_color, move.to_square)
    if min_defender is None:
        return True  # nothing to recapture — pure win
    capturing_value = _piece_value(capturing_piece)
    # We'd lose `capturing_value` to win `captured_value`. Safe iff we
    # gain ≥ what we lose.
    return captured_value >= capturing_value


def _square_is_safe_for(board: chess.Board, square: int, color: bool) -> bool:
    """True iff a piece of ``color`` standing on ``square`` is safe.

    Uses the min-SEE heuristic: safe iff no enemy attacker exists OR the
    cheapest enemy attacker is worth more than the piece being
    threatened (so any capture loses material for the enemy).
    """
    piece = board.piece_at(square)
    if piece is None:
        return True
    enemy_color = not color
    min_attacker = _min_attacker_value(board, enemy_color, square)
    if min_attacker is None:
        return True
    min_defender = _min_attacker_value(board, color, square)
    piece_val = _piece_value(piece)
    # If we have a defender of equal/lower value than the attacker, the
    # trade is at worst even.
    if min_defender is not None and min_defender <= min_attacker:
        return True
    # Otherwise we just compare attacker value to the piece value: if
    # the attacker is cheaper, the piece is lost.
    return min_attacker >= piece_val


# ---------------------------------------------------------------------------
# Detectors — each is `detect_X(board_before, move, pv) -> str | None`
# ---------------------------------------------------------------------------


def detect_mate_threat(
    board: chess.Board, move: chess.Move, pv: list[chess.Move] | None
) -> str | None:
    """Move leads to forced checkmate within the PV's horizon.

    A move qualifies if (a) it gives check, AND (b) the PV continuation
    ends in checkmate within len(pv) plies, OR (c) it IS checkmate.
    """
    after = board.copy()
    after.push(move)
    if after.is_checkmate():
        return MOTIF_MATE_THREAT  # mate in 1
    if not after.is_check():
        # Could still be a "mating attack" sequence — but without check
        # right now, it's not a *threat* in the immediate sense.
        return None
    # Walk the PV. If we reach checkmate within the PV, tag it.
    if not pv:
        return None
    pv_board = after.copy()
    for next_move in pv:
        if next_move not in pv_board.legal_moves:
            return None
        pv_board.push(next_move)
        if pv_board.is_checkmate():
            return MOTIF_MATE_THREAT
    return None


def detect_discovered_check(
    board: chess.Board, move: chess.Move, pv: list[chess.Move] | None
) -> str | None:
    """Moving piece reveals a check from another piece behind it.

    Diagnostic: after the move, the king is in check, but the moving
    piece itself does NOT attack the king. The check comes from a
    discovered attacker on the move's from_square's line of attack.
    """
    after = board.copy()
    after.push(move)
    if not after.is_check():
        return None
    enemy_color = not board.color_at(move.from_square)
    enemy_king_sq = after.king(enemy_color)
    if enemy_king_sq is None:
        return None
    # Squares from which the MOVING piece (now on to_square) attacks
    # the enemy king
    moving_attacks_king = enemy_king_sq in after.attacks(move.to_square)
    if not moving_attacks_king:
        return MOTIF_DISCOVERED_CHECK
    # If the moving piece DOES attack the king directly, we need to
    # check whether ANOTHER piece also attacks — that's a double check,
    # which is also a discovery.
    checkers = after.checkers()
    if len(checkers) >= 2:
        return MOTIF_DISCOVERED_CHECK
    return None


def detect_fork(
    board: chess.Board, move: chess.Move, pv: list[chess.Move] | None
) -> str | None:
    """Moving piece attacks ≥2 enemy pieces of greater value after the move.

    Conservative: only tags when the moving piece attacks 2+ pieces
    each worth MORE than the moving piece itself, AND each of those
    attacked pieces is not currently safe (no sufficient defender at
    a value less than the attacker).
    """
    moving_piece = board.piece_at(move.from_square)
    if moving_piece is None:
        return None
    after = board.copy()
    after.push(move)
    # Squares now attacked by the moved piece (now on to_square)
    attacked_squares = after.attacks(move.to_square)
    moving_value = _piece_value(moving_piece)
    enemy_color = not moving_piece.color
    higher_value_targets = 0
    for sq in attacked_squares:
        target = after.piece_at(sq)
        if target is None or target.color != enemy_color:
            continue
        if _piece_value(target) <= moving_value:
            continue
        # Is this attacked piece safe? If yes, the fork doesn't win it.
        # We check by considering whether the moving piece could capture
        # without losing material. min_defender_value of target square
        # (from the target's perspective).
        min_defender = _min_attacker_value(after, enemy_color, sq)
        # If the target has a defender cheaper than the moving piece,
        # the capture trades down — not a winning fork prong.
        if min_defender is not None and min_defender < moving_value:
            continue
        higher_value_targets += 1
    if higher_value_targets >= 2:
        return MOTIF_FORK
    return None


def detect_pin(
    board: chess.Board, move: chess.Move, pv: list[chess.Move] | None
) -> str | None:
    """Move pins an enemy piece against its king (absolute pin).

    Looks for: after the move, there exists an enemy piece that is
    pinned (cannot legally move without exposing its king to check).
    Only counts pins CREATED by this move — we compare before/after.
    """
    enemy_color = not board.color_at(move.from_square)
    # Pre-move: which enemy pieces were already pinned?
    before_pinned = {
        sq for sq in chess.SQUARES
        if board.piece_at(sq)
        and board.piece_at(sq).color == enemy_color
        and board.is_pinned(enemy_color, sq)
    }
    after = board.copy()
    after.push(move)
    # Post-move: which enemy pieces are pinned now?
    after_pinned = {
        sq for sq in chess.SQUARES
        if after.piece_at(sq)
        and after.piece_at(sq).color == enemy_color
        and after.is_pinned(enemy_color, sq)
    }
    newly_pinned = after_pinned - before_pinned
    if newly_pinned:
        return MOTIF_PIN
    return None


def detect_skewer(
    board: chess.Board, move: chess.Move, pv: list[chess.Move] | None
) -> str | None:
    """Move attacks an enemy piece that, if it moves, exposes a more valuable
    piece behind it.

    A skewer is the inverse of a pin: the higher-value piece is IN
    FRONT. We detect by checking sliding pieces (rook/bishop/queen)
    that attack a less-valuable enemy piece with a more-valuable enemy
    piece directly behind it on the same line.

    v1.15.1: tightened the classical-skewer geometry. The attacker
    must be LESS VALUABLE than the front piece — otherwise the move
    isn't "threatening" the front piece in any meaningful way (a
    queen attacking a pawn doesn't force the pawn off the line; the
    pawn is just a one-point trade waiting to happen). Without this
    guard the detector tagged any aligned attacker+front+back trio,
    producing 10–18× more skewer firings than other geometric motifs
    in v1.14.0 — the classic *"queen ends on a-file, pawn-then-king
    is incidentally on the diagonal"* false positive.

    Classical pattern preserved:
      bishop(3) attacks queen(9) with king(100) behind → skewer ✓
      rook(5)   attacks queen(9) with king(100) behind → skewer ✓
      bishop(3) attacks rook(5)  with queen(9) behind → skewer ✓
    Newly rejected (false positives in v1.14.0):
      queen(9) attacks pawn(1) with king(100) behind → not a skewer
      bishop(3) captures knight(3) with queen(9) behind → opening trade
      rook(5) attacks pawn(1) with bishop(3) behind → not forcing
    """
    moving_piece = board.piece_at(move.from_square)
    if moving_piece is None:
        return None
    # Only sliding pieces can skewer
    if moving_piece.piece_type not in (chess.ROOK, chess.BISHOP, chess.QUEEN):
        return None
    after = board.copy()
    after.push(move)
    enemy_color = not moving_piece.color
    from_sq = move.to_square
    attacker_val = _piece_value(moving_piece)
    # For each direction the sliding piece moves, walk outward and find
    # the first 2 enemy pieces — if the FIRST is less valuable than the
    # SECOND, that's the geometry of a skewer.
    directions = _sliding_directions_for(moving_piece.piece_type)
    for dx, dy in directions:
        first_enemy_sq = None
        second_enemy_sq = None
        sq = from_sq
        while True:
            sq = _step(sq, dx, dy)
            if sq is None:
                break
            piece = after.piece_at(sq)
            if piece is None:
                continue
            if piece.color != enemy_color:
                break  # blocked by own piece
            if first_enemy_sq is None:
                first_enemy_sq = sq
                continue
            second_enemy_sq = sq
            break
        if first_enemy_sq is None or second_enemy_sq is None:
            continue
        first_val = _piece_value(after.piece_at(first_enemy_sq))
        second_val = _piece_value(after.piece_at(second_enemy_sq))
        # v1.15.1: classical skewer — attacker < front, front < back.
        # The attacker<front gate is the new one; it ensures the front
        # piece is genuinely threatened by the trade (the attacker
        # actually gains material if the front piece doesn't move).
        if attacker_val < first_val and first_val < second_val:
            return MOTIF_SKEWER
    return None


def _sliding_directions_for(piece_type: int) -> list[tuple[int, int]]:
    """Return the (file_delta, rank_delta) directions for a sliding piece type."""
    if piece_type == chess.ROOK:
        return [(0, 1), (0, -1), (1, 0), (-1, 0)]
    if piece_type == chess.BISHOP:
        return [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    if piece_type == chess.QUEEN:
        return [(0, 1), (0, -1), (1, 0), (-1, 0),
                (1, 1), (1, -1), (-1, 1), (-1, -1)]
    return []


def _step(square: int, dfile: int, drank: int) -> int | None:
    """Step from ``square`` by (dfile, drank); return new square or None if off-board."""
    file_ = chess.square_file(square) + dfile
    rank = chess.square_rank(square) + drank
    if not (0 <= file_ <= 7 and 0 <= rank <= 7):
        return None
    return chess.square(file_, rank)


def detect_removing_defender(
    board: chess.Board, move: chess.Move, pv: list[chess.Move] | None
) -> str | None:
    """Move captures a piece that was the sole defender of another enemy
    piece, leaving that other piece hanging.

    Diagnostic: ``move`` is a capture of an enemy piece P. There exists
    another enemy piece Q such that BEFORE the move, P was among Q's
    defenders, AND AFTER the move, Q is now undefended (or under-
    defended) and attackable.
    """
    if not board.is_capture(move):
        return None
    moving_piece = board.piece_at(move.from_square)
    if moving_piece is None:
        return None
    enemy_color = not moving_piece.color
    captured_sq = move.to_square
    # En passant: the captured pawn is on a different square
    if board.is_en_passant(move):
        ep_rank = chess.square_rank(move.from_square)
        captured_sq = chess.square(chess.square_file(move.to_square), ep_rank)
    # Find enemy pieces that the captured piece was defending pre-move
    captured_piece = board.piece_at(captured_sq)
    if captured_piece is None:
        return None
    # Squares the captured piece attacks (i.e., potentially defends)
    defended_squares = board.attacks(captured_sq)
    after = board.copy()
    after.push(move)
    for sq in defended_squares:
        target = board.piece_at(sq)
        if target is None or target.color != enemy_color or sq == captured_sq:
            continue
        # Was target defended by the captured piece? Yes by construction
        # (captured piece's attacks() set includes sq). Now: is target
        # still safe after the capture?
        if _square_is_safe_for(after, sq, enemy_color):
            continue
        # The target is now unsafe — was it safe BEFORE? If not, this
        # capture didn't change anything, so it's not "removing the
        # defender" — it's just a capture next to an already-hanging piece.
        if not _square_is_safe_for(board, sq, enemy_color):
            continue
        # The capture made an otherwise-safe piece unsafe → removing the defender
        return MOTIF_REMOVING_DEFENDER
    return None


def detect_hanging_piece(
    board: chess.Board, move: chess.Move, pv: list[chess.Move] | None
) -> str | None:
    """Move captures an enemy piece that had no sufficient defenders.

    True iff the move is a capture and the captured piece's value
    exceeds the cheapest defender's value (we don't lose material via
    recapture). For pawn-takes-pawn this rarely tags (same value); for
    knight-takes-undefended-bishop this tags.
    """
    if not board.is_capture(move):
        return None
    if not _is_safe_capture(board, move):
        return None
    moving_piece = board.piece_at(move.from_square)
    captured_value = _piece_value(board.piece_at(move.to_square))
    if board.is_en_passant(move):
        captured_value = PIECE_VALUES[chess.PAWN]
    # Only tag when we actually win material — if the captured piece is
    # the same value as ours (e.g. NxN trade), it's not a hanging
    # capture. Threshold: captured piece must be worth ≥ 1 pawn AND the
    # capture must be a net positive after potential recapture.
    if captured_value == 0 or moving_piece is None:
        return None
    moving_value = _piece_value(moving_piece)
    # If captured value > moving value, even losing the recapture is a
    # net win → hanging-piece capture.
    if captured_value > moving_value:
        return MOTIF_HANGING_PIECE
    # Equal values: only tag if there's no recapture (truly free)
    if captured_value == moving_value:
        after = board.copy()
        after.push(move)
        enemy_color = not moving_piece.color
        if not after.attackers(enemy_color, move.to_square):
            return MOTIF_HANGING_PIECE
    return None


def detect_trapped_piece(
    board: chess.Board, move: chess.Move, pv: list[chess.Move] | None
) -> str | None:
    """Move traps an enemy piece — after the move, an enemy piece has no
    safe square to retreat to.

    Conservative: only tags when (a) the move attacks an enemy minor or
    major piece (not a pawn or king — those are different concepts),
    AND (b) every legal destination of that piece (including its
    current square if it stays) is unsafe per the min-SEE heuristic.
    """
    moving_piece = board.piece_at(move.from_square)
    if moving_piece is None:
        return None
    after = board.copy()
    after.push(move)
    enemy_color = not moving_piece.color
    # Find each enemy piece newly attacked by the moving piece
    attacked_squares = after.attacks(move.to_square)
    for sq in attacked_squares:
        target = after.piece_at(sq)
        if target is None or target.color != enemy_color:
            continue
        # Skip pawns + king (different tactical concepts)
        if target.piece_type in (chess.PAWN, chess.KING):
            continue
        # Skip if the target is already under safe attack (we want
        # newly-trapped, not already-attacked); compare before vs after
        before_attackers = board.attackers(moving_piece.color, sq)
        if before_attackers:
            continue  # was already attacked — not newly trapped
        # Can the target move to any safe square (or stay safely)?
        # Quick test: enumerate target's legal moves in the after
        # position and see if any destination square would be safe.
        # But we need it to be the target's turn — set up a hypothetical
        # board with the opposite turn.
        hypo = after.copy()
        # Swap turn so we can probe the target's moves
        if hypo.turn != enemy_color:
            # Can't trivially swap turn in python-chess without breaking
            # state; use a heuristic instead: check all of the target's
            # potential destination squares directly.
            target_destinations = _target_legal_destinations(after, sq)
        else:
            target_destinations = [m.to_square for m in hypo.legal_moves
                                   if m.from_square == sq]
        has_safe_destination = False
        # Staying put: is the current square safe? (no, it's attacked
        # by definition — but maybe defended)
        if _square_is_safe_for(after, sq, enemy_color):
            has_safe_destination = True
        if not has_safe_destination:
            for dest in target_destinations:
                # Project the target moving there
                hypo2 = after.copy()
                # Build the candidate move
                cand = chess.Move(sq, dest)
                # Validate the candidate by checking piece moves
                # (python-chess won't let us call legal_moves filtered
                # by from_square without being that color's turn)
                if not _is_pseudo_legal_move(after, target, sq, dest):
                    continue
                # Project: would target be safe on dest?
                hypo2_target_piece = after.piece_at(sq)
                if hypo2_target_piece is None:
                    continue
                # Manually compute: is dest safe for the target?
                # Build a hypothetical board where target is on dest
                hypo_board = after.copy()
                # Remove target from sq, place on dest (no capture
                # complication for this check — we just want safety)
                hypo_board.remove_piece_at(sq)
                # If dest is occupied by an enemy of the target (us),
                # it's a capture move
                hypo_board.set_piece_at(dest, target)
                if _square_is_safe_for(hypo_board, dest, enemy_color):
                    has_safe_destination = True
                    break
        if not has_safe_destination:
            return MOTIF_TRAPPED_PIECE
    return None


def _target_legal_destinations(board: chess.Board, from_sq: int) -> list[int]:
    """Approximate the legal destination squares for the piece on from_sq.

    Returns the squares that piece pseudo-attacks (a superset of legal
    moves — close enough for the trapped-piece heuristic since we then
    re-check safety on each destination).
    """
    piece = board.piece_at(from_sq)
    if piece is None:
        return []
    return list(board.attacks(from_sq))


def _is_pseudo_legal_move(
    board: chess.Board, piece: chess.Piece, from_sq: int, to_sq: int
) -> bool:
    """Cheap check: is the to_square in the piece's attack set?

    Misses some legal-move nuance (pawn pushes, castling, etc.) but is
    sufficient for the trapped-piece heuristic, which then validates
    safety via SEE on the candidate destination.
    """
    if piece.piece_type == chess.PAWN:
        # Pawn pushes: empty square 1 forward (or 2 from start rank)
        direction = 1 if piece.color == chess.WHITE else -1
        start_rank = 1 if piece.color == chess.WHITE else 6
        rank_from = chess.square_rank(from_sq)
        if chess.square_file(from_sq) == chess.square_file(to_sq):
            steps = (chess.square_rank(to_sq) - rank_from) * direction
            if steps == 1 and board.piece_at(to_sq) is None:
                return True
            if (steps == 2 and rank_from == start_rank
                    and board.piece_at(to_sq) is None):
                return True
            return False
        # Pawn captures: diagonal one square, requires enemy on dest
        if to_sq in board.attacks(from_sq):
            target = board.piece_at(to_sq)
            return target is not None and target.color != piece.color
        return False
    return to_sq in board.attacks(from_sq)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_DETECTORS = {
    MOTIF_MATE_THREAT: detect_mate_threat,
    MOTIF_DISCOVERED_CHECK: detect_discovered_check,
    MOTIF_FORK: detect_fork,
    MOTIF_PIN: detect_pin,
    MOTIF_SKEWER: detect_skewer,
    MOTIF_REMOVING_DEFENDER: detect_removing_defender,
    MOTIF_HANGING_PIECE: detect_hanging_piece,
    MOTIF_TRAPPED_PIECE: detect_trapped_piece,
}


def detect_motifs(
    board_before: chess.Board,
    move: chess.Move,
    pv: list[chess.Move] | None = None,
) -> list[str]:
    """Run all detectors on ``move`` from ``board_before``.

    Returns a list of motif name strings in specificity order (most
    specific first). Empty list if no motifs detected.

    The PV argument is the engine's principal variation starting from
    the position AFTER ``move`` is played. Used by detectors that need
    to look ahead (currently only mate_threat).
    """
    results: list[str] = []
    for name in _DETECTOR_ORDER:
        detector = _DETECTORS[name]
        if detector(board_before, move, pv):
            results.append(name)
    return results
