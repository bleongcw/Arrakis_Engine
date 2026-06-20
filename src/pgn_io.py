# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""PGN data I/O — import (parse + ingest) and export (raw + annotated).

This is the open, portable data layer: get a PGN into the system (paste/upload
or, in the commercial layer, OCR) and back out again. It is deliberately format
plumbing — the moat lives elsewhere (OCR capture + correction). python-chess
(`chess`) is already a core dependency.

- parse_pgn()       raw PGN  -> ParsedGame (legality-validated, maps onto `games`)
- ingest_game()     ParsedGame -> row in `games` (analysis_status='pending')
- build_pgn()       a stored game -> PGN text (raw, or annotated with evals+NAGs)
- build_bulk_pgn()  many games -> one multi-game PGN file
"""

from __future__ import annotations

import hashlib
import io
import sqlite3
from dataclasses import dataclass

import chess
import chess.pgn


class PgnParseError(ValueError):
    """Raised when a PGN cannot be parsed or replayed legally."""


@dataclass
class ParsedGame:
    """Everything ingest needs to write a row into `games`."""

    pgn: str
    game_url: str          # UNIQUE NOT NULL — synthesized if PGN has no Site/Link
    player_color: str      # 'white' | 'black'
    result: str            # 'win' | 'loss' | 'draw' (player's perspective)
    player_rating: int | None
    opponent_rating: int | None
    opponent_username: str | None
    time_control: str | None
    time_class: str | None
    date_played: str | None
    move_count: int
    white: str | None
    black: str | None


@dataclass
class IngestResult:
    game_id: int
    created: bool        # False if the game already existed (dedup hit)
    game_url: str


_RESULT_MAP = {
    ("1-0", "white"): "win",
    ("1-0", "black"): "loss",
    ("0-1", "white"): "loss",
    ("0-1", "black"): "win",
    ("1/2-1/2", "white"): "draw",
    ("1/2-1/2", "black"): "draw",
}

# Move-classification → numeric NAG (Numeric Annotation Glyph) for annotated
# export. Only the imperfect moves are glyphed; good/excellent stay clean.
_CLASS_NAG = {"blunder": 4, "mistake": 2, "inaccuracy": 6}  # ?? / ? / ?!


def _classify_time_control(tc: str | None) -> str | None:
    """Map a PGN TimeControl ("600+5", "180", "-") to a chess.com-style class."""
    if not tc or tc in {"-", "?"}:
        return None
    base = tc.split("+", 1)[0]
    try:
        seconds = int(base)
    except ValueError:
        return None
    if seconds < 180:
        return "bullet"
    if seconds < 600:
        return "blitz"
    if seconds < 1800:
        return "rapid"
    return "classical"


def _normalize_date(headers: dict[str, str]) -> str | None:
    raw = headers.get("UTCDate") or headers.get("Date")
    if not raw or raw.startswith("?"):
        return None
    date = raw.replace(".", "-")
    time = headers.get("UTCTime") or headers.get("StartTime") or "00:00:00"
    return f"{date} {time}"


def _synthesize_url(pgn: str, headers: dict[str, str]) -> str:
    """Prefer an explicit Site/Link URL; else a stable content hash so the
    UNIQUE(game_url) constraint both holds and dedups re-imports."""
    for key in ("Link", "Site"):
        val = headers.get(key, "")
        if val.startswith("http"):
            return val
    digest = hashlib.sha1(pgn.strip().encode("utf-8")).hexdigest()[:16]
    return f"imported:{digest}"


def _to_int(val: str | None) -> int | None:
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def parse_pgn(
    pgn_text: str,
    player_color: str | None = None,
    known_usernames: list[str] | None = None,
    result: str | None = None,
) -> ParsedGame:
    """Parse and legally validate a single-game PGN.

    Args:
        pgn_text: raw PGN (headers + movetext).
        player_color: 'white'/'black' if the caller knows which side the
            player had. If None, inferred by matching `known_usernames`
            against the White/Black headers, defaulting to 'white'.
        known_usernames: the player's chess.com / lichess handles, used to
            infer color when not given explicitly.
        result: explicit player-perspective result ('win'/'loss'/'draw'),
            REQUIRED when the PGN's own Result header is undecided ("*") —
            e.g. an in-progress or unrecorded OTB scoresheet. The `games`
            schema only allows win/loss/draw, so an undecided game can't be
            stored without the caller naming the outcome. When the header IS
            decided, an override here takes precedence.

    Raises PgnParseError on empty input, unparseable PGN, no moves, an illegal
    move, or an undecided result with no `result` override.
    """
    if not pgn_text or not pgn_text.strip():
        raise PgnParseError("Empty PGN.")

    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise PgnParseError("Could not parse PGN — no game found.")

    # python-chess does NOT raise on an illegal/malformed move — it logs the
    # move, drops it from the mainline, and records it in game.errors. Treat
    # any such error as a hard parse failure so we never ingest a truncated game.
    if game.errors:
        raise PgnParseError(f"Invalid move in PGN: {game.errors[0]}")

    headers = {k: v for k, v in game.headers.items()}

    # Replay every move to confirm legality. python-chess raises on illegal SAN.
    board = game.board()
    move_count = 0
    try:
        for move in game.mainline_moves():
            if move not in board.legal_moves:
                raise PgnParseError(
                    f"Illegal move at ply {move_count + 1}: "
                    f"{board.san(move) if move in board.pseudo_legal_moves else move.uci()}"
                )
            board.push(move)
            move_count += 1
    except PgnParseError:
        raise
    except Exception as exc:  # malformed SAN, etc.
        raise PgnParseError(f"Invalid move sequence: {exc}") from exc

    if move_count == 0:
        raise PgnParseError("PGN contains no moves.")

    white = headers.get("White")
    black = headers.get("Black")

    # Resolve player color.
    if player_color in {"white", "black"}:
        color = player_color
    else:
        color = "white"
        if known_usernames:
            lowered = {u.lower() for u in known_usernames if u}
            if black and black.lower() in lowered:
                color = "black"
            elif white and white.lower() in lowered:
                color = "white"

    if result is not None:
        # Explicit player-perspective override (lets undecided "*" games in).
        if result not in {"win", "loss", "draw"}:
            raise PgnParseError(
                f"Invalid result override '{result}' — use 'win', 'loss', or 'draw'."
            )
        final_result = result
    else:
        result_header = headers.get("Result", "*")
        final_result = _RESULT_MAP.get((result_header, color))
        if final_result is None:
            raise PgnParseError(
                f"This PGN has no decided result (Result \"{result_header}\"). "
                "Pass an explicit result (win/loss/draw, from the player's "
                "perspective) to import an in-progress or unrecorded game."
            )

    if color == "white":
        player_rating = _to_int(headers.get("WhiteElo"))
        opponent_rating = _to_int(headers.get("BlackElo"))
        opponent_username = black
    else:
        player_rating = _to_int(headers.get("BlackElo"))
        opponent_rating = _to_int(headers.get("WhiteElo"))
        opponent_username = white

    time_control = headers.get("TimeControl")
    if time_control in {"-", "?"}:
        time_control = None

    return ParsedGame(
        pgn=pgn_text.strip(),
        game_url=_synthesize_url(pgn_text, headers),
        player_color=color,
        result=final_result,
        player_rating=player_rating,
        opponent_rating=opponent_rating,
        opponent_username=opponent_username,
        time_control=time_control,
        time_class=_classify_time_control(time_control),
        date_played=_normalize_date(headers),
        move_count=move_count,
        white=white,
        black=black,
    )


def ingest_game(
    conn: sqlite3.Connection,
    player_id: int,
    game: ParsedGame,
    platform: str = "import",
) -> IngestResult:
    """Insert `game` for `player_id`, or return the existing row on dedup.

    Dedup is by the UNIQUE `game_url` column — same as the harvester. The
    caller owns the connection and the commit. The row lands with
    analysis_status='pending', so analyze_pending() + coach_pending() pick it
    up exactly like a harvested game.
    """
    existing = conn.execute(
        "SELECT id FROM games WHERE game_url = ?", (game.game_url,)
    ).fetchone()
    if existing:
        return IngestResult(game_id=existing[0], created=False, game_url=game.game_url)

    cur = conn.execute(
        """INSERT INTO games
           (player_id, game_url, pgn, player_color, player_rating,
            opponent_rating, opponent_username, result, time_control,
            time_class, date_played, platform)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            player_id,
            game.game_url,
            game.pgn,
            game.player_color,
            game.player_rating,
            game.opponent_rating,
            game.opponent_username,
            game.result,
            game.time_control,
            game.time_class,
            game.date_played,
            platform,
        ),
    )
    return IngestResult(game_id=cur.lastrowid, created=True, game_url=game.game_url)


