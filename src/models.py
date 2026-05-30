# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

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


def backfill_acpl_for_games(conn: sqlite3.Connection, force: bool = False) -> int:
    """Backfill per-game ACPL from existing move_analysis data.

    Applies ±1000cp cap to stored evals AND ±1000cp cap to per-move loss,
    matching the Lichess/Chess.com standard. Only considers moves from the
    player's side.

    v1.7.1 fix: also gives zero loss to any move where the player chose the
    engine's best move (including checkmate-delivering moves like Qxf7#).
    Previously these registered as ~2000cp losses because Stockfish reports
    mate-encoded values that survive the per-eval cap but produce huge
    differences. See test_models.py::test_backfill_acpl_handles_mate_delivery.

    Args:
        conn: Open SQLite connection (init_db'd).
        force: If True, recompute ACPL for ALL analyzed games (overwriting
               any existing value). If False, only computes for games where
               `acpl IS NULL` (initial backfill behaviour).

    Returns the number of games whose ACPL was updated.
    """
    EVAL_CAP = 1000

    where_clause = "WHERE g.analysis_status = 'complete'"
    if not force:
        where_clause += " AND g.acpl IS NULL"

    games = conn.execute(
        f"SELECT g.id, g.player_color FROM games g {where_clause}"
    ).fetchall()

    if not games:
        return 0

    updated = 0
    for game in games:
        moves = conn.execute(
            """SELECT eval_before_cp, eval_after_cp, side, move_played, best_move
               FROM move_analysis WHERE game_id = ? ORDER BY move_number""",
            (game["id"],),
        ).fetchall()

        player_losses = []
        for m in moves:
            if m["side"] != game["player_color"]:
                continue
            before = m["eval_before_cp"]
            after = m["eval_after_cp"]
            if before is None or after is None:
                continue

            # v1.7.1: if the player chose the engine's #1 move, no loss.
            played = m["move_played"]
            best = m["best_move"]
            if played and best and played == best:
                loss = 0
            else:
                # Cap evals at ±1000 BEFORE computing difference
                capped_before = max(-EVAL_CAP, min(EVAL_CAP, before))
                capped_after = max(-EVAL_CAP, min(EVAL_CAP, after))

                if m["side"] == "white":
                    loss = max(0, capped_before - capped_after)
                else:
                    loss = max(0, capped_after - capped_before)

                # v1.7.1: per-move loss cap (safety net) — any single move
                # contributes at most EVAL_CAP cp to the average.
                loss = min(loss, EVAL_CAP)

            player_losses.append(loss)

        if player_losses:
            acpl = round(sum(player_losses) / len(player_losses), 1)
            conn.execute("UPDATE games SET acpl = ? WHERE id = ?", (acpl, game["id"]))
            updated += 1

    if updated:
        conn.commit()
    return updated


def _backfill_acpl(conn: sqlite3.Connection):
    """Legacy alias retained for the in-place migration on first init_db.
    Use `backfill_acpl_for_games(conn)` directly in new code."""
    updated = backfill_acpl_for_games(conn, force=False)
    if updated:
        print(f"  Backfilled ACPL for {updated} games (±1000cp capped)")


def _slugify(text: str) -> str:
    """v1.16.1: convert a display name to a URL slug.

    Rule (per user preference): lowercase + strip every
    non-alphanumeric character. NO separator — `"Evan Leong"` becomes
    `"evanleong"`, `"Mary Jane"` becomes `"maryjane"`. Falls back to
    `"player"` if the input produces an empty string (defensive).

    Why no hyphen: short single-word slugs (`evanleong` /
    `estellaleong`) are easier to type and remember than hyphenated
    forms. The user picked this format explicitly.

    Edge cases:
      - apostrophes ("O'Brien"  → "obrien")
      - hyphens ("Anne-Marie"  → "annemarie")
      - non-ASCII letters are stripped (the simplest rule for an
        English-name-only dataset); a future enhancement could
        unidecode them if needed.
    """
    s = re.sub(r"[^a-z0-9]+", "", (text or "").lower())
    return s or "player"


