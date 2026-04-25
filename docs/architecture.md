# Arrakis Engine — Architecture

*Last updated: 2026-04-25 — corresponds to v1.0.2*

This document describes the technical architecture of Arrakis Engine: how the pieces fit together, what runs where, and the design decisions behind them. It is aimed at contributors and developers reading the codebase. For end-user / setup docs, see [README.md](../README.md). For changelog, see [CHANGELOG.md](../CHANGELOG.md).

---

## 1. System Overview

Arrakis Engine is a local chess coaching application. It pulls games from chess.com and Lichess, analyzes them with Stockfish, runs LLM-based coaching on top of the engine output, aggregates patterns across games, and exposes everything through a Next.js dashboard.

The core insight is **two-step analysis**:

1. **Stockfish** produces objective per-move evaluations (centipawn loss, best move, win probability).
2. A **reasoning LLM** interprets that engine output into human coaching language — appropriate for the player's age and rating.

A third **pattern aggregation** layer runs across all of a player's games to surface trends that no single-game review can show (e.g. "blunders cluster between moves 30–40 across the last 20 games").

### High-level flow

```
chess.com / Lichess API
        │
        ▼
   harvester.py  ──► SQLite (games)
        │
        ▼
   analyzer.py   ──► SQLite (move_analysis)         [Stockfish, depth 22]
        │
        ▼
     coach.py    ──► SQLite (game_coaching)         [LLM reasoning model]
        │
        ▼
   patterns.py   ──► SQLite (player_patterns)       [aggregation across games]
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
| Tests | pytest |

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
- **ACPL capping at ±1000 cp** matches the Lichess / chess.com convention so that mating sequences don't dominate average centipawn loss.
- Move classifications:
  - Excellent: `< 30 cp` loss
  - Good: `< 50 cp`
  - Inaccuracy: `< 100 cp`
  - Mistake: `< 300 cp`
  - Blunder: `≥ 300 cp`
- Win probability: Lichess formula — `winPct = 50 + 50 × (2 / (1 + exp(-0.00368208 × cp)) − 1)`.
- Configurable depth (22), threads (6), hash (512 MB), and per-move time limit.

### `coach.py` + `llm_providers.py` — LLM coaching layer
- `llm_providers.py` is the unified abstraction for **8 providers**: Anthropic, OpenAI, Google, xAI, Mistral, DeepSeek, Qwen, and Ollama. Each provider is registered with its SDK type, default model, API key env var, and request shape.
- `coach.py` builds the prompt from Stockfish data + recent coaching history, sends it through the provider abstraction, and stores the structured output in `game_coaching`.
- **Reasoning models are required.** The system enforces this — non-reasoning models produce shallow, generic coaching that misses tactics. See [`ROADMAP.md`](../ROADMAP.md) (root, not the gitignored one) for the full rationale.
- Coaching output is structured: narrative, key lesson, practical focus, critical moments, opening analysis, coach notes — for two audiences (child-facing, coach-facing).
- **Coaching history injection**: the last 5 coached games' lessons are fed into the prompt so the LLM doesn't repeat itself across a session and can build on prior advice.
- **Game-type detection** classifies games into 10 archetypes (tactical battle, comeback, collapse, positional grind, miniature, etc.) and tailors the prompt accordingly.
- Resilience: exponential backoff (30s → 60s → 120s, max 5 min), 3-failure circuit breaker, 300s SDK timeout for reasoning models, interruptible sleep via `threading.Event`.

### `patterns.py` — cross-game aggregation
Aggregates 16 metrics per player across all analyzed games. Stored as one JSON blob per player in `player_patterns.stats_json`.

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

### `report.py` — markdown reports
Weekly / monthly markdown reports for coaches: game-by-game summaries, ACPL trend, pattern highlights, annotated critical positions. Saved to `reports/`.

### `tiers.py` — adaptive tier system
Rating-based tiers (Beginner → Elementary → Intermediate → Advanced → Expert) drive analysis depth, blunder thresholds, coaching language, and pattern priorities. A 1000-rated player's "blunder" should not be calibrated the same way as a 2000-rated player's.

### `scheduler.py` + `pipeline_state.py` — automation
- `scheduler.py` runs the full pipeline (harvest → analyze → patterns → coach) on a configurable interval as a daemon thread.
- `pipeline_state.py` enforces single-task-at-a-time across CLI, scheduler, and dashboard so two pipelines can't fight over the SQLite lock or the Stockfish process.

### `dashboard_server.py` — REST API
Single-process Python HTTP server. SQLite WAL mode + 30s busy timeout; returns 503 gracefully when the analyzer is holding the lock.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/players` | List active players with tier + stats |
| GET | `/api/games?player=X` | Game list with filters |
| GET | `/api/games/{id}` | Game detail with analysis + coaching |
| GET | `/api/patterns?player=X` | All 16 pattern metrics + trend summary |
| GET | `/api/report?player=X&period=Y` | Generated report data |
| GET | `/api/status` | Health check |
| GET | `/api/pipeline/status` | Current pipeline task |
| GET | `/api/settings` | Analysis config + API key status |
| GET | `/api/schedule/status` | Scheduler state |
| POST | `/api/players` | Add player |
| POST | `/api/coach` | Trigger coaching for a game |
| POST | `/api/trend-summary` | Generate AI trend summary |
| POST | `/api/pipeline/{harvest,analyze,patterns,run-all}` | Trigger pipeline steps |
| POST | `/api/schedule/{toggle,interval}` | Scheduler control |
| PUT | `/api/players/{id}` | Edit player |
| PUT | `/api/settings/{analysis,api-keys}` | Update settings |
| DELETE | `/api/players/{id}` | Soft-delete player |