def build_pgn(game_row, move_rows=None, annotated: bool = False) -> str:
    """Return a single game's PGN text.

    raw (default): the exact stored PGN.
    annotated: the stored PGN re-emitted with per-move `{[%eval <pawns>]}`
    comments and classification NAGs ($4 blunder / $2 mistake / $6 inaccuracy),
    sourced from `move_rows` (move_analysis rows). Falls back to raw if the PGN
    can't be reparsed or no move data is given.
    """
    raw = (game_row["pgn"] or "").strip()
    if not annotated or not move_rows:
        return raw + "\n"

    by_ply = {
        (r["move_number"], r["side"]): r for r in move_rows
    }
    game = chess.pgn.read_game(io.StringIO(raw))
    if game is None:
        return raw + "\n"

    board = game.board()
    node = game
    while node.variations:
        next_node = node.variations[0]
        mv_num = board.fullmove_number
        side = "white" if board.turn == chess.WHITE else "black"
        r = by_ply.get((mv_num, side))
        if r is not None:
            ev = r["eval_after_cp"]
            if ev is not None:
                tag = f"[%eval {ev / 100:.2f}]"
                next_node.comment = (
                    f"{next_node.comment} {tag}".strip() if next_node.comment else tag
                )
            nag = _CLASS_NAG.get(r["classification"])
            if nag:
                next_node.nags.add(nag)
        board.push(next_node.move)
        node = next_node

    exporter = chess.pgn.StringExporter(headers=True, comments=True, variations=True)
    return game.accept(exporter).strip() + "\n"


def build_bulk_pgn(pgns) -> str:
    """Join individual game PGN strings into one multi-game PGN file (blank-line
    separated, as the PGN spec expects)."""
    cleaned = [p.strip() for p in pgns if p and p.strip()]
    return "\n\n".join(cleaned) + ("\n" if cleaned else "")
