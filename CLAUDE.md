# Arrakis Engine — Chess Coach AI

## Project Overview
Local Python app that pulls chess.com games, runs Stockfish analysis,
and uses LLMs to generate age-appropriate coaching insights with
pattern tracking over time. Inspired by Eleanor, Evan, and Estella.

## Architecture
- Python 3.11+, SQLite, local Stockfish on Apple Silicon
- Two-step analysis: Stockfish engine eval → LLM coaching interpretation
- Third layer: cross-game pattern aggregation over time

## Players
- Configured in config.yaml (chess.com usernames, display names, ages, ratings)

## Key Configuration
- Stockfish: depth 22, 6 threads, 512MB hash, path configured in config.yaml
- LLM: abstracted provider supporting both Anthropic (Claude Opus 4.6) and OpenAI (GPT-5.4)
- Config via config.yaml, secrets via .env (ARRAKIS_ANTHROPIC_API_KEY, ARRAKIS_OPENAI_API_KEY)
- Initial scope: last 6 months of games

## Analysis Standards
- Win probability: Lichess formula → win% = 50 + 50 × (2 / (1 + exp(-0.00368208 × cp)) - 1)
- Move classifications: excellent (<30cp loss), good (<50), inaccuracy (<100), mistake (<300), blunder (300+)
- Coaching output has two tones: child-facing (age-appropriate, concrete, encouraging) and coach-facing (technical, actionable)
- Player age and rating are read dynamically from the database — coaching tone adapts per player

## Project Structure
```
ArrakisEngine/
├── CLAUDE.md
├── config.yaml                # Config template (copy to config.yaml)
├── requirements.txt
├── main.py                    # CLI entry point
├── src/
│   ├── harvester.py           # Chess.com + Lichess game fetcher
│   ├── analyzer.py            # Stockfish analysis engine
│   ├── coach.py               # LLM coaching layer (Anthropic + OpenAI)
│   ├── patterns.py            # Cross-game pattern detection
│   ├── models.py              # SQLite schema & data models
│   ├── tiers.py               # Adaptive tier system (rating-based)
│   ├── report.py              # Markdown report generator
│   ├── export.py              # Data export utilities
│   └── dashboard_server.py    # SQLite REST API for frontend
├── frontend/                  # Next.js 16 + shadcn/ui dashboard
│   ├── app/
│   │   ├── layout.tsx         # Root layout with theme provider
│   │   ├── page.tsx           # Player dashboard landing page
│   │   ├── dashboard/page.tsx # Legacy dashboard redirect
│   │   ├── games/page.tsx     # Games list with filters
│   │   ├── games/[id]/page.tsx# Game detail: board, eval, coaching
│   │   └── patterns/page.tsx  # Pattern analytics & insights
│   ├── components/
│   │   ├── game-detail/       # Chessboard, eval chart, move list
│   │   ├── patterns/          # ACPL trend, openings, phases, tactics
│   │   └── ui/                # shadcn/ui primitives
│   ├── hooks/                 # useChessNavigation, useCoaching
│   └── lib/                   # API client, types, utilities
├── dashboard/                 # Legacy single-file HTML dashboard
│   └── index.html
├── data/
│   └── chess_coach.db         # SQLite database (auto-created, gitignored)
├── tests/                     # pytest test suite
└── reports/                   # Generated coach reports (gitignored)
```

## Testing

182 tests across 13 test files, organized into three tiers via pytest markers (`pyproject.toml`).

### Running Tests
```bash
pytest                                  # 169 unit tests (~14s, no deps)
pytest -m integration                   # 7 Stockfish tests (~25s)
pytest -m live                          # 5 LLM API tests (~3min, ~$0.05)
pytest -m "integration and live"        # 1 full pipeline E2E (~1min)
pytest -m ""                            # All 182 tests
```

### Tier 1: Unit Tests (169 tests, default)
All external dependencies mocked. No Stockfish or API keys needed.

| File | Tests | What it covers |
|------|-------|---------------|
| test_models.py | 16 | Schema init, ensure_player upsert, constraints, extract_opponent_from_pgn, get_db_path, migrations |
| test_harvester.py | 20 | Chess.com + Lichess parsing: side detection, result classification, time control, date extraction, deduplication |
| test_analyzer.py | 19 | cp_to_win_prob formula, classify_move thresholds, cap_eval clamping, score_to_cp with mock PovScore |
| test_coach.py | 18 | Move formatting, analysis text truncation (short vs long games), critical moments sorting, JSON parsing, provider switching (Claude/OpenAI), coach_pending limit, DB status transitions |
| test_patterns.py | 38 | Phase classification, results aggregation, rating buckets, accuracy, consistency, danger zones, endgame conversion, comeback/collapse, opening ACPL, tactical misses, repertoire consistency, opening name extraction, single-game and empty-game edge cases |
| test_tiers.py | 21 | Rating→tier boundary mapping, tier-specific move classification, config validation (depth, thresholds, focus areas) |
| test_report.py | 9 | Weekly/monthly report generation, ACPL interpretation thresholds (excellent/good/needs work), time control table, missing coaching data handling |
| test_dashboard_server.py | 14 | Real HTTP server: players/games/status/patterns endpoints, result/time_class/date_from/date_to filtering, CORS headers, 404 handling |
| test_export.py | 7 | JSON export, PGN preview truncation, coaching data inclusion, missing analysis, empty DB |

### Tier 2: Integration Tests (7 tests, `pytest -m integration`)
Requires Stockfish binary. Uses Scholar's Mate (4 moves) for fast, deterministic analysis.

| File | Tests | What it covers |
|------|-------|---------------|
| test_analyzer_integration.py | 7 | Real Stockfish: move row creation, eval sanity (opening ~0cp, mate→±1000cp), ACPL storage, classification validity, batch processing, stuck game recovery, empty PGN handling |

### Tier 3: Live Tests (5 tests, `pytest -m live`)
Requires `ARRAKIS_ANTHROPIC_API_KEY` or `ARRAKIS_OPENAI_API_KEY`. Uses whichever is available (prefers Claude).

| File | Tests | What it covers |
|------|-------|---------------|
| test_coach_live.py | 5 | Real LLM API: valid JSON response, required keys present (narrative, key_lesson, practical_focus, critical_moments, coach_notes), DB storage with provider:model format, missing API key error, unknown provider error |

### Full Pipeline E2E (1 test, `pytest -m "integration and live"`)

| File | Tests | What it covers |
|------|-------|---------------|
| test_pipeline_e2e.py | 1 | Insert game → Stockfish analysis → LLM coaching → verify analysis_status=complete, coaching_status=complete, move rows populated, coaching JSON valid |

### Shared Fixtures (`tests/conftest.py`)
- `db_path` — fresh SQLite test DB (used by most test files)
- `player_id` — test player (TestKid, age 9, rating 1050)
- `insert_game()` — callable: insert a game row with full control over all fields
- `insert_moves()` — callable: insert move_analysis rows from a list of dicts
- `stockfish_path` — auto-resolves: config.yaml → `STOCKFISH_PATH` env → `which stockfish` (skips if not found)
- `llm_provider` — returns `(provider, model)` for whichever API key is set (skips if none)
- `SAMPLE_PGN` / `SCHOLARS_MATE_PGN` — reusable PGN constants

## Git Workflow
- Commit after each working component
- Keep data/ and reports/ in .gitignore
- Never commit API keys