def _migrate(conn: sqlite3.Connection):
    """Add columns that may not exist in older databases."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(game_coaching)").fetchall()}
    if "opening_analysis_json" not in cols:
        conn.execute("ALTER TABLE game_coaching ADD COLUMN opening_analysis_json TEXT")
        conn.commit()
    if "player_feedback" not in cols:
        conn.execute("ALTER TABLE game_coaching ADD COLUMN player_feedback TEXT")
        conn.commit()
    # v1.6.0: coaching meta — history_games_injected, prompt_tokens_estimate,
    # provider, model — stored as JSON for forward-compatibility.
    if "coaching_meta_json" not in cols:
        conn.execute("ALTER TABLE game_coaching ADD COLUMN coaching_meta_json TEXT")
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

    if "acpl" not in game_cols:
        conn.execute("ALTER TABLE games ADD COLUMN acpl REAL")
        conn.commit()
        # Backfill ACPL from existing move analysis with ±1000cp cap
        _backfill_acpl(conn)

    move_cols = {r[1] for r in conn.execute("PRAGMA table_info(move_analysis)").fetchall()}
    if "clock_seconds" not in move_cols:
        conn.execute("ALTER TABLE move_analysis ADD COLUMN clock_seconds REAL")
        conn.commit()
    if "motifs_json" not in move_cols:
        # v1.14.0: per-critical-move tactical motif tags (fork/pin/skewer/
        # discovered_check/mate_threat/removing_defender/hanging_piece/
        # trapped_piece). Nullable — populated only for critical moves
        # (|cp_loss| >= 100). Pre-v1.14.0 rows just have NULL; frontend
        # treats NULL as "no motifs" and renders no badge row.
        conn.execute("ALTER TABLE move_analysis ADD COLUMN motifs_json TEXT")
        conn.commit()

    pattern_cols = {r[1] for r in conn.execute("PRAGMA table_info(player_patterns)").fetchall()}
    if "trend_summary" not in pattern_cols:
        conn.execute("ALTER TABLE player_patterns ADD COLUMN trend_summary TEXT")
        conn.commit()
    if "recent_form_review" not in pattern_cols:
        # v1.9.0: LLM-generated narrative across the last 10 coached games.
        # Distinct from trend_summary (which is a 30-day stats aggregate) —
        # this names specific games and identifies cross-game through-lines.
        conn.execute("ALTER TABLE player_patterns ADD COLUMN recent_form_review TEXT")
        conn.execute("ALTER TABLE player_patterns ADD COLUMN recent_form_review_updated_at TEXT")
        conn.commit()

    player_cols = {r[1] for r in conn.execute("PRAGMA table_info(players)").fetchall()}
    if "fide_id" not in player_cols:
        conn.execute("ALTER TABLE players ADD COLUMN fide_id TEXT")
        conn.commit()
    if "fide_rating" not in player_cols:
        conn.execute("ALTER TABLE players ADD COLUMN fide_rating INTEGER")
        conn.commit()
    if "lichess_username" not in player_cols:
        conn.execute("ALTER TABLE players ADD COLUMN lichess_username TEXT")
        conn.commit()
    if "is_active" not in player_cols:
        conn.execute("ALTER TABLE players ADD COLUMN is_active INTEGER DEFAULT 1")
        conn.commit()
    if "slug" not in player_cols:
        # v1.16.1: decouple the URL slug from the chess.com username.
        # `username` keeps the chess.com handle (used by the harvester
        # API); `slug` is the human-facing identifier used by URLs,
        # the API ?player= param, and the CLI --player flag. Auto-
        # derived from display_name via _slugify, but can be overridden
        # explicitly in config.yaml.
        conn.execute("ALTER TABLE players ADD COLUMN slug TEXT")
        conn.commit()
    # v1.16.1: UNIQUE INDEX is partial (only when slug IS NOT NULL) so
    # mid-migration or future-NULL rows don't trigger a constraint.
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_players_slug "
        "ON players(slug) WHERE slug IS NOT NULL"
    )
    conn.commit()
    # v1.16.1: backfill any NULL slugs (idempotent — runs on every
    # _migrate() call but the WHERE clause makes it a no-op once all
    # rows have slugs). This also catches edge cases where someone
    # manually NULL'd a slug for any reason. Collisions across the
    # batch are handled by carrying a `seen` set + DB collision check.
    null_rows = conn.execute(
        "SELECT id, display_name, username FROM players "
        "WHERE slug IS NULL ORDER BY id"
    ).fetchall()
    if null_rows:
        # Pre-load existing slugs so the seen-set starts populated —
        # avoids colliding with rows that already have slugs.
        seen: set[str] = {
            r["slug"] for r in conn.execute(
                "SELECT slug FROM players WHERE slug IS NOT NULL"
            ).fetchall()
        }
        for r in null_rows:
            base = _slugify(r["display_name"] or r["username"])
            slug = base
            suffix = 2
            while slug in seen:
                slug = f"{base}{suffix}"
                suffix += 1
            seen.add(slug)
            conn.execute(
                "UPDATE players SET slug = ? WHERE id = ?",
                (slug, r["id"]),
            )
        conn.commit()

    # v1.10.0: one-time migration of player_patterns.recent_form_review (v1.9.0
    # field) into the new journal_entries table. The legacy column stays
    # populated for backward-compat but new generations write to journal_entries.
    # Idempotent: only inserts if no journal entry exists for the player.
    existing = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='journal_entries'"
    ).fetchone()
    if existing:
        # Migrate one entry per player who has a non-null recent_form_review
        rows = conn.execute(
            """SELECT pp.player_id, pp.recent_form_review,
                      pp.recent_form_review_updated_at, pp.updated_at
            FROM player_patterns pp
            WHERE pp.recent_form_review IS NOT NULL AND pp.recent_form_review != ''"""
        ).fetchall()
        for r in rows:
            already = conn.execute(
                "SELECT 1 FROM journal_entries WHERE player_id = ? AND kind = 'review' LIMIT 1",
                (r["player_id"],),
            ).fetchone()
            if already:
                continue
            created_at = r["recent_form_review_updated_at"] or r["updated_at"]
            conn.execute(
                """INSERT INTO journal_entries
                (player_id, kind, platform, body, refs_json, provider,
                 metadata_json, created_at)
                VALUES (?, 'review', 'chess.com', ?, NULL, NULL,
                        '{"migrated_from": "player_patterns.recent_form_review"}', ?)""",
                (r["player_id"], r["recent_form_review"], created_at),
            )
        conn.commit()

    # v1.4.1 Hunter Mode: opponent_cache table for cached opponent profiles.
    # Schema is minimal; profile data is stored as a JSON blob, similar to
    # player_patterns.stats_json. Idempotent — safe to run on existing DBs.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS opponent_cache (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT NOT NULL,
            platform     TEXT NOT NULL,
            profile_json TEXT NOT NULL,
            fetched_at   TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(username, platform)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_opponent_cache_lookup "
        "ON opponent_cache(username, platform)"
    )

    # v1.4.4: opponent_games — accumulating local cache of opponent PGNs.
    # Used to (a) avoid re-fetching games we already have on each refresh
    # (fetch-since-last-known-date), (b) survive past chess.com/lichess
    # rate limits, and (c) provide representative PGNs for the "expand a
    # weakness opening row" UI. Pruned to a sliding window per
    # `features.hunter_lookback_months` and an optional hard cap per
    # `features.hunter_max_games_per_opponent`.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS opponent_games (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT NOT NULL,
            platform     TEXT NOT NULL,
            game_url     TEXT,
            pgn          TEXT NOT NULL,
            player_color TEXT,
            result       TEXT,
            opening_name TEXT,
            eco          TEXT,
            date_played  TEXT,
            fetched_at   TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(username, platform, game_url)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_opponent_games_lookup "
        "ON opponent_games(username, platform)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_opponent_games_date "
        "ON opponent_games(username, platform, date_played DESC)"
    )
    conn.commit()

    # v1.20.0: Hunter Mode deep scan — per-game tactical-motif analysis of
    # an opponent's games. opponent_games gains a cached per-game motif
    # summary (motifs_json) + an analyzed_at marker so a deep scan is
    # incremental (only newly-fetched games get the expensive Stockfish
    # pass). Both nullable — pre-v1.20.0 rows / un-scanned games are simply
    # "not analyzed yet" and surface no Tactical Blind Spots until scanned.
    opp_cols = {r[1] for r in conn.execute("PRAGMA table_info(opponent_games)").fetchall()}
    if "motifs_json" not in opp_cols:
        conn.execute("ALTER TABLE opponent_games ADD COLUMN motifs_json TEXT")
        conn.commit()
    if "analyzed_at" not in opp_cols:
        conn.execute("ALTER TABLE opponent_games ADD COLUMN analyzed_at TEXT")
        conn.commit()

    # v1.21.0: Tournament Prep — a player-scoped, named roster of opponents
    # for an upcoming event + combined cross-opponent analysis. Builds on
    # the Hunter Mode opponent cache (no opponent data is duplicated here —
    # the roster just references usernames; profiles live in opponent_cache).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tournaments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id   INTEGER NOT NULL REFERENCES players(id),
            name        TEXT NOT NULL,
            event_date  TEXT,
            notes       TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tournaments_player "
        "ON tournaments(player_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tournament_opponents (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
            username      TEXT NOT NULL,
            platform      TEXT NOT NULL DEFAULT 'chess.com',
            seed          INTEGER,
            added_at      TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(tournament_id, username, platform)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tournament_opponents_lookup "
        "ON tournament_opponents(tournament_id)"
    )
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

-- v1.10.0: journal_entries — chronological diary of coaching artifacts.
-- Each entry is tagged with a platform so the Journal can scope by
-- chess.com / lichess. `kind` is a free-form text column so new entry
-- types can be added without a schema migration.
CREATE TABLE IF NOT EXISTS journal_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL REFERENCES players(id),
    kind            TEXT NOT NULL,        -- 'review' (v1.10.0), 'note' (v1.12.0)
    platform        TEXT NOT NULL DEFAULT 'chess.com',  -- chess.com / lichess
    body            TEXT,                 -- LLM text or note body
    refs_json       TEXT,                 -- JSON array of referenced game IDs
    provider        TEXT,                 -- e.g. 'openai:gpt-5.5-pro-2026-04-23' (NULL for manual notes)
    metadata_json   TEXT,                 -- forward-compat slot for per-entry metadata
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_journal_entries_player_date
    ON journal_entries(player_id, created_at DESC);
"""


