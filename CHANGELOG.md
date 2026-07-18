# Changelog

All notable changes to ArrakisEngine will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.27.1] - 2026-07-18

### Fixed
- **Dashboard stuck on "Working…" after a crash or restart mid-pipeline.** If the
  process holding the pipeline lock died without releasing it (e.g. restarting
  the backend during a `run_all`), `pipeline_lock` was left at
  `status='running'` with a frozen heartbeat. `get_state()` correctly judged the
  lock **stale**, then copied the row's *raw* `'running'` string into the
  snapshot anyway — so `/api/pipeline/status` returned the contradictory
  `{task: null, status: "running"}` indefinitely and the Data Update panel spun
  on a task nobody was executing. A stale `running` now reports `idle`.
  The lock itself was always reclaimable (`is_busy()` returned False), so this
  was a false "stuck" indicator, not a real block — new runs could still start.

### Tests
- Backend **724 → 725**: regression lock asserting a stale `running` row is never
  reported as running by `get_state()` / `is_busy()` / `current_task()`, and that
  the lock stays reclaimable.

---

## [1.27.0] - 2026-07-15

### Changed
- **Upgraded every coaching provider to its current flagship reasoning model.**
  Claude → **Opus 4.8** (`claude-opus-4-8`), ChatGPT → **GPT-5.6 "Sol"**
  (`gpt-5.6-sol`), Gemini → `gemini-3.5-flash`, Grok → `grok-4.5`, DeepSeek →
  `deepseek-v4-pro` (the old `deepseek-reasoner` alias retires 2026-07-24),
  Qwen → `qwen3.7-max`; Mistral stays on the latest-tracking `mistral-medium-latest`
  and Ollama on the local `deepseek-r1:8b`. Both the registry defaults and the
  live `config.yaml` overrides were updated (the config override wins).

### Added
- **Configurable reasoning effort** — new `coaching.reasoning_effort` setting
  (default **`xhigh`** = "extra high") + a **Reasoning Effort** dropdown in
  Settings → Coaching (low / medium / high / xhigh / max). Applied where the
  provider exposes a granular scale — Claude (`output_config.effort`), ChatGPT
  (`reasoning.effort`), Mistral (`reasoning_effort`) — and clamped down to each
  provider's ceiling by `_effort_for` (e.g. `max`→`xhigh` for ChatGPT,
  `xhigh`/`max`→`high` for Mistral). Gemini/Grok/DeepSeek/Qwen reason by default
  and ignore it; Ollama is local.

### Docs
- Corrected the long-standing CLAUDE.md claim that a "reasoning-models-required"
  contract is *code-enforced in `llm_providers.py`* — there is no allowlist; it's
  a convention held by the defaults + the adaptive-thinking / Responses-API paths.

### Tests
- Backend **701 → 724** (+23): `_effort_for` clamp matrix; mock-based checks that
  `output_config.effort` (Claude) and `reasoning.effort` (ChatGPT) reach the SDK
  call and default to `xhigh`; coaching-settings GET defaults + `reasoning_effort`
  persist/reject round-trip; all hardcoded model IDs refreshed.

---

## [1.26.3] - 2026-07-12

### Added
- **Edit a game's date/time (timing) from the game detail page.** OTB PGNs carry
  a date but no time, so imported games showed a midnight placeholder
  (`… 00:00:00`). The **Edit details** editor (formerly "Edit type") now has a
  **Date** field (a date+time picker) alongside Category and Type — set the real
  date and time the game was played. `PUT /api/games/{id}/classification` accepts
  `date_played` (a date or datetime; normalized to `YYYY-MM-DD HH:MM:SS`).

### Tests
- Backend **698 → 701** (+3): set date+time, a date-only value normalizes to
  midnight, and an unparseable date is rejected.

### Added
- **Reclassify a game's category & type from the game detail page.** A new
  **Edit type** control (next to Edit ratings) lets you set a game's **Category**
  (Chess.com / Lichess / **Competition**) and **game type** (Classical / Rapid /
  Blitz / Bullet / Daily). This is for OTB games imported through the generic
  Import path (which land as a plain import with no time class) — mark them as a
  Competition + Classical without re-uploading.
- **Reclassifying to Competition also applies the privacy strip.** Setting a
  game's category to Competition removes the `Event`/`Site` (name + venue)
  headers from the stored PGN and re-hashes it — the same treatment a native
  competition import gets (v1.26.1). Backed by `PUT /api/games/{id}/classification`
  (validates platform + time_class, 404 for a missing game).

### Tests
- Backend **695 → 698** (+3): reclassify-to-competition sets platform/time_class
  and strips the name/venue from the stored PGN; invalid platform/time_class are
  rejected; missing game is 404.

---

## [1.26.1] - 2026-07-12

### Changed (privacy)
- **Competition imports no longer store the tournament name or location.** The
  PGN `Event` (competition name) and `Site` (venue) headers are stripped on
  import for `platform="competition"` games — neither the stored PGN nor its
  dedup hash carries them, so they can't leak via the game detail, the API, or
  PGN export. Player names, date, result, round/board, and the moves are kept.
  Existing competition games in the local DB were scrubbed in place.

### Tests
- Backend **693 → 695** (+2): a competition import strips `Event`/`Site` (name +
  venue) while keeping players/result/moves; non-competition parsing leaves
  headers untouched. Test fixtures no longer carry any real competition name,
  venue, or opponent name.

---

## [1.26.0] - 2026-07-12

### Added
- **Three FIDE ratings per player — Classical, Rapid, Blitz.** FIDE publishes a
  separate rating for each time control, so the single "FIDE Rating" field is now
  three. The Settings player form (Add + Edit, all players) has a **FIDE Ratings**
  row with Classical / Rapid / Blitz inputs; each is optional (blank = unrated).
  The player list and player card show the three compactly (e.g. `FIDE: C 1516 ·
  R 1480 · B 1470`), Classical as the card headline.

### Changed
- **FIDE ratings no longer override the chess.com / lichess rating.** Previously a
  player's single FIDE rating replaced their platform rating everywhere (player
  cards, coaching). Now FIDE ratings are FIDE-specific: chess.com and lichess use
  their own ratings, and the three FIDE ratings are shown as separate FIDE info.
  The player's primary rating reverts to the latest game's rating (or the stored
  platform rating).

### Migration
- Adds `fide_rating_classical` / `fide_rating_rapid` / `fide_rating_blitz` to
  `players`; the existing single `fide_rating` is **backfilled into Classical** so
  no data is lost (runs automatically on next start; the legacy column is kept).

### Tests
- Backend **691 → 693** (+2, plus new migration-column assertions): create/update
  a player with the three FIDE ratings, and a guard that FIDE does not override
  the platform rating. Settings form verified live (three FIDE inputs render).

---

## [1.25.1] - 2026-07-12

### Added
- **Editable ratings on the game detail page.** Over-the-board competition PGNs
  carry no `WhiteElo`/`BlackElo`, so imported games showed both players as `(?)`.
  The matchup bar now has an **Edit ratings** control: click it to reveal inline
  inputs for each player, enter the FIDE (or any) ratings, and Save. Leaving a
  field blank stores it as *unrated* (NULL). Backed by a new
  `PUT /api/games/{id}/ratings` endpoint (validates 0–4000 or null, partial
  updates leave the other field untouched).

### Tests
- Backend **687 → 691** (+4): set/clear ratings, partial update, out-of-range
  rejection, and 404 for a missing game.

---

## [1.25.0] - 2026-07-12

### Added
- **Competition games — import over-the-board tournament PGNs.** Games played
  in person exist only as a PGN, never on chess.com / lichess. The Import page
  now has an **"Over-the-board / competition game"** mode:
  - **Tagged as a distinct source.** Competition games get `platform="competition"`
    and show a 🏆 badge in the games list and game detail, and a **Competition**
    option in the Games platform filter (was a hardcoded chess.com/lichess binary
    that mislabeled everything else as chess.com).
  - **Game type sets the time control.** An OTB PGN carries no machine
    `TimeControl`, so you pick the type — **Classical / Rapid / Blitz** — which
    sets `time_class` (default Classical). The game then appears under its
    time-class chip in Games and Reports (the v1.24.2 data-driven filter).
  - **Color mapped to the in-system player.** The PGN names the real player
    ("Evan Leong"), not a chess.com handle, so color is auto-detected by matching
    the White/Black header against the player's own display name — no manual
    "played as" needed, even across a batch.
  - **File upload + multi-game.** Upload a `.pgn` file (or paste). A multi-game
    tournament file imports **every game at once**; an undecided game (`Result
    "*"`) is reported as skipped rather than failing the batch. Each game runs
    through the same Stockfish → coaching pipeline as an online game.
  - Backend: new `parse_pgn_multi` + `time_class_override` in `src/pgn_io.py`;
    `/api/import-pgn` accepts `platform` + `time_class` and returns a batch
    summary (`created_count` / `existing_count` / `skipped`) while keeping its
    single-game keys. **No schema change** — reuses existing `platform`,
    `time_class`, `opponent_username`, `date_played` columns. New frontend
    `lib/platforms.ts` centralizes the per-source icon/label.

### Docs
- Refreshed the test-count references to **687 backend / 228 frontend** (~915
  total); current release → v1.25.0.

### Tests
- Backend **680 → 687** (+7): `parse_pgn_multi` split + skip-undecided,
  `time_class_override`, the real OTB PGN (color-by-name → loss, classical), and
  competition-import API tests (platform stored, display-name color detect, batch
  counts, dedup, skipped).
- Frontend **225 → 228** (+3): `platformMeta` — Competition icon/label + fallback.

---

## [1.24.2] - 2026-06-05

### Added
- **Blitz (and any other time control) now appears in the Reports filter.** The
  Reports time-class filter was hardcoded to Rapid / Daily / All, so blitz and
  bullet games — which the backend has always aggregated — had no chip. The
  filter is now **data-driven**: chips are derived from the time classes
  actually present in the loaded report (`report.time_class_stats`), ordered
  canonically (bullet → blitz → rapid → daily) with **All** last. A class shows
  up only when the player has in-window games of it, so there are no empty
  chips, and future time controls need no code change. The default stays
  **Rapid** (falling back to the first available class — never an empty view —
  when a player has no rapid games).
  - Frontend-only: `report.py`, the `/api/report` endpoint, and
    `report-view.tsx`'s filter were already time-class-agnostic; only the
    hardcoded chip list in `reports/page.tsx` needed replacing (new exported
    `buildTimeClassChips` helper).

### Docs
- Refreshed the test-count references (which had drifted at v1.22.5) to the
  current **680 backend / 225 frontend** (~905 total); ROADMAP current release
  → v1.24.2.

### Tests
- Frontend **219 → 225** (+6): `buildTimeClassChips` — Blitz surfaces when
  present, canonical ordering + All-last, default Rapid, fallback when no rapid,
  empty report → only All, and a capitalized label for unknown classes.
  Verified live: the Reports page renders the data-driven chips with Rapid
  active by default and no console errors.

---

## [1.24.1] - 2026-06-05

### Fixed
- **Nav items off-screen.** v1.24.0 added an 8th nav item (Import), which pushed
  the last entries (Tournament, Reports) past the right edge of the single-row,
  hidden-scrollbar nav — they looked missing. The nav now **wraps** (`flex-wrap`)
  so every item is reachable at any window width.

## [1.24.0] - 2026-06-05

### Added
- **PGN data I/O — import and export** (`src/pgn_io.py`), the open, portable
  data layer. Get a game into the system and back out again; the format
  plumbing is open, the moat (OCR capture + correction) lives elsewhere.
  - **Import:** `POST /api/import-pgn` — paste/upload a PGN; it parses, legality-
    validates, ingests as a `pending` game, and (by default) analyzes + coaches
    it. New **Import** nav item + `/[player]/import` page. Handles undecided
    (`*`) results via an explicit `result` (win/loss/draw) — for in-progress or
    unrecorded OTB scoresheets.
  - **Export:** `POST /api/games/export` — `{ids, annotated}` → a `.pgn` file.
    **Raw** (the stored PGN) or **annotated** (Stockfish `{[%eval]}` comments +
    classification NAGs: $4 blunder / $2 mistake / $6 inaccuracy). Surfaced as
    an **Export PGN** button on the game-detail page and a select-some/all +
    **filter-aware bulk export** on the games list (the existing filter +
    selection infra generalized — `GamesTable` gained `selectable`/
    `maxSelectable`, replacing the compare-only cap).
- `tests/test_pgn_io.py` (12) + a native-Import nav test.

### Note
- Generic PGN import/export is now an **open** feature. Only OCR scoresheet
  *capture* + move correction remains reserved for the commercial layer.

## [1.22.5] - 2026-06-05

### Fixed
- **A transient backend hiccup during analysis crashed the whole dashboard
  page** with the Next.js error overlay ("API error: 500 Internal Server
  Error"). Two layers:
  - The 500 itself was the dev proxy's response to a connection reset from the
    single-threaded-server freeze during a heavy analyze — already fixed in
    v1.22.3 (ThreadingHTTPServer + read-only status poll). A `serve` restart
    is required to pick that up on a long-running instance.
  - **Frontend hardening (defense-in-depth):** `fetchJSON` now retries the
    backend's explicitly-retryable **503 "Database is busy"** response (up to
    2 times, 500ms/1000ms backoff) before surfacing an error, so a momentary
    DB-busy blip while a "Run All" analysis holds the write lock no longer
    nukes the page. Non-503 errors still throw immediately (no masking of real
    failures).

### Tests
- Frontend suite green at **218**; `tsc` + `next build` clean.

---

## [1.22.4] - 2026-06-05

### Fixed
- **"Run All Steps" couldn't be cancelled during analysis.** Clicking Cancel
  while the analyze step was running (minutes per game) did nothing — the
  pipeline ground through every pending game before the cancel took effect.
  Root cause: `run_full_pipeline` only passed the `cancel_event` to the *coach*
  step (its docstring even said "the coaching step stops gracefully"); harvest,
  analyze, and patterns ignored it. Now:
  - `analyze_pending` accepts a `cancel_event` and checks it **before each
    game**, so analysis stops between games (the in-progress game finishes;
    the rest stay `pending` and resume on the next run).
  - `run_full_pipeline` threads the `cancel_event` into `analyze_pending` and
    checks for cancellation **between every step** (after harvest, after
    analyze, after patterns), returning early with a `cancelled: True` result
    instead of pressing on to the next phase.

### Tests
- Backend **665 → 668**: `analyze_pending` stops with a pre-set cancel event
  (no games analyzed, all stay pending); `run_full_pipeline` cancelled
  mid-analyze skips patterns + coach and threads the event into the analyzer;
  cancel-before-analyze stops after harvest.

---

## [1.22.3] - 2026-06-05

### Fixed
- **Dashboard froze ("socket hang up" / "database is locked") during a running
  analyze.** While the analyzer wrote per-move rows, the frontend's
  `/api/pipeline/status` poll hit `database is locked` and the connection was
  reset. Two compounding causes, both fixed:
  1. **`pipeline_state.get_state()` ran `init_db()` on every status poll** —
     re-executing `executescript(SCHEMA)` + `CREATE INDEX` (schema *writes*)
     ~once per second. Those writes contended with the analyzer's writes and
     blocked for the full 30s `busy_timeout`. The lock read is now a
     lightweight read-only `SELECT` (WAL readers never wait on the writer),
     capped at a 2s timeout, and falls back to the in-memory mirror on any
     transient `OperationalError` — the status poll never blocks or raises.
  2. **The dashboard ran on a single-threaded `HTTPServer`**, so one
     lock-waiting request stalled *every* other request → the frontend's
     concurrent polls were connection-reset. Switched to
     `ThreadingHTTPServer` (each request gets its own SQLite connection; the
     pipeline lock remains the cross-request coordinator).
- **Time-bomb in the v1.19.0 weakness-alert tests.** `_seed_priority_fork`
  hardcoded game dates (`2026-05-0N`); once the calendar advanced > 30 days
  past them, the games fell outside the escalation window, fork dropped below
  the priority tier, and no alert fired → the tests failed purely due to the
  passage of time. Dates are now seeded relative to `now`.

### Tests
- New regression test `test_status_poll_does_not_block_under_write_lock`
  (`tests/test_pipeline_state.py`): holds a WAL write lock and asserts
  `get_state()` returns in < 3s with the correct task/status. Backend **665
  passed**.

---

## [1.22.2] - 2026-05-30

### Fixed
- `tests/test_hunter.py::TestComputeOpponentMotifSummary::test_none_when_no_analyzed_games`
  called `compute_opponent_motif_summary(..., db_path=None)`, which opens the
  default DB via `get_connection` — but that DB never had `init_db()` run, so it
  raised `sqlite3.OperationalError: no such table: opponent_games`
  (`src/hunter.py`). It now uses the `db_path` fixture + `init_db(db_path)`
  (mirroring the sibling `test_sums_distinct_games_exactly`), querying an
  empty-but-existing `opponent_games` table and correctly returning `None`.
  Production code was never affected — real runs always `init_db` first.
  Full suite green (664 passed).

## [1.22.1] - 2026-05-30

### Changed
- **Route registry for the dashboard server (`src/dashboard_server.py`).**
  HTTP dispatch is now table-driven — `do_GET`/`do_POST`/`do_PUT`/`do_DELETE`
  look up module-level `_{GET,POST,PUT,DELETE}_ROUTES` dicts (exact path →
  handler) and ordered regex-route lists, replacing the hardcoded if/elif
  chains. New public `register_route(method, path, handler)` and
  `register_regex_route(method, pattern, handler)` let out-of-tree code add
  endpoints before `serve()` starts (e.g. the commercial Atreides build
  registering `/api/import-pgn` into the core dashboard instead of running a
  separate sidecar). Pure refactor — every existing endpoint registered
  exactly as it dispatched before, proven by the unchanged
  `test_dashboard_server.py` suite. (roadmap §6)

## [1.22.0] - 2026-05-30

### Added
- **Extensible nav bar (`frontend/components/nav-bar.tsx`).** `<NavBar>` now
  accepts an optional `extraItems` prop (`NavItem[]`, defaults to `[]`),
  rendered after the base `NAV_ITEMS` through the same player-scoping mapping
  (player-scoped entries get the `/${currentPlayer}` prefix). The `NavItem`
  type and `NAV_ITEMS` array are exported so out-of-tree code can compose its
  own entries (e.g. the commercial Atreides build surfacing a PGN-import page)
  without forking the component. The OSS `app/layout.tsx` caller passes
  `extraItems={[]}` — no behavior change. (roadmap §6)

## [1.21.0] - 2026-05-30

### Added
- **Tournament Prep — multi-opponent Hunter Mode.** Hunter Mode scouted one
  opponent at a time; real prep is for an *event*. v1.21.0 adds a saved, named
  **roster** of opponents with a **combined cross-opponent analysis** so a kid
  can prep a whole tournament field at once.

  **Persistence (`src/models.py`, `src/tournament.py`).** Two new tables —
  `tournaments` (player-scoped, named, optional event date/notes) +
  `tournament_opponents` (roster, de-duped on username+platform). `tournament.py`
  owns the CRUD (mirrors `journal.py`: ValueError → 400/404). No opponent data
  is duplicated — the roster references usernames; profiles live in the Hunter
  Mode caches.

  **Combined analysis (`compute_tournament_prep`).** Cache-only (no network, no
  Stockfish) aggregation across the roster:
  - **Opening targets / cautions** — groups each opponent's weak/strong openings
    by `(opening, color)`: "Prep the Italian — 5 of 8 lose to it" /
    "Avoid the Najdorf — 4 win with it." Only openings ≥`tournament_min_shared`
    opponents share surface (keeps single-opponent noise out).
  - **Field blind spots** — sums the v1.20.0 per-opponent Deep-Scan motif
    summaries into a field-level `motif_summary` (rendered by the existing
    `<MotifThemes>` card) + `scan_coverage`, so partial coverage never reads as
    "the whole field."
  - Opponents without a cached profile are marked `pending`.

  **Surfaces.** A new **Tournament** tab → list of saved events + a detail view
  with roster management (reuses `OpponentSearch`), a **Prep Roster** button
  (background job that warms every opponent's opening-profile cache; fast, no
  Stockfish; progress via `pipeline_state`), an **Opening Targets** panel, a
  per-opponent card grid (each links to the full Hunt view + shows Deep-Scan
  coverage), and a **Field Blind Spots** card. The Hunt page gains an **"Add to
  tournament"** control — scout one opponent, drop them onto a roster.
  CLI: `python main.py tournament-prep --id <n>`.

  **API.** GET `/api/tournaments` + `/api/tournament`; POST
  `/api/tournament/{create,add-opponent,remove-opponent,delete}` +
  `/api/pipeline/tournament-prep` (background, single-task lock). All guarded by
  `features.hunter_mode`. Additive schema (two new tables) — no breaking change.

