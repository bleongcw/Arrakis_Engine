# Arrakis Engine — Architecture

*Last updated: 2026-05-29 — corresponds to v1.18.3*

This document describes the technical architecture of Arrakis Engine: how the pieces fit together, what runs where, and the design decisions behind them. It is aimed at contributors and developers reading the codebase. For end-user / setup docs, see [README.md](../README.md). For changelog, see [CHANGELOG.md](../CHANGELOG.md).

---

## 1. System Overview

Arrakis Engine is a local chess coaching application. It pulls games from chess.com and Lichess, analyzes them with Stockfish, runs LLM-based coaching on top of the engine output, aggregates patterns across games, and exposes everything through a Next.js dashboard.

The core insight is **two-step analysis**:

1. **Stockfish** produces objective per-move evaluations (centipawn loss, best move, win probability).
2. A **reasoning LLM** interprets that engine output into human coaching language — appropriate for the player's age and rating.

A third **pattern aggregation** layer runs across all of a player's games to surface trends that no single-game review can show (e.g. "blunders cluster between moves 30–40 across the last 20 games").

Two later layers build on this:
- **Tactical-motif detection** (v1.14.0–v1.17.0): `motifs.py` tags each critical move
  with the 12 themes it executes or misses (fork, pin, skewer, …, zugzwang). These
  feed a cross-game aggregation (`_compute_motif_summary`) with per-phase breakdown
  that lands in coaching prompts + the Tactical Themes Patterns card.
- **Journal** (v1.10.0–v1.12.0): a chronological diary of coaching artifacts —
  LLM-generated Recent Form Reviews and manual Parent Notes — stored in
  `journal_entries` and rendered as a threaded social feed.

### High-level flow

```
chess.com / Lichess API
        │
        ▼
   harvester.py  ──► SQLite (games)
        │
        ▼
   analyzer.py   ──► SQLite (move_analysis)         [Stockfish depth 22 + motif tags]
        │
        ▼
     coach.py    ──► SQLite (game_coaching)         [LLM reasoning model]
        │
        ▼
   patterns.py   ──► SQLite (player_patterns)       [aggregation + motif summary]
        │
        ▼
dashboard_server.py  ──► Next.js frontend            [REST API + dashboard UI]
```

The same pipeline can be triggered three ways:

- **CLI** — `python main.py run-all` and per-step commands
- **Dashboard UI** — pipeline control panel on `/dashboard`
- **Scheduler** — daemon thread driven by `scheduler.py` on a configurable interval

---

## 2. Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Database | SQLite (WAL mode, single-file `data/chess_coach.db`) |
| Engine | Stockfish (local binary, e.g. `/opt/homebrew/bin/stockfish`) |
| LLM SDKs | `anthropic`, `openai`, `google-generativeai`, `mistralai`, plus OpenAI-compatible HTTP for xAI / DeepSeek / Qwen / Ollama |
| Backend HTTP | Python `http.server` (stdlib) — no FastAPI / Flask dependency |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/ui (Base UI primitives) |
| Charts | Recharts |
| Tests | pytest (backend) + Vitest + Testing Library (frontend, v1.6.0+) |

The backend is intentionally dependency-light — `http.server` is enough for a single-user local app and avoids pulling in a web framework.

---

## 3. Backend (`src/`)

### `harvester.py` — game ingestion
- Pulls monthly archives from the chess.com public API and the Lichess `/api/games/user/{username}` endpoint.
- Deduplicates against existing rows in `games` (keyed on `game_url`).
- Extracts color, opponent, time control, ratings, and result from PGN headers.
- Default lookback: 6 months (`months_lookback` in `config.yaml`).
- Rate-limited with backoff to respect the public APIs.

### `analyzer.py` — Stockfish engine layer
- Replays each PGN move-by-move against a local Stockfish process via `python-chess`.
- Per move it stores `eval_cp`, `swing_cp`, `win_prob`, `best_move`, `pv_line`, and a classification.
- **ACPL capping at ±1000 cp + played-best-zero rule** (v1.7.1, extended in v1.7.4): per-move centipawn loss caps both the raw eval AND the resulting loss at `EVAL_CAP=1000`. If the played move equals the engine's #1 best move (`move_played == best_move`), loss is recorded as 0 — Lichess convention. This avoids the mate-transition bug where checkmate-delivering moves like `Qxf7#` would otherwise register as 2000cp losses (Stockfish encodes mate as ±30000 internally). v1.7.4 extracted the formula into a single helper `_per_move_player_loss()` in `patterns.py` and applied it across all 6 cross-game ACPL widgets that previously inlined the broken formula. Backfill via `python main.py backfill-acpl --force` after upgrading.
- Move classifications:
  - Excellent: `< 30 cp` loss
  - Good: `< 50 cp`
  - Inaccuracy: `< 100 cp`
  - Mistake: `< 300 cp`
  - Blunder: `≥ 300 cp`
