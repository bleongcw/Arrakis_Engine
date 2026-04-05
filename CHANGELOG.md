# Changelog

All notable changes to ArrakisEngine will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-04-05

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
- Automated pipeline scheduler (harvest → analyze → patterns)
- CLI with 10 commands: harvest, analyze, coach, patterns, export-json, report, dashboard, fide-update, backfill-clocks, run-all

**LLM Coaching**
- Game type detection — classifies games into 10 types (tactical battle, comeback, collapse, positional grind, opening disaster, miniature, etc.) with type-specific coaching guidance
- Coaching history injection — last 5 coached games' lessons fed into the LLM prompt to avoid repetitive feedback and build on prior advice
- Coaching settings UI — customizable tone (encouraging / balanced / technical), detail level, focus areas, and free-form custom instructions
- Variety instructions in coaching prompt to ensure fresh, non-formulaic output
- "Generate Coaching Briefs" pipeline button — batch-coach games from the dashboard UI with progress tracking, cancel support, and per-player filtering
- Provider selector (8 providers with Cloud/Local grouping) for coaching briefs and per-game coaching
- Games coached in chronological order (oldest-first) so coaching history builds naturally
- Full datetime storage in `date_played` for correct chronological ordering
- Exponential backoff on API rate limits (30s → 60s → 120s, max 5 minutes)
- Consecutive failure circuit breaker (3 failures → abort batch)
- Authentication error detection with immediate abort
- Interruptible sleep via threading.Event for responsive cancellation

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
- Settings page (player CRUD, Stockfish config, API key management, coaching settings)
- Pipeline control panel (harvest → analyze → insights → coaching briefs from UI)
- Dark/light mode toggle
- Mobile responsive layout

**Infrastructure**
- SQLite database with auto-migration
- Config via YAML with environment variable secrets
- AGPL-3.0 license
- GitHub Actions CI (Python 3.11/3.12 + frontend build)
- 169 tests (unit, integration, live API)
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
