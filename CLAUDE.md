# ArrakisEngine — Chess Coach AI for Evan & Estella

## Project Overview
Local Python app that pulls chess.com games, runs Stockfish analysis,
and uses LLMs to generate age-appropriate coaching insights with
pattern tracking over time.

## Architecture
- Python 3.11+, SQLite, local Stockfish on Apple Silicon
- Two-step analysis: Stockfish engine eval → LLM coaching interpretation
- Third layer: cross-game pattern aggregation over time

## Players
- Evan (evanleongxinyu) — age 9, rated 1000-1100
- Estella (estellaleong)

## Key Configuration
- Stockfish: depth 22, 6 threads, 512MB hash, binary at /usr/local/bin/stockfish
- LLM: abstracted provider supporting both Anthropic (claude-sonnet-4-6) and OpenAI
- Config via config.yaml, secrets via environment variables (ANTHROPIC_API_KEY, OPENAI_API_KEY)
- Initial scope: last 6 months of games

## Analysis Standards
- Win probability: Lichess formula → win% = 50 + 50 × (2 / (1 + exp(-0.00368208 × cp)) - 1)
- Move classifications: excellent (<30cp loss), good (<50), inaccuracy (<100), mistake (<300), blunder (300+)
- Coaching output has two tones: child-facing (age 9, concrete, encouraging) and coach-facing (technical, actionable)

## Project Structure
```
ArrakisEngine/
├── CLAUDE.md
├── config.yaml
├── requirements.txt
├── main.py                    # CLI entry point
├── src/
│   ├── harvester.py           # Chess.com API game fetcher
│   ├── analyzer.py            # Stockfish analysis engine
│   ├── coach.py               # LLM coaching layer (abstracted)
│   ├── patterns.py            # Cross-game pattern detection
│   ├── models.py              # SQLite schema & data models
│   └── report.py              # Markdown report generator
├── dashboard/
│   └── index.html             # Single-file local web dashboard
├── data/
│   └── chess_coach.db         # SQLite database (auto-created, gitignored)
├── tests/                     # Test suite
└── reports/                   # Generated coach reports (gitignored)
```

## Testing
- pytest for test runner
- Tests live in tests/ directory
- Use real chess.com data for integration tests
- Test Stockfish integration with known PGN

## Git Workflow
- Commit after each working component
- Keep data/ and reports/ in .gitignore
- Never commit API keys
