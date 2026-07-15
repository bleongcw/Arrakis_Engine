# Arrakis Engine — Chess Coach AI

## Project Overview
Local Python app that pulls games from Chess.com and Lichess, runs Stockfish analysis,
and uses reasoning LLMs to generate age-appropriate coaching insights with
pattern tracking over time. Inspired by Eleanor, Evan, and Estella.

Current release: **v1.27.0** (2026-07-15). See `CHANGELOG.md` for full history.

## Architecture
- Python 3.11+, SQLite (WAL mode), local Stockfish on Apple Silicon
- Two-step analysis: Stockfish engine eval → LLM coaching interpretation
- Third layer: cross-game pattern aggregation over time
- Fourth layer: LLM-powered trend summaries interpreting cross-game patterns
- Fifth layer: time pressure analysis from per-move clock data
- Sixth layer (v1.4+): Self-Analysis (loss openings, trap patterns) + Hunter Mode (opponent prep)
- Seventh layer (v1.14–v1.17): tactical-motif detection — 12 detectors tag each
  critical move with the themes it executes or misses (fork, pin, skewer,
  discovered check, mate threat, removing the defender, hanging piece, trapped
  piece, back-rank mate, deflection, overloaded defender, zugzwang)
- Eighth layer (v1.15–v1.16): cross-game motif aggregation with per-phase
  (opening/middlegame/endgame) breakdown, surfaced in coaching prompts + the
  Tactical Themes Patterns card
- Journal (v1.10–v1.12): chronological diary of coaching artifacts — Recent Form
  Reviews + manual Parent Notes, threaded social-feed UI
- Frontend: Next.js 16 + React 19 + shadcn/ui + Tailwind CSS + Recharts (mobile
  responsive — viewport meta tag added v1.18.2)

## Players
- Configured in `config.yaml` initially; managed via Settings page after that.
  DB is the source of truth.
- Three distinct identifiers (v1.16.x):
  - **`username`** — the chess.com / lichess handle, used ONLY by the harvester's
    API calls. Mutable (chess.com allows renames).
  - **`slug`** — the URL / API `?player=` / CLI `--player` identifier. Auto-derived
    from `display_name` (lowercase, strip non-alphanumeric → "Evan Leong" =
    "evanleong"). v1.16.4 made lookups slug-only; v1.18.1 extended that to
    rescan-motifs + harvest/report CLI.
  - **`display_name`** — what every visible label shows.
- **FIDE ratings (v1.26.0):** three separate ratings —
  `fide_rating_classical` / `fide_rating_rapid` / `fide_rating_blitz` (FIDE
  publishes one per time control) — plus `fide_id`. Edited per player on the
  Settings form. **FIDE ratings are FIDE-specific: they do NOT override the
  chess.com / lichess rating** (the primary rating stays the latest game /
  platform rating). The legacy single `fide_rating` column is kept and was
  backfilled into Classical.

## Key Configuration
- Stockfish: depth 22, 6 threads, 512MB hash, path configured in `config.yaml`
- LLM: unified provider abstraction (`src/llm_providers.py`) supporting 8 providers:
  - **Cloud (v1.27.0 flagships):** Claude (`claude-opus-4-8`), ChatGPT (`gpt-5.6-sol`),
    Gemini (`gemini-3.5-flash`), Grok (`grok-4.5`), Mistral (`mistral-medium-latest`),
    DeepSeek (`deepseek-v4-pro`), Qwen (`qwen3.7-max`)
  - **Local:** Ollama (`deepseek-r1:8b`) — no API key required
- Reasoning models are required (convention, not code-enforced — see below)
- Reasoning effort (v1.27.0): `coaching.reasoning_effort` (default `xhigh`) —
  applied where the provider has a granular scale: Claude (`output_config.effort`),
  ChatGPT (`reasoning.effort`), Mistral (`reasoning_effort`, capped at high);
  clamped per provider by `_effort_for` in `src/llm_providers.py`
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
- Motif detection threshold: critical moves with |cp_loss| ≥ 50 get scanned
  (`MOTIF_DETECTION_THRESHOLD_CP` in `src/analyzer.py`)
- Tier-adjusted thresholds via `src/tiers.py` (Beginner → Elementary → Intermediate
  → Advanced → Expert)
- Coaching output has two tones: child-facing (age-appropriate, concrete, encouraging)
  and coach-facing (technical, actionable). Player age and rating are read dynamically
  from the database.

