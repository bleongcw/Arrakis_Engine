# Changelog

All notable changes to ArrakisEngine will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-04-04

First public open-source release under AGPL-3.0.

### Added

**Core Pipeline**
- Chess.com game harvester with rate limiting and deduplication
- Lichess game harvester with API integration
- FIDE rating lookup and sync
- Stockfish analysis engine (depth 22, multi-threaded, per-move timeout)
- ACPL calculation with ±1000cp eval capping (Lichess/Chess.com standard)
- Adaptive tier system — analysis depth and move thresholds scale with player rating
- LLM coaching layer with abstracted provider support (Anthropic Claude, OpenAI GPT)
- Cross-game pattern detection (16 metrics)
- Markdown report generator with time control filtering
- Automated pipeline scheduler (harvest → analyze → patterns)
- CLI with 10 commands: harvest, analyze, coach, patterns, export-json, report, dashboard, fide-update, backfill-clocks, run-all

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
- Settings page (player CRUD, Stockfish config, API key management)
- Pipeline control panel (harvest/analyze/patterns/run-all from UI)
- Dark/light mode toggle
- Mobile responsive layout

**Infrastructure**
- SQLite database with auto-migration
- Config via YAML with environment variable secrets
- AGPL-3.0 license
- GitHub Actions CI (Python 3.11/3.12 + frontend build)
- 169 tests (unit, integration, live API)

**Documentation**
- Comprehensive README with installation, CLI usage, and architecture overview
- CONTRIBUTING.md with CLA for dual-licensing
- CODE_OF_CONDUCT.md (Contributor Covenant v2.1)