### Tests
- Backend **639 → 658** (+19): roster CRUD + validation, `compute_tournament_prep`
  aggregation (opening grouping/threshold, cautions, field blind-spots sum,
  pending opponents, scan coverage), the HTTP create→add→list→prep flow, and the
  `tournament-prep` CLI dispatch.
- Frontend **213 → 216** (+3): `OpeningTargets` headline + prep/avoid lists +
  empty state.
- Manual smoke: created a roster for `evanleong`, added cached opponents, ran
  Prep Roster → "Prep the Italian — 2 of this field lose to it."

---

## [1.20.0] - 2026-05-29

### Added
- **Hunter Mode Deep Scan — opponent tactical blind spots.** Hunter Mode has
  been opening-level and fast-by-design since v1.4.1: it tells you *what an
  opponent plays*, never *which tactics they miss*. v1.20.0 adds an opt-in
  **Deep Scan** that runs Stockfish + the 12 motif detectors over the
  opponent's recent games and surfaces the themes they MISS — the patterns to
  bait them into.

  **Engine pass (`analyze_opponent_game`, `src/hunter.py`).** A focused,
  read-only mirror of the analyzer's motif loop: walks one game, and for each
  move where the *opponent* was to move and lost ≥50cp, detects played-vs-best
  motifs and tallies the misses (with a per-motif phase breakdown). Reuses the
  analyzer's `score_to_cp`/`cap_eval`/`MOTIF_DETECTION_THRESHOLD_CP` and
  `motifs.detect_motifs` — no DB writes, no ACPL/clock/classification overhead.

  **Scan orchestration.** `deep_scan_opponent` analyzes the opponent's last N
  accumulated games (config `features.hunter_scan_games`, default 20) at the
  same depth as player analysis (depth 22). **Incremental**: a per-game result
  + `analyzed_at` marker are cached on each `opponent_games` row, so a re-scan
  only analyzes newly-fetched games. `compute_opponent_motif_summary`
  aggregates the per-game results into the same shape as the player-side
  `motif_summary`, so the frontend `<MotifThemes>` card renders opponent data
  with zero new chart code.

  **Surfaces.** A new **"Tactical Blind Spots"** section on `/[player]/hunt`
  with a "Deep Scan (Stockfish)" button (carrying a time warning — depth-22
  over 20 games is minutes), a live progress bar, and on completion the
  `<MotifThemes>` card + a deterministic headline ("Bait pins — misses 82% of
  pin tactics across N critical moves"). `GET /api/hunt/profile` now carries
  `motif_summary` + a `deep_scan` status block; `python main.py hunt-scan
  --opponent X` runs the same scan from the CLI.

  **Opt-in + safe.** The scan only runs via the explicit
  `POST /api/pipeline/hunt-scan` (background job) or the CLI — never
  automatically, so the default profile fetch stays sub-second. It reuses the
  single-task `pipeline_state` lock so it can't collide with
  harvest/analyze/patterns, and fails gracefully with a brew-install hint when
  Stockfish is missing. Additive schema (two nullable `opponent_games`
  columns) — no breaking change.

### Tests
- Backend **627 → 639** (+12 unit) plus a new Stockfish-gated integration test:
  `compute_opponent_motif_summary` exact per-phase aggregation,
  `get_deep_scan_status`, `_resolve_opponent_color` (player_color → PGN-header
  fallback → skip), incremental skip, the `hunt-scan` CLI dispatch (depth/limit
  resolution + Stockfish-missing path), and the `/api/hunt/profile` enrichment
  shape.
- Frontend **210 → 213** (+3): the Deep Scan section renders the button + time
  warning when un-scanned, and the Tactical Blind Spots card + "Bait …"
  headline after a scan.
- Manual smoke: `python main.py hunt-scan --opponent oligonucleotide_88x`
  analyzed 8 games incrementally and surfaced "deflection" as the top blind
  spot.

---

## [1.19.0] - 2026-05-29

### Added
- **Recurring weakness escalation.** The motif aggregation (v1.15.0–v1.16.0)
  already found a player's most-missed tactical themes, but it treated every
  run the same — "you missed forks" got restated whether it was a one-off or a
  pattern running game after game. v1.19.0 detects *persistence* and escalates
  the coaching register accordingly: stop repeating the diagnosis, start
  prescribing a fix.

  **Signal (`_compute_motif_summary`, `src/patterns.py`).** Per motif we now
  track two things across the 30-day window:
  - **distinct-game spread** — how many *separate* games show the missed
    motif (not raw instances: "13 misses across 2 games" is not recurring;
    "missed in 6 different games" is). This sets the base tier:
    ≥3 games → `watch`, ≥5 → `focus`, ≥8 → `priority`.
  - **recency streak** — consecutive most-recent games (with motif data) in
    which the motif was missed. An active streak of ≥3 *boosts* the tier one
    level (watch→focus, focus→priority).

  A small-sample guard (`_escalation_tier`) suppresses all escalation until at
  least 4 games carry motif data, so a brand-new account can't trigger a
  "priority" alert off one rough patch. Each `by_motif` row gains
  `missed_games`, `streak`, and `escalation`; a new top-level
  `escalated_weaknesses` list (watch+, sorted priority→watch) plus
  `games_with_motif_data` drive the three surfaces below.

  **Surface 1 — coaching.** `build_trajectory_block` now leads with a prominent
  `⚠ RECURRING WEAKNESS: fork — missed in 6 of the last 9 games (3 in a row),
  mostly in the middlegame. Treat as the #1 fix.` line when a focus/priority
  weakness exists, and records `recurring_weakness` + tier in
  `coaching_meta_json`. The `TREND_PROMPT` and `GAME_COACHING_PROMPT` gained a
  v1.19.0 escalation clause: when a weakness is flagged recurring, **lead with
  it and prescribe a concrete, observable drill** ("10 middlegame fork puzzles
  daily; before every capture, ask what your knight forks") rather than a
  restated diagnosis.

  **Surface 2 — Patterns card.** The Tactical Themes card shows a per-row
  escalation badge — 🔴 priority / 🟠 focus / 🟡 watch — reading "missed in N of
  M games · K in a row" (streak suffix only when ≥2).

  **Surface 3 — Journal.** A one-time `weakness_alert` Journal entry is filed
  for each **priority**-tier weakness, with a motif-specific drill in the body.
  Reuses the `journal_entries` table (no migration); the existence of an open
  alert row *is* the fire-once state — de-duped per motif within the window so
  an ongoing weakness files **one** entry per episode, not on every run.
  weakness_alert entries are immutable (no edit/delete) and render with a ⚠️
  icon, "Priority Weakness" label, and a red timeline node.

  **Trigger discipline.** Alerts fire only on the explicit user-driven paths —
  the `patterns` CLI and the `/api/pipeline/patterns` dashboard trigger
  (`compute_player_patterns(emit_weakness_alerts=True)`). The silent
  auto-refresh inside `coach_game` leaves the flag `False`, so coaching never
  surprise-spawns Journal entries.

### Tests
- Backend **597 → 627** (+30): `_escalation_tier` boundary/streak/guard cases,
  `_compute_motif_summary` distinct-game spread + streak + `escalated_weaknesses`
  shape, `build_trajectory_block` RECURRING line + diag, prompt source-grep
  guards, `create_weakness_alert` fire-once/different-motif/past-window de-dup,
  and `compute_player_patterns(emit_weakness_alerts=…)` integration.
- Frontend **205 → 210** (+5): escalation badge (tier + "N of M games" + streak
  suffix; absent when none/missing), and the `weakness_alert` Journal kind
  (⚠️ icon + "Priority Weakness" label, no edit menu).
- Manual smoke on Evan's DB: 51 games with motif data → deflection (priority,
  17 games), hanging_piece (priority, 10), overloaded_defender (priority, 10),
  pin (focus, 6); exactly 3 priority alerts filed, re-run idempotent.

---

## [1.18.5] - 2026-05-29

### Removed
- **The "Recent Form Review moved to its own tab → Open Journal" pointer
  banner** at the top of the Patterns page. Added in v1.10.0 when the
  Recent Form Review card relocated to the Journal tab, it was always
  meant to be temporary ("drop this banner after a couple of releases"
  per its own code comment). The Journal tab has been a permanent
  fixture for 8 releases now, so the redirect hint is long-stale.
  Removed the banner and its now-orphaned `next/link` import.

### Tests
- No new tests. Frontend suite unchanged at **205**; `next build` clean
  (confirms the orphaned import was fully removed).

---

## [1.18.4] - 2026-05-29

### Docs
- **Full documentation refresh to v1.18.3.** README.md, CLAUDE.md, and
  docs/architecture.md had drifted ~10 versions — they were frozen at
  v1.8.0, missing the entire motif arc, Journal, Recent Form Review,
  slug routing, trap expansion, mobile viewport, and chart rework.
  This brings all three current. No code changes.

  Corrected facts across the docs:
  - Version v1.8.0 → **v1.18.3**
  - Backend tests 362–384 → **597**; frontend 66–76 → **205**
  - Traps ~102 → **1,475** (v1.18.0 substring filter)
  - Added the **12 tactical motifs** (was unmentioned), the
    `_compute_motif_summary` aggregation + per-phase splits, and the
    Tactical Themes Patterns card
  - Added the **Journal** subsystem (journal_entries table, reviews +
    parent notes, `/[player]/journal` route, `journal.py`)
  - Documented the **slug ≠ username** model (v1.16.x): slug for
    URLs/API/CLI, chess.com username for the harvester only;
    `_resolve_player_id` resolver; slug-only lookups
  - Updated schema tables (`motifs_json`, `journal_entries`, `slug`,
    `motif_summary`, `coaching_meta` motif fields)
  - Updated the CLI command list (`trend`, `review`, `note`,
    `rescan-motifs`, `backfill-acpl`) and API endpoint tables
    (`/api/journal`, `/api/journal/review`, `/api/journal/note`)
  - Updated file trees (`motifs.py`, `journal.py`, `lib/motifs.ts`,
    `lib/chart-format.ts`; removed the deleted `export.py`)
  - Noted mobile viewport (v1.18.2) and the time-scale rating chart
    (v1.18.3)

  CHANGELOG itself was already per-release accurate and is unchanged
  except for this entry. ROADMAP was already current (v1.18.2 edit).

---

## [1.18.3] - 2026-05-29

### Fixed
- **Rating Progression chart had a cluttered, misleading X-axis.**
  Two compounding bugs:
  1. **Categorical axis, not time-scaled.** The chart used
     `dataKey="date"` with raw date strings, so Recharts treated
     each of the ~590 games as an equal-width category and thinned
     tick labels by *index*. Time wasn't to scale — gaps where the
     player played little looked the same width as busy weeks, and
     the visible tick dates appeared irregular (Nov 26 → Dec 3 →
     Dec 8 … then jumping to Feb 16 → Apr 5).
  2. **Tick formatter leaked the time-of-day.** It split
     `"2025-10-01 10:28:12"` on `-` and used `parts[2]` = `"01
     10:28:12"`, so labels read `10/01 10:28:12` instead of a clean
     month.

### Changed
- **Time-scaled X-axis.** Axis is now `type="number"` `scale="time"`
  over epoch-ms (`domain=["dataMin","dataMax"]`), so the horizontal
  position of every game reflects *when* it was actually played.
  Quiet stretches compress; busy stretches spread out — an honest
  timeline.
- **Clean month labels** via the new `formatAxisTick` helper:
  month abbreviation, with a 2-digit year shown only at January
  (finance-chart convention) — "Oct", "Nov", "Dec", "Jan '26",
  "Feb"… Unambiguous across the year boundary, uncluttered within.
  `minTickGap={48}` spaces ticks by pixels, so the dense series
  never overcrowds the axis.
- **Date-range zoom.** Added a Recharts `Brush` below the chart —
  drag the handles to focus a date window and the main plot
  re-scales to the selection. Traveller width bumped for easier
  touch targets (the app went mobile-usable in v1.18.2).
- **Tooltip** now shows a clean `"Oct 1, 2025"` instead of the raw
  `"2025-10-01 10:28:12"` timestamp.

### Added
- **`frontend/lib/chart-format.ts`** — `parsePlayedDate`,
  `formatAxisTick`, `formatTooltipDate`. Extracted so the date logic
  is unit-testable independent of the Recharts render tree.

### Tests
- New `frontend/lib/__tests__/chart-format.test.ts` (10 tests):
  DB-format parsing, ISO-T form, NaN handling, chronological
  ordering, bare-month vs January-year labels, the no-time-leak
  regression lock (the exact v1.18.3 bug), and tooltip formatting.
- Updated the rating-chart test's recharts mock to include `Brush`.
- Frontend: 195 → **205**. Backend unchanged at 597.

---

## [1.18.2] - 2026-05-29

### Fixed
- **Mobile viewport meta tag was missing.** The app shipped with 74
  responsive Tailwind breakpoint classes (`sm:`/`md:`/`lg:`),
  progressive table column-hiding, an auto-sizing chess board, and
  a mobile-aware nav — but `app/layout.tsx` had no viewport meta
  tag. Without it, mobile browsers render the page at desktop width
  and zoom out, so **none of those breakpoints ever fired on a
  phone**. The README claimed "fully mobile-responsive (320px+)" in
  three places; that claim was aspirational until now.

  Fix: added a Next.js 16 `Viewport` export to the root layout,
  which injects
  `<meta name="viewport" content="width=device-width, initial-scale=1">`.
  The existing responsive CSS now actually works on mobile — the
  Games table sheds low-priority columns, the board fits the screen,
  the layout flows at 1:1 scale instead of desktop-zoomed-out.

  Deliberately did NOT set `maximumScale` / `userScalable=false` —
  locking pinch-zoom is an accessibility anti-pattern, and a
  9-year-old may genuinely want to zoom the board.

### Tests
- New `frontend/app/__tests__/layout.test.tsx` (4 tests): asserts
  the `viewport` export exists with `width=device-width`,
  `initialScale=1`, does NOT lock zoom, and sits alongside (not
  replacing) the page metadata. Regression lock against the exact
  "missing meta tag" gap class this ship fixes.
- Frontend: 191 → **195**. Backend unchanged at 597.

### Docs
- README mobile-responsive bullet now documents the mechanism
  (viewport meta tag), not just the claim.
- ROADMAP mobile-status line updated: core pages are now mobile-
  ready; dense chart grids still benefit from a future mobile-
  layout pass.

---

## [1.18.1] - 2026-05-29

### Fixed
- **`rescan-motifs --player <slug>` returned "No analyzed games
  match".** A v1.16.4 miss: when v1.16.4 went slug-only, it updated
  4 CLI lookup functions (cmd_note / cmd_review / cmd_trend /
  cmd_fide_update) but **missed `cmd_rescan_motifs`**, which still
  filtered by `WHERE p.username = ?`. So `python main.py
  rescan-motifs --player evanleong` matched nothing (evanleong is
  the slug; the row's username is nevergiveupgreatthings).

  The v1.16.3 static guard only scans `dashboard_server.py`, not
  `main.py`, so it didn't catch this. v1.18.1 fixes the lookup and
  also makes `cmd_harvest` and `cmd_report` (which filter
  config-loaded player dicts, not DB rows) accept slug via the new
  `_player_matches` / `_config_slug` helpers — so `--player
  evanleong` works consistently across the entire CLI surface now.

  Symptom Bernard hit:
  ```
  $ python main.py rescan-motifs --player evanleong
  No analyzed games match. Run `python main.py analyze` first.
  ```
  (The games WERE analyzed — the lookup just used the wrong column.)

### Added
- **`_config_slug(player)` + `_player_matches(player, requested)`**
  helpers in `main.py`. Config-loaded player dicts don't have the
  DB's auto-derived slug, so these mirror `src.models._slugify`
  (lowercase display_name, strip non-alphanumeric) to keep CLI
  `--player` matching consistent whether or not `config.yaml` sets
  an explicit `slug`.

### Tests
- 8 new tests in `tests/test_main_cli.py`:
  - `TestConfigSlugHelpers` × 7 — explicit slug / derived /
    username-fallback / empty-fallback / matches-by-slug /
    matches-by-username / rejects-unrelated
  - `TestRescanMotifsSlug::test_rescan_resolves_by_slug` — the
    regression lock for the exact bug (rescan-motifs --player
    <slug> resolves, doesn't report zero games)
- Backend: 589 → **597** (+8)

### Note on the bug class

This is the same "slug refactor missed a site" class as v1.16.3
(which added a static guard for `dashboard_server.py`). The
guard's scope didn't extend to `main.py`. A follow-up could add
`main.py` to the static guard's scan, but the CLI lookups are
fewer and now test-covered; deferred unless a third miss surfaces.

---

## [1.18.0] - 2026-05-29

### Changed
- **Expanded the Lichess trap library from 102 → 1,475 entries.**
  v1.4.0 shipped a hand-curated 36-pattern allowlist
  (`TRAP_NAME_PATTERNS`) that selected 102 named traps from
  Lichess's full 3,209-opening dataset. v1.18.0 replaces the
  allowlist with a generic substring filter on five keywords:

  ```python
  TRAP_KEYWORDS = ("Trap", "Gambit", "Attack", "Mate", "Sacrifice")
  ```

  Plus a small `TRAP_NAME_SUPPLEMENT` allowlist for beginner traps
  Lichess publishes under names without the keywords (currently:
  Fishing Pole).

  The `MAX_TRAP_DEPTH = 16` plies cap is preserved — it's the
  load-bearing guard against deep theoretical lines named
  "Anything Attack" matching games where they don't really fire.

  **Bernard's YouFallFor card now surfaces ~14× more named traps**
  — Stockholm Variation (Englund Gambit), Krause Variation
  (Queen's Gambit Declined Semi-Tarrasch), 6 Krause sublines
  across other openings, Halloween Attack lines, Bongcloud Attack,
  Levitsky Attack, and ~1300 others the curated list missed.

### Tests
- 4 new regression tests in
  `tests/test_trap_matcher.py::TestLoadTrapLibrary`:
  - `test_v18_0_trap_count_at_least_400` — guard against accidental
    regression to the narrow allowlist
  - `test_v18_0_includes_non_curated_named_traps` — Stockholm /
    Krause / Halloween all surface
  - `test_v18_0_keeps_curated_v14_traps` — every v1.4.0 trap that
    Lichess actually publishes (under the depth cap) is still
    present. Documents which curated names are excluded:
    - Lichess-doesn't-publish: Scholar's Mate, Légal, Blackburne
      Shilling
    - Depth ≥29 (over the 16-ply cap): Marshall Trap, Monticelli
      Trap
    - Keyword-missing but kept via supplement: Fishing Pole
  - `test_v18_0_respects_depth_cap` — every entry has depth ≤ 16
- Backend: 585 → **589** (+4)

### Recovery / no-op for existing data

The trap-matching pipeline (`_match_trap`,
`_aggregate_traps_by_outcome`, `_compute_loss_openings`,
`_compute_your_arsenal`) is data-shape-agnostic. The next
`python main.py patterns` run automatically picks up the expanded
trap matches — no special backfill step.

### File sizes
- `frontend/public/data/traps.json`: 19 KB → **287 KB**
- `frontend/public/data/openings.json`: 482 KB (unchanged)

Frontend loads `traps.json` once on Patterns page load. 287 KB is
well within budget.

---

## [1.17.0] - 2026-05-29

### Added
- **4 new tactical motif detectors** completing the v1.14.0
  vocabulary. v1.14.0 explicitly named these as deferred; v1.17.0
  ships them:
  - 🏰 **back_rank_mate** — the classical pawn-walled back-rank
    mate. Slotted BEFORE mate_threat in the specificity order so
    both fire on the right positions and the LLM has the more
    specific label available. Strict pattern: requires escape
    squares blocked by the mated side's own PAWNS (the textbook
    image kids learn first).
  - ↗️ **deflection** — threat-based variant of removing_defender.
    Our move attacks an enemy defender that's MORE valuable than
    our attacker (so they can't trade — they must move), and once
    they move, the piece they were defending hangs. Excludes
    captures (those are removing_defender) to avoid double-tagging.
  - 🤹 **overloaded_defender** — enemy piece defending two
    valuable pieces, where attacking one forces the defender to
    choose. Conservative: requires the overloaded defender to be
    the SOLE defender of both targets (no other defenders pick up
    the slack).
  - ⛓ **zugzwang** — endgame-only, intentionally narrow.
    Fires only when total non-king material ≤4 AND the enemy has
    1-3 legal moves AND every legal move is a king move AND the
    king is not currently in check (true zugzwang, not check
    response). Captures classical K+P opposition patterns; under-
    tags rather than over-tags. If real-world false negatives
    surface for middlegame zugzwangs, tighten v1.17.x.

- **Aggregation + LLM prompt + frontend MOTIF_LABELS all extended**
  to surface the 4 new motifs automatically. No schema change —
  `motifs_json` is unstructured text. The MotifThemes Patterns
  card + MotifBadgeRow on Critical Moments cards render the new
  motifs as soon as they appear in the data.

- **`_MOTIF_IDENTIFIERS` extended from 8 to 12** in
  `src/patterns.py`. Aggregator's per-motif loop picks them up
  with no per-motif code path.

- **LLM motif-citation rule in `GAME_COACHING_PROMPT`** gains the
  4 new natural-language mappings (back-rank mate / deflection /
  overloaded defender / zugzwang). Zugzwang explicitly marked
  "use sparingly — advanced endgame concept."

### Tests
- 12 new unit tests in `tests/test_motifs.py`:
  - `TestBackRankMate` × 3 (classic / near-miss / unrelated)
  - `TestDeflection` × 3 (queen-defender pattern / value-asymmetry
    near-miss / non-capture unrelated)
  - `TestOverloadedDefender` × 3 (rook-defends-two pattern /
    extra-defender near-miss / unrelated)
  - `TestZugzwang` × 3 (K+P opposition / middlegame material gate
    near-miss / legal-non-king-move unrelated)
- 2 existing tests updated to reference `_MOTIF_IDENTIFIERS` len
  rather than the magic number 8 (future-proof against further
  motif additions).
- 1 existing test swapped "zugzwang" placeholder for
  "future_motif_v99" (zugzwang is now a real motif).
- Backend: 573 → **585** (+12 new, -0 net change from refactors)

### Optional post-ship action

Run `python main.py rescan-motifs --player evanleong` to backfill
the 4 new motifs on Evan's 583 games. The aggregator and Patterns
card will surface them on the next `python main.py patterns` run.
No data migration required — just additive `motifs_json` updates.

---

## [1.16.4] - 2026-05-29

### Changed (breaking)
- **Slug-only lookups.** The v1.16.1 backward-compat fallback that
  accepted the chess.com username in URLs / API params / CLI args is
  gone. From v1.16.4 onward, all player identifiers across the user-
  facing surface are slugs:
  - `http://localhost:3000/evanleong/patterns` ✓
  - `http://localhost:3000/nevergiveupgreatthings/patterns` ✗ (404)
  - `?player=evanleong` ✓
  - `?player=nevergiveupgreatthings` ✗ (empty result)
  - `python main.py trend --player evanleong` ✓
  - `python main.py trend --player nevergiveupgreatthings` ✗ (WARN, skipped)

  The `players.username` column stays unchanged — it's now reserved
  exclusively for the harvester's chess.com API calls. The previous
  3 versions (v1.16.1 → v1.16.3) carried the dual lookup as a
  bridge; v1.16.4 retires it because:
  - The v1.16.1+ frontend never emits chess.com-username URLs
  - No external integrations / scripts depend on the old shape
  - The two-identifier query produced subtle bug-class confusion
    (the v1.16.1 → v1.16.3 patches all came from one or another
    site forgetting the `OR username = ?` clause)

  Slug-only is one identifier per surface — clearer to reason about,
  easier to keep correct.

- **Sites updated:** `_resolve_player_id`, `_api_games_list`,
  `build_report_data`, and 4 CLI lookups in `main.py` (cmd_note,
  cmd_review, cmd_trend, cmd_fide_update). All drop the `OR username
  = ?` clause and look up by slug only.

- **`build_report_data` arg renamed** from `player_identifier`
  (v1.16.3) to `player_slug` (v1.16.4) to reflect the slug-only
  contract.

### Tests
- Static guard tightened: `WHERE username = ?` is now allowed ONLY
  inside `_handle_create_player` (the chess.com-handle uniqueness
  check during player creation). The v1.16.1 resolver-fallback
  exception is gone too.
- Existing tests converted from "accepts legacy username" to
  "rejects legacy username":
  - `test_v16_4_legacy_username_no_longer_resolves` (patterns API)
  - `test_v16_4_games_rejects_legacy_username` (games API)
  - `test_v16_4_legacy_username_rejected` (CLI)
- Test fixtures updated: `db_with_data` in test_dashboard_server.py
  now uses `slug="test"` (different from `username="testplayer"`)
  so test queries genuinely exercise the slug-only lookup path.
  test_report.py and test_main_cli.py fixtures pin slug similarly.
- Backend: 572 → **573**
- Frontend: unchanged at 191

### Bookmarks

The v1.16.1 frontend has been emitting slug-only URLs for over a day
now, so the practical impact on Bernard's setup is zero — every URL
the browser saw was already in the `/<slug>/` form. Any stale
browser bookmarks from before v1.16.1 (chess.com-username URLs) now
404; just re-bookmark from the live UI.

---

## [1.16.3] - 2026-05-29

### Fixed
- **Games tab showed `0 games` after v1.16.1's slug routing rollout.**
  v1.16.1 introduced the slug column + refactored 5 backend lookup
  sites to use the new `_resolve_player_id` helper. But two sites
  were missed — both still doing `WHERE p.username = ?` directly,
  which never matches when the frontend sends a slug:
  - `src/dashboard_server.py::_api_games_list` (line 1268-1270) —
    drove the empty Games tab
  - `src/report.py::build_report_data` (line 97) — same bug shape,
    just hadn't been triggered yet because the Reports tab is less
    visited

  Both now accept `(slug = ? OR username = ?)`. Old URLs with the
  chess.com username still work; new slug-based URLs (which the
  v1.16.1 frontend always sends) now work too.

- **`build_report_data` arg renamed** from `player_username` to
  `player_identifier` to match its v1.16.3 semantics (accepts both
  slug and chess.com username). The old positional name was a
  semantic lie after v1.16.3.

### Added
- **Static regression guard** `TestPlayerLookupStaticGuard` in
  `tests/test_dashboard_server.py`. Scans `src/dashboard_server.py`
  for any `WHERE username = ?` site outside the resolver itself or
  the player-creation existence check. Future endpoints that bypass
  `_resolve_player_id` will fail this test at lint speed (no live
  server, no fixture). This is the test that would have caught the
  v1.16.1 miss instantly.

### Tests
- 2 new live-server tests on `/api/games`:
  - `?player=<slug>` returns the same game count as
    `?player=<chess.com-username>` (the bug Bernard hit)
  - Slug-based query combines correctly with other filters
    (`&result=win`)
- 1 new static guard (3 tests total)
- Backend: 569 → **572** (+3)

### Recovery

No data action needed. The fix is purely server-side: restart the
backend (`python main.py serve`), hard-refresh the browser, and the
Games tab will populate.

---

## [1.16.2] - 2026-05-29

### Fixed
- **`UnboundLocalError: cannot access local variable 'best_info'
  where it is not associated with a value`** in
  `src/analyzer.py::analyze_game`. The v1.14.0 motif-detection
  wiring put `best_move_obj = best_info["pv"][0] if best_info.get("pv")
  else None` BEFORE `best_info = info` in the per-move loop. On the
  first iteration of every freshly-analyzed game, `best_info` didn't
  exist yet, raising the error and aborting analysis with
  `analysis_status='error'` on the games row.

  The bug only triggered on `analyze_game` (new analyses) — never on
  `rescan-motifs` (which doesn't call `analyze_game`) or on already-
  analyzed games. Symptom in production: *"Failed to analyze game N:
  cannot access local variable 'best_info' where it is not associated
  with a value"* in the analyzer logs, no Stockfish output, game
  marked errored.

  Why it survived from v1.14.0 ship → v1.16.1: rescan-motifs was the
  primary motif-data driver during testing; the bug only surfaces on
  the `analyze` code path, which Bernard hit when a freshly-harvested
  game (game 976) came through.

  Fix: swap the two lines so `best_info = info` runs first, then
  derive `best_move_obj` from it.

### Tests
- New regression lock `TestAnalyzeGameBestInfoOrdering` in
  `tests/test_analyzer.py`. Static source inspection
  (`inspect.getsource`) asserts `best_info = info` appears BEFORE
  `best_info["pv"][0] if best_info.get("pv")`. Zero-cost (no
  Stockfish needed), runs on every commit, and would have caught
  the v1.14.0 regression instantly if it had existed back then.
- Backend: 568 → **569** (+1)

### Recovery for affected games

Any games left in `analysis_status='error'` from this bug can be
re-analyzed after upgrading:

```bash
sqlite3 data/chess_coach.db \
  "UPDATE games SET analysis_status='pending' WHERE analysis_status='error'"
python main.py analyze
```

---

## [1.16.1] - 2026-05-28

### Added
- **Friendly URL slugs decoupled from chess.com handles.** Two
  chess.com renames in one session (`evanleongxinyu` →
  `nevergiveupgreatthings`, `estellaleong` → `sixsevenequals42`)
  exposed that v1.0–v1.16.0 conflated three distinct identifiers
  into one `username` column: chess.com API handle, URL routing
  slug, and DB unique key. v1.16.1 separates them.

  ```
  Before: http://localhost:3000/nevergiveupgreatthings/patterns
  After:  http://localhost:3000/evanleong/patterns
  ```

  - **`players.slug TEXT`** — new column, partial UNIQUE INDEX
    (only enforces uniqueness when slug IS NOT NULL). Auto-derived
    from `display_name` via the new `_slugify` helper: lowercase +
    strip ALL non-alphanumeric (no separator) — `"Evan Leong"` →
    `"evanleong"`. The user's chosen format.
  - **`players.username`** — unchanged, keeps mapping to chess.com
    handle. ONLY used by the harvester to pull games via the
    chess.com API. Never appears in URLs after v1.16.1.
  - **Schema migration is additive + idempotent.** Runs on next
    `init_db()` call. `WHERE slug IS NULL` filter means the
    backfill loop is a no-op once everything's populated. Pre-
    v1.16.1 rows backfilled cleanly on Bernard's live DB: Evan
    Leong → `evanleong`, Estella Leong → `estellaleong`, Eleanor
    Leong → `eleanorleong`, Bernard Leong → `bernardleong`.

- **`_resolve_player_id(conn, identifier)` backend helper** —
  resolves a `?player=X` API param or CLI `--player X` arg by
  slug first, falling back to chess.com username if the slug
  lookup misses. Preserves backward compatibility: old bookmarks
  / cached integrations / shell scripts using the chess.com handle
  continue to work indefinitely. Replaces 5 duplicated
  `SELECT id FROM players WHERE username = ?` sites in
  `dashboard_server.py`.

- **`ensure_player` extended** with optional `slug` kwarg + the
  new `_allocate_slug` helper for collision-safe suffixing
  (`evanleong` / `evanleong2` / `evanleong3` when display_names
  collide).

- **Frontend routing now slug-canonical.** `app/providers.tsx`
  matches URL segments against `slug ?? username` (slug primary,
  username as legacy fallback). `player-selector.tsx` routes to
  `/<slug>/...` for new URLs. `Player` type gains optional `slug`.
  `Settings → Players` panel now shows the distinction clearly:
  ```
  Evan Leong
    URL: /evanleong/…
    Chess.com: nevergiveupgreatthings
  ```

- **CLI `--player` accepts slug or username** across every
  cmd_* function — single `WHERE slug = ? OR username = ?` per
  lookup. Both `python main.py trend --player evanleong` and
  `python main.py trend --player nevergiveupgreatthings` resolve
  to the same player.

- **`config.yaml` supports optional `slug:` field** per player
  entry. Omitted → auto-derived from `display_name`. Explicit →
  overrides the auto-derivation.

### Tests
- 24 new backend tests in `tests/test_models.py`:
  - `TestSlugify` × 9 — basic / multi-word / apostrophe / hyphen /
    non-ASCII / empty fallback / all-symbol fallback / idempotent /
    digits-preserved
  - `TestSlugMigration` × 3 — backfills NULL slugs, idempotent
    re-runs, UNIQUE INDEX blocks duplicates
  - `TestEnsurePlayerSlugSupport` × 6 — auto-derivation, explicit
    override, collision suffixing (×2 and ×3), username fallback,
    update-existing-slug
  - `TestAllocateSlug` × 2 — no-collision passthrough, self-
    exclusion via `excluding_player_id`
- 4 new backend resolver tests in `tests/test_dashboard_server.py`:
  - `?player=<slug>` resolves correctly
  - `?player=<legacy-username>` still works (backward compat)
  - Unknown identifier returns `stats: null` cleanly (never 500)
  - `/api/players` response surfaces `slug` field
- 3 new CLI tests in `tests/test_main_cli.py::TestCmdTrendSlugSupport`:
  - `--player evanleong` (slug) → resolves to right id
  - `--player nevergiveupgreatthings` (legacy) → still works
  - Unknown identifier → WARN, no crash
- 4 new frontend tests in
  `frontend/components/__tests__/player-selector.test.tsx` (NEW):
  - Display names render for each player
  - Click routes to `/<slug>/<subpath>` not `/<username>/...`
  - Pre-v1.16.1 players without slug fall back to username
  - currentPlayer comparison uses slug as the canonical id
- Backend: 541 → **568** (+27). Frontend: 187 → **191** (+4).

### Upgrade

```bash
# 1. Pull v1.16.1 — migration runs on next backend start
python -c "from src.models import init_db; init_db('data/chess_coach.db')"

# 2. Verify the new slugs landed
sqlite3 data/chess_coach.db "SELECT id, username, slug, display_name FROM players"

# 3. Restart the dev server so the in-memory config picks up
python main.py serve

# 4. Open http://localhost:3000/evanleong/patterns
#    (old URL /nevergiveupgreatthings/patterns still works too)
```

No data migration needed beyond the auto-backfill. All historical
games / patterns / journal entries / motif data are FK'd by
`player_id` and follow the rename transparently.

---

## [1.16.0] - 2026-05-28

### Added
- **Phase × motif breakdown.** Each motif's missed/found counts are
  now split by game phase (opening / middlegame / endgame), and the
  aggregate flags when a motif's misses are *concentrated* in a
  single phase. Coaching can now say *"you miss forks in the
  middlegame but find them in the endgame"* instead of just *"you
  miss forks."*

  Each `by_motif[]` row gains three v1.16.0 fields (all additive —
  pre-v1.16.0 stored patterns rows still render correctly):
  ```python
  "missed_by_phase": {"opening": 1, "middlegame": 10, "endgame": 2}
  "found_by_phase":  {"opening": 0, "middlegame":  2, "endgame": 0}
  "dominant_missed_phase": "middlegame"  # or None
  ```
  Plus a top-level `top_missed_dominant_phase` mirror of the top
  motif's tag.

  **Dominant phase rule:** total missed must be ≥3 AND one phase
  must hold ≥60% of misses. Avoids over-claiming on small samples
  (e.g. 1 missed fork in opening isn't a "concentration"); the 60%
  threshold catches real patterns like 4/6 (67%) without flagging
  noise like 3/6 (50%).

- **LLM prompts surface the phase signal at every layer.**
  - `TREND_PROMPT` motif section: each bullet now shows
    `phase split: opening N, middlegame N, endgame N — X focus`,
    plus a concentration sentence in the Headline ("concentrated in
    middlegame (10 of 13)") when the top motif has a dominant phase
  - `TREND_PROMPT` Paragraph 3 rule: when a motif's
    practice-recommendation gate fires AND it has a "X focus" tag,
    the LLM is asked to NAME the phase in the recommendation —
    e.g. *"10 middlegame hanging-piece puzzles every day"* rather
    than just *"hanging-piece puzzles"*
  - `build_trajectory_block` (per-game coach prompt): the
    "Recurring tactical themes" line gains a "— concentrated in
    {phase}" suffix; `diag` dict gains a `motif_top_missed_phase`
    key for `coaching_meta_json` introspection

- **MotifThemes Patterns card** gains a phase breakdown line under
  each non-zero motif row: `Opening 1 · Middlegame 10 · Endgame 2`.
  When a motif has a dominant phase, that phase span is amber-bold
  and prefixed with 🎯 (e.g. `🎯 Middlegame 10`). Pre-v1.16.0
  patterns rows that lack phase fields still render — the line is
  simply skipped.

- **No schema migration.** All v1.16.0 changes are additive.
  `move_analysis.move_number` is already populated;
  `_classify_game_phase()` already exists. Aggregation runs at
  compute time. Pre-v1.16.0 patterns rows just don't have the new
  fields until next `python main.py patterns` run.

### Verified live
- ✅ `test_v16_0_gpt_5_5_pro_cites_dominant_phase` PASSED (166s
  against real gpt-5.5-pro-2026-04-23). The full chain — phase
  split flows into prompt → LLM names "middlegame" in the practice
  recommendation → existing motif citation rules still hold —
  works end-to-end on real APIs.

### Tests
- 15 new backend tests:
  - `TestComputeMotifSummary::test_v16_0_*` × 7 — per-phase
    tracking, dominance detection, balanced=None, insufficient-signal
    handling, top passthrough, malformed-move-number safety, helper
    direct boundary cases
  - `TestFormatMotifSummaryForPrompt::test_v16_0_*` × 4 — phase
    split lines, focus tag, no-focus-when-balanced, pre-v1.16.0
    backward-compat
  - `TestTrendPromptWiring::test_v16_0_prompt_paragraph3_mentions_phase_naming`
  - `TestGenerateTrendSummaryPlumbing::test_v16_0_phase_data_in_prompt`
  - `TestBuildTrajectoryBlockMotifSection::test_v16_0_*` × 2 —
    block surfaces phase + diag passthrough; no-tag when balanced
- 4 new frontend tests:
  - phase breakdown line renders with counts
  - dominant phase highlighted (🎯 + amber-bold)
  - balanced / low-count motifs have no dominant highlight
  - pre-v1.16.0 rows (no `missed_by_phase`) skip the phase line
- 1 new live LLM compliance test (gated on `-m live`):
  - phase-name citation in the practice recommendation
- Backend: 526 → **541**. Frontend: 183 → **187**. Live: 11 → **12**.

### Upgrade

```bash
python main.py patterns          # populate phase fields
python main.py trend --player <username> --provider openai
# the regenerated summary will name the phase when applicable
```

---

## [1.15.4] - 2026-05-28

### Changed
- **Tightened `TREND_PROMPT` and `RECENT_FORM_REVIEW_PROMPT` to
  emphatically forbid JSON output.** v1.15.3's live testing surfaced
  that gpt-5.5-pro occasionally returned the trend summary as a JSON
  array of paragraph strings (`["para 1", "para 2", ...]`) instead
  of plain prose. The frontend rendered correctly because v1.14.1's
  `parseTrendSummary` already handles JSON arrays — but the prompt
  said "no JSON" and the LLM was ignoring it. v1.15.4 fixes the
  root cause.

  Both prompts now open with a dedicated `## Output format (REQUIRED
  — read carefully)` block listing explicit rules:
  - Plain text only, 3-4 paragraphs (or 4 for journal reviews),
    separated by blank lines
  - NO JSON, NO arrays, NO objects — do not wrap in `[...]` or
    `{...}`
  - NO markdown headings (no `#`, `##`), NO bullet lists, NO code
    fences
  - NO preamble ("Sure,", "Certainly,", "Here is your summary:")
  - The FIRST CHARACTER must be a letter — never an opening bracket,
    brace, hash, code fence, or quotation mark
  - NO trailing commentary

  The closing instruction also gains a positive reinforcement: *"Begin
  with the first word of paragraph 1; end with the last word of the
  final paragraph."*

  This mirrors the v1.14.1 client-side fix at the source. Journal
  reviews (RECENT_FORM_REVIEW_PROMPT) were vulnerable to the same
  bug class — patched proactively in the same ship.

- **Live compliance test swap.** v1.15.3 deferred
  `test_claude_opus_4_7_cites_top_motif` because the Anthropic API
  hit a usage cap (regains 2026-06-01). Rather than leave a dead
  test for a month, v1.15.4 replaces it with
  `test_gpt_5_5_pro_borderline_threshold_cites_motif` — a more
  meaningful coverage scenario that pins the prompt's
  *"when >= 5 instances"* rule at its exact boundary
  (`top_missed_count = 5`). Catches bugs the high-N test would miss
  (e.g. a future prompt edit accidentally raising the gate to >5).

  Once Claude API restores, the original cross-provider test can be
  added back alongside the borderline test.

### Tests
- 2 new fast source-grep guards in
  `tests/test_patterns.py::TestTrendPromptWiring`:
  - `test_v15_4_trend_prompt_has_emphatic_no_json_block` — pins the
    new format block + first-character guard + preamble-forbidden
    wording so a future refactor can't silently strip them
  - `test_v15_4_recent_form_review_prompt_has_emphatic_no_json_block`
    — same lock for the journal review prompt
- 1 swapped live test:
  `tests/test_coach_live.py::TestTrendSummaryCompliance::test_gpt_5_5_pro_borderline_threshold_cites_motif`
  (replaces the deferred Claude test). New fixture
  `trend_stats_borderline_db` with `top_missed=fork, count=5`.
- Backend total: 524 → **526** (2 new fast tests, 1 swapped live test)

### Verified live
All 3 live compliance tests pass against real gpt-5.5-pro-2026-04-23
(363s total = ~2 min per call × 3 reasoning calls):
- ✅ Top motif citation @ 13 instances — full pattern + JSON-free
- ✅ Borderline citation @ exactly 5 instances — fork named at gate
- ✅ Zero-motif data — no invented N-counts, no JSON shape

The `FORBIDDEN_PREAMBLE_PREFIXES` strict check (`[`, `{`, `## `,
"Sure,", etc.) now passes consistently — the v1.15.4 prompt
tightening eliminated the JSON-array shape we observed during
v1.15.3 development.

---

## [1.15.3] - 2026-05-28

### Added (tests only — no production code changes)
- **Test coverage for the trend summary pipeline** at three layers,
  closing a gap that became visible after v1.15.0-v1.15.2: the
  motif citation in Bernard's Coaching Summary card was working
  correctly, but there was no automated check that the LLM would
  *continue* to comply with the v1.15.0 prompt instructions if a
  model swap or prompt refactor happened. Without these tests, a
  future regression would be silent.

  **Layer 1 — Backend plumbing** (`tests/test_patterns.py::
  TestGenerateTrendSummaryPlumbing`, 6 fast tests, no LLM):
  - `test_calls_llm_with_motif_text_in_prompt` — patches
    `src.llm_providers.call_provider`, captures the prompt
    argument, asserts the motif section is present with the
    headline and bullet rows for the top-missed motif. Regression
    lock for the v1.15.0 prompt-injection seam.
  - `test_persists_summary_to_player_patterns` — confirms LLM
    response lands verbatim in `player_patterns.trend_summary`.
  - `test_raises_when_no_pattern_stats_row` — `ValueError` with
    actionable message ("Run patterns first.") when no row exists.
  - `test_provider_and_model_pass_through` — `--provider` and
    `--model` reach `call_provider` unchanged. Catches the
    v1.13.1-shape regression class.
  - `test_below_threshold_skips_headline` — `top_missed_count=3`
    must NOT emit the "Headline" line (under the >=5 LLM-citation gate).
  - `test_zero_motif_data_uses_placeholder` — empty
    `motif_summary` produces the "No motif data yet" placeholder.

  **Layer 2 — CLI dispatch** (`tests/test_main_cli.py`, NEW file,
  5 fast tests):
  - `test_dispatches_to_generate_trend_summary` — fake Namespace
    + patched generate_trend_summary; asserts exactly-once call
    with resolved player_id, provider, model.
  - `test_model_override_passes_through` — `--model` flag reaches
    the inner function.
  - `test_skips_missing_player_with_warn` — unknown username
    prints `WARN:` line and exits cleanly without invoking the LLM.
  - `test_reports_no_pattern_stats_per_target` — ValueError from
    the inner function is caught and reported as `✗ <player>:`
    without propagating.
  - `test_no_player_flag_iterates_active_players` — bare `trend`
    iterates all active players.

  **Layer 3 — Live LLM compliance** (`tests/test_coach_live.py::
  TestTrendSummaryCompliance`, 3 tests gated behind `pytest -m
  live`, costs ~$0.10-0.20 per run):
  - `trend_stats_db` fixture seeds a `motif_summary` with
    `top_missed="hanging_piece"` at 13 instances (well over the
    >=5 gate).
  - `test_claude_opus_4_7_cites_top_motif` — runs against real
    Claude API, asserts: length >600, "Evan" appears, one of
    several motif-name variants ("hanging piece" / "free piece" /
    etc.) appears, a numeric reference (13 or any 2-digit number)
    appears, no JSON/markdown/preamble leakage.
  - `test_gpt_5_5_pro_cites_top_motif` — same shape against
    GPT-5.5-pro. Per-provider coverage mirrors the v1.13.2
    `TestStructuredFeedbackCompliance` pattern.
  - `test_zero_motif_data_does_not_crash_live` — empty motif
    summary still produces a usable narrative AND the LLM does
    NOT invent a motif citation (regression lock for "obey the
    prompt's no-data rule").

  **Layer 4 — Frontend rendering** (`frontend/components/patterns/
  __tests__/trend-summary.test.tsx`, NEW file, 4 tests):
  - Motif citation paragraph reaches the DOM as a `<p>` tag
  - Multi-paragraph summary splits into the expected number of
    `<p>` tags
  - Empty-state copy renders when `summary={null}`; motif text
    does not leak in
  - "AI-generated" provenance label renders when summary exists,
    is absent when summary is null

  **How to run the live tests:**
  ```bash
  ARRAKIS_ANTHROPIC_API_KEY=... ARRAKIS_OPENAI_API_KEY=... \
    pytest tests/test_coach_live.py -m live -k TrendSummaryCompliance -v
  ```

### Tests
- Backend total: 513 → **524** (11 new fast tests)
- Backend live total: 8 → **11** (3 new gated live tests, run
  manually pre-release)
- Frontend total: 179 → **183** (4 new render tests)

### Verified live
- `test_gpt_5_5_pro_cites_top_motif` passed against real OpenAI API
  (159s): "hanging piece" cited by name, numeric count referenced,
  no JSON/markdown preamble. The full v1.15.0→v1.15.1→v1.15.2→v1.15.3
  chain is now end-to-end verified on a real model.
- `test_zero_motif_data_does_not_crash_live` passed (110s): LLM
  returned 4-paragraph narrative without inventing any specific
  motif instance count. Note: the LLM may still mention motifs as
  generic kid-coaching tips ("watch out for hanging pieces") — the
  assertion narrowly forbids invented N-count claims, which is the
  actual regression we want to catch.
- `test_claude_opus_4_7_cites_top_motif` not run for v1.15.3 ship
  (Claude API rate-limited until 2026-06-01); will run pre-release
  once access restores.

### Known issue (deferred to v1.15.4)
- On some runs, gpt-5.5-pro returns the trend summary as a JSON
  array of paragraph strings (`["para 1", "para 2", ...]`) rather
  than plain prose — same shape as the v1.14.1 Journal review bug.
  The frontend renders correctly because v1.14.1's `parseTrendSummary`
  already handles JSON arrays. But the trend_summary prompt says
  "Respond with ONLY the text paragraphs, no JSON" — the LLM is
  ignoring this on some samples. Tighter prompt wording to land in
  v1.15.4 (mirror the journal review prompt fix).

---

## [1.15.2] - 2026-05-28

### Added
- **`python main.py trend` CLI subcommand** — closes a long-standing
  ergonomic gap. `generate_trend_summary` has existed since v1.9.0
  but was only reachable via `POST /api/trend-summary` or the
  Patterns page "Refresh Summary" button. Every other LLM-generating
  pipeline (`coach`, `review`, `patterns`, `analyze`) had a matching
  CLI subcommand; `trend` finally joins them.

  Mirrors `cmd_review`'s shape exactly:
  ```bash
  python main.py trend --player evanleongxinyu --provider openai
  python main.py trend                                  # all active players
  python main.py trend --player evan --player estella   # multiple
  python main.py trend --player evan --model gpt-5.5    # model override
  ```

  Same provider list as the rest of the LLM CLI surface (claude /
  openai / gemini / grok / mistral / deepseek / qwen / ollama).
  Defaults to `coaching.default_provider` from `config.yaml`.
  Handles "player not found" and "no pattern stats yet" gracefully
  — emits a per-target ✓/✗ line, never crashes on partial failure.

  Prereq: `python main.py patterns` must have run at least once
  so there's a `stats_json` row to summarize. (The CLI's error
  message points this out when the row is missing.)

  Especially useful right after v1.15.1's skewer recalibration —
  one command regenerates the LLM narrative so it picks up the
  corrected top-missed motif.

### Tests
- No new tests — `cmd_trend` is pure CLI plumbing over the
  already-tested `generate_trend_summary` (v1.15.0 wired the
  motif data; v1.9.0 ships the core path). Verified end-to-end
  manually against Evan's live data. Backend total unchanged at
  **513**. Frontend unchanged at **179**.

---

## [1.15.1] - 2026-05-28

### Fixed
- **Skewer detector was over-firing 10–18× over other geometric motifs.**
  v1.15.0 surfaced the bug at the aggregate level: Evan's "top missed
  theme" came back as `skewer (26 instances)` over a 30-day window,
  which seemed suspiciously high — real skewers are rarer than forks
  or pins. Spot-checking Evan's #1 missed-skewer position (game 966
  vs Giant_Ro, move 27, FEN
  `8/Rp2bpkp/3pb1p1/4p3/2PqP3/3P2P1/3Q1PBP/1r2N1K1`) revealed the
  false-positive pattern: after `Qxa7` the black queen sits on a7
  with a white pawn on f2 and the white king on g1 along the
  a7–g1 diagonal. The v1.14.0 detector tagged this as a skewer
  because the geometry matched (front pawn < back king), but the
  attacker (queen, value 9) is *more* valuable than the front piece
  (pawn, value 1) — so the pawn isn't meaningfully threatened with
  a winning trade. It's an incidental alignment, not a forcing
  tactical theme.

  Aggregated across all four players' history, the v1.14.0 detector
  fired skewer **1930 times** as "played", **1566** as "best", and
  **1250** as "missed" — vs fork at 108/144/138 and pin at
  532/446/414. The skewer numbers were ~10–18× too high.

  Fix: `src/motifs.py::detect_skewer` now requires the classical
  geometry — **attacker value < front piece value** (in addition to
  the existing front < back rule). A queen attacking a pawn no
  longer registers; a bishop attacking a knight no longer registers
  in opening trades. The detector now matches the textbook
  definition: a sliding piece threatens a more valuable enemy piece,
  with an even more valuable piece exposed behind. Three classical
  cases preserved:
  - `bishop(3) → queen(9) → king(100)` ✓
  - `rook(5) → queen(9) → king(100)` ✓
  - `bishop(3) → rook(5) → queen(9)` ✓

  Re-ran `rescan-motifs` for Evan after the fix. Window contracted
  from 117 → 64 critical moves (the 53 false-positive skewer
  tags went away). Top-missed motif flipped from `skewer (26)` to
  **`hanging_piece (13)`** — which matches what the per-game coach
  has been calling out all along. Skewer dropped from 26 missed
  instances to just 1.

  No schema change. After upgrading, run:
  ```bash
  python main.py rescan-motifs --player <username>
  python main.py patterns
  ```
  to repopulate `motifs_json` with the tightened detector and
  refresh the aggregate. Then regenerate the trend summary so the
  LLM coach picks up the corrected top-missed motif.

### Tests
- 4 new regression tests in `tests/test_motifs.py::TestSkewer`:
  - `test_v15_1_queen_attacks_pawn_with_king_behind_is_not_skewer`
    — the literal FEN from Evan's game 966 (the position that
    prompted the calibration)
  - `test_v15_1_bishop_captures_knight_with_queen_behind_is_not_skewer`
    — equal-value attacker → front trade, must not tag
  - `test_v15_1_rook_attacks_pawn_with_bishop_behind_is_not_skewer`
    — attacker > front, no forcing threat
  - `test_v15_1_bishop_skewers_rook_through_queen_still_works` —
    positive case (`bishop(3) → rook(5) → queen(9)`) must still tag
- Backend total: 509 → **513**. Frontend unchanged at 179.

---

## [1.15.0] - 2026-05-28

### Added
- **Motif-aware pattern aggregation.** v1.14.0 tagged every critical move
  with named tactical themes (fork, pin, skewer, etc.) but the data
  stayed invisible at the cross-game level. v1.15.0 aggregates those
  per-move tags into a player-level "Tactical Themes" insight surface —
  the Patterns page can now answer *"which themes do you miss most?"*,
  not just *"how often do you miss tactics?"*

  New **Tactical Themes** card on the Patterns page, paired side-by-
  side with the existing Tactical Awareness card:
  - Hero stat: the most-missed theme + its 30-day instance count
    (e.g. *"🍴 fork — 8"*)
  - Per-motif bar row, sorted missed-desc — emerald fill = themes you
    executed correctly when the engine wanted them, amber fill =
    themes the best move had that yours didn't
  - Zero-count motifs filtered out; empty-state copy when no
    critical moves have motif data yet (e.g. before `rescan-motifs`
    has populated history)

- **Backend aggregation (`src/patterns.py::_compute_motif_summary`).**
  Pure Python, no new DB query — derives from the existing
  `move_analysis.motifs_json` column already pulled into
  `compute_player_patterns`'s `moves_by_game` dict. Counts
  player-side critical moves only, within the same 30-day window
  the rest of the Patterns page uses. Returns a stable shape
  consumed by the prompt formatter, the trajectory block, and the
  frontend card:
  ```python
  {
    "period_days": 30,
    "total_critical_moves": N,
    "by_motif": [{"motif", "missed", "found", "miss_rate"}, ...],  # all 8, sorted
    "top_missed": "fork" | None,
    "top_missed_count": int,
  }
  ```
  Pre-v1.14.0 games (NULL `motifs_json`) and games with missing
  `date_played` are silently skipped — the card just becomes more
  accurate as more games get rescanned.

- **LLM trend summary** (`src/patterns.py::TREND_PROMPT`) gains a new
  *Recurring Tactical Themes (last 30 days)* section. When a single
  motif crosses 5 missed instances in the window, the prompt now
  explicitly asks the LLM to make ONE of the three Paragraph-3
  practice recommendations specifically about that theme (e.g.
  *"set a weekly goal of solving 10 fork puzzles"*). Below the
  threshold, the rule is ignored — avoids over-recommending practice
  on a single missed fork.

- **Per-game coaching trajectory block**
  (`src/patterns.py::build_trajectory_block`) gains a *Recurring
  tactical themes* section listing the most-missed motif and up to
  4 also-recurring runners-up. The per-game coach can now ground
  feedback in cross-game patterns: *"forks have been your biggest
  blind spot — 8 missed in the last 30 days; this game's move 18
  was another one"*. Diagnostic dict gains a `motif_top_missed`
  key for `coaching_meta_json` introspection.

- **Frontend shared motif map (`frontend/lib/motifs.ts`).** Lifted the
  `MOTIF_LABELS` map from `coaching-panels.tsx` into a shared module
  so the new MotifThemes Patterns card uses the same 8 emoji + label
  pairs as the per-game Critical Moments badges. Single source of
  truth — no drift between the two surfaces.

- **No schema migration.** v1.15.0 derives from data the v1.14.0
  schema already stores. Running `python main.py rescan-motifs
  --player <username>` once is the recommended pre-step to backfill
  motif tags on historical games, then `python main.py patterns`
  to recompute the aggregate.

### Tests
- 22 new backend tests in `tests/test_patterns.py`:
  - `TestComputeMotifSummary` (10 cases) — empty / aggregation /
    player-side-only / 30-day window / NULL date / top-missed picker /
    played-only / malformed JSON / unknown identifier
  - `TestMotifSummaryInPlayerPatterns` (1 case) — full pipeline
    through `compute_player_patterns` with a real `motifs_json` row
  - `TestFormatMotifSummaryForPrompt` (5 cases) — empty / zero / under
    threshold / at-threshold / zero-count filtering
  - `TestTrendPromptWiring` (3 cases) — source-grep guards on
    `TREND_PROMPT` + `generate_trend_summary` so the new motif slot
    can't be silently removed in a future refactor
  - `TestBuildTrajectoryBlockMotifSection` (3 cases) — motif block
    emitted when data exists, skipped when zero, `motif_top_missed`
    diag wired correctly
- 6 new frontend tests in
  `frontend/components/patterns/__tests__/motif-themes.test.tsx`:
  - Renders nothing when prop is undefined (pre-v1.15.0 patterns row)
  - Empty-state copy when `total_critical_moves === 0`
  - Top-missed hero number renders correctly
  - One row per non-zero motif with emoji + label
  - Per-row miss-rate + count display
  - Rows sorted missed-desc
- Backend total: 487 → **509**. Frontend total: 173 → **179**.

---

## [1.14.1] - 2026-05-28

### Fixed
- **Journal Recent Form Review entries showed raw JSON brackets and
  quoted paragraphs.** Bernard's gpt-5.5-pro-2026-04-23 reviews were
  rendering as:
  ```
  [
    "Evan Leong, your last 10 games were 6 wins, 4 losses…",
    "On 2026-05-27 against Giant_Ro…",
    …
  ]
  ```
  instead of clean paragraphs.

  Root cause: `parseTrendSummary()` in `frontend/lib/summary.ts` only
  handled JSON *objects* (`{"paragraphs": [...]}` — the older Claude
  shape) and plain prose. When the LLM emits a JSON *array* of
  paragraph strings (`["para 1", "para 2", ...]` — what gpt-5.5-pro
  produces for Journal reviews), the parser fell through to the plain-
  text branch, which split on `\n\n` boundaries but preserved the
  brackets and quotes from the JSON serialization, leaking them into
  the rendered card.

  Fix: added a `trimmed.startsWith("[")` branch that JSON-parses the
  input as an array and extracts the string elements. Falls through
  to the plain-text path if the parse fails (so malformed JSON-like
  input renders as-is rather than crashing).

  No backend change. No DB change. No re-coach needed — existing
  reviews stored in `journal_entries.body` render correctly on next
  page load.

### Tests
- 4 new frontend tests in
  `frontend/lib/__tests__/summary.test.ts`:
  - JSON array of strings parses as ordered paragraphs (no bracket/
    quote leakage)
  - Pretty-printed JSON array with indentation also parses (the exact
    shape gpt-5.5-pro emitted)
  - JSON array with `\n` escape-leak inside paragraphs combines
    cleanly with the v1.8.2 normalization
  - Invalid JSON-array-ish input falls through to plain-text path
    rather than crashing
- Frontend total: 169 → **173**. Backend unchanged at 487.

---

## [1.14.0] - 2026-05-28

### Added
- **Tactical motif tagging on critical moves.** The biggest analyzer-layer
  unlock since v1.0 — Stockfish tells us *what* the best move is and the
  centipawn loss, but not *why* it's best. v1.14.0 layers a new tactical-
  motif detector on top of every critical move so coaching can cite themes
  by name:
  *"At move 18 you missed a knight fork on f7 that would have won the queen"*
  instead of the vague *"the engine prefers a different move here."*

  Eight motifs detected, all on positions with `|cp_loss| ≥ 50cp` (the
  inaccuracy threshold and above):
  - **🍴 fork** — moving piece attacks ≥2 enemy pieces of greater value,
    none safely defended
  - **📌 pin** — moving piece pins an enemy piece against its king
  - **🗡 skewer** — sliding piece attacks an enemy piece with a more
    valuable piece directly behind it
  - **💥 discovered check** — moving piece reveals a check from a
    different attacker (or double check)
  - **🎯 mate threat** — move IS checkmate, or PV continuation reaches
    checkmate within its horizon
  - **🛡 removing the defender** — capturing the sole defender of an
    otherwise-safe enemy piece, leaving it hanging
  - **🎁 hanging piece** — capturing an enemy piece worth more than yours
    (or equal-value with no recapture)
  - **🪤 trapped piece** — newly attacked enemy minor/major piece with no
    safe destination

  Each detector is a conservative pure function — false negatives are
  preferred over false positives. The min-value SEE heuristic ensures
  we only tag captures that actually win material at face value.

- **`src/motifs.py`** — NEW. 8 detectors + `detect_motifs(board, move, pv)`
  top-level entry. ~500 lines. Pure Python, only depends on `python-chess`.
  Specificity-ordered (mate threat first → trapped piece last) so the
  most distinctive label leads when multiple apply.

- **`tests/test_motifs.py`** — NEW. 26 unit tests using hand-crafted FEN
  positions covering a positive case, a near-miss, and an unrelated case
  for each motif. All pass on CPython 3.12.

- **Analyzer wiring (`src/analyzer.py`).** Per-move loop now calls
  `detect_motifs` on every critical move (`|cp_loss| ≥ 50cp`) for both
  the played move and the engine's best move. Stores
  `{played: [...], best: [...], missed: [...]}` as
  `move_analysis.motifs_json`. NULL for sub-threshold moves so the
  column stays sparse (typically 5–15 rows per game).

- **Coach prompt integration (`src/coach.py`).**
  `_build_critical_moments` surfaces motif annotations into the
  LLM-visible critical-moments block — moves with motifs render with
  `⟶ tactical motifs — MISSED: fork | PLAYED: …`. The
  `GAME_COACHING_PROMPT` `critical_moments` JSON schema extended with
  `motifs_found` + `motifs_missed` array fields. The player_feedback
  Middlegame and Endgame section requirements now include explicit
  instruction to cite motifs **by name** when annotated (with a
  motif-id → natural-language mapping), and a *"do NOT invent motifs
  that aren't tagged"* guardrail.

- **Frontend motif badges (`coaching-panels.tsx`).** New
  `MotifBadgeRow` component renders on each Critical Moment card.
  Amber chips for missed motifs ("missed: 🍴 fork"), emerald chips
  for executed motifs ("found: 📌 pin"). Silent (no row rendered)
  when both arrays are empty — keeps pre-v1.14.0 entries visually
  unchanged.

- **`python main.py rescan-motifs`** — NEW backfill CLI. Re-parses
  each analyzed game's PGN, walks moves, runs `detect_motifs` from
  the position before each critical move using the existing
  `move_analysis` row's `best_move` + `pv_line` data. **No Stockfish
  call, no LLM call** — pure Python, free, ~1–2s per game. Supports
  `--player X` and `--limit N`.
  ```
  python main.py rescan-motifs                          # all analyzed games
  python main.py rescan-motifs --player evanleongxinyu  # one player
  python main.py rescan-motifs --limit 10               # smoke test
  ```

### Schema
- New `move_analysis.motifs_json TEXT` column. Idempotent
  `ALTER TABLE` migration in `init_db()`. Pre-v1.14.0 rows have NULL;
  no data loss.

### Tests
- **+31 backend tests** (456 → 487):
  - `tests/test_motifs.py` (26): per-motif unit tests + `detect_motifs`
    aggregator tests
  - `tests/test_coach.py::TestBuildCriticalMomentsMotifs` (5):
    legacy moves render without annotation, populated motifs surface
    into the block, played motifs render too, malformed `motifs_json`
    handled gracefully, prompt schema specifies the fields
- **+4 frontend tests** (165 → 169):
  - `coaching-panels.test.tsx` extension: motif badges render when
    populated, silent for legacy entries, found-only when nothing
    missed, all 8 emoji+label pairs verified
- Frontend build clean. All existing tests still green.

### Migration
- **Pre-v1.14.0 entries**: silent. Existing `move_analysis` rows have
  `motifs_json = NULL`; the frontend treats absent motif arrays as
  "no motifs" and renders no badge row.
- **To backfill historical games**: run `python main.py rescan-motifs`
  once. ~1–2 seconds per game, free (no Stockfish, no LLM). For a
  full ~1,000-game DB this is ~20–30 minutes.
- **To get motif-aware coaching on existing games**: after rescan,
  re-coach the game (`python main.py coach <game_id>` or click
  Re-coach in the UI). The new prompt context block + frontend badges
  appear automatically.

---

## [1.13.3] - 2026-05-27

### Removed
- **`export_json` and the static-file dashboard path are gone.** The
  Next.js frontend at `frontend/` has been the only consumer of
  Arrakis data since the v1.0 dashboard migration — it pulls live
  from `/api/*`. The legacy static-HTML dashboard (and its companion
  JSON-export pipeline) had no consumers but the code lived on as
  dead weight.

  Deletions:
  - `src/export.py` — `export_json()` function (wrote
    players/games/patterns JSON files into `dashboard/data/`).
  - `tests/test_export.py` — 7 unit tests for `export_json` (using
    `tmp_path` so the tests passed but tested a feature no consumer
    used).
  - `cmd_export_json` and the `export-json` subparser in `main.py`.
  - The `static_dir` parameter from `run_dashboard()` in
    `src/dashboard_server.py` and the matching `static_dir="dashboard"`
    arguments from `cmd_dashboard` and `cmd_serve` in `main.py`.
  - The static-file serving fallback in `DashboardHandler.do_GET` —
    non-`/api/` paths now return 404 directly (the Next.js frontend
    on port 3000 serves every UI asset; the backend on port 8000 is
    API-only).
  - Run-all pipeline's "Step 5/5: Exporting JSON" is gone — now
    runs as 4 steps (harvest → analyze → coach → patterns) ending
    with a "run `python main.py serve` to view results" hint.
  - README references to `export-json` (3 occurrences) and the local
    `dashboard/` / `dashboard-legacy/` directories themselves (the
    latter were untracked artifacts of the pre-Next.js dashboard
    that local installs had been regenerating).

### Changed
- **`DashboardHandler` base class switched from
  `SimpleHTTPRequestHandler` to `BaseHTTPRequestHandler`.** The
  backend never served static files in practice — the Next.js
  frontend handles all UI on port 3000. The new base class makes
  that explicit: only `/api/*` is routable, everything else is 404.
  The `directory=` kwarg is gone from the `DashboardHandler`
  constructor signature.

### Tests
- 463 backend → **456** (−7 from removed `test_export.py`).
- Frontend unchanged at 165.
- `tests/test_dashboard_server.py` fixture updated to drop the
  `directory="dashboard"` kwarg.

### Migration
- None for end users. The `export-json` CLI subcommand is gone — if
  any external scripting was calling it, it'll get
  `main.py: error: invalid choice: 'export-json'`. Internal pipelines
  using `run-all` keep working (just one fewer step).
- Local `dashboard/` and `dashboard-legacy/` directories can be
  deleted to reclaim ~13 MB (they were never tracked in git;
  whatever's left locally is JSON regenerations from before this
  patch and is safe to remove).

---

## [1.13.2] - 2026-05-27

### Added
- **Runtime validator for the v1.13.0 player_feedback structure.** The
  v1.13.1 config-drift incident — where `gpt-5.4` silently produced
  freeform text instead of the required 5-section markdown layout, and
  the frontend's graceful legacy fallback masked the problem — wouldn't
  have shipped this fix in place.

  New `_validate_player_feedback_structure()` in `src/coach.py` runs
  after every LLM response, checks that all 5 required headings
  (♟ Opening / ⚔ Middlegame / ♔ Endgame / 🪤 Watch Out For /
  🎯 Top 3 Improvements) appear in the response, and:

  - **Logs a WARNING** identifying the model + listing missing
    headings when output is non-compliant
  - **Persists compliance state** in `coaching_meta_json`
    (`feedback_structure_compliant: bool` +
    `feedback_missing_headings: list[str]`)
  - **Renders a ⚠ "unstructured" badge** in the "Feedback to the
    Player" card header when non-compliant, with a tooltip explaining
    the model mismatch and pointing at the recommended reasoning
    models (claude-opus-4-7 / gpt-5.5-pro-2026-04-23)

  The validator accepts heading variants — `## 🪤 Watch Out For` matches
  whether the LLM writes the bare form or the spec's `## 🪤 Watch Out
  For (Trap Awareness)`. Extra headings the LLM adds are tracked in
  `extra_headings` but don't fail compliance (graceful forward-compat).

- **Per-provider live integration tests.** New `TestStructuredFeedback
  Compliance` class in `tests/test_coach_live.py` (marked
  `@pytest.mark.live`, excluded from default runs). One test per major
  reasoning model — actually calls the LLM and asserts the response
  contains all 5 required headings. Cost: ~$0.10–0.30 per model per
  run.

  Run on demand:
  ```
  pytest -m live -k Compliance
  ```

  Catches format-spec drift at the model level. The v1.13.1 incident
  would have failed `test_gpt_5_5_pro_compliance` if Bernard had been
  routing `gpt-5.4` through the GPT-5.5-pro test — the failure message
  would have shown exactly which headings were missing and which model
  produced the bad output.

### Changed
- `coaching_meta_json` schema extended with `feedback_structure_compliant`
  + `feedback_missing_headings`. Backward-compatible — pre-v1.13.2
  rows simply don't have these fields and the UI treats `undefined`
  as "no check performed" (no badge shown).
- `CoachingMeta` TypeScript interface in `frontend/lib/types.ts`
  extended with the two new optional fields.
- `coaching-panels.tsx` "Feedback to the Player" card header gets a
  small amber ⚠ "unstructured" badge when
  `meta.feedback_structure_compliant === false`. Silent in all other
  cases (true, undefined for legacy entries).

### Tests
- **+8 backend tests** in `tests/test_coach.py`:
  - `TestValidatePlayerFeedbackStructure` (7) — fully-compliant
    5-section, trap-awareness heading variant accepted, legacy
    freeform flagged, partial compliance lists missing, extra
    headings tracked but not a failure, null/empty input handled,
    `_REQUIRED_FEEDBACK_HEADINGS` constant kept in sync with the
    prompt template (cross-reference guard)
  - `TestCoachGameWiresValidator` (1) — source-grep guard against
    silent removal of the validator wiring
- **+2 live tests** in `tests/test_coach_live.py` (default-excluded):
  per-model real-API compliance for Claude opus-4-7 + GPT-5.5-pro.
- **Backend total: 455 → 463. Frontend unchanged at 165.**

### Migration
- None. Pure additive change. The two new `coaching_meta_json` fields
  appear on newly coached games from v1.13.2 onward; older briefs just
  don't have the badge.

---

## [1.13.1] - 2026-05-27

### Fixed
- **`config.yaml.example` model defaults were stale.** When v1.7.0
  bumped the reasoning-model defaults to `gpt-5.5-pro-2026-04-23` and
  `claude-opus-4-7`, the change landed in `src/llm_providers.py`'s
  registry but `config.yaml.example` was never updated. Any user who
  created `config.yaml` from the example after v1.7.0 ended up stuck
  on the old `gpt-5.4` and `claude-opus-4-6` models.

  This bit on v1.13.0 specifically: the older models don't reliably
  follow the new structured 5-section markdown output format the
  v1.13.0 `player_feedback` spec requires, so coaching output showed
  up as a single freeform paragraph instead of the intended phase-
  structured layout — the v1.13.0 frontend parser correctly fell back
  to the legacy single-block render, masking the real cause.

  Fixed `config.yaml.example` to point at the v1.7.0 defaults. Code
  defaults in `src/llm_providers.py` are unchanged (they were already
  correct).

### Required user action (existing installs)
If your local `config.yaml` (gitignored, your personal copy) was
created before v1.13.1 and points at `openai_model: gpt-5.4` or
`anthropic_model: claude-opus-4-6`, edit it to match the new defaults:

```yaml
coaching:
  anthropic_model: claude-opus-4-7
  openai_model: gpt-5.5-pro-2026-04-23
```

Then restart `python main.py serve` and re-coach any game from
v1.13.0 onward — the 5-section structured "Feedback to the Player"
will appear correctly with the newer models.

The older models still work, but they don't follow strict format
specs reliably. If you want to stay on the older models for any
reason, the frontend parser will gracefully render the freeform
output as before.

### Tests
- No new tests. Pure config/docs patch.
- Backend 455 / frontend 165 unchanged.

---

## [1.13.0] - 2026-05-27

### Changed
- **"Feedback to the Player" now reads phase-by-phase with explicit
  trap awareness.** Bernard observed that the green-bordered
  "Feedback to the Player" card on each game's detail page felt
  generic — it mixed opening / middlegame / endgame observations
  together, didn't reliably call out specific move numbers, didn't
  discuss opening theory deviation, and never analyzed which traps
  the opponent could have unleashed in the chosen opening.

  v1.13.0 restructures the field's content into a 5-section markdown
  format that the per-game LLM is required to produce in exact order:

  - **♟ Opening** — what opening was played and how the player's
    moves compared to standard theory (exact match / slight
    deviation / off-book early), with 1-2 specific opening moves
    cited if they meaningfully illustrate the deviation.
  - **⚔ Middlegame** — key middlegame moments, with 1-2 specific
    mistakes or blunders named by move number. The LLM gets a
    pre-computed move-quality breakdown so it can't invent move
    numbers.
  - **♔ Endgame** — conversion quality assessment, or a clear note
    that the game ended in the middlegame.
  - **🪤 Watch Out For (Trap Awareness)** — names one well-known
    trap from the opening played that the opponent *could* have
    unleashed, with a one-line refutation. Forward-looking,
    educational, not retrospective.
  - **🎯 Top 3 Improvements** — exactly 3 concrete, observable
    next-game focuses (e.g. "Find one knight outpost before move
    15" — not "Play more accurately").

  No DB schema change. `game_coaching.player_feedback` stays the
  same TEXT column with new structured content. Existing pre-v1.13.0
  coached games keep their freeform feedback in the DB and continue
  to render as a single block — the frontend parser detects "no
  `##` headings" and falls back to the legacy layout. To get the
  new structure on old games, click "Re-coach" on the game-detail
  page or run `python main.py coach <game_id>`.

### Added
- **`src/coach.py::_phase_classification_summary(moves, player_color)`**
  — returns a per-phase breakdown (opening / middlegame / endgame)
  of the player's move-quality counts (inaccuracies, mistakes,
  blunders) plus the specific move numbers where mistakes and
  blunders happened. Injected into the prompt as a new
  `## Move Quality by Phase` block so the LLM can ground statements
  like "your 18.Qh4 was a mistake" without hallucinating.

- **`src/coach.py::_traps_for_opening(pgn, max=3)`** — looks up
  to 3 well-known traps from `frontend/public/data/traps.json` that
  share this game's opening prefix. Uses longest-common-prefix
  matching (minimum 4 plies) so the most specific opening match
  wins — Ruy Lopez (5 plies) beats generic 1.e4 e5 (4 plies).
  Injected into the prompt as `## Trap Awareness`. Graceful empty
  case for off-book openings.

- **`frontend/lib/feedback-sections.ts::parseSectionedFeedback`**
  — new parser that splits the markdown-sectioned `player_feedback`
  text into ordered `FeedbackSection[]` objects. Reuses the v1.8.2
  `unescapeNewlines` helper from `summary.ts` so the OpenAI
  Responses-API escape leak doesn't break heading detection.
  Graceful fallback for legacy single-block feedback.

- **`frontend/components/game-detail/coaching-panels.tsx`** — the
  "Feedback to the Player" card's `<CardContent>` now renders each
  section with a styled emerald-600 heading (only when present)
  followed by the section's paragraphs. Legacy entries render
  exactly as before because the parser returns a single section
  with empty heading + the full body.

### Tests
- **+16 backend tests** in `tests/test_coach.py`:
  - `TestPhaseClassificationSummary` (5) — empty, player-color
    filter, per-phase counts, mistake/blunder move-number lists,
    ignored-classification handling
  - `TestTrapsForOpening` (6) — empty PGN, Italian Game finds
    Italian traps, Ruy Lopez finds Ruy traps (not Italian — proves
    LCP sort works), off-book returns empty, max_results honored,
    unparseable PGN
  - `TestFormatRelevantTrapsBlock` (2) — empty fallback, full
    rendering with eco/depth/name
  - `TestCoachGameWiresPhaseTraps` (3) — source-grep guards
    confirming the new helpers are wired into `coach_game()` and
    the prompt template carries all 5 required section headings
- **+15 frontend tests** across 2 files:
  - `frontend/lib/__tests__/feedback-sections.test.ts` (11) —
    empty input, 5-section parse, section ordering, body text
    integrity, legacy single-block fallback, v1.8.2 escape-leak
    handling, preamble dropping, bonus-heading forward-compat,
    paragraph-break preservation, whitespace trimming
  - `frontend/components/game-detail/__tests__/coaching-panels.test.tsx`
    (4, NEW file) — renders 5 headings for v1.13.0 entry, renders
    section bodies, legacy entry renders with no headings, null
    feedback omits the card entirely
- **Backend total: 439 → 455. Frontend total: 150 → 165.**

### Migration
- None. Pure additive change. Existing coached games keep their
  pre-v1.13.0 feedback text unchanged and continue to render
  correctly via the parser's legacy-fallback branch. The new
  5-section structure appears on newly-coached games only.

---

## [1.12.0] - 2026-05-26

### Added
- **Parent Note entry type — write your own observations in the
  Journal.** v1.11.0 polished the Journal feed but everything in it
  was LLM-generated. v1.12.0 lets you add your own entries alongside
  the AI reviews — tournament context, weekend recap, anything worth
  remembering. Notes share the same chronological feed, the same
  vertical timeline rail, and the same per-platform scoping as
  reviews. They just have a 📝 blue node instead of a 📖 emerald one.

  Core flow:
  - New **"📝 Add Note"** button next to "Generate Review" at the top
    of the Journal page. Equal weight — notes are a first-class
    action.
  - Click → an inline form expands (not a modal, so it doesn't fight
    with the sticky day-group headers). Type the body in the
    textarea, Cmd/Ctrl+Enter to post, Escape to cancel.
  - Submit → the note lands at the top of the feed, smoothly scrolls
    into view, and pulses for 2 seconds — same UX as a freshly
    generated review.
  - 4000-character soft limit with a live counter (matches the
    backend `MAX_NOTE_BODY_LEN`).

  Edit + delete:
  - Each note card gets **Edit** and **Delete** links in its header
    (notes only — reviews stay immutable through the UI).
  - Edit → swaps the body for a textarea; Save/Cancel. Body-only edit;
    `kind`, `platform`, `created_at` stay locked so the timeline order
    can't be rewritten.
  - Delete → confirmation dialog → DELETE the row. Reviews are
    protected at both the API and helper level — attempting to delete
    a review via the note endpoint returns 400.

- **CLI command `python main.py note`** for quick text entry from the
  terminal:
  ```
  python main.py note --player evanleongxinyu "Round 3 win against Sarah!"
  python main.py note --player bernardleong --platform lichess "Crushed in the Italian"
  ```

- **New `src/journal.py` module** with `create_note`, `update_note`,
  `delete_note` helpers. Centralizes note write logic outside
  `patterns.py` (which was getting large). Reused by the API endpoints
  and the CLI command.

- **New API endpoints** (mirroring REST conventions):
  - `POST /api/journal/note` — `{player, body, platform?}` → creates
    note, returns the full entry shape (matching `GET /api/journal`).
  - `PUT /api/journal/note/<id>` — `{body}` → updates body. Guards
    against editing non-note entries.
  - `DELETE /api/journal/note/<id>` — removes the note. Guards against
    deleting reviews.

### Schema
- **No changes.** v1.10.0's `journal_entries` table already has
  `kind`, `platform`, `body`, `provider` (NULL for notes), `created_at`,
  and `metadata_json` — every column v1.12.0 needs.

### Tests
- **+42 tests** (414 → 439 backend, 134 → 151 frontend):
  - `tests/test_journal.py` (NEW, 17 tests) — `create_note` happy path
    + whitespace + platform handling + empty/None/oversize/unknown-player
    rejection; `update_note` body-only updates + strip + same rejections
    + refusal to edit reviews; `delete_note` removes rows + refusal
    to delete reviews.
  - `tests/test_dashboard_server.py` (+8 tests, `TestJournalNoteEndpoints`)
    — POST/PUT/DELETE happy paths, missing-player 400, unknown-player
    404, empty-body 400, review-edit 400, review-delete 400.
  - `frontend/components/journal/__tests__/add-note-form.test.tsx`
    (NEW, 9 tests) — collapsed default, opens on click, validates
    empty body, calls API, surfaces server error, Cancel clears,
    whitespace rejection, char counter.
  - `frontend/components/journal/__tests__/entry-card.test.tsx` (+8
    tests) — no Edit/Delete on reviews, both visible on notes, edit
    flow, cancel restores original, Save guards on empty, Delete
    requires confirm.

### Migration
- None. Pure additive change on top of v1.10.0's schema.

---

## [1.11.0] - 2026-05-26

### Changed
- **Journal redesigned as a threaded social-media-style feed.** v1.10.0
  shipped the right architecture (entries accumulate, never replace)
  but the cards still felt formal — a stack of report tiles rather than
  a coaching diary. Bernard asked for it to feel like a Twitter /
  Mastodon / Substack chronological feed: a visible timeline thread,
  day grouping, live timestamps, motion when new entries arrive.

  v1.11.0 lands all five polish items in one ship:

  1. **Vertical timeline thread.** Each entry card carries a 2px left
     border that visually stitches into the next, forming a continuous
     rail down the feed. A colored node attaches each card to the rail
     at its date line — emerald 🟢 for reviews, with blue 🔵 reserved
     for the parent-note kind (introduced in v1.12.0). Scrolling the
     Journal now reads as one coherent timeline rather than a stack of
     business cards.

  2. **Day-grouping headers.** The feed groups into sticky section
     headers: *Today / Yesterday / This week / Last week / Earlier*.
     Empty buckets are dropped (a fresh Journal with one entry shows
     just "Today"). Each header carries an entry count and sticks to
     the top while you scroll through its bucket.

  3. **Auto-refreshing relative timestamps.** Per-entry labels —
     "just now / 5 minutes ago / today, 14:23 / yesterday / 3 days ago
     / 2 weeks ago / 4 months ago / 1 year ago" — update every 60s
     without a page reload. An entry generated at 14:23 visibly
     transitions from "just now" → "5 minutes ago" → "today" →
     "yesterday" over real time.

  4. **Scroll-to-new + soft highlight pulse.** When you click
     "Generate Review" and the new entry lands (poll detects it), the
     feed smoothly scrolls to that entry and pulses with a 2-second
     emerald glow. After 2–5 minutes of waiting for the reasoning
     model, you don't have to hunt for what arrived.

  5. **Per-entry expand/collapse.** The latest 3 entries default to
     expanded (full body). Older entries collapse to a one-line
     preview — *"📖 Review · May 19 · Over your last 10 games you
     played 7-2-1…"* — click anywhere on the preview to expand. Keeps
     the feed dense as it grows past the screen, while keeping every
     entry one click away.

  No schema change, no backend change, no migration. Pure frontend
  presentation polish on top of the v1.10.0 data layer.

### Added
- **`frontend/lib/relative-time.ts`** — `getRelativeTime(date)` plus
  `useLiveRelativeTime(date)` hook that re-renders every 60 seconds.
  Handles SQLite's `'YYYY-MM-DD HH:MM:SS'` (no timezone) format by
  treating it as UTC to match `datetime('now')`, plus ISO strings and
  date-only inputs.
- **`frontend/lib/journal-grouping.ts`** — `groupEntriesByDay(entries)`
  returns ordered day-buckets with empty buckets dropped. ISO-week
  aware so "This week" / "Last week" boundaries shift cleanly each
  Monday.
- **`frontend/components/journal/timeline-thread.tsx`** —
  `<TimelineNode kind="review|note" />` rendering the colored dot on
  the rail.
- **`frontend/components/journal/day-group.tsx`** — sticky section
  header for a day bucket.
- **`frontend/components/journal/entry-card.tsx`** — extracted from
  `journal/page.tsx`; adds expand/collapse, scroll-into-view + pulse
  when freshly generated, live-updating relative timestamp.

### Tests
- 4 new frontend test files (+43 tests; 91 → 134 total):
  - `frontend/lib/__tests__/relative-time.test.ts` (12 tests) —
    boundary cases (just-now / N min / today / yesterday / N days /
    weeks / months / years), SQL parser + ISO + date-only inputs,
    future-date clock-skew handling.
  - `frontend/lib/__tests__/journal-grouping.test.ts` (10 tests) —
    bucket assignment for Today/Yesterday/This week/Last week/Earlier,
    invalid input fallback, empty-bucket dropping, intra-bucket order
    preservation, multi-bucket spread.
  - `frontend/components/journal/__tests__/timeline-thread.test.tsx`
    (5 tests) — node color per kind (review / note / fallback), title
    attribute, aria-hidden.
  - `frontend/components/journal/__tests__/entry-card.test.tsx`
    (11 tests) — defaultExpanded behavior, click-to-expand,
    click-header-to-collapse, kind icons, platform + model badges,
    referenced-game pills as links, no-refs row absent when empty,
    pulseOnMount triggers scrollIntoView.
- Backend unchanged at 414.

### Migration
- None. Pure presentation change; reuses v1.10.0 data unchanged. After
  pulling, hard-reload the Journal tab — the redesign is immediate.

---

## [1.10.0] - 2026-05-26

### Added
- **Journal — new top-level tab for chronological coaching reviews.**
  Bernard pushed for a sharper conceptual split: the Patterns page should
  be the stats *overview* (charts, present-tense aggregates, Coaching
  Summary), while a new Journal page should be the narrative *evolution*
  — a chronological diary that names specific games and accumulates over
  time.

  Today's "Regenerate" button on Recent Form Review *replaces* the
  previous text. That's fine for a stats card but a non-starter for a
  diary; the whole point of a journal is the accumulation. v1.10.0 fixes
  that architecturally.

  What's new:
  - **New `/[player]/journal` page** in the player nav, between Patterns
    and Hunt.
  - **`journal_entries` table** with `kind` (review, with note added in
    v1.12.0) and `platform` (chess.com / lichess) columns. `kind` is
    free-form text so new entry types can be added without a schema
    migration.
  - **Recent Form Review now INSERTS a new journal entry per generation**
    instead of UPDATE-ing a single column. Reviews accumulate
    chronologically — generate as many as you want, all are preserved.
  - **Timeline at top of Journal**: reuses the v1.7.2/v1.7.3 platform-
    aware rating-progression chart. v1.10.1 will add entry-dot
    annotations on the line; for now the chart + the dated feed below
    let you correlate visually.
  - **Entry feed** with clickable "referenced games" pills — when the
    LLM names an opponent or a date in the review, the corresponding
    `games.id` is parsed out and rendered as a link to that game's
    detail page.

- **Platform-aware reviews (forward-compat for v1.10.1 / v1.11.0).** New
  `platform` parameter on `compute_recent_form_review()`. Defaults to
  the player's most-played analyzed platform — same default-selection
  logic as the v1.7.2 Rating Progression chart. Avoids the cross-platform
  rating-pool noise we already fixed there. v1.10.1 will add a chip-row
  filter at the top of Journal; the backend already supports it.

- **New API endpoints**:
  - `GET /api/journal?player=X&platform=Y&kind=Z&limit=N` — returns
    chronological entries newest-first plus per-platform counts.
  - `POST /api/journal/review` — canonical endpoint for generating a
    new review entry. Accepts optional `platform`. The v1.9.0
    `/api/recent-form-review` endpoint is kept as an alias.

- **One-time migration on `init_db()`**: each player who had a non-null
  `player_patterns.recent_form_review` gets their existing review
  promoted into a journal entry (kind='review', platform='chess.com',
  created_at preserved from `recent_form_review_updated_at`). Idempotent:
  re-running `init_db()` doesn't duplicate. No data loss; the legacy
  column stays populated for backward-compat.

### Changed
- **Patterns page**: Recent Form Review card removed. Replaced with a
  small emerald-bordered banner: *"📖 Looking for the Recent Form Review?
  It moved to its own tab. Open Journal →"* Keeps users from getting
  lost during the transition. Drop the banner in a future release once
  the move is known.

### Tests
- 18 new backend tests in `tests/test_patterns.py` and
  `tests/test_dashboard_server.py`:
  - `TestMostPlayedPlatform` (3) — default-platform fallback logic
  - `TestParseReferencedGameIds` (5) — opponent / date matching for
    the clickable game pills
  - `TestJournalEntryCreation` (5) — first review creates an entry,
    second review accumulates (not replaces), platform filter scopes
    correctly, default platform uses most-played, refs_json populated
  - `TestJournalAPI` (5) — GET endpoint shape, platform filter,
    unknown player handling, empty state
- Backend total: 396 → **414 tests**. Frontend unchanged at 91.

### Migration
- Automatic on first `init_db()` call after upgrade. No manual step
  required — the next time you start `python main.py serve` or run any
  CLI command, your existing review is promoted into a journal entry.
- Backward-compat: `player_patterns.recent_form_review` column stays
  populated for any tooling still reading it. Source of truth is now
  `journal_entries`.

### Recommended next step
After upgrading:
1. Restart `python main.py serve`, hard-reload your browser
2. Click the new **Journal** tab on any player's page
3. Your existing review will appear as the first entry (migrated)
4. Click "Generate Review" to add a new entry — the old one stays

The Patterns page Coaching Summary is unchanged (that's the stats
overview; Journal is the evolution).

---

## [1.9.0] - 2026-05-25

### Added
- **Recent Form Review — LLM narrative across the last 10 coached games.**
  Bernard noticed that the per-game coaching panels feel game-internal
  even with v1.8.0's trajectory injection working as designed — the
  per-game prompt acknowledges measured trends, but you only see those
  trends one game at a time. There was no "let me tell you about your
  last 10 games as a unit, naming specific games" view.

  v1.9.0 adds a new card at the top of the Patterns page
  (`/[player]/patterns`), sitting above the existing AI Coaching
  Summary. The new card displays an LLM-generated 4-paragraph review:

  1. **The arc** — recent W/L/D record, what kind of week it's been
  2. **Standout games** — 2–3 specific games named by date + opponent
  3. **What's working / what's not** — tied to the measured trajectory
  4. **Forward guidance** — one concrete coaching mission for the next 10 games

  Distinct from the existing `trend_summary` (which is a 30-day stats
  aggregate written without knowledge of specific games). The review
  pulls each of the last 10 games' `key_lesson`, `practical_focus`,
  and a 200-char excerpt of `player_feedback`, combines them with the
  v1.8.0 trajectory snapshot, and asks the LLM to synthesize.

- **Reuses the v1.8.0 trajectory infrastructure** — the review prompt
  includes the same `build_trajectory_block` snapshot the per-game
  coach sees, so it knows the player's measured weakest phase, ACPL
  trend direction, tactical miss rate, endgame conversion,
  comeback/collapse rates without restating numbers to the reader.

- **Manual refresh trigger** — same UX pattern as the existing
  Coaching Summary card. Click "Generate Review" / "Regenerate", pick
  a provider, wait 2–5 minutes for a reasoning model to write it. Cost
  per refresh: ~$0.10–0.15 with gpt-5.5-pro on a typical prompt.

- **New CLI command** `python main.py review`:
  ```
  python main.py review                            # all active players
  python main.py review --player evanleongxinyu    # one player
  python main.py review --provider claude --window 15
  ```
  Useful for batch-generating reviews after re-coaching a backlog of
  games (cf. `scripts/recoach_test.py`).

- **New API endpoint** `POST /api/recent-form-review` mirrors the
  existing `/api/trend-summary` shape. GET `/api/patterns?player=X`
  now also includes `recent_form_review` and
  `recent_form_review_updated_at` in the response payload.

### Schema
- **New columns** on `player_patterns`: `recent_form_review TEXT` and
  `recent_form_review_updated_at TEXT`. Idempotent migration via
  `init_db()` — runs automatically on next startup. No data loss; old
  rows just get NULL until a review is generated.

### Tests
- 11 new backend tests in `tests/test_patterns.py`:
  - `TestRecentGamesTableFormatting` (3) — date / opponent / opening
    rendering + 40-char opening-name truncation
  - `TestRecentLessonsBlockFormatting` (3) — 200-char player_feedback
    truncation + short-feedback passthrough
  - `TestComputeRecentFormReview` (5) — no coached games → empty,
    missing player → ValueError, mocked LLM persists review +
    timestamp, window param works with fewer-than-N games, trajectory
    block flows into the prompt
- Backend total: 385 → **396 tests**. Frontend unchanged at 91.

### Migration
- No backfill needed. The first time a player loads the Patterns page
  after upgrade, the Recent Form Review card appears in empty state
  with a "Generate Review" button. Click it to populate.
- Existing `trend_summary` rows are untouched.

### Recommended usage
1. After coaching a batch of new games (e.g. via
   `scripts/recoach_test.py`), open the Patterns page for the player.
2. Click "Generate Review" on the new card at the top.
3. Wait 2–5 minutes for the reasoning model.
4. The review names specific games from the last 10 coached, ties them
   to measured trajectory, and gives a forward coaching mission.
5. Re-generate when you've coached another batch of games and want a
   fresh take.

---

## [1.8.2] - 2026-05-25

### Fixed
- **Coaching Summary now renders paragraph breaks instead of literal
  `\n\n` text.** Bernard noticed that Evan's coaching summary on the
  patterns page was showing visible `\n\n` characters between paragraphs
  instead of actually breaking. Root cause: the parser in
  `frontend/components/patterns/trend-summary.tsx` was splitting on real
  `"\n\n"` (two newline chars), but the LLM payload sometimes arrives
  with the **two-character escape sequence** `\` + `n` instead of a real
  newline — most often from the OpenAI Responses API. The split silently
  matched nothing, the whole summary rendered as one giant paragraph,
  and the unrendered escape sequences leaked into the UI.

  Fix: extracted the parser into `frontend/lib/summary.ts` as
  `parseTrendSummary()` and added a normalization pass that converts
  literal `\n` (and `\r\n`) sequences to real newlines *before* splitting,
  and again on each JSON-extracted paragraph in case the escape leaked
  through the JSON layer too. The component now calls the helper instead
  of inlining the regex.

  Pure frontend fix — no backend change, no database change, no
  re-coaching needed. Already-stored summaries from every provider now
  render correctly on next page load.

- **Coaching-panel badges rendered escape sequences instead of emoji.**
  The "Game Story" header on the per-game coaching panel was showing
  literal text `📚 10 recent games in context` and
  `📊 30-day trajectory (Nd old)` instead of the intended
  📚 / 📊 glyphs. Root cause: the JSX source contained the JavaScript
  string-escape form `📚` and `📊` as plain text
  inside the element body — and JSX doesn't decode JS escape sequences
  in text nodes (it does in `{"\uD83D…"}` JS expressions or in
  attribute-value strings, but not in raw JSX text). The pre-existing
  history-stamp badge from v1.6.0 had the same latent bug; it just
  hadn't been spotted because the v1.8.0 trajectory stamp landed next
  to it with the same pattern.

  Fix: replace the literal escape strings with actual UTF-8 emoji
  bytes (📚, 📊) in
  `frontend/components/game-detail/coaching-panels.tsx`. Both badges
  now render correctly. No data-shape changes, no API changes — pure
  presentational patch.

### Tests
- New `frontend/lib/__tests__/summary.test.ts` with 15 cases including
  two v1.8.2 regression locks: one with the exact `\\n\\n` shape that
  triggered the bug, and one with the verbatim Evan Leong summary from
  the report (4 paragraphs, asserts no literal `\n` survives in any
  rendered paragraph).
- Frontend total: 76 → **91 tests**. Backend unchanged at 385.

---

## [1.8.1] - 2026-05-25

### Fixed
- **OpenAI provider timeout bumped 120s → 600s.** The OpenAI registry
  entry in `src/llm_providers.py` was carrying a 120s `default_timeout`
  set back when the default model was the older gpt-5.4. With v1.7.0
  switching the default to `gpt-5.5-pro-2026-04-23` (a deeper-reasoning
  model) and v1.8.0 layering ~250 tokens of trajectory context on top of
  the existing ~5000-token history injection, the total prompt is now
  ~6200 tokens and the OpenAI Responses API consistently runs past 120s
  on real coaching calls — surfacing as `httpx.ReadTimeout` →
  `openai.APITimeoutError` mid-pipeline.

  Live measurement on Bernard's DB: coaching Evan's game 954
  (2026-05-24 win, closed Sicilian, 80 plies) with
  `gpt-5.5-pro-2026-04-23` clocked **5 minutes 02 seconds** end-to-end.
  The 300s floor matches Claude / Gemini / DeepSeek (the other three
  reasoning-model providers), but the live measurement shows 300s is
  still cutting it close — 600s gives real headroom for longer games or
  larger trajectory snapshots without forcing the user back to the
  retry path. The non-reasoning `openai_chat` providers (Grok, Mistral,
  Qwen) stay at 120s.

### Tests
- New regression test `test_openai_timeout_at_least_600s` in
  `tests/test_llm_providers.py` pins the OpenAI timeout at ≥ 600s so a
  future model swap can't silently re-introduce the 120s ceiling.
- Backend total: 384 → **385 tests**. Frontend unchanged.

---

## [1.8.0] - 2026-05-25

### Added
- **Trajectory-aware per-game coaching.** Bernard noticed the "Feedback
  to the Player" box on each game's coaching panel reads like every
  game lives in a vacuum — it has no awareness of the player's
  measurable trajectory across recent games, no idea whether the lesson
  raised last week was applied this week, and no sense that every
  Elementary-tier player gets the same static `focus_areas` regardless
  of where their actual measured weaknesses are.

  The raw material to fix this already existed: `player_patterns.stats_json`
  has 14 cross-game pattern dimensions, computed by
  `compute_player_patterns()`. It was just never flowing into the
  per-game coaching prompt.

  v1.8.0 adds a new `build_trajectory_block()` helper in
  `src/patterns.py` that fetches the latest player_patterns row and
  produces a structured `## Player Trajectory (last 30 days)` block:

  - **6-8 numeric facts** (one line each): weakest phase + ACPL,
    strongest phase + ACPL, tactical miss rate, winning-endgame
    conversion, ACPL trend direction (improving / flat / declining
    over last 4 weekly buckets, deterministic Python calc), comeback
    and collapse rates, repertoire focus rating per color.
  - **A synthesized headline sentence** like *"ACPL has been improving
    over the last 4 weeks; middlegame remains the weakest phase at
    77.8cp avg loss."*

  The block is injected into `GAME_COACHING_PROMPT` as a new
  `{player_trajectory}` slot. Three new prompt instructions tell the
  LLM how to use it: acknowledge real progress, note recurring
  weaknesses *gently* (don't re-lecture), and tie the per-game lesson
  to the broader arc without restating the numbers.

  The existing tier-based system (rating → language complexity,
  Stockfish depth, classification thresholds, default focus_areas) is
  unchanged — trajectory is *layered on top*, not a replacement.

  Net effect on Evan's data: the coach now sees in every game brief
  that his middlegame is his measured weakest phase (68.6 ACPL vs 45.1
  in the opening) and his tactical miss rate is 48.3%, so per-game
  feedback can reference the trajectory ("this game is another example
  of the middlegame drift you've been working on") instead of
  rediscovering it from scratch each time.

- **Auto-refresh of player_patterns when stale.** New helper
  `_maybe_refresh_patterns()` in `src/coach.py` calls
  `compute_player_patterns()` (pure-Python, no LLM, ~3-5s per player
  on Bernard's DB) before coaching if the patterns row is >7 days old
  OR if completed games exist beyond the row's `period_end`. Means
  Bernard doesn't have to remember to re-run `python main.py patterns`
  before coaching new games. We do NOT auto-call
  `generate_trend_summary()` — that's a paid LLM round-trip.

- **`coaching_trajectory_enabled: true` config flag.** New knob in
  `config.yaml` and `config.yaml.example`, default ON. Set to `false`
  on Ollama-8B local deployments if you're already running a high
  `coaching_history_count` and want to save context.

- **`--no-trajectory` CLI flag** on `python main.py coach` for one-off
  A/B comparisons of coaching output with vs without trajectory
  context. Useful for verifying the trajectory injection is actually
  improving feedback quality (or for debugging if it's getting in the
  way).

- **UI stamp** on the game-detail coaching panel: next to the existing
  v1.7.0 "📚 N recent games in context" badge, a new "📊 30-day
  trajectory (Nd old)" badge appears when trajectory was injected.
  Tooltip explains what the LLM saw and suggests re-running
  `python main.py patterns` if the freshness exceeds 7 days. When the
  player has no trajectory yet (first coached games), the badge is
  silent — same UX as before.

### Changed
- **Softened the "MUST be different from previous lessons" rule** in
  the coaching prompt to "different in wording and angle, even when
  reinforcing a recurring theme." Resolves tension with the new
  trajectory-aware "note recurrence gently" instruction — the LLM
  needed permission to revisit a theme without forcing artificial
  novelty when the player genuinely has a persistent weakness worth
  flagging twice.

- **Coaching meta diagnostics extended.** `coaching_meta_json` now
  includes `trajectory_injected`, `trajectory_age_days`,
  `trajectory_weakest_phase`, `trajectory_trend_direction`, and
  `trajectory_tokens_estimate`. The existing log line is extended with
  `trajectory=injected/skipped (age=Nd, ~T tokens)`.

### Tests
- 11 new backend tests in `tests/test_patterns.py`:
  - `TestAcplTrendDirection` (4): improving / declining / flat /
    insufficient-data classifier semantics
  - `TestFindBestPhase` (2): the new helper that finds the
    lowest-ACPL phase (mirror of existing `_find_worst_phase`)
  - `TestBuildTrajectoryBlock` (5): no patterns → empty block,
    populated patterns → expected keywords, heading doesn't contain
    `### Game ` (preserves `_count_history_games` correctness),
    token budget bounded under 400 tokens, no-signal skip path
- 6 new backend tests in `tests/test_coach.py` (`TestTrajectoryInjection`):
  - Trajectory injected when enabled + patterns populated
  - Trajectory disabled via `trajectory_enabled=False` argument
  - Trajectory disabled via `coaching_trajectory_enabled=False` config
  - Trajectory diagnostics persisted to `coaching_meta_json`
  - Silently skipped when no patterns row exists
  - Source-grep wiring guard (mirror of the v1.7.0 history-count
    wiring test)
- Backend total: 367 → **384 tests**. Frontend unchanged at 76.

### Migration
- No schema change, no DB migration. Players who have never run
  `patterns` see the silent-skip path; players with stale patterns
  get auto-refreshed when they next coach.
- The trajectory block only appears for **newly coached games** after
  upgrading. Existing coached games keep their pre-v1.8.0 feedback
  unless explicitly re-coached.

---

## [1.7.4] - 2026-05-24

### Fixed
- **ACPL fix from v1.7.1 now applied across all widgets.** v1.7.1
  corrected the mate-transition bug in three sites (real-time analyzer,
  backfill in `models.py`, and the ACPL Trend fallback in
  `patterns.py::_compute_acpl_trend`). But six *other* pattern widgets
  still computed per-move centipawn loss with the old broken formula
  inline — meaning mate-delivering moves continued to register as
  ~2000cp losses inside those widgets even after v1.7.1.

  Affected widgets (all in `src/patterns.py`):
  - `_compute_phase_analysis` — opening / middlegame / endgame ACPL
  - `_compute_consistency` (fallback path when `g.acpl` is null)
  - `_compute_time_control_performance` — per-time-control ACPL
  - `_compute_opening_repertoire` — per-opening ACPL
  - `_compute_opening_acpl` — opening-pool ACPL
  - `_compute_tactical_misses` — opportunity-cost loss calc

  The fix extracts the v1.7.1 logic into a single helper,
  `_per_move_player_loss(move, side, eval_cap=1000)`, and replaces all
  six inline calculations (plus the `_compute_acpl_trend` fallback for
  code consistency). The helper applies the played-best-move zero rule
  AND the per-move loss cap at `EVAL_CAP`, identical to v1.7.1.

  Also removed dead `player_eval_before` tracking in
  `_compute_tactical_misses` that the rewrite orphaned.

  **No migration needed.** Run `python main.py patterns` once after
  upgrading to refresh aggregations (analyzer.py + models.py were
  already correct from v1.7.1, so the underlying game records are fine
  — only the cross-game pattern aggregations recomputed from them
  needed the helper). On the reference DB the refresh completes in
  ~10s for 4 players / 954 games.

### Tests
- 9 new backend tests in `tests/test_patterns.py`:
  - `TestPerMovePlayerLoss` (7): played-best-move returns 0, non-best
    normal swing unchanged, mate-transition capped at `eval_cap`,
    black perspective, missing fields safe defaults, no negative loss,
    custom `eval_cap` honored.
  - `TestAcplConsistencyAcrossWidgets`: synthetic mate game → ACPL
    Trend and Phase Analysis agree (both bounded, both apply the
    played-best rule).
  - `TestPhaseAcplNoLongerInflated`: endgame phase ACPL bounded by
    `EVAL_CAP` even for mate-delivering moves.
- Backend total: 358 → **367 tests**. Frontend unchanged at 76.

---

## [1.7.3] - 2026-05-24

### Changed
- **Rating Progression chart no longer mixes time-control rating pools
  by default.** Bernard spotted suspicious sudden dips in the chart —
  the rating would drop from ~1200 to ~400 for a single game and snap
  back. Not data errors: chess.com (and lichess) run **independent Elo
  pools per time control**. Evan plays mostly rapid (509 games, ratings
  ~1100) but occasionally daily (52 games, ratings ~400-800), so when
  a daily game landed on the timeline between rapid games, the
  combined trend line plunged.

  Same class of bug v1.7.2 fixed for chess.com vs lichess (different
  rating systems on the same axis) — just one layer deeper. The fix
  mirrors v1.7.2's pattern:

  - **Default to the most-played time class**, not "All". For Evan that's
    rapid; clean trend with no dips.
  - **Hide chips for time classes the player has zero games in.** A
    pure-rapid player no longer sees Bullet / Blitz / Daily chips that
    do nothing when clicked.
  - **The "All" chip is only shown when multiple time classes exist**,
    and it now carries a ⚠ marker. Hovering shows: "Mixes rating pools
    across time controls — each pool has its own Elo. The trend line
    can dip when a different time control's game lands on the timeline.
    Pick a single time control for an accurate trend."
  - **Single-time-class players see no UI change** — for kids who only
    play rapid, the chart looks identical to before.

  Implementation: frontend-only, same file as v1.7.2
  (`rating-progression-chart.tsx`). No backend, no schema, no API,
  no migration. Zero regression for the typical single-time-class user.

### Tests
- 4 new frontend tests in
  `frontend/components/patterns/__tests__/rating-progression-chart.test.tsx`:
  - Default selection = most-played time class (not "All")
  - Chips for empty time classes are hidden
  - Single-time-class player → no "All" chip
  - Multi-time-class player → "All" chip present with ⚠ marker + tooltip
- Frontend total: 72 → **76 tests**. Backend unchanged at 358.

---

## [1.7.2] - 2026-05-24

### Changed
- **Rating Progression chart now splits chess.com and lichess.** The
  previous single-line chart aggregated both platforms into one trend,
  which was incoherent because chess.com (Elo) and lichess (Glicko-2)
  use different rating systems — lichess typically runs 100–300 points
  higher for the same player strength. The two also have very uneven
  game counts for many users (Bernard's data: 940 chess.com vs 14
  lichess), making the minor platform invisible and creating spurious
  "rating spikes" when the rare points crossed.

  New behaviour on the Patterns page Rating Progression card:

  - **Players with only one platform** see no change — the chart looks
    identical to before. Zero regression.
  - **Players with both platforms** see a new toggle:
    `[Both | chess.com | lichess]`. Defaults to the most-played
    platform (single chart). Switching to `Both` shows two charts
    stacked vertically, each with its own Y-axis range. Switching to
    a single platform shows just that one full-width.
  - The existing time-class filter (`all / rapid / blitz / bullet /
    daily`) applies to all visible charts simultaneously.

  Implementation is entirely frontend — the chart was already computed
  client-side from the `games` prop (which already includes the
  `platform` field per game). No backend changes, no schema migration,
  no API changes.

### Tests
- 6 new frontend tests in
  `frontend/components/patterns/__tests__/rating-progression-chart.test.tsx`:
  - Single-platform players (chess.com only / lichess only) — no
    platform toggle rendered
  - Both platforms present — toggle visible with three options
  - Default selection = most-played platform (single chart)
  - Clicking `Both` renders two stacked charts
  - No rated games at all → component returns `null` (preserved legacy
    behaviour)
- Frontend total: 66 → **72 tests**. Backend unchanged at 358.

---

## [1.7.1] - 2026-05-24

### Fixed
- **ACPL inflation on mate-ending games.** The per-move centipawn-loss
  calculation capped each eval at ±1000cp but never capped the resulting
  loss, so a single move could contribute up to 2000cp to the average.
  This bit specifically on **checkmate-delivering moves** (e.g. `Qxf7#`)
  where Stockfish reports mate-encoded values (29990 → -30000) that
  survive the per-eval cap but produce huge differences. A 7-move
  Scholar's-Mate-style win could register ACPL ~291 instead of the real
  ~4. Visible as anomalous spikes on the ACPL Trend chart.

  Two-part fix applied to `analyzer.py`, `models.py::_backfill_acpl`,
  and `patterns.py::_compute_acpl_trend` (the fallback path):
  - **Played-best-move zero rule** — if `move_played == best_move`, the
    loss is 0. Playing the engine's #1 choice (including delivering
    mate) cannot be a "mistake". Matches Lichess convention.
  - **Per-move loss cap of `EVAL_CAP=1000`** — safety net for any
    remaining edge case where the cap-then-difference arithmetic could
    still produce >1000.

  Scope at time of release: across 952 analyzed games in the reference
  database, 339 games had at least one player-side move with raw
  swing > 1000 (potential mate artifact). 12 games had stored ACPL > 200
  (clearly distorted); 2 had ACPL > 300. After the fix: 3 games > 200
  (real bad games), 0 > 300.

### Added
- **`python main.py backfill-acpl [--force]`** — new CLI command. Without
  `--force`, computes ACPL only for games where it's currently NULL
  (same as the original migration behaviour). With `--force`, recomputes
  ACPL for ALL analyzed games — the migration path from v1.7.0 → v1.7.1.

### Migration
Run once after upgrade:
```
python main.py backfill-acpl --force
python main.py patterns
```
Takes ~30 seconds for ~1000 games. Idempotent (safe to re-run).

### Tests
- 3 new regression tests in `tests/test_models.py::TestBackfillAcplMateTransition`:
  - synthetic Scholar's-Mate game → ACPL ≤ EVAL_CAP, mate-delivering move
    contributes 0
  - non-best move with >2000cp raw swing → properly capped at 1000
  - `force=True` correctly overwrites previously-stored values
- Backend total: 354 → 358 tests, all green.

### Backwards-compatibility notes
- `move_analysis.swing_cp` historical values are NOT modified. Per-move
  data stays raw (preserves mate-transition signal for diagnostic use).
  Only the aggregate `games.acpl` is corrected.
- `classification` column is NOT touched (mate-delivering moves still
  show as "blunder" by raw swing; that's a separate, lower-priority
  fix deferred to a future release).

---

## [1.7.0] - 2026-05-18

### Changed
- **Model defaults bumped** for the two flagship cloud providers:
  - Anthropic: `claude-opus-4-6` → `claude-opus-4-7`
  - OpenAI: `gpt-5.4` → `gpt-5.5-pro-2026-04-23`

  The same change is reflected in `src/llm_providers.py` (the authoritative
  source), the Settings UI defaults + placeholders, README + ROADMAP +
  CLAUDE.md docs, and the relevant test mocks. Users with the old strings
  in their `config.yaml` continue to work — only the defaults move.

### Added — Phase 2 coaching diagnostics

Concerns surfaced during real use that the configured coaching history
depth (default 5, range 1-20) might not actually be reaching the LLM at
the user-set value. Audit confirmed the data flow is correct end-to-end,
but there was no visible signal to verify it from the outside. v1.7.0
adds three layers of visibility, no behaviour change:

- **Diagnostic log line** before every LLM coaching call. Format:
  ```
  Coaching game 1234 with claude:claude-opus-4-7 — history=10 games
  (~5,000 tokens), full prompt ~18,200 tokens
  ```
  Visible in the backend console / dashboard log.

- **`--dump-prompt PATH` flag** on `python main.py coach` and
  `python main.py run-all`. When set, the full assembled prompt is
  written to disk (one file per game) so you can verify with your own
  eyes that the history block is present and the LLM is getting what
  you configured. PATH can be a directory (files named
  `prompt_game_<id>.txt`) or a file path (suffixed `_game_<id>`).

- **"📚 N recent games in context" stamp** on the coaching panel in
  the dashboard. Shows the count of games the LLM had in its context
  window when generating that brief. Hover for explanation. Older
  briefs (pre-v1.7.0) show no stamp.

### Schema
- **New `coaching_meta_json` column** on the `game_coaching` table.
  Stores history depth, prompt token estimate, provider, and model
  used at coach time. Idempotent migration via `init_db()`.

### Tests
- 6 new tests in `tests/test_coach.py::TestCoachingDiagnostics` covering
  the token estimator, history counter, meta persistence, prompt dump,
  and response shape.
- Backend test count: 348 → 354.

### Why diagnostics, not "fix"
The audit confirmed history injection is working correctly. The user
concern was a *visibility* gap (the LLM is prompted to NOT repeat
history, so there's no observable cue that history was used). Phase 2
ships visibility. Phase 3 (context-window safety / auto-truncation if
the prompt overflows on smaller models like Ollama 8B) is deferred
until Phase 2 logging surfaces actual overflow cases on real games.

---

## [1.6.0] - 2026-05-18

A developer-quality release: no new user-facing features, but the frontend
finally has the same kind of test safety net the backend has had since v1.0.0.

### Added
- **Frontend test infrastructure** — Vitest + jsdom + Testing Library
  harness wired into the `frontend/` workspace. **66 frontend tests across
  7 files**, sub-second full run.
  - `lib/chess/{pgn,openings,lichess}.ts` — 35 unit tests covering helper
    behaviour, normalisation edge cases, and the load-bearing v1.4.5
    Lichess URL form (`/analysis/standard/{FEN}`; the `?pgn=` form is
    explicitly forbidden by `lichess.test.ts`).
  - `hooks/__tests__/use-chess-navigation.test.ts` — 17 tests, including
    the v1.4.5 clock-comment leak guard (chess.com `{[%clk ...]}`
    annotations must not leak into the moves array), FEN-array length
    invariant, boundary navigation, board orientation, and the
    keyboard handler's input/textarea focus guard.
  - Three component smoke + interaction tests:
    `components/hunter/__tests__/targeted-prep.test.tsx` (5 tests),
    `components/patterns/__tests__/you-fall-for.test.tsx` (4 tests),
    `components/patterns/__tests__/opening-explorer.test.tsx` (5 tests).
- **`frontend/lib/chess/`** — shared chess helpers extracted from three
  components that had been carrying near-duplicate copies:
  - `pgn.ts` → `parseMoveText`
  - `openings.ts` → `normalizeOpeningName`, `findCanonicalLine`,
    `findDeviationIndex`, and the `LibraryOpening` interface
  - `lichess.ts` → `lichessAnalysisUrl`
- **CI gate on frontend tests** — `.github/workflows/ci.yml` now runs
  `pnpm test:run` between `pnpm install --frozen-lockfile` and `pnpm build`
  in the frontend job so test regressions fail fast before the production
  build.
- **v1.4.5 regression locks at three layers** — helper (`lichess.test.ts`
  asserts the URL form), hook (`use-chess-navigation.test.ts` asserts no
  clock-comment leak), and component (all three component tests assert the
  `/analysis/standard/` form on the rendered `<a>`).

### Changed
- `components/hunter/targeted-prep.tsx` (−94 net lines),
  `components/patterns/opening-explorer.tsx`, and
  `components/patterns/you-fall-for.tsx` now import from `lib/chess/`
  instead of defining local helpers. Behaviour is byte-for-byte preserved;
  `opening-explorer.tsx`'s `parseMoveText` now also strips PGN result
  markers (`1-0` / `0-1` / `1/2-1/2` / `*`), which is additive — canonical
  book lines don't carry them.
- `frontend/vitest.setup.ts` gains a global `next/link` mock (async factory
  + dynamic React import to dodge ESM hoisting) so component tests can
  render `<Link>` without the Next runtime.
- Total project test count: **362 backend + 66 frontend = 428 tests**.

### Removed
- `STATE.md` — session-handoff file for the in-progress refactor; the work
  it tracked has shipped, so the file is no longer load-bearing.

## [1.5.0] - 2026-04-26

### Added
- **`python main.py serve`** — single command that starts both the API backend
  AND the Next.js frontend together. Spawns `pnpm dev` as a subprocess in its
  own process group, waits for the Next.js ready line, and prints a **unified
  banner** with both URLs in one place:

  ```
  🏰 Arrakis Engine running

     📡 Frontend UI:    http://localhost:3000   ← open this
     🔌 API backend:    http://localhost:8000
     📊 Live data from: data/chess_coach.db
     🕒 Auto-updates:   disabled (every 6h)

  Press Ctrl+C to stop both servers.
  ```

  Frontend output is line-prefixed with `[frontend]` so Next.js compile errors
  and hot-reload notifications stay legible. **Ctrl+C stops both servers
  cleanly** — SIGTERM to the frontend process group, then SIGKILL after a 5s
  grace period if it overstays.

  Recommended end-user entry point. The existing `python main.py dashboard`
  command still works for API-only setups (custom frontends, debugging,
  scripted pipelines) — its banner now includes a one-line hint pointing at
  `serve` for discoverability.

- **`src/dev_runner.py`** — new helper module owning the subprocess
  orchestration: `find_pnpm` (resolves direct `pnpm` or `corepack pnpm`),
  `check_node_modules`, `spawn_frontend`, `tail_with_prefix` (parses Next.js
  ready line + auto-detects the actual port when 3000 is taken),
  `terminate_process_group` (SIGTERM → wait → SIGKILL), `print_unified_banner`.

- Optional flags on `serve`:
  - `--port N` — backend port (default 8000)
  - `--frontend-port N` — passes through to `pnpm dev`. Omit to let Next.js
    auto-pick (handles port-3000-already-in-use gracefully)
  - `--install` — run `pnpm install --frozen-lockfile` first if
    `frontend/node_modules` is missing. Off by default — explicit beats
    surprising downloads.

- 30 new tests in `tests/test_dev_runner.py` covering pnpm resolution,
  node_modules detection, subprocess argv building, output prefixing + ready-line
  regex on multiple Next.js banner formats, wait-for-ready timeout / process-die
  handling, and SIGTERM-then-SIGKILL teardown.

### Changed
- `src/dashboard_server.py::run_dashboard` now accepts `api_only_banner: bool`
  (default `True`). The `dashboard` command keeps its verbose two-terminal
  banner with the new `serve` hint appended; `serve` passes `False` to
  suppress that banner and prints its own unified version.
- Backend test count: 318 → 348.

### Migration
None required. `python main.py dashboard` works exactly as before, with one
extra banner line pointing at `serve`. New users should start with `serve`.

---

## [1.4.5] - 2026-04-26

### Fixed
- **Hunt Mode "How the game went" panel was empty.** Chess.com PGNs include per-move clock annotations like `{[%clk 0:09:55]}` between every move. The annotated-move-list parser used a simple regex that didn't strip these, leaving the first parsed token as a stray `}`. The mini-board still rendered correctly (chess.js handles annotations), but the move list shown next to it was just `1.}`. Switched the annotated move list to consume `nav.moves` from `useChessNavigation` directly — chess.js does the heavy lifting and produces clean SAN, removing ~10 lines of fragile regex.
- **Canonical-line lookup missed openings whose names use different punctuation between chess.com and Lichess.** Chess.com calls it "Caro Kann Defense Advance Short Variation with 4 Nf3...e6"; Lichess calls it "Caro-Kann Defense: Advance Variation, Short Variation". The previous `findCanonicalLine` matcher only did `startsWith` on raw names — so it failed. New `_normalizeOpeningName` helper strips colons/commas/hyphens/apostrophes/dots, lowercases, and collapses whitespace before comparing. Both names now match. Returns the longest match to prefer specific variations over generic openings.
- **Hunt Mode opponent input was triggering iCloud Keychain / 1Password / LastPass autofill.** The label "Opponent username" plus `id="opponent"` looked enough like a credential field that Safari surfaced "Open Passwords App" on focus. Renamed the label to "Opponent handle", changed `id` and `name` to `opponent-handle`, added `data-1p-ignore`, `data-lpignore`, `data-form-type="other"`, and `autoComplete="off"` on both the form and input. Combined effect: no password manager dropdown.

### Changed
- `useChessNavigation` hook is now the canonical source for parsed game moves. The Hunt Mode `AnnotatedMoves` component takes `gameMoves: string[]` directly instead of re-parsing the raw PGN with regex.

---

## [1.4.4] - 2026-04-26

### Added

**Hunter Mode opening rows are now click-to-expand.**

Click any row in **Their Weaknesses** or **Their Strengths** to see how the opponent actually played that opening. The expanded panel shows:

1. **Mini chess board** with step-through controls walking through an actual game where the opponent had that outcome (most recent first).
2. **"Game N of M" flip controls** to step through up to 5 representative games per opening.
3. **Annotated move list** with green ✓ markers for canonical book moves and an orange `!` highlighting the move where the opponent first deviated from book theory. Below: a one-line summary of the deviation ("Deviation at move 6: opponent played Bb4, book is Bc5").
4. **"Study this position on Lichess →"** deep link opening Lichess analysis at the trap's final position with cloud eval + opening explorer pre-loaded.
5. **"View source ↗"** link to the original game on chess.com / lichess (when available).
6. **Fallback:** if no actual games are cached for an opening (old profile from before v1.4.4), the board falls back to the canonical opening line from the Lichess CC0 library so the row is never empty.

Same UX applied symmetrically to both Weaknesses and Strengths.

**Local accumulating game cache for Hunter Mode.**

New `opponent_games` SQLite table keeps per-opponent PGNs locally. Each refresh:
- Fetches only games newer than the last cached date (faster, kinder to chess.com / lichess APIs)
- Dedups on `game_url`
- Prunes by sliding window (`features.hunter_lookback_months`, default 6) — old games drop off naturally
- Optionally caps total games per opponent (`features.hunter_max_games_per_opponent`)
- Recomputes the profile from the accumulated set

Profile UI now shows "X games · Y accumulated" in the header so you can see the underlying cache size.

### Fixed
- **Lichess deep link in Trap Patterns** now actually pre-loads the position. The previous `?pgn=...` query format wasn't honoured by Lichess. Switched to the documented `/analysis/standard/{FEN}` URL format using a new `endFen` value exposed by the `useChessNavigation` hook. Same fix benefits the Hunter Mode opening rows.

### Schema
- New `opponent_games` table — idempotent migration via `init_db()`. Indexes on `(username, platform)` and `(username, platform, date_played DESC)`.
- New config flags in `config.yaml`:
  - `features.hunter_lookback_months: 6`
  - `features.hunter_max_games_per_opponent: null`
- `useChessNavigation` hook now returns `endFen` and `fens` (the raw FEN array) in addition to `currentFen`. Backward-compatible — existing callers ignore the new fields.

### Tests
- 10 new tests in `tests/test_hunter.py` covering accumulation (first-call insert, dedup on game_url, sliding window prune, max-games cap, NULL-date defensive keep) + representative games (newest-first, 5-cap, ECO propagation, outcome filtering) + meta `accumulated_games` counter.
- Backend test count: 308 → 318.

### Migration note
First time you refresh an opponent profile after upgrading, Hunter Mode will fetch the full lookback window (6 months by default). Subsequent refreshes are incremental — only new games since the last fetch.

---

## [1.4.3] - 2026-04-26

### Added
- **Click-to-expand on every trap row** in the Patterns → Self-Analysis → Trap Patterns section. Each row now opens an inline detail view with three things:
  1. **Mini chess board** with step-through controls (⏮ ◀ ▶ ⏭) playing the trap's signature moves so the player can SEE how it unfolds. Reuses the existing `ChessBoard` + `useChessNavigation` + `MoveControls` components.
  2. **"Recent games where this happened"** — clickable links to `/<player>/games/<id>` for the actual games where the player fell into (or won with) the trap.
  3. **"Study this line on Lichess →"** deep link to `lichess.org/analysis` with the trap's PGN pre-loaded for deeper study with Lichess's own opening explorer + cloud eval.
- All three apply symmetrically to **Your Arsenal** (traps you win with) and **You Fall For** (traps that beat you).

### Fixed
- **Hunter Mode 404 for mixed-case usernames** — chess.com's API requires lowercase usernames in the URL path; mixed-case names returned a 301 that worked but cost an extra round-trip. Both `_fetch_chesscom_opponent_games` and `_fetch_lichess_opponent_games` now lowercase the input username up front. The user-facing fix: opponents like `Cyborg_warrior` resolve correctly on first try.

### Changed
- `src/patterns.py::_aggregate_traps_by_outcome` now tracks `recent_game_ids` (up to 5, newest-first) alongside `recent_dates`. Required for the trap-row links to work. **After upgrading, run `python main.py patterns` once** to repopulate `stats_json` with the new field.
- Backend test count: 304 → 308 (+4 new tests covering trap `recent_game_ids` and username lowercasing).

### Migration note
The new trap-row expansion only renders when:
1. You've re-run `python main.py patterns` (or hit "Insights" in the dashboard) after upgrading, AND
2. You have at least one named trap detected in your games.

Without (1), the trap rows still render the v1.4.0 summary but expansion shows "trap library entry not loaded" because `recent_game_ids` is missing from the cached stats.

---

## [1.4.2] - 2026-04-26

### Added
- **Hunter Mode UI** — new `/[player]/hunt` page with opponent search and the targeted-prep view. Enter an opponent username + platform (chess.com or lichess), get back a White/Black-toggle view of:
  - **Their Weaknesses** (red, "target these openings") — openings the opponent loses
  - **Their Strengths** (green, "avoid these lines") — openings the opponent wins
- **Hunt nav link** added to the player-scoped nav bar (between Patterns and Reports).
- **Refresh button** on the targeted-prep view forces a re-fetch (bypasses the 24h cache from v1.4.1).
- New typed API client functions: `fetchHunterProfile`, `refreshHunterProfile`.
- New types in `frontend/lib/types.ts`: `OpponentProfile`, `OpponentOpeningEntry`, `OpponentOpeningSplit`, `HunterMeta`, `HuntPlatform`.

### How to try it

```bash
git pull
# Terminal 1: backend
python main.py dashboard
# Terminal 2: frontend
cd frontend && pnpm dev
# Open http://localhost:3000/<your-player>/hunt
# Enter an opponent's username and platform → click "Hunt Mode"
```

---

## [1.4.1] - 2026-04-26

### Added
- **Hunter Mode — backend (data + API).** Fetches an opponent's recent public games from chess.com or lichess (no Stockfish, no DB pollution) and computes their opening profile so the player can prepare against them. Two new REST endpoints:
  - `GET /api/hunt/profile?opponent=<username>&platform=<chess.com|lichess>` — returns the opponent's profile, served from cache if fresh (within 24 hours) or fetched live otherwise.
  - `POST /api/hunt/refresh` (body `{opponent, platform}`) — forces a re-fetch, bypassing the 24h TTL.
- **`src/hunter.py`** — new module: `fetch_opponent_games`, `compute_opponent_profile`, `get_or_fetch_profile` with cache wrapper. Reuses the chess.com / lichess fetch helpers from `harvester.py` to avoid code duplication.
- **`opponent_cache` table** — new SQLite table (idempotent migration via `init_db()`); profile is stored as a JSON blob keyed on `(username, platform)`. 24h TTL.
- **`features.hunter_mode` config flag** — defaults to `true`; set to `false` in `config.yaml` to disable opponent prep entirely (returns 403 from the hunt endpoints).
- 29 new tests in `tests/test_hunter.py` covering platform normalization, profile aggregation, cache hit/miss/TTL, fetch dispatch, end-to-end get-or-fetch, and the schema migration.

### Note on UI
This is a **backend-only release**. The Hunter Mode UI lands in v1.4.2 (planned next). You can hit the API today with `curl`:
```bash
curl 'http://localhost:8000/api/hunt/profile?opponent=MagnusCarlsen&platform=chess.com' | jq
```

### Changed
- Backend test count: 285 → 318.

---

## [1.4.0] - 2026-04-26

### Added
- **Self-Analysis on the Patterns page** — new section below Opening Performance with two components:
  - **Fix Your Openings** — surfaces openings you lose (Your ELO Leaks) and openings you win (Your Strengths) with White/Black tabs and a "Study most recent" link to the relevant game.
  - **Trap Patterns** — recognizes ~100 well-known named opening traps in your games and groups them into "Your Arsenal · Keep using!" (traps you win with) and "You Fall For · Avoid these!" (traps that beat you). Includes Stafford, Elephant, Fried Liver, Englund, Halloween, Cochrane, Wayward Queen Attack, Latvian, Damiano, Traxler, and many more.
- **Lichess CC0 opening library upgrade** — `frontend/public/data/openings.json` upgraded from a 440-entry subset to the full Lichess CC0 dataset (3,690 named openings).
- **Curated trap library** — new `frontend/public/data/traps.json` with 102 shallow named traps suitable for beginner-trap detection.
- **Build script** — `scripts/build_traps.py` fetches the Lichess TSV source and rebuilds both data files. Supports `--dry-run` and `--offline` modes.
- 39 new tests across `tests/test_loss_openings.py` and `tests/test_trap_matcher.py` covering loss/strong opening aggregation, trap-library loading, longest-prefix matching, and end-to-end trap-falls / your-arsenal computation.

### Changed
- `src/patterns.py` — adds `_load_trap_library`, `_extract_san_moves`, `_match_trap`, `_compute_loss_openings`, `_compute_strong_openings`, `_compute_trap_falls`, `_compute_your_arsenal`. All four are wired into `compute_player_patterns()` and ride the existing `player_patterns.stats_json` blob — no DB schema change.
- `frontend/lib/types.ts` — new `LossOpeningEntry`, `LossOpeningAnalysis`, `TrapEntry` types; `PatternStats` extended with `loss_openings`, `strong_openings`, `trap_falls`, `your_arsenal`.
- Backend test count: 246 → 285.

---

## [1.3.2] - 2026-04-26

### Changed
- **Clearer dashboard startup banner** — `python main.py dashboard` now explicitly tells you it's the API server (port 8000) and points you to start the Next.js frontend (port 3000) in a second terminal. Previously the banner said "ArrakisEngine Dashboard" which was confusing because the actual dashboard UI lives at port 3000, not 8000.
- **README Quick Start clarified** — the two-server architecture (Python backend + Next.js frontend) is now an explicit numbered step with a two-row table instead of a single buried `# Open http://localhost:3000` comment.

---

## [1.3.1] - 2026-04-26

### Fixed
- **Dashboard server console noise** — when a client (typically the Next.js dev server during hot reload, or any browser navigating away mid-fetch) closes the connection while the API is still writing a response, the server raised `ConnectionResetError` / `BrokenPipeError` and logged two full stack traces at ERROR level. Both spots now swallow the error, log it at DEBUG instead, and skip the doomed recovery 500-response. No behavior change for real errors — those still log and respond as before.
- 4 new tests in `TestClientDisconnectHandling` covering both `_send_json` swallowing and `_handle_api` short-circuit on disconnect, plus a regression guard that real exceptions (non-disconnect) still propagate.

---

## [1.3.0] - 2026-04-26

### Added
- **Configurable coaching history depth** — new `coaching_history_count` setting (default 5, range 1–20) controls how many recent coached games are injected into the LLM prompt. Previously hardcoded to 5. Surfaced in the Settings → Coaching UI with token-cost guidance and as a `--history N` CLI flag on `coach` and `run-all` commands.
- README section "Coaching History Depth" documenting per-game token cost (~500 tokens) and per-provider recommendations (5 for Ollama 8B, up to 20 for large-context cloud providers).
- 6 new tests in `tests/test_coach.py::TestCoachingHistoryDepth` covering default behavior, custom limits, current-game exclusion, and config-wiring contract.

---

## [1.0.2] - 2026-04-21

### Fixed
- **Settings player dialogs**: resolved `<button> cannot be a descendant of <button>` hydration error in `PlayerFormDialog` and `RemovePlayerDialog`. Base UI's `DialogClose` was wrapping a `<Button>`, creating nested `<button>` elements. Switched to Base UI's `render` prop pattern so props merge into the Button instead of wrapping it.
- **Add/edit player form**: FIDE ID and other fields now save reliably — the hydration error above was breaking the form's `onSubmit` handler, preventing new player records (and FIDE ID updates) from being saved.

---

## [1.0.1] - 2026-04-12

### Fixed
- **Opening explorer game list**: date and opponent name no longer overlap — widened the date column from 80px to 144px to fit full datetime strings
- **Patterns page tooltips**: Coaching Summary and all six StatCard info icons now open clickable portal-based info modals instead of relying on HTML `title` attributes (which were clipped by Card `overflow-hidden`)

---

## [1.0.0] - 2026-04-06

First public open-source release under AGPL-3.0.

### Added

**Core Pipeline**
- Chess.com game harvester with rate limiting and deduplication
- Lichess game harvester with API integration
- FIDE rating lookup and sync
- Stockfish analysis engine (depth 22, multi-threaded, per-move timeout)
- ACPL calculation with ±1000cp eval capping (Lichess/Chess.com standard)
- Adaptive tier system — analysis depth and move thresholds scale with player rating
- LLM coaching layer with unified provider abstraction (`src/llm_providers.py`) supporting 8 providers
- 8 LLM providers: Claude, ChatGPT, Gemini, Grok, Mistral, DeepSeek, Qwen, Ollama (local)
- Ollama integration for free, local coaching with no API key required
- Reasoning models required — chain-of-thought essential for tactical analysis, coaching history, and age-appropriate explanations
- Cross-game pattern detection (16 metrics)
- Markdown report generator with time control filtering
- Automated pipeline scheduler (harvest → analyze → patterns → coach) with cancel support
- CLI with 10 commands: harvest, analyze, coach, patterns, export-json, report, dashboard, fide-update, backfill-clocks, run-all

**LLM Coaching**
- Game type detection — classifies games into 10 types (tactical battle, comeback, collapse, positional grind, opening disaster, miniature, etc.) with type-specific coaching guidance
- Coaching history injection — last 5 coached games' lessons fed into the LLM prompt to avoid repetitive feedback and build on prior advice
- Coaching settings UI — customizable tone (encouraging / balanced / technical), detail level, focus areas, and free-form custom instructions
- Variety instructions in coaching prompt to ensure fresh, non-formulaic output
- "Generate Coaching Briefs" pipeline button — batch-coach games from the dashboard UI with progress tracking, cancel support, and per-player filtering
- Provider selector (8 providers with Cloud/Local grouping) for coaching briefs and per-game coaching
- "Run All Steps" executes the full 4-step pipeline (harvest → analyze → patterns → coach) with provider selection
- Per-game coaching runs independently from batch coaching — skip guard prevents overwrites
- Games coached in chronological order (oldest-first) so coaching history builds naturally
- Full datetime storage in `date_played` for correct chronological ordering
- Exponential backoff on API rate limits (30s → 60s → 120s, max 5 minutes)
- Consecutive failure circuit breaker (3 failures → abort batch)
- Authentication error detection with immediate abort
- Interruptible sleep via threading.Event for responsive cancellation
- Extended SDK timeouts (300s) for reasoning models (Claude Opus, Gemini 2.5 Pro, DeepSeek Reasoner)

**Frontend Dashboard (Next.js + shadcn/ui)**
- Player landing page with rating cards and platform links
- Games list with coaching status filter, month/year filter, and search
- Game detail view with interactive chessboard, move-by-move eval chart, and coaching panels
- Game comparison (side-by-side analysis of two games)
- Patterns page with 16 analysis components:
  - Move Quality Distribution, Phase Performance, Time Control Performance
  - Opening Performance, Trend Summary, Danger Zones
  - Endgame Conversion, Critical Positions, Tactical Misses
  - Comeback & Collapse, Repertoire Consistency, Opening ACPL
  - Opening Repertoire Tracker, Time Pressure Analysis
- Info modals (ⓘ) with educational explanations for every pattern component
- Reports page with LLM-powered cross-game trend summaries
- Opening explorer with Lichess opening book integration
- Rating progression charts
- Settings page — player CRUD, Stockfish config, API key management for all 7 cloud providers (collapsible), coaching settings
- Pipeline control panel (harvest → analyze → insights → coaching briefs from UI) with provider selector
- Portal-rendered tooltips for pipeline buttons (prevents card overflow clipping)
- Error boundaries — root error boundary, player-scoped error boundary, custom 404 page
- Accessibility — aria-labels on player selector buttons and game table rows
- Dark/light mode toggle
- Mobile responsive layout

**Infrastructure**
- SQLite database with auto-migration
- Config via YAML with environment variable secrets (schedule section for auto-pipeline)
- Pinned Python dependencies (`==`) for reproducible installs
- AGPL-3.0 license
- GitHub Actions CI (Python 3.11/3.12 + frontend build)
- 240 tests across 15 files (227 unit + integration + live API)
- CONTRIBUTING.md with CLA for dual-licensing
- CODE_OF_CONDUCT.md (Contributor Covenant v2.1)
- ROADMAP.md with Ollama/open-source reasoning model plans
- README.md table of contents with linked section navigation
- 10 screenshots added to README.md (Dashboard, Games, Patterns 1–7, Reports)

---

## Pre-release Development History

### [0.8.0] - 2026-04-04

**Settings & Pipeline Controls**
- Settings page with player CRUD (add, edit, delete players from UI)
- Stockfish configuration panel in Settings
- API key management in Settings
- Info modals (ⓘ) for all 16 pattern components with educational explanations
- Pipeline control panel with Fetch → Analyze → Insights → Run All buttons
- Real-time progress bar and step indicators for pipeline tasks
- Automatic updates toggle with configurable interval (1-24 hours)
- Player selector for pipeline operations (run for one player or all)

---

### [0.7.0] - 2026-03-29

**Reports, Opening Explorer & Game Comparison**
- Reports page with monthly/weekly coaching reports for coaches
- Time class filter tabs (Rapid / Daily / All) — stats recompute per filter
- Game-by-game results table with clickable links, sorted most-recent-first
- LLM-powered trend summaries — AI-generated coaching narratives interpreting cross-game patterns
- Generate with Claude / ChatGPT buttons for trend summaries
- Player-scoped URLs (`/<player>/games`, `/<player>/patterns`, `/<player>/reports`)
- Opening explorer — click any opening to expand a chessboard showing the position with step-through move controls
- Opening book integration — 438 ECO entries (A00-E99) with book move vs player move annotations
- Rating progression chart with result-colored dots and 10-game moving average trend line
- Game comparison — select two games and compare side-by-side with independent chessboards
- Opening repertoire tracker with ECO distribution and trend indicators
- Time pressure analysis (time management score, blunder rate under pressure)
- PDF export via `window.print()` with print-optimized CSS

---

### [0.6.0] - 2026-03-27

**Advanced Pattern Metrics & Testing**

Phase 1 Metrics:
- Accuracy % — percentage of moves matching engine's best move
- Consistency Score — standard deviation of per-game ACPL with rating
- Danger Zones — histogram of blunders/mistakes by move number range (5-move buckets)
- Endgame Conversion — tracks winning/losing/equal endgame outcomes
- Time Control Performance — win rate, ACPL, and blunder rate per format

Phase 2 Deeper Insights:
- Critical Position Success Rate with SVG gauge charts
- Comeback & Collapse Rate — measures mental resilience and composure
- Opening Quality Analysis — ACPL per opening with verdict badges
- Tactical Miss Rate — positions where a tactic existed but was missed, by game phase
- Repertoire Consistency — opening focus score split by color

Testing:
- 78 new tests (91 → 169 total) with shared conftest.py
- Integration tests for Stockfish analysis on Scholar's Mate
- Live API tests for LLM coaching (~$0.05/run)
- Full pipeline E2E test (analyze → coach end-to-end)

---

### [0.5.0] - 2026-03-26

**Next.js Frontend Rewrite**
- Complete Next.js 16 + React 19 + shadcn/ui frontend rewrite
- Interactive chessboard with custom CSS grid and lichess cburnett SVG pieces
- Game detail page with eval chart (bars colored by move classification), move list, coaching panels
- Move quality summary table with proportional bars
- Color-coded moves for both player and opponent in move list
- Pattern component visualizations (move quality donut, phase performance, ACPL trend)
- Dark/light mode toggle with session persistence
- Mobile responsive layout (320px+)

---

### [0.4.0] - 2026-03-22

**Multi-Platform Support & Dashboard Polish**
- Lichess game harvester alongside Chess.com (multi-platform support)
- FIDE rating integration with player profile links
- Player dashboard landing page with rating cards and platform links
- Adaptive tier system (Beginner → Expert) with rating-scaled move thresholds
- Light/dark mode toggle
- Coaching buttons on dashboard for on-demand LLM analysis (Claude / ChatGPT)
- Coaching status filter and icons in games list
- Opening analysis in coaching prompt and dashboard display
- "Feedback to the Player" coaching section with 3 actionable tips
- Move quality summary table and color-coded moves
- Opening performance split by color with tabbed view (All / White / Black)
- ACPL Trend tooltip with definition and rating benchmarks
- OpenAI switched to Responses API
- Rate limit handling — 10s delay between calls, 60s retry on 429
- Analyzer per-move time limit to prevent hanging on complex positions
- ACPL calculation with ±1000cp eval capping
- Token overflow fix for long games in coaching prompts

---

### [0.3.0] - 2026-03-20

**Web Dashboard & CLI Integration**
- Web dashboard served by Python HTTP server
- Live SQLite API backend with REST endpoints
- Coach reports generator (weekly/monthly Markdown exports)
- Full CLI integration with 10 commands
- Comprehensive README with installation, CLI usage, and architecture documentation

---

### [0.2.0] - 2026-03-20

**LLM Coaching & Pattern Detection**
- LLM coaching layer with dual provider support (Anthropic Claude, OpenAI GPT)
- Structured coaching output: game narrative, key lesson, practical focus, critical moments, coach notes
- Cross-game pattern tracker with opening performance, ACPL trends, and rating performance
- JSON export for dashboard consumption

---

### [0.1.0] - 2026-03-20

**Initial Core Pipeline**
- Initial project structure and SQLite schema (players, games, move_analysis tables)
- Chess.com game harvester with monthly archive API integration
- Stockfish analysis engine with configurable depth, threads, and hash
- Per-move centipawn evaluation and win probability calculation
- Move classification (excellent, good, inaccuracy, mistake, blunder)