def _allocate_slug(conn: sqlite3.Connection, base: str,
                   excluding_player_id: int | None = None) -> str:
    """v1.16.1: return a UNIQUE slug derived from `base`, appending
    numeric suffixes ("2", "3", ...) if needed to avoid collisions.
    If `excluding_player_id` is given, that row's existing slug is
    ignored for the collision check (so updating a player's own
    slug doesn't fight itself)."""
    base = _slugify(base)
    candidate = base
    suffix = 2
    while True:
        if excluding_player_id is not None:
            existing = conn.execute(
                "SELECT 1 FROM players WHERE slug = ? AND id != ?",
                (candidate, excluding_player_id),
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT 1 FROM players WHERE slug = ?", (candidate,)
            ).fetchone()
        if not existing:
            return candidate
        candidate = f"{base}{suffix}"
        suffix += 1


def ensure_player(conn: sqlite3.Connection, username: str,
                  display_name: str | None = None, age: int | None = None,
                  rating: int | None = None, fide_id: str | None = None,
                  fide_rating: int | None = None,
                  lichess_username: str | None = None,
                  slug: str | None = None) -> int:
    """Insert or update a player, returning the player id.

    v1.16.1: accepts optional `slug` — the URL/CLI/API identifier
    decoupled from chess.com `username`. If not provided, derived
    from `display_name` (or `username` fallback) via _slugify, with
    collision-safe suffixing.
    """
    row = conn.execute(
        "SELECT id, slug FROM players WHERE username = ?", (username,)
    ).fetchone()
    if row:
        # Resolve slug for an existing player:
        # - If caller provided one explicitly, validate uniqueness
        #   excluding this row's own current slug.
        # - Otherwise leave the existing slug alone.
        resolved_slug = None
        if slug:
            resolved_slug = _allocate_slug(
                conn, slug, excluding_player_id=row["id"],
            )
        if (display_name or age or rating or fide_id or fide_rating
                or lichess_username or resolved_slug):
            conn.execute(
                """UPDATE players SET
                    display_name = COALESCE(?, display_name),
                    age = COALESCE(?, age),
                    rating = COALESCE(?, rating),
                    fide_id = COALESCE(?, fide_id),
                    fide_rating = COALESCE(?, fide_rating),
                    lichess_username = COALESCE(?, lichess_username),
                    slug = COALESCE(?, slug)
                WHERE username = ?""",
                (display_name, age, rating, fide_id, fide_rating,
                 lichess_username, resolved_slug, username),
            )
            conn.commit()
        return row["id"]
    # New player: derive slug from explicit arg, display_name, or username.
    slug_source = slug or display_name or username
    resolved_slug = _allocate_slug(conn, slug_source)
    conn.execute(
        """INSERT INTO players
        (username, display_name, age, rating, fide_id, fide_rating,
         lichess_username, slug)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (username, display_name, age, rating, fide_id, fide_rating,
         lichess_username, resolved_slug),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM players WHERE username = ?", (username,)
    ).fetchone()["id"]


def update_player(conn: sqlite3.Connection, player_id: int, **fields) -> bool:
    """Update a player's fields explicitly (not COALESCE — fields can be cleared to NULL).

    Only updates columns that are passed as keyword arguments.
    Returns True if a row was updated.
    """
    allowed = {"display_name", "age", "rating", "fide_id", "fide_rating", "lichess_username"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [player_id]
    conn.execute(f"UPDATE players SET {set_clause} WHERE id = ?", values)
    conn.commit()
    return conn.total_changes > 0
