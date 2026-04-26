# Arrakis Engine — Chess Coach AI

## Project Overview
Local Python app that pulls games from Chess.com and Lichess, runs Stockfish analysis,
and uses reasoning LLMs to generate age-appropriate coaching insights with
pattern tracking over time. Inspired by Eleanor, Evan, and Estella.

Current release: **v1.5.0** (2026-04-26). See `CHANGELOG.md` for history.

## Architecture
- Python 3.11+, SQLite (WAL mode), local Stockfish on Apple Silicon
- Two-step analysis: Stockfish engine eval → LLM coaching interpretation
- Third layer: cross-game pattern aggregation over time
- Fourth layer: LLM-powered trend summaries interpreting cross-game patterns
- Fifth layer: time pressure analysis from per-move clock data
- Sixth layer (v1.4+): Self-Analysis (loss openings, trap patterns) + Hunter Mode (opponent prep)
- Frontend: Next.js 16 + React 19 + shadcn/ui + Tailwind CSS + Recharts (mobile responsive)

## Players
- Configured in `config.yaml` initially; managed via Settings page after that.
  DB is the source of truth (chess.com username, lichess username, display name,
  age, rating, FIDE ID).

## Key Configuration
- Stockfish: depth 22, 6 threads, 512MB hash, path configured in `config.yaml`
- LLM: unified provider abstraction (`src/llm_providers.py`) supporting 8 providers:
  - **Cloud:** Claude (`claude-opus-4-6`), ChatGPT (`gpt-5.4`), Gemini (`gemini-2.5-pro`),
    Grok (`grok-3`), Mistral (`mistral-medium-latest`), DeepSeek (`deepseek-reasoner`),
    Qwen (`qwen3-235b-a22b`)
  - **Local:** Ollama (`deepseek-r1:8b`) — no API key required
- Reasoning models are required (hard requirement, not preference)
- Coaching history depth (v1.3.0+): default 5 recent games, configurable 1-20
- Hunter Mode (v1.4.4+): sliding window default 6 months, optional max games cap
- Config via `config.yaml`, secrets via `.env`:
  - `ARRAKIS_ANTHROPIC_API_KEY`, `ARRAKIS_OPENAI_API_KEY`, `ARRAKIS_GOOGLE_API_KEY`
  - `ARRAKIS_XAI_API_KEY`, `ARRAKIS_MISTRAL_API_KEY`, `ARRAKIS_DEEPSEEK_API_KEY`,
    `ARRAKIS_QWEN_API_KEY`

## Analysis Standards
- Win probability: Lichess formula → `winPct = 50 + 50 × (2 / (1 + exp(-0.00368208 × cp)) - 1)`
- ACPL capped at ±1000cp (matches Lichess / chess.com convention)
- Move classifications: excellent (<30cp loss), good (<50), inaccuracy (<100),
  mistake (<300), blunder (300+)
- Tier-adjusted thresholds via `src/tiers.py` (Beginner → Elementary → Intermediate
  → Advanced → Expert)
- Coaching output has two tones: child-facing (age-appropriate, concrete, encouraging)
  and coach-facing (technical, actionable). Player age and rating are read dynamically
  from the database.

## URL Structure (Player-Scoped Routes)
```
/                           → redirects to /dashboard
/dashboard                  → all players overview + pipeline control panel
/<player>/games             → game list for player
/<player>/games/<id>        → game detail (board, eval, coaching panels)
/<player>/games/compare     → side-by-side game comparison
/<player>/patterns          → 16 pattern visualizations + Self-Analysis section
/<player>/hunt              → Hunter Mode (opponent prep)
/<player>/reports           → monthly/weekly coaching reports with PDF export
/settings                   → players, Stockfish config, API keys, coaching settings
```

