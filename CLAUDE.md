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

Three test tiers configured via pytest markers in `pyproject.toml`:

| Command | Tests | Time | Requirements |
|---------|-------|------|-------------|
| `pytest` | 169 unit tests | ~14s | None (all mocked) |
| `pytest -m integration` | 7 Stockfish tests | ~25s | Stockfish binary |
| `pytest -m live` | 5 LLM API tests | ~3min | API key (Anthropic or OpenAI) |
| `pytest -m ""` | All 182 tests | ~5min | Stockfish + API key |

- Unit tests mock all external dependencies (Stockfish, LLM APIs, chess.com/Lichess)
- Integration/live tests are excluded by default via `pyproject.toml` addopts
- `stockfish_path` fixture auto-resolves from config.yaml → STOCKFISH_PATH env → PATH
- `llm_provider` fixture picks whichever API key is available (prefers Claude)
- Shared fixtures in `tests/conftest.py` (db_path, player_id, insert_game, insert_moves)

## Git Workflow
- Commit after each working component
- Keep data/ and reports/ in .gitignore
- Never commit API keys