## URL Structure (Player-Scoped Routes)
```
/                           → redirects to /dashboard
/dashboard                  → all players overview + pipeline control panel
/<slug>/games               → game list for player (+ PGN export: select/filtered bulk)
/<slug>/games/<id>          → game detail (board, eval, coaching panels, motif badges,
                              Export PGN; inline editors: Edit ratings (v1.25.1),
                              Edit details = category/type/date (v1.26.2–v1.26.3))
/<slug>/import              → import a PGN (paste/upload) → analyzed game (v1.24.0);
                              competition mode (v1.25.0) tags OTB tournament games
                              (multi-game file; game type sets time_class; Event/Site
                              name+venue stripped for privacy, v1.26.1)
/<slug>/games/compare       → side-by-side game comparison
/<slug>/patterns            → pattern visualizations + Self-Analysis + Tactical Themes
/<slug>/journal             → chronological coaching diary (reviews + parent notes)
/<slug>/hunt                → Hunter Mode (opponent prep)
/<slug>/reports             → monthly/weekly coaching reports with PDF export
/settings                   → players, Stockfish config, API keys, coaching settings
```
`<slug>` is the player slug (v1.16.x). Legacy chess.com-username URLs no longer
resolve (v1.16.4 slug-only).

## Project Structure
```
ArrakisEngine/
├── CLAUDE.md
├── README.md                  # public-facing, 3-zone structure
├── CHANGELOG.md
├── ROADMAP.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── INSTRUCTION.md             # user install guide
├── LICENSE                    # AGPL-3.0
├── config.yaml.example
├── requirements.txt
├── requirements-dev.txt
├── main.py                    # CLI entry point (15 subcommands)
├── src/
│   ├── harvester.py           # chess.com + lichess game fetcher
│   ├── analyzer.py            # Stockfish analysis + clock extraction + motif tagging
│   ├── motifs.py              # v1.14.0/v1.17.0 — 12 tactical-motif detectors
│   ├── llm_providers.py       # Unified LLM provider abstraction (8 providers)
│   ├── coach.py               # LLM coaching layer (configurable history depth)
│   ├── patterns.py            # cross-game patterns + motif aggregation + trend summaries
│   ├── journal.py             # v1.12.0 — Journal entry helpers (reviews + notes)
│   ├── hunter.py              # v1.4.1+ Hunter Mode (opponent prep)
│   ├── models.py              # SQLite schema + idempotent migrations + _slugify
│   ├── tiers.py               # Adaptive tier system (rating-based)
│   ├── scheduler.py           # Auto-pipeline daemon
│   ├── pipeline_state.py      # Single-task lock across CLI/scheduler/dashboard
│   ├── dev_runner.py          # v1.5.0 — `serve` subprocess orchestration
│   ├── report.py              # Report generator
│   └── dashboard_server.py    # SQLite REST API (GET/POST/PUT/DELETE)
│                              # (export.py removed in v1.13.3 — API-only now)
├── frontend/                  # Next.js 16 + React 19 + shadcn/ui dashboard
│   ├── app/
│   │   ├── layout.tsx         # Root layout + Viewport export (v1.18.2 mobile)
│   │   ├── page.tsx           # Home → /dashboard
│   │   ├── providers.tsx      # ThemeProvider + PlayerProvider (slug-aware)
│   │   ├── dashboard/page.tsx # All-players overview + pipeline control
│   │   ├── settings/page.tsx  # Players, Stockfish, API keys, coaching settings
│   │   └── [player]/          # Player-scoped routes (segment = slug)
│   │       ├── games/         # List + detail + compare
│   │       ├── patterns/      # Charts + Self-Analysis + Tactical Themes
│   │       ├── journal/       # v1.10.0+ threaded coaching diary
│   │       ├── hunt/          # v1.4.2+ Hunter Mode UI
│   │       └── reports/       # Coaching reports
│   ├── components/
│   │   ├── app-header.tsx, nav-bar.tsx, player-selector.tsx
│   │   ├── game-detail/       # ChessBoard, MoveControls, eval chart, coaching panels (motif badges)
│   │   ├── patterns/          # visualization components + MotifThemes + Self-Analysis
│   │   ├── journal/           # v1.11.0 TimelineThread, DayGroup, EntryCard, AddNoteForm
│   │   ├── hunter/            # v1.4.2+ OpponentSearch, TargetedPrep
│   │   ├── settings/          # Players, Stockfish, API keys, Coaching sections
│   │   └── ui/                # shadcn/ui primitives (Base UI under the hood)
│   ├── hooks/                 # useChessNavigation, use-pipeline, use-coaching
│   ├── lib/                   # API client, types, providers metadata
│   │   ├── chess/             # shared chess helpers (parseMoveText, lichess URL, openings)
│   │   ├── motifs.ts          # v1.15.0 shared MOTIF_LABELS (12 emoji+label pairs)
│   │   ├── summary.ts         # parseTrendSummary (JSON-array tolerant, v1.14.1)
│   │   └── chart-format.ts    # v1.18.3 date-axis helpers (time-scale chart)
│   └── public/data/
│       ├── openings.json      # 3,690-entry Lichess CC0 opening database
│       └── traps.json         # 1,475-entry Lichess trap/gambit/attack library (v1.18.0)
├── scripts/
│   └── build_traps.py         # Rebuilds openings.json + traps.json from Lichess
├── docs/
│   ├── architecture.md        # Tracked: contributor architecture reference
│   └── screenshots/           # Architecture diagram + UI screenshots
├── data/
│   └── chess_coach.db         # SQLite database (auto-created, gitignored)
├── tests/                     # Backend pytest suite (680 tests across 3 tiers)
└── reports/                   # Generated coach reports (gitignored)
```