## Project Structure
```
ArrakisEngine/
├── CLAUDE.md
├── README.md                  # public-facing, 3-zone structure
├── CHANGELOG.md
├── ROADMAP.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── LICENSE                    # AGPL-3.0
├── config.yaml.example
├── requirements.txt
├── requirements-dev.txt
├── main.py                    # CLI entry point
├── src/
│   ├── harvester.py           # chess.com + lichess game fetcher
│   ├── analyzer.py            # Stockfish analysis engine + clock extraction
│   ├── llm_providers.py       # Unified LLM provider abstraction (8 providers)
│   ├── coach.py               # LLM coaching layer (configurable history depth)
│   ├── patterns.py            # 20 cross-game patterns + LLM trend summaries
│   ├── hunter.py              # v1.4.1+ Hunter Mode (opponent prep)
│   ├── models.py              # SQLite schema (6 tables) + idempotent migrations
│   ├── tiers.py               # Adaptive tier system (rating-based)
│   ├── scheduler.py           # Auto-pipeline daemon
│   ├── pipeline_state.py      # Single-task lock across CLI/scheduler/dashboard
│   ├── dev_runner.py          # v1.5.0 — `serve` subprocess orchestration
│   ├── report.py              # Report generator
│   ├── export.py              # Data export utilities
│   └── dashboard_server.py    # SQLite REST API (GET/POST/PUT/DELETE)
├── frontend/                  # Next.js 16 + React 19 + shadcn/ui dashboard
│   ├── app/
│   │   ├── layout.tsx         # Root layout (providers, header, nav)
│   │   ├── page.tsx           # Home → /dashboard
│   │   ├── providers.tsx      # ThemeProvider + PlayerProvider
│   │   ├── dashboard/page.tsx # All-players overview + pipeline control
│   │   ├── settings/page.tsx  # Players, Stockfish, API keys, coaching settings
│   │   └── [player]/          # Player-scoped routes
│   │       ├── games/         # List + detail + compare
│   │       ├── patterns/      # 16 charts + Self-Analysis (Fix Your Openings + Trap Patterns)
│   │       ├── hunt/          # v1.4.2+ Hunter Mode UI
│   │       └── reports/       # Coaching reports
│   ├── components/
│   │   ├── app-header.tsx
│   │   ├── nav-bar.tsx        # Dashboard / Games / Patterns / Hunt / Reports
│   │   ├── pipeline-control-panel.tsx
│   │   ├── game-detail/       # ChessBoard, MoveControls, eval chart, coaching
│   │   ├── patterns/          # 16 visualization components + Self-Analysis components
│   │   ├── hunter/            # v1.4.2+ OpponentSearch, TargetedPrep
│   │   ├── settings/          # Players, Stockfish, API keys, Coaching sections
│   │   └── ui/                # shadcn/ui primitives (Base UI under the hood)
│   ├── hooks/                 # useChessNavigation (returns currentFen, endFen, moves)
│   ├── lib/                   # API client, types, providers metadata
│   └── public/data/
│       ├── openings.json      # 3,690-entry Lichess CC0 opening database
│       └── traps.json         # 102-entry curated beginner-trap library
├── scripts/
│   └── build_traps.py         # Rebuilds openings.json + traps.json from Lichess
├── docs/
│   ├── architecture.md        # Tracked: contributor architecture reference
│   ├── roadmap.md             # Gitignored: private working roadmap
│   ├── what_we_have_built_so_far.md  # Gitignored: implementation snapshot
│   └── screenshots/           # Architecture diagram + UI screenshots
├── data/
│   └── chess_coach.db         # SQLite database (auto-created, gitignored)
├── tests/                     # pytest suite (362 tests across 3 tiers)
└── reports/                   # Generated coach reports (gitignored)
```

## Database Tables (`src/models.py`)

| Table | Purpose |
|---|---|
| `players` | Player profiles |
| `games` | Stored games with PGN |
| `move_analysis` | Per-move Stockfish results |
| `game_coaching` | LLM coaching output |
| `player_patterns` | Aggregated pattern stats (JSON blob) |
| `opponent_cache` (v1.4.1) | Hunter Mode profile JSON cache (24h TTL) |
| `opponent_games` (v1.4.4) | Hunter Mode accumulating PGN cache (sliding window) |

## Pattern Components (16 visualizations + Self-Analysis section)

Move quality donut, ACPL trend, danger zones, phase performance, endgame conversion,
critical positions, tactical misses, comeback/collapse, repertoire consistency,
opening performance, opening ACPL, opening repertoire tracker, time pressure,
time control performance, rating progression, coaching summary.

**Self-Analysis (v1.4.0+)** adds: Fix Your Openings (loss/strength by opening),
Trap Patterns (Your Arsenal + You Fall For with click-to-expand mini-board,
recent game links, Lichess deep links).

**Hunter Mode (v1.4.1+)** is its own page. Each opening row click-to-expands with
mini-board, "Game N of 5" flip controls, annotated move list with deviation
highlighting against canonical book theory, and "Study on Lichess" deep link.

## API Endpoints

### GET
- `/api/players` — all players with tier info
- `/api/games?player=X[&...]` — filtered game list
- `/api/games/<id>` — game detail with moves + coaching
- `/api/patterns?player=X` — all 20 pattern metrics + trend_summary
- `/api/report?player=X&period=monthly|weekly` — structured report data
- `/api/status` — pipeline status counts
- `/api/pipeline/status` — current task
- `/api/settings` — analysis + API key + coaching settings
- `/api/schedule/status` — scheduler state
- `/api/hunt/profile?opponent=X&platform=Y` — (v1.4.1+) opponent profile

### POST
- `/api/players` — add player
- `/api/coach` — trigger coaching for a single game
- `/api/trend-summary` — LLM trend summary
- `/api/pipeline/{harvest,analyze,patterns,coach,run-all,cancel}` — pipeline triggers
- `/api/schedule/{toggle,interval}` — scheduler control
- `/api/hunt/refresh` — force opponent profile re-fetch (v1.4.1+)