---

## 4. Database (`models.py`)

Single-file SQLite. Schema migrations run via `init_db()` at startup — column adds are idempotent (`ALTER TABLE ... ADD COLUMN` guarded by a `PRAGMA table_info` check).

### Tables

| Table | Key fields |
|---|---|
| `players` | username, display_name, age, rating, fide_id, fide_rating, lichess_username, is_active |
| `games` | player_id, game_url, pgn, player_color, ratings, result, time_class, platform, analysis_status, coaching_status, date_played |
| `move_analysis` | game_id, move_number, side, move_played, best_move, eval_cp, swing_cp, win_prob, classification, pv_line |
| `game_coaching` | game_id, provider, narrative, key_lesson, practical_focus, coach_notes, critical_moments_json, opening_analysis_json |
| `player_patterns` | player_id, period_start, period_end, stats_json, trend_summary, updated_at |

### Design decisions

- **DB as the source of truth for players** — the dashboard, scheduler, and CLI all read from `players`, not from `config.yaml`. `config.yaml` is for engine + API config only.
- **Soft-delete via `is_active`** — removing a player archives them; game history is preserved.
- **WAL mode** — concurrent reads while the analyzer holds a write lock.
- **Coaching status is a separate column from analysis status** — a game can be analyzed but not yet coached, which the UI surfaces as a filterable state.
- **`date_played` is full datetime, not just date** — needed so coaching runs in true chronological order across multiple games on the same day.

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
| `/[player]/patterns` | 16 pattern visualizations + AI coaching summary |
| `/[player]/reports` | Period selector, time-class filter, print-to-PDF |
| `/settings` | Players, Stockfish config, API keys, coaching settings |

### Key conventions

- **Player-scoped URLs** — `/[player]/...` pattern lets the player switcher swap context cleanly.
- **Pattern components** — each lives in `frontend/components/patterns/*.tsx`. They share an info-modal pattern using `createPortal` to escape `Card`'s `overflow: hidden` clipping. (See `v1.0.1` fix.)
- **Provider metadata** — `frontend/lib/providers.ts` is the single source for the 8-provider list (slug, display name, group, color). Used by every provider selector.
- **API client** — `frontend/lib/api.ts` is the typed wrapper around the backend REST endpoints.
- **Pipeline hook** — `frontend/hooks/use-pipeline.ts` owns pipeline state (running step, progress, cancel) and is shared between the dashboard control panel and the per-game coaching button.