- Win probability: Lichess formula — `winPct = 50 + 50 × (2 / (1 + exp(-0.00368208 × cp)) − 1)`.
- Configurable depth (22), threads (6), hash (512 MB), and per-move time limit.
- **Motif tagging** (v1.14.0): for each critical move (|cp_loss| ≥ 50), the analyzer
  calls `motifs.detect_motifs` on both the played move and the engine's best move,
  storing the result as `move_analysis.motifs_json`.

### `motifs.py` — tactical-motif detection (v1.14.0, v1.17.0)
- 12 pure-Python detectors, each `detect_X(board, move, pv) -> str | None`, depending
  only on `python-chess` primitives (`board.attackers`, `board.is_pinned`,
  `board.gives_check`, a min-value SEE heuristic, PV-walking for mate look-ahead).
- The 12: `fork`, `pin`, `skewer`, `discovered_check`, `mate_threat`,
  `removing_defender`, `hanging_piece`, `trapped_piece` (v1.14.0) + `back_rank_mate`,
  `deflection`, `overloaded_defender`, `zugzwang` (v1.17.0).
- `detect_motifs(board, move, pv)` runs all detectors in specificity order and returns
  the matching identifiers. Conservative by design — false negatives preferred over
  false positives. The skewer detector was calibrated in v1.15.1 to require
  attacker-value < front-piece-value (the original over-fired ~10–18×).
- Standalone: no DB / analyzer / coach imports. Backfillable via
  `python main.py rescan-motifs` (no Stockfish — reuses stored `pv_line`/`best_move`).

### `coach.py` + `llm_providers.py` — LLM coaching layer
- `llm_providers.py` is the unified abstraction for **8 providers**: Anthropic, OpenAI, Google, xAI, Mistral, DeepSeek, Qwen, and Ollama. Each provider is registered with its SDK type, default model, API key env var, and request shape. Current default reasoning models (v1.7.0): Claude Opus 4.7 (`claude-opus-4-7`), GPT-5.5 Pro (`gpt-5.5-pro-2026-04-23`), Gemini 2.5 Pro.
- `coach.py` builds the prompt from Stockfish data + recent coaching history + the player's measured 30-day trajectory (v1.8.0), sends it through the provider abstraction, and stores the structured output in `game_coaching`.
- **Reasoning models are required.** The system enforces this — non-reasoning models produce shallow, generic coaching that misses tactics. See [`ROADMAP.md`](../ROADMAP.md) (root, not the gitignored one) for the full rationale.
- Coaching output is structured: narrative, key lesson, practical focus, critical moments, opening analysis, coach notes, and a personal `player_feedback` letter — for two audiences (child-facing, coach-facing).
- **Coaching history injection** (v1.7.0): a configurable number of recent coached games' lessons are fed into the prompt so the LLM doesn't repeat itself and can build on prior advice. Default is 5 (range 1–20) via the `coaching_history_count` setting in `config.yaml` or the `--history N` CLI flag. Each history game adds ~500 prompt tokens — see the README "Coaching History Depth" section for per-provider guidance.
- **Player trajectory injection** (v1.8.0): in addition to history, the per-game prompt now includes a structured `## Player Trajectory (last 30 days)` block built by `patterns.py::build_trajectory_block`. The block surfaces 6–8 measured cross-game signals (weakest/strongest phase ACPL, tactical miss rate, endgame conversion, ACPL trend direction over 4 weekly buckets, comeback/collapse rates, repertoire focus) plus a synthesized headline. ~200–250 tokens. Gated by `coaching_trajectory_enabled: true` (default ON); the CLI `--no-trajectory` flag overrides per-run for A/B comparison. When the player has no `player_patterns` row yet, the block is silently skipped.
- **Auto-refresh of player_patterns** (v1.8.0): `_maybe_refresh_patterns()` calls `compute_player_patterns(player_id)` (pure-Python, no LLM, ~3–5s per player on a full DB) before coaching if the patterns row is >7 days old OR if completed games exist beyond the row's `period_end`. Means trajectory is always reasonably fresh without the user having to remember `python main.py patterns`. Never auto-calls `generate_trend_summary()` — that's a paid LLM round-trip.
- **Game-type detection** classifies games into 10 archetypes (tactical battle, comeback, collapse, positional grind, miniature, etc.) and tailors the prompt accordingly.
- **Coaching meta diagnostics** (v1.7.0, extended in v1.8.0): every coached game stores `coaching_meta_json` capturing history depth, prompt size, model, and trajectory state (`trajectory_injected`, `trajectory_age_days`, `trajectory_weakest_phase`, `trajectory_trend_direction`, `trajectory_tokens_estimate`). The frontend renders these as small badges on the coaching panel so the user can verify what the LLM actually saw.
- Resilience: exponential backoff (30s → 60s → 120s, max 5 min), 3-failure circuit breaker, 300s SDK timeout for reasoning models, interruptible sleep via `threading.Event`.