### PUT / DELETE
- `PUT /api/players/<id>`
- `PUT /api/settings/{analysis,api-keys,coaching}`
- `DELETE /api/players/<id>` (soft-delete via `is_active`)

## Testing

**362 tests** across 16 test files, organized into three tiers via pytest markers
(see `pyproject.toml`).

### Running Tests
```bash
pytest                                  # ~318 unit tests (~14s, no deps)
pytest -m integration                   # Stockfish tests (requires binary)
pytest -m live                          # LLM API tests (~$0.05)
pytest -m "integration and live"        # Full pipeline E2E
pytest --override-ini "addopts="        # All 362 tests across all tiers
```

### Tier 1: Unit Tests (default)
All external dependencies mocked. No Stockfish or API keys needed.

| File | Approx tests | What it covers |
|---|---|---|
| test_models.py | ~16 | Schema init, ensure_player upsert, migrations |
| test_harvester.py | ~20 | chess.com + lichess parsing, dedup |
| test_analyzer.py | ~19 | Eval/win-prob formulas, classification |
| test_coach.py | ~24 | Move formatting, JSON parsing, history depth (v1.3) |
| test_patterns.py | ~38 | All pattern aggregations + edge cases |
| test_loss_openings.py (v1.4.0) | 10 | Loss/strong opening aggregation |
| test_trap_matcher.py (v1.4.0) | 31 | Trap library + longest-prefix matching + recent_game_ids (v1.4.3) |
| test_hunter.py (v1.4.1+) | 41 | Profile aggregation, cache, accumulating games (v1.4.4), reps |
| test_tiers.py | ~21 | Rating→tier, tier-specific classification |
| test_report.py | ~9 | Report generation, ACPL interpretation |
| test_dashboard_server.py | ~18 | API endpoints + client-disconnect handling (v1.3.1) |
| test_scheduler.py | ~10 | Pipeline orchestration |
| test_export.py | ~7 | JSON export, edge cases |
| test_dev_runner.py (v1.5.0) | 30 | `serve` orchestration: pnpm resolution, subprocess argv, Next.js ready-line parsing, SIGTERM→SIGKILL teardown |

### Tier 2: Integration Tests (`pytest -m integration`)
Requires Stockfish binary. Uses Scholar's Mate for fast deterministic analysis.

### Tier 3: Live Tests (`pytest -m live`)
Requires at least one cloud API key. Uses whichever is available.

### Patch-target rule
Functions imported locally inside another function (e.g. `from src.coach import
coach_pending` inside `run_full_pipeline()`) must be patched at the **source**
module — `@patch("src.coach.coach_pending")` — not at the consuming module.

## Key Technical Decisions
- **DB as the source of truth for players** — UI-driven CRUD, not config.yaml
- **Soft-delete via `is_active`** — preserves game history
- **Reasoning models required** — hard contract enforced in `llm_providers.py`
- **Single-task pipeline lock** — across CLI + scheduler + dashboard
- **`ARRAKIS_` prefix on env keys** — avoids collisions with other tools
- **`useChessNavigation` is the canonical source for parsed game moves** — chess.js
  handles PGN annotations like `{[%clk ...]}` correctly. Avoid regex-parsing PGN
  bodies in components; consume `nav.moves` instead. (v1.4.5 lesson)
- **Base UI `render` prop pattern** — avoids nested `<button>` hydration errors
  with `DialogClose`. (v1.0.2 lesson)
- **Portal-based info modals** — escapes `Card overflow:hidden` clipping. (v1.0.1)
- **Lichess deep link format** — use `/analysis/standard/{FEN}`, not `?pgn=`.
  (v1.4.5 lesson)

## Two-Server Setup

The app runs as two cooperating servers. Two ways to start:

**Recommended (v1.5.0+) — single command:**
```bash
python main.py serve
```
Spawns both servers, prints a unified banner, Ctrl+C stops both. See
`src/dev_runner.py` for the orchestration. Optional flags: `--port` (backend),
`--frontend-port` (frontend), `--install` (auto-runs `pnpm install` if
`node_modules` is missing).

**Manual two-terminal mode** (for hot-reload visibility on each side):

| | Port | Start with |
|---|---|---|
| Python API backend | 8000 | `python main.py dashboard` |
| Next.js frontend | 3000 | `cd frontend && pnpm dev` |

Open `http://localhost:3000` (the frontend). It calls back to the API on 8000.

## Git Workflow
- Commit after each working component
- Keep `data/`, `reports/`, `docs/` (mostly), `.claude/`, `.mcp.json` in `.gitignore`
- Never commit API keys
- Tag releases as `vX.Y.Z`; ship via `gh release create`
