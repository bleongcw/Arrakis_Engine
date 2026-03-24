"""SQLite schema and data models for ArrakisEngine."""

import os
import re
import sqlite3
from pathlib import Path


def get_db_path(config_path: str = "data/chess_coach.db") -> str:
    """Return absolute path to the database, creating the directory if needed."""
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    if db_path is None:
        db_path = get_db_path()
    else:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db(db_path: str | None = None) -> sqlite3.Connection:
    """Initialize the database schema. Returns the connection."""
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    # Migrations for existing databases
    _migrate(conn)
    return conn


def extract_opponent_from_pgn(pgn: str, player_color: str) -> str | None:
    """Extract opponent username from PGN headers.

    If player is black, opponent is the [White] header, and vice versa.
    """
    if player_color == "black":
        match = re.search(r'\[White\s+"([^"]+)"\]', pgn)
    else:
        match = re.search(r'\[Black\s+"([^"]+)"\]', pgn)
    return match.group(1) if match else None


def _backfill_opponent_usernames(conn: sqlite3.Connection):
    """Backfill opponent_username from PGN headers for existing games."""
    rows = conn.execute(
        "SELECT id, pgn, player_color FROM games WHERE opponent_username IS NULL"
    ).fetchall()
    updated = 0
    for row in rows:
        opponent = extract_opponent_from_pgn(row["pgn"], row["player_color"])
        if opponent:
            conn.execute(
                "UPDATE games SET opponent_username = ? WHERE id = ?",
                (opponent, row["id"]),
            )
            updated += 1
    if updated:
        conn.commit()


def _migrate(conn: sqlite3.Connection):
    """Add columns that may not exist in older databases."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(game_coaching)").fetchall()}
    if "opening_analysis_json" not in cols:
        conn.execute("ALTER TABLE game_coaching ADD COLUMN opening_analysis_json TEXT")
        conn.commit()
    if "player_feedback" not in cols:
        conn.execute("ALTER TABLE game_coaching ADD COLUMN player_feedback TEXT")
        conn.commit()

    game_cols = {r[1] for r in conn.execute("PRAGMA table_info(games)").fetchall()}
    if "opponent_username" not in game_cols:
        conn.execute("ALTER TABLE games ADD COLUMN opponent_username TEXT")
        conn.commit()
        # Backfill from PGN headers
        _backfill_opponent_usernames(conn)
    if "platform" not in game_cols:
        conn.execute("ALTER TABLE games ADD COLUMN platform TEXT DEFAULT 'chess.com'")
        conn.commit()

    player_cols = {r[1] for r in conn.execute("PRAGMA table_info(players)").fetchall()}
    if "fide_id" not in player_cols:
        conn.execute("ALTER TABLE players ADD COLUMN fide_id TEXT")
        conn.commit()
    if "fide_rating" not in player_cols:
        conn.execute("ALTER TABLE players ADD COLUMN fide_rating INTEGER")
        conn.commit()


SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE NOT NULL,
    display_name TEXT,
    age         INTEGER,
    rating      INTEGER
);

CREATE TABLE IF NOT EXISTS games (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL REFERENCES players(id),
    game_url        TEXT UNIQUE NOT NULL,
    pgn             TEXT NOT NULL,
    player_color    TEXT NOT NULL CHECK (player_color IN ('white', 'black')),
    player_rating   INTEGER,
    opponent_rating INTEGER,
    result          TEXT NOT NULL CHECK (result IN ('win', 'loss', 'draw')),
    time_control    TEXT,
    time_class      TEXT,
    date_played     TEXT,
    analysis_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (analysis_status IN ('pending', 'analyzing', 'complete', 'error')),
    coaching_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (coaching_status IN ('pending', 'complete', 'error'))
);

CREATE INDEX IF NOT EXISTS idx_games_player_id ON games(player_id);
CREATE INDEX IF NOT EXISTS idx_games_analysis_status ON games(analysis_status);
CREATE INDEX IF NOT EXISTS idx_games_date_played ON games(date_played);

CREATE TABLE IF NOT EXISTS move_analysis (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES games(id),
    move_number     INTEGER NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('white', 'black')),
    move_played     TEXT NOT NULL,
    best_move       TEXT,
    eval_before_cp  INTEGER,
    eval_after_cp   INTEGER,
    swing_cp        INTEGER,
    win_prob_before REAL,
    win_prob_after  REAL,
    classification  TEXT CHECK (classification IN
        ('excellent', 'good', 'inaccuracy', 'mistake', 'blunder')),
    pv_line         TEXT,
    UNIQUE(game_id, move_number, side)
);

CREATE INDEX IF NOT EXISTS idx_move_analysis_game_id ON move_analysis(game_id);

CREATE TABLE IF NOT EXISTS game_coaching (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id                 INTEGER NOT NULL REFERENCES games(id),
    provider                TEXT NOT NULL,
    narrative               TEXT,
    key_lesson              TEXT,
    practical_focus         TEXT,
    critical_moments_json   TEXT,
    opening_analysis_json   TEXT,
    coach_notes             TEXT,
    UNIQUE(game_id, provider)
);

CREATE TABLE IF NOT EXISTS player_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL REFERENCES players(id),
    period_start    TEXT NOT NULL,
    period_end      TEXT NOT NULL,
    stats_json      TEXT,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(player_id, period_start, period_end)
);
"""


def ensure_player(conn: sqlite3.Connection, username: str,
                  display_name: str | None = None, age: int | None = None,
                  rating: int | None = None, fide_id: str | None = None,
                  fide_rating: int | None = None) -> int:
    """Insert or update a player, returning the player id."""
    row = conn.execute(
        "SELECT id FROM players WHERE username = ?", (username,)
    ).fetchone()
    if row:
        if display_name or age or rating or fide_id or fide_rating:
            conn.execute(
                """UPDATE players SET
                    display_name = COALESCE(?, display_name),
                    age = COALESCE(?, age),
                    rating = COALESCE(?, rating),
                    fide_id = COALESCE(?, fide_id),
                    fide_rating = COALESCE(?, fide_rating)
                WHERE username = ?""",
                (display_name, age, rating, fide_id, fide_rating, username),
            )
            conn.commit()
        return row["id"]
    conn.execute(
        """INSERT INTO players (username, display_name, age, rating, fide_id, fide_rating)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (username, display_name, age, rating, fide_id, fide_rating),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM players WHERE username = ?", (username,)
    ).fetchone()["id"]
