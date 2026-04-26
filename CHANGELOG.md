# Changelog

All notable changes to ArrakisEngine will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
