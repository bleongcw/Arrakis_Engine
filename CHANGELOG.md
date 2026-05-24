# Changelog

All notable changes to ArrakisEngine will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