### `patterns.py` — cross-game aggregation
Aggregates 20+ metrics per player across all analyzed games. Stored as one JSON blob per player in `player_patterns.stats_json`. Also exposes `build_trajectory_block(conn, player_id)` (v1.8.0) which extracts a structured 6–8-fact snapshot of the player's measured trajectory for injection into the per-game coaching prompt; see `coach.py` above.

The four metrics added in v1.4.0 are the **Self-Analysis** family — they answer "what should I study next?" rather than "what's true about my play?":

| Metric | Backed by | What it answers |
|---|---|---|
| `loss_openings` | PGN opening name + outcome filter | Which openings cost you the most ELO, split by color |
| `strong_openings` | mirror of above for wins | Which openings you should keep playing |
| `trap_falls` | longest-prefix match against `frontend/public/data/traps.json` (curated CC0 Lichess subset) | Recurring named traps your opponents use to beat you |
| `your_arsenal` | mirror for wins | Recurring named traps you successfully use |

The trap library is built once by `python scripts/build_traps.py`, which fetches the Lichess [`chess-openings`](https://github.com/lichess-org/chess-openings) CC0 TSV data, filters to named traps / gambits / attacks / mates (≤16 plies), and writes `frontend/public/data/traps.json` and the full opening book at `frontend/public/data/openings.json`. v1.18.0 broadened the filter from a ~100-entry curated allowlist to a substring match over the full Lichess set → **1,475 traps** (openings: 3,690). Both files are vendored so runtime has no network dependency. Re-run when Lichess updates upstream (a few times per year).

**Motif aggregation (v1.15.0–v1.16.0):** `_compute_motif_summary(games, moves_by_game, period_days)` rolls the per-move `motifs_json` tags up into a player-level view — per-motif missed/found counts over the 30-day window, with per-phase (opening/middlegame/endgame) splits and a `dominant_missed_phase` tag (set when one phase holds ≥60% of misses and total ≥3). Surfaced three ways: the `TREND_PROMPT` motif section, the per-game `build_trajectory_block` recurring-themes block, and the frontend `<MotifThemes>` Patterns card. The prompts ask the LLM to name the motif (and its dominant phase, if any) in a practice recommendation when it crosses the ≥5-instance bar.

**Recurring weakness escalation (v1.19.0):** the same aggregator additionally tracks, per motif, the **distinct-game spread** (`missed_games` — separate games carrying a missed instance, not raw instance count) and the **recency streak** (consecutive most-recent games with motif data in which it was missed). `_escalation_tier(missed_games, streak, games_with_motif_data)` maps these to `none`/`watch`/`focus`/`priority`: spread sets the base (≥3 → watch, ≥5 → focus, ≥8 → priority), an active streak ≥3 boosts one level, and the whole thing is gated by ≥4 games-with-motif-data so new accounts can't false-alarm. Output: per-motif `missed_games`/`streak`/`escalation` fields plus a top-level `escalated_weaknesses` list and `games_with_motif_data`. Three surfaces: (1) `build_trajectory_block` leads with a `⚠ RECURRING WEAKNESS` line + records `recurring_weakness`/tier in `coaching_meta_json`, and the coaching prompts gain a clause to lead with it and prescribe a concrete drill instead of restating the diagnosis; (2) the `<MotifThemes>` card renders a 🔴/🟠/🟡 escalation badge; (3) a fire-once `weakness_alert` Journal entry is filed for priority-tier weaknesses (see `journal.py`). Alerts fire only via `compute_player_patterns(emit_weakness_alerts=True)` — the `patterns` CLI + `/api/pipeline/patterns`, never the silent `coach_game` auto-refresh.

### `journal.py` — coaching diary (v1.12.0)
Helpers over the `journal_entries` table. Three entry kinds: `'review'` (LLM-generated Recent Form Review across the last N coached games — `compute_recent_form_review` in `patterns.py`, v1.9.0), `'note'` (manual Parent Note, v1.12.0), and `'weakness_alert'` (auto-filed priority recurring-weakness alert, v1.19.0). Entries accumulate chronologically and render as a threaded social feed on `/[player]/journal`. Reviews name specific games by date + opponent and identify the cross-game through-line; v1.15.0 made them motif-aware. `create_weakness_alert` is fire-once: it skips insertion when an open same-motif alert already exists within `period_days` (the row's existence *is* the dedup state), so an ongoing weakness files one entry per episode. weakness_alert entries are immutable — only `'note'` exposes edit/delete.

| Metric | What it answers |
|---|---|
| Move quality distribution | How often do excellent / good / inaccurate / mistake / blunder moves occur? |
| ACPL trend | Is accuracy improving over time? |
| Phase performance | Where do mistakes cluster — opening, middlegame, or endgame? |
| Danger zones | Which move-number ranges have the highest blunder rate? |
| Endgame conversion | Win % from winning, equal, and losing endgames |
| Critical positions | Success under pressure vs. ability to capitalize |
| Tactical misses | How often does a tactic exist but go unplayed? |
| Comeback / collapse | Recovery rate vs. squandered-advantage rate |
| Repertoire consistency | How focused is the opening choice (per color)? |
| Opening performance | Win % per opening, with white / black split |
| Time control performance | ACPL and win % per time format |
| Time pressure | Blunder rate when low on clock |
| Opening repertoire tracker | ECO distribution and trend |
| Opening ACPL | Per-opening accuracy with verdict |
| Trend summary | LLM-generated cross-game narrative |
| Rating progression | Rating over time with moving average |
| Loss openings (v1.4.0) | Which openings lose most often, by color |
| Strong openings (v1.4.0) | Which openings win most often, by color |
| Trap falls (v1.4.0) | Recurring named traps the player loses to |
| Your arsenal (v1.4.0) | Recurring named traps the player wins with |
| Motif summary / Tactical Themes (v1.15.0–v1.16.0) | Which named tactical themes the player misses most, with per-phase concentration |

### `report.py` — markdown reports
Weekly / monthly markdown reports for coaches: game-by-game summaries, ACPL trend, pattern highlights, annotated critical positions. Saved to `reports/`.

### `tiers.py` — adaptive tier system
Rating-based tiers (Beginner → Elementary → Intermediate → Advanced → Expert) drive analysis depth, blunder thresholds, coaching language, and pattern priorities. A 1000-rated player's "blunder" should not be calibrated the same way as a 2000-rated player's.

### `scheduler.py` + `pipeline_state.py` — automation
- `scheduler.py` runs the full pipeline (harvest → analyze → patterns → coach) on a configurable interval as a daemon thread.
- `pipeline_state.py` enforces single-task-at-a-time across CLI, scheduler, and dashboard so two pipelines can't fight over the SQLite lock or the Stockfish process. The lock is **DB-backed** (a `pipeline_lock` row with a heartbeat, reclaimed after a 15-min stale window), so it coordinates across independent *processes* sharing the DB. `get_state()` reads it with a lightweight read-only connection (v1.22.3) so the high-frequency `/api/pipeline/status` poll never re-runs migrations or contends with a running analyzer. The pipeline `cancel_event` is honoured between every step **and between games inside the analyze step** (v1.22.4), so a long Run All is actually cancellable.

### `dev_runner.py` — `serve` orchestration (v1.5.0)
Owns the subprocess plumbing for `python main.py serve`. Used only by the
`cmd_serve` orchestrator in `main.py`; nothing else in the backend imports it.

- `find_pnpm()` — resolves `pnpm` directly or via `corepack pnpm`; raises
  `DevRunnerError` with an actionable message otherwise.
- `check_node_modules(cwd)` — bool guard; explicit error rather than auto-install.
- `spawn_frontend(pnpm_cmd, cwd, port)` — `subprocess.Popen` with `start_new_session=True`
  on POSIX and `CREATE_NEW_PROCESS_GROUP` on Windows. Stdout / stderr merged on a
  single PIPE for the tail thread.
- `tail_with_prefix(proc, prefix, ready_event, port_holder)` — daemon thread
  reads stdout line-by-line, prepends `[frontend]`, and matches the Next.js
  ready line via `NEXTJS_READY_PATTERN`. Sets the event + writes the detected
  port (handles auto-bump when 3000 is taken).
- `wait_for_ready(event, proc, timeout_s)` — blocks until ready, process dies,
  or timeout.
- `terminate_process_group(proc, grace_s)` — SIGTERM the whole process group,
  wait `grace_s` seconds, escalate to SIGKILL. Whole-group is essential because
  `pnpm dev` itself spawns Next.js workers that don't inherit signals from a
  bare pid kill.
- `print_unified_banner(...)` — the v1.5.0 single-banner format showing both
  URLs in one place. The `dashboard` command keeps its older verbose two-terminal
  banner (with a `serve`-discovery hint appended).

### `hunter.py` — opponent prep (v1.4.1, v1.4.4 accumulating cache)
Two-layer cache:

1. **`opponent_games` (v1.4.4)** — accumulating local PGN cache. Each fetch is incremental: pulls only games newer than the last cached `date_played`, dedups on `game_url`. Pruned by sliding window (`hunter_lookback_months`, default 6 months) and an optional hard cap (`hunter_max_games_per_opponent`). Source of truth for opponent history.
2. **`opponent_cache`** — recomputed profile JSON, 24h TTL. Hit on every page load; rebuilt only when stale or refresh is forced.

Key functions:
- `fetch_opponent_games(username, platform, lookback_months=6)` — pulls fresh PGN from chess.com or lichess. **No Stockfish, no DB writes to the player-centric `games` table.**
- `accumulate_opponent_games(...)` — orchestrates fetch-since-last + insert + prune. Returns the full accumulated set.
- `compute_opponent_profile(games)` — aggregates by opening + color and includes up to `MAX_REPS_PER_OPENING=5` representative PGNs per `(opening, outcome)` so the UI can render mini-board step-through. Mirrors `_compute_loss_openings` from `patterns.py`.
- `get_or_fetch_profile(...)` — public entry point. Cache-aware; returns profile + `meta` block with `cached`, `accumulated_games`, `fetched_at`, `platform`, `username`. v1.20.0 also attaches `motif_summary` + a `deep_scan` status block when the opponent has been scanned.
- Feature-flagged via `features.hunter_mode` (default `true`).

**Deep Scan (v1.20.0) — opponent tactical blind spots.** Opt-in Stockfish pass over an opponent's games to find the tactical themes they MISS (the patterns to bait them into). `analyze_opponent_game(pgn, opponent_color, ...)` is a focused, read-only mirror of the analyzer motif loop (reuses `score_to_cp`/`cap_eval`/`MOTIF_DETECTION_THRESHOLD_CP` + `motifs.detect_motifs`; tallies only the opponent's own critical moves, with a per-motif phase breakdown). `deep_scan_opponent(username, platform, config, limit=20, progress_cb)` scans the last N (`features.hunter_scan_games`, default 20) accumulated games at the same depth as player analysis and caches a per-game motif summary + `analyzed_at` on each `opponent_games` row — **incremental**, so a re-scan only analyzes newly-fetched games. `compute_opponent_motif_summary` sums the per-game results into the same shape as the player-side `_compute_motif_summary`, so the frontend `<MotifThemes>` card renders opponent data unchanged (retitled "Tactical Blind Spots"). Opt-in only: `POST /api/pipeline/hunt-scan` (background job under the single-task `pipeline_state` lock) or `python main.py hunt-scan --opponent X` — never the default profile fetch, which stays sub-second. Opponent color per game comes from `opponent_games.player_color` with a PGN-header fallback (`_resolve_opponent_color`); unattributable games are skipped + logged.

### `tournament.py` — Tournament Prep (v1.21.0)
Multi-opponent Hunter Mode. A `tournament` is a player-scoped, named roster (`tournaments` + `tournament_opponents` tables) — CRUD mirrors `journal.py` (ValueError → 400/404; no opponent data duplicated, the roster just references usernames). `compute_tournament_prep(tournament_id, min_shared)` aggregates the Hunter Mode profiles across the roster **cache-only** (no network, no Stockfish): **opening targets/cautions** group each opponent's weak/strong openings by `(opening, color)` and surface only those shared by ≥`tournament_min_shared` opponents ("Prep the Italian — 5 of 8 lose to it" / "Avoid the Najdorf"); **field blind spots** sum the v1.20.0 per-opponent Deep-Scan `motif_summary` objects into a field-level summary the existing `<MotifThemes>` card renders, with `scan_coverage` so partial coverage never reads as the whole field; opponents without a cached profile are `pending`. The **Prep Roster** background job (`POST /api/pipeline/tournament-prep`, single-task `pipeline_state` lock) warms every opponent's opening-profile cache (fast, no Stockfish) so the combined view fills in. Surfaced as a new Tournament tab + a Hunt "Add to tournament" bridge. CLI: `python main.py tournament-prep --id N`.

### `dashboard_server.py` — REST API
**Multi-threaded** Python `ThreadingHTTPServer` (v1.22.3 — was single-threaded, which let one lock-waiting request freeze every poll and reset the frontend's connections). Each request opens its own SQLite connection. WAL mode + 30s busy timeout; returns **503** ("database is busy") gracefully when the analyzer is holding the write lock — the frontend `fetchJSON` retries 503 with backoff (v1.22.5) so a transient blip during analysis doesn't crash the page.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/players` | List active players with tier + stats |
| GET | `/api/games?player=X` | Game list with filters |
| GET | `/api/games/{id}` | Game detail with analysis + coaching |
| GET | `/api/patterns?player=X` | Pattern metrics + trend summary + motif_summary |
| GET | `/api/journal?player=X` | (v1.10.0) Chronological diary entries |
| GET | `/api/report?player=X&period=Y` | Generated report data |
| GET | `/api/status` | Health check |
| GET | `/api/pipeline/status` | Current pipeline task |
| GET | `/api/settings` | Analysis config + API key status |
| GET | `/api/schedule/status` | Scheduler state |
| GET | `/api/hunt/profile?opponent=X&platform=Y` | (v1.4.1) Opponent profile from cache or live fetch |
| POST | `/api/players` | Add player |
| POST | `/api/coach` | Trigger coaching for a game |
| POST | `/api/trend-summary` | Generate AI trend summary |
| POST | `/api/journal/review` | (v1.10.0) Generate a Recent Form Review entry |
| POST | `/api/journal/note` | (v1.12.0) Create a Parent Note |
| POST | `/api/pipeline/{harvest,analyze,patterns,run-all}` | Trigger pipeline steps |

All `?player=X` params resolve by **slug** (v1.16.4) via the `_resolve_player_id` helper. `PUT`/`DELETE /api/journal/note/{id}` edit/delete notes (v1.12.0).
| POST | `/api/schedule/{toggle,interval}` | Scheduler control |
| POST | `/api/hunt/refresh` | (v1.4.1) Force refresh of an opponent profile (bypass 24h cache) |
| PUT | `/api/players/{id}` | Edit player |
| PUT | `/api/settings/{analysis,api-keys}` | Update settings |
| DELETE | `/api/players/{id}` | Soft-delete player |

---

## 4. Database (`models.py`)

Single-file SQLite. Schema migrations run via `init_db()` at startup — column adds are idempotent (`ALTER TABLE ... ADD COLUMN` guarded by a `PRAGMA table_info` check).

### Tables

| Table | Key fields |
|---|---|
| `players` | username (chess.com handle), **slug** (v1.16.1 — URL/API/CLI id, partial UNIQUE index), display_name, age, rating, fide_id, fide_rating, lichess_username, is_active |
| `games` | player_id, game_url, pgn, player_color, ratings, result, time_class, platform, analysis_status, coaching_status, date_played |
| `move_analysis` | game_id, move_number, side, move_played, best_move, eval_cp, swing_cp, win_prob, classification, pv_line, **clock_seconds**, **motifs_json** (v1.14.0 — `{played, best, missed}`, NULL on non-critical moves) |
| `game_coaching` | game_id, provider, narrative, key_lesson, practical_focus, coach_notes, player_feedback, critical_moments_json, opening_analysis_json, **coaching_meta_json** (v1.7.0; trajectory_* v1.8.0; motif_top_missed / motif_top_missed_phase v1.15.0/v1.16.0) |
| `player_patterns` | player_id, period_start, period_end, stats_json (includes **motif_summary** v1.15.0 with per-phase splits v1.16.0), trend_summary, recent_form_review (legacy, superseded by journal_entries), updated_at |
| `journal_entries` (v1.10.0) | player_id, **kind** ('review'\|'note'), platform, body, refs_json, provider, metadata_json, created_at — chronological coaching diary |
| `opponent_cache` (v1.4.1) | username, platform, profile_json, fetched_at — 24h TTL cache for Hunter Mode profile JSON |
| `opponent_games` (v1.4.4) | username, platform, game_url, pgn, player_color, result, opening_name, eco, date_played, fetched_at — accumulating local PGN cache for Hunter Mode (sliding window + optional cap) |

### Design decisions

- **DB as the source of truth for players** — the dashboard, scheduler, and CLI all read from `players`, not from `config.yaml`. `config.yaml` is for engine + API config only.
- **slug ≠ username (v1.16.x)** — `username` is the chess.com/lichess handle, used only by the harvester. `slug` (auto-derived from `display_name` via `_slugify`) is the identifier for URLs, the API `?player=` param, and the CLI `--player` flag. v1.16.4 made lookups slug-only (one explicit `WHERE username = ?` exception: the player-creation existence check, enforced by a static guard test). Decoupling means chess.com renames don't break bookmarks.
- **Soft-delete via `is_active`** — removing a player archives them; game history is preserved.
- **WAL mode** — concurrent reads while the analyzer holds a write lock.
- **Coaching status is a separate column from analysis status** — a game can be analyzed but not yet coached, which the UI surfaces as a filterable state.
- **`date_played` is full datetime, not just date** — needed so coaching runs in true chronological order across multiple games on the same day.
- **`motifs_json` is sparse** — only critical moves (|cp_loss| ≥ 50) carry motif tags, so the column stays small. `rescan-motifs` backfills it from existing `move_analysis` rows without re-running Stockfish.

---

## 5. Frontend (`frontend/`)

Next.js 16 + React 19 + TypeScript + Tailwind + shadcn/ui (built on Base UI primitives).

### Routes

| Route | Page |
|---|---|
| `/` | Redirects to `/dashboard` |
| `/dashboard` | Player cards grid + pipeline control panel |
| `/[player]/games` | Filterable games list with compare-mode checkbox |
| `/[player]/games/[id]` | Game detail (board, eval chart, coaching panels) |
| `/[player]/games/compare` | Two boards side-by-side, synchronized navigation |
| `/[player]/patterns` | Pattern components + AI coaching summary + Self-Analysis (Fix Your Openings & Trap Patterns) + **Tactical Themes** (v1.15.0 motif aggregation). Rating Progression chart uses a time-scale axis + brush zoom (v1.18.3). |
| `/[player]/journal` | (v1.10.0) Chronological coaching diary — threaded feed of Recent Form Reviews + Parent Notes (v1.11.0 timeline, v1.12.0 add/edit/delete notes) |
| `/[player]/hunt` | (v1.4.2) Hunter Mode — opponent search + Their Weaknesses / Their Strengths view |
| `/[player]/reports` | Period selector, time-class filter, print-to-PDF |
| `/settings` | Players, Stockfish config, API keys, coaching settings |

Route segment `[player]` is the **slug** (v1.16.x), not the chess.com username.

### Key conventions

- **Player-scoped URLs** — `/[player]/...` pattern lets the player switcher swap context cleanly.
- **Pattern components** — each lives in `frontend/components/patterns/*.tsx`. They share an info-modal pattern using `createPortal` to escape `Card`'s `overflow: hidden` clipping. (See `v1.0.1` fix.)
- **Provider metadata** — `frontend/lib/providers.ts` is the single source for the 8-provider list (slug, display name, group, color). Used by every provider selector.
- **API client** — `frontend/lib/api.ts` is the typed wrapper around the backend REST endpoints.
- **Pipeline hook** — `frontend/hooks/use-pipeline.ts` owns pipeline state (running step, progress, cancel) and is shared between the dashboard control panel and the per-game coaching button.
- **Chess helpers (v1.6.0)** — `frontend/lib/chess/` is the canonical home for shared chess utilities: `parseMoveText` (PGN tokenization), `lichessAnalysisUrl` (deep link builder; see v1.4.5 lesson), `normalizeOpeningName` / `findCanonicalLine` / `findDeviationIndex` (Lichess book matching). Three components import from here (`hunter/targeted-prep`, `patterns/opening-explorer`, `patterns/you-fall-for`); previously they each carried near-duplicate copies, which is what hid the v1.4.5 regressions until they were noticed in production.

### UI primitives

shadcn/ui components live in `frontend/components/ui/`. They wrap Base UI primitives. Two gotchas worth knowing:

- `DialogClose` from Base UI renders as a `<button>`. Wrapping a `<Button>` inside it produces nested buttons → hydration error. Use Base UI's `render` prop pattern instead. (See `v1.0.2` fix.)
- `Card` has `overflow: hidden`, which clips native `title="..."` tooltips and any non-portal-rendered overlays. Tooltips and modals must use `createPortal` to `document.body`.

---

## 6. Configuration

### `config.yaml`
Engine and runtime config — Stockfish path / depth / threads / hash, lookback period, coaching provider, coaching tone / detail level / focus areas / `coaching_history_count` / `coaching_trajectory_enabled` (v1.8.0, default true), schedule interval, database path. Player list is **not** stored here (DB is the source of truth). Coaching settings can be edited live via the Settings page (`PUT /api/settings/coaching`) which writes back to `config.yaml`.

### Environment variables
```
ARRAKIS_ANTHROPIC_API_KEY     # Claude
ARRAKIS_OPENAI_API_KEY        # ChatGPT
ARRAKIS_GOOGLE_API_KEY        # Gemini
ARRAKIS_XAI_API_KEY           # Grok
ARRAKIS_MISTRAL_API_KEY       # Mistral
ARRAKIS_DEEPSEEK_API_KEY      # DeepSeek
ARRAKIS_QWEN_API_KEY          # Qwen
# Ollama runs locally — no key required
```

The `ARRAKIS_` prefix avoids collisions with other tools that use the unprefixed `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`.

---

## 7. Testing

**~905 tests total** — 680 backend (pytest) + 225 frontend (Vitest). Counts as of v1.24.2; see CHANGELOG for per-release deltas. Backend integration (`-m integration`, Stockfish) and live (`-m live`, LLM key) tiers are excluded by default.

### Backend (`tests/`)

| Suite | What it covers |
|---|---|
| Unit tests | `models`, `analyzer`, `harvester`, `coach`, `patterns`, `motifs` (v1.14.0), `journal` (v1.12.0), `loss_openings` (v1.4.0), `trap_matcher` (v1.4.0), `hunter` (v1.4.1+ / Deep Scan v1.20.0), `tournament` (v1.21.0), `report`, `tiers`, `scheduler`, `pipeline_state`, `dashboard_server`, `dev_runner` (v1.5.0) |
| Integration | Full pipeline E2E (analyze → coach end-to-end on a known PGN) |
| Stockfish integration | Specific lines (Scholar's Mate, etc.) verified against engine output |
| Live LLM | Real API calls, marked separately, ~$0.05 / run |

### Frontend (`frontend/.../__tests__/`, v1.6.0+)

| Suite | What it covers |
|---|---|
| `lib/chess/__tests__/` | Helper unit tests — `parseMoveText`, `normalizeOpeningName`, `findCanonicalLine`, `findDeviationIndex`, `lichessAnalysisUrl`. **`lichess.test.ts` is the load-bearing v1.4.5 regression lock**: forbids the `?pgn=` URL form. |
| `hooks/__tests__/use-chess-navigation.test.ts` | Empty/invalid PGN safety, **v1.4.5 clock-comment leak guard** (`{[%clk ...]}` must not leak into the moves array), FEN-array length invariant, boundary navigation, keyboard handler focus guard. |
| `components/**/__tests__/` | Component smoke + interaction tests for `targeted-prep`, `you-fall-for`, `opening-explorer`. Each asserts the rendered Lichess URL is `/analysis/standard/` form. |

Vitest runs sub-second. Setup mocks `next/navigation` and `next/link` globally (`frontend/vitest.setup.ts`) so component tests render without the Next runtime.

### CI

CI runs backend pytest unit tests, frontend Vitest (`pnpm test:run`), and frontend `pnpm build` on Node 24 + pnpm 10 + Python 3.11 / 3.12. The frontend test step gates the build — regressions fail fast.

### Patch-target rule for tests
Functions imported locally inside another function (e.g. `from src.coach import coach_pending` inside `run_full_pipeline()`) must be patched at the **source** module — `@patch("src.coach.coach_pending")` — not at the consuming module. This trips up new tests regularly.

---

## 8. Operational notes

- **Single-user, local-first.** No multi-tenant concerns, no auth, no remote DB. Everything runs on one machine.
- **Apple Silicon is the reference platform.** Stockfish via Homebrew, Ollama via the native installer.
- **The pipeline lock is global.** Only one harvest / analyze / pattern / coach task runs at a time. If you trigger one from the dashboard and another from CLI, the second blocks until the first releases.
- **Reports are markdown first, HTML second.** Backend writes markdown to `reports/`. The `/[player]/reports` page renders structured HTML from the API. PDF export is `window.print()` with print-optimized CSS — no headless Chrome.
- **CI runs on Node 24 + pnpm 10.** The lockfile is `lockfileVersion: 9.0` which requires pnpm 10. `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` is set in the workflow to silence Node-20 deprecation warnings.
- **Subprocess model for `serve` (v1.5.0).** The `serve` command runs the API server in the main thread (after starting it in a daemon thread to free Ctrl+C handling) and spawns `pnpm dev` as a child in its own process group. A daemon tail thread reads the child's merged stdout/stderr, prefixes lines with `[frontend]`, and watches for the Next.js ready line to capture the actual port. Ctrl+C → SIGTERM the process group → wait 5 s → SIGKILL on overstay. Whole-group signalling is essential because `pnpm dev` itself spawns Next.js workers that don't inherit signals from a bare-pid kill.

---

## 9. Where to look when…

| Need | Start here |
|---|---|
| Adding a new LLM provider | `src/llm_providers.py` (registration), `frontend/lib/providers.ts` (UI metadata) |
| Adding a new pattern metric | `src/patterns.py` (compute), `frontend/components/patterns/*.tsx` (visualize), `frontend/app/[player]/patterns/page.tsx` (compose) |
| Adding a new named trap | Update `TRAP_NAME_PATTERNS` in `scripts/build_traps.py`, then re-run the script to rebuild `frontend/public/data/traps.json` |
| Adding a new pipeline step | `src/scheduler.py::run_full_pipeline`, `src/dashboard_server.py` (POST endpoint), `frontend/components/pipeline-control-panel.tsx` |
| Changing Stockfish behavior | `src/analyzer.py` + `config.yaml` |
| Tuning coaching prompts | `src/coach.py` (`GAME_COACHING_PROMPT`), `src/tiers.py` (per-tier guidance), `src/patterns.py::build_trajectory_block` (v1.8.0 trajectory snapshot) |
| Verifying what the LLM actually saw | `python main.py coach <id> --dump-prompt /tmp/` (v1.6.0+); A/B with `--no-trajectory` (v1.8.0+) |
| Adding a new dashboard page | `frontend/app/[player]/<page>/page.tsx`, plus a corresponding GET endpoint in `dashboard_server.py` |
| Database migration | `src/models.py::init_db` — add a new `ALTER TABLE` guarded by `PRAGMA table_info` |
| Test patches not firing | Check whether the import is local-in-function; patch the **source** module |
| Parsing PGN moves in a frontend component | Use `nav.moves` from `useChessNavigation` — chess.js handles annotations like `{[%clk ...]}` that regex doesn't (v1.4.5 lesson) |
| Building a Lichess deep link | Use `https://lichess.org/analysis/standard/{URL-encoded FEN}` with `nav.endFen` — the `?pgn=` query format isn't honoured (v1.4.5 lesson) |
| Suppressing browser autofill / password manager popups | Avoid `id="username"` / labels containing "username" / "user" / "email"; add `autoComplete="off"` on form + input + `data-1p-ignore` + `data-lpignore` + `data-form-type="other"` |

---

## 10. Versioning

Arrakis Engine follows semver from `v1.0.0` onward.

- Breaking changes (DB schema, API endpoints, CLI commands) → major bump
- New features (new pattern, new provider, new page) → minor bump
- Fixes → patch bump

See [CHANGELOG.md](../CHANGELOG.md) for the full release history.