## Database Tables (`src/models.py`)

| Table | Purpose |
|---|---|
| `players` | Player profiles (+ `slug` v1.16.1, `is_active` soft-delete, `fide_id` + three FIDE ratings `fide_rating_{classical,rapid,blitz}` v1.26.0) |
| `games` | Stored games with PGN |
| `move_analysis` | Per-move Stockfish results (+ `clock_seconds`, `motifs_json` v1.14.0) |
| `game_coaching` | LLM coaching output (+ `player_feedback`, `coaching_meta_json`) |
| `player_patterns` | Aggregated pattern stats JSON (+ `trend_summary`, motif_summary) |
| `journal_entries` (v1.10.0) | Chronological coaching diary — `kind`='review'\|'note'\|'weakness_alert' (v1.19.0, fire-once priority-weakness alert) |
| `opponent_cache` (v1.4.1) | Hunter Mode profile JSON cache (24h TTL) |
| `opponent_games` (v1.4.4) | Hunter Mode accumulating PGN cache (sliding window) (+ `motifs_json`, `analyzed_at` v1.20.0 Deep Scan) |
| `tournaments` / `tournament_opponents` (v1.21.0) | Tournament Prep — player-scoped named roster of opponents |

`move_analysis.motifs_json` shape: `{"played": [...], "best": [...], "missed": [...]}`,
NULL on non-critical moves.

## Tactical Motifs (`src/motifs.py`, v1.14.0 + v1.17.0)

12 detectors, each a pure function `detect_X(board, move, pv) -> str | None`,
specificity-ordered. Run on both the played move and the engine's best move;
the delta is the "missed" set.

`fork`, `pin`, `skewer`, `discovered_check`, `mate_threat`, `removing_defender`,
`hanging_piece`, `trapped_piece` (v1.14.0) + `back_rank_mate`, `deflection`,
`overloaded_defender`, `zugzwang` (v1.17.0).

Aggregated by `_compute_motif_summary` in `patterns.py` into per-motif missed/found
counts with per-phase splits + a dominant-phase tag (≥60% concentration, ≥3
instances). Surfaced in `TREND_PROMPT`, `build_trajectory_block`, and the frontend
`<MotifThemes>` card. Skewer detector calibrated in v1.15.1 (require
attacker-value < front-piece-value).

**Recurring weakness escalation (v1.19.0):** `_compute_motif_summary` also derives,
per motif, the distinct-game spread (`missed_games`) + recency `streak` and an
`escalation` tier via `_escalation_tier` — spread sets the base (≥3/≥5/≥8 games →
watch/focus/priority), an active streak ≥3 boosts one level, guarded by ≥4
games-with-motif-data. The top-level `escalated_weaknesses` list drives three
surfaces: a `⚠ RECURRING WEAKNESS` line + drill-prescribing clause in the coaching
prompts, an escalation badge on the Tactical Themes card, and a fire-once
`weakness_alert` Journal entry (priority tier only, de-duped per motif within the
window). Alerts fire only when `compute_player_patterns(emit_weakness_alerts=True)`
— the `patterns` CLI + `/api/pipeline/patterns`, never the silent auto-refresh.

**Tournament Prep (v1.21.0):** `src/tournament.py` — roster CRUD (mirrors
`journal.py`) + `compute_tournament_prep`, which aggregates the Hunter Mode
opponent profiles across a saved roster (cache-only, no network/Stockfish):
opening targets/cautions grouped by `(opening, color)` over a
`tournament_min_shared` threshold, plus a field-level `motif_summary` summed
from the v1.20.0 per-opponent Deep-Scan summaries (rendered by `<MotifThemes>`).
Tournament tab + Hunt "Add to tournament" bridge. Endpoints under
`/api/tournament*` + a `/api/pipeline/tournament-prep` warm-all background job
(single-task `pipeline_state` lock). CLI: `python main.py tournament-prep --id N`.