### UI primitives

shadcn/ui components live in `frontend/components/ui/`. They wrap Base UI primitives. Two gotchas worth knowing:

- `DialogClose` from Base UI renders as a `<button>`. Wrapping a `<Button>` inside it produces nested buttons → hydration error. Use Base UI's `render` prop pattern instead. (See `v1.0.2` fix.)
- `Card` has `overflow: hidden`, which clips native `title="..."` tooltips and any non-portal-rendered overlays. Tooltips and modals must use `createPortal` to `document.body`.

---

## 6. Configuration

### `config.yaml`
Engine and runtime config — Stockfish path / depth / threads / hash, lookback period, coaching provider, schedule interval, database path. Player list is **not** stored here (DB is the source of truth).

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

| Suite | What it covers |
|---|---|
| Unit tests | `models`, `analyzer`, `harvester`, `coach`, `patterns`, `report`, `tiers`, `export`, `scheduler`, `pipeline_state` |
| Integration | Full pipeline E2E (analyze → coach end-to-end on a known PGN) |
| Stockfish integration | Specific lines (Scholar's Mate, etc.) verified against engine output |
| Live LLM | Real API calls, marked separately, ~$0.05 / run |

Tests live in `tests/`. CI runs unit + integration on Python 3.11 and 3.12, plus `pnpm build` for the frontend.

### Patch-target rule for tests
Functions imported locally inside another function (e.g. `from src.coach import coach_pending` inside `run_full_pipeline()`) must be patched at the **source** module — `@patch("src.coach.coach_pending")` — not at the consuming module. This trips up new tests regularly.

---

## 8. Operational notes

- **Single-user, local-first.** No multi-tenant concerns, no auth, no remote DB. Everything runs on one machine.
- **Apple Silicon is the reference platform.** Stockfish via Homebrew, Ollama via the native installer.
- **The pipeline lock is global.** Only one harvest / analyze / pattern / coach task runs at a time. If you trigger one from the dashboard and another from CLI, the second blocks until the first releases.
- **Reports are markdown first, HTML second.** Backend writes markdown to `reports/`. The `/[player]/reports` page renders structured HTML from the API. PDF export is `window.print()` with print-optimized CSS — no headless Chrome.
- **CI runs on Node 24 + pnpm 10.** The lockfile is `lockfileVersion: 9.0` which requires pnpm 10. `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` is set in the workflow to silence Node-20 deprecation warnings.

---

## 9. Where to look when…

| Need | Start here |
|---|---|
| Adding a new LLM provider | `src/llm_providers.py` (registration), `frontend/lib/providers.ts` (UI metadata) |
| Adding a new pattern metric | `src/patterns.py` (compute), `frontend/components/patterns/*.tsx` (visualize), `frontend/app/[player]/patterns/page.tsx` (compose) |
| Adding a new pipeline step | `src/scheduler.py::run_full_pipeline`, `src/dashboard_server.py` (POST endpoint), `frontend/components/pipeline-control-panel.tsx` |
| Changing Stockfish behavior | `src/analyzer.py` + `config.yaml` |
| Tuning coaching prompts | `src/coach.py` (build_prompt), `src/tiers.py` (per-tier guidance) |
| Adding a new dashboard page | `frontend/app/[player]/<page>/page.tsx`, plus a corresponding GET endpoint in `dashboard_server.py` |
| Database migration | `src/models.py::init_db` — add a new `ALTER TABLE` guarded by `PRAGMA table_info` |
| Test patches not firing | Check whether the import is local-in-function; patch the **source** module |

---

## 10. Versioning

Arrakis Engine follows semver from `v1.0.0` onward.

- Breaking changes (DB schema, API endpoints, CLI commands) → major bump
- New features (new pattern, new provider, new page) → minor bump
- Fixes → patch bump

See [CHANGELOG.md](../CHANGELOG.md) for the full release history.