**Hunter Mode Deep Scan (v1.20.0):** `src/hunter.py::analyze_opponent_game`
(read-only mirror of the analyzer motif loop) + `deep_scan_opponent`
(incremental, last N games via `features.hunter_scan_games`) +
`compute_opponent_motif_summary` (same shape as the player `motif_summary`)
find the tactical themes an OPPONENT misses → "Tactical Blind Spots" on the
hunt page. Opt-in only: `POST /api/pipeline/hunt-scan` (background, single-task
`pipeline_state` lock) or `python main.py hunt-scan --opponent X` — never
automatic.

## Pattern Components (Patterns page)

Move quality donut, ACPL trend, danger zones, phase performance, endgame conversion,
critical positions, tactical misses (Tactical Awareness), **Tactical Themes**
(v1.15.0 motif aggregation), comeback/collapse, repertoire consistency, opening
performance, opening ACPL, opening repertoire tracker, time pressure, time control
performance, rating progression (v1.18.3 time-scale axis + brush zoom), coaching
summary (LLM trend summary).

**Self-Analysis (v1.4.0+):** Fix Your Openings, Trap Patterns (Your Arsenal + You
Fall For with click-to-expand mini-board, recent game links, Lichess deep links).

**Hunter Mode (v1.4.1+)** is its own page (opponent prep).

## API Endpoints

All `?player=X` params + path slugs resolve by **slug** (v1.16.4). Backend helper
`_resolve_player_id(conn, identifier)` in `dashboard_server.py`.

### GET
- `/api/players` — all players with tier info + slug
- `/api/games?player=X[&...]` — filtered game list
- `/api/games/<id>` — game detail with moves + coaching
- `/api/patterns?player=X` — pattern metrics + trend_summary + motif_summary
- `/api/journal?player=X[&platform=&kind=&limit=]` — chronological diary entries
- `/api/report?player=X&period=monthly|weekly` — structured report data
- `/api/status`, `/api/pipeline/status`, `/api/settings`, `/api/schedule/status`
- `/api/hunt/profile?opponent=X&platform=Y` — (v1.4.1+) opponent profile

### POST
- `/api/players` — add player
- `/api/coach` — trigger coaching for a single game
- `/api/trend-summary` — LLM trend summary
- `/api/journal/review` — generate Recent Form Review entry (v1.10.0)
- `/api/journal/note` — create Parent Note (v1.12.0)
- `/api/pipeline/{harvest,analyze,patterns,coach,run-all,cancel}` — pipeline triggers
- `/api/schedule/{toggle,interval}` — scheduler control
- `/api/hunt/refresh` — force opponent profile re-fetch (v1.4.1+)
- `/api/import-pgn` — (v1.24.0) import a raw PGN → analyzed game; (v1.25.0)
  `platform="competition"` + `time_class` imports OTB tournament games (multi-game;
  v1.26.1 strips the Event/Site name+venue from stored competition PGNs)
- `/api/games/export` — (v1.24.0) `{ids, annotated}` → PGN file (raw / annotated)

### PUT / DELETE
- `PUT /api/players/<id>` (incl. the three FIDE ratings v1.26.0),
  `PUT /api/settings/{analysis,api-keys,coaching}`
- `PUT /api/games/<id>/ratings` — (v1.25.1) set player/opponent rating
  (int or null=unrated); OTB PGNs carry no Elo
- `PUT /api/games/<id>/classification` — (v1.26.2) set `platform` (category) +
  `time_class` (game type) + (v1.26.3) `date_played` (timing). Marking a game
  `competition` also strips the private Event/Site headers from its stored PGN.
- `PUT /api/journal/note/<id>`, `DELETE /api/journal/note/<id>` (v1.12.0)
- `DELETE /api/players/<id>` (soft-delete via `is_active`)

## CLI Commands (`main.py`)

`harvest`, `analyze`, `coach`, `patterns`, `trend` (v1.15.2 — LLM trend summary),
`review` (v1.9.0 — Recent Form Review), `note` (v1.12.0 — Parent Note),
`report`, `dashboard`, `serve` (v1.5.0), `rescan-motifs` (v1.14.0 — backfill motif
tags, no Stockfish), `backfill-acpl`, `backfill-clocks`, `fide-update`, `run-all`.

`--player` accepts the slug (v1.16.4 slug-only; v1.18.1 fixed rescan-motifs +
harvest + report).

## Testing

**~952 tests total** — 724 backend (pytest, three tiers via `pyproject.toml`
markers) + 228 frontend (Vitest). Integration (`-m integration`, needs Stockfish)
and live (`-m live`, needs an LLM key) tiers are excluded by default.

### Running Tests
```bash
pytest                                  # default unit tier (~30s, no deps)
pytest -m integration                   # Stockfish tests (requires binary)
pytest -m live                          # LLM API tests (~$0.30)
cd frontend && npx vitest run           # 228 frontend tests, ~3s
cd frontend && npx next build           # type-check
```

### Notable test files
- `test_motifs.py` — per-motif detectors incl. v1.15.1 skewer calibration
- `test_patterns.py` — pattern aggregations + motif summary + phase split + prompt wiring
- `test_main_cli.py` (v1.15.3) — CLI dispatch, slug resolution
- `test_dashboard_server.py` — API endpoints + slug resolver + static guard
- `test_coach_live.py` (`-m live`) — per-model structured-output + motif-citation compliance
- Frontend: `chart-format.test.ts`, `motif-themes.test.tsx`, `layout.test.tsx`,
  `player-selector.test.tsx`, `summary.test.ts`, + chess-helper + component suites

### Patch-target rule
Functions imported locally inside another function (e.g. `from src.coach import
coach_pending` inside `run_full_pipeline()`) must be patched at the **source**
module — `@patch("src.coach.coach_pending")` — not at the consuming module.

## Key Technical Decisions
- **DB as the source of truth for players** — UI-driven CRUD, not config.yaml
- **slug ≠ username** — slug for URLs/API/CLI, username for the chess.com API only
  (v1.16.x). Slug-only lookups; one explicit `WHERE username = ?` exception
  (player-creation existence check), enforced by a static guard test.
- **Soft-delete via `is_active`** — preserves game history
- **Reasoning models required** — a convention, NOT a code gate. `resolve_model`
  / `call_provider` accept any model string; the contract holds because every
  registry default is a reasoning model, the Anthropic path sends
  `thinking={"type":"adaptive"}`, and OpenAI uses the Responses (reasoning) API.
  There is no allowlist to update when adding a model.
- **LLM output is plain text, never JSON** — `TREND_PROMPT` /
  `RECENT_FORM_REVIEW_PROMPT` emphatically forbid JSON (v1.15.4); the frontend
  `parseTrendSummary` is JSON-array tolerant as belt-and-braces (v1.14.1).
- **Motif tags are conservative** — false negatives preferred over false positives;
  min-value SEE heuristic; specificity-ordered so the most distinctive label leads.
- **Single-task pipeline lock** — across CLI + scheduler + dashboard
- **`ARRAKIS_` prefix on env keys** — avoids collisions with other tools
- **Lichess deep link format** — `/analysis/standard/{FEN}`, not `?pgn=` (v1.4.5 lesson)
- **Competition games never store the tournament name/venue** (v1.26.1) — the PGN
  `Event`/`Site` headers are stripped on import (and on reclassify-to-competition)
  so they can't leak via the API or PGN export. `strip_private_headers` in
  `src/pgn_io.py` is the single seam (import, reclassification, backfill all reuse it).
- **FIDE ratings are FIDE-only** (v1.26.0) — three ratings (Classical/Rapid/Blitz),
  shown as FIDE info; they never override the chess.com/lichess platform rating.
- **Shared chess + motif helpers in `frontend/lib/`** — single source of truth to
  avoid the duplication that hid the v1.4.5 regressions.

## Two-Server Setup

**Recommended (v1.5.0+) — single command:**
```bash
python main.py serve     # spawns both servers; Ctrl+C stops both
```
Requires `pnpm` (or `corepack enable`). Optional flags: `--port`, `--frontend-port`,
`--install`.

**Manual two-terminal mode:**

| | Port | Start with |
|---|---|---|
| Python API backend | 8000 | `python main.py dashboard` |
| Next.js frontend | 3000 | `cd frontend && npx next dev` |

Open `http://localhost:3000`. It calls back to the API on 8000.

## Git Workflow
- Commit after each working component; ship via branch → ff-merge → tag `vX.Y.Z` → push → `gh release create`
- Keep `data/`, `reports/`, `.claude/`, `.mcp.json` in `.gitignore`
- Never commit API keys
- **Reserved for commercial Atreides version** (not public): tournament-game
  scoresheet **photo capture + OCR + move correction**. NOTE: generic PGN
  import/export (`src/pgn_io.py`, v1.24.0) is now an **open** feature — only the
  OCR capture/correction layer that produces a validated PGN is commercial. OCR
  layers on top of the open `parse_pgn` / `ingest_game` seam.
