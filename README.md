# Arrakis Engine

A local Python application that pulls games from **Chess.com** and **Lichess**, runs deep Stockfish analysis on every move, and uses LLMs (Claude Opus 4.6 / GPT-5.4) to generate age-appropriate coaching insights. Built for tracking improvement over time with pattern detection, a live web dashboard, and exportable coach-ready reports.

Inspired by my three children — Eleanor, Evan, and Estella — and their journey learning chess.

## Architecture

![Arrakis Engine Architecture](docs/screenshots/arrakis-engine-architecture.png)

The pipeline is three layers:
1. **Stockfish engine evaluation** — objective, per-move centipawn analysis
2. **LLM coaching interpretation** — transforms raw engine output into human-readable insights
3. **Pattern aggregation** — tracks trends across games over weeks and months

## Screenshots

<!-- Replace these placeholders with actual screenshots -->

| Dashboard — Games List | Dashboard — Game Analysis |
|---|---|
| ![Games List](docs/screenshots/games-list-placeholder.png) | ![Game Analysis](docs/screenshots/game-analysis-placeholder.png) |

| Dashboard — Patterns | Coach Report |
|---|---|
| ![Patterns](docs/screenshots/patterns-placeholder.png) | ![Report](docs/screenshots/report-placeholder.png) |

## Requirements

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Tested on 3.12 |
| Stockfish | 16+ | Apple Silicon recommended |
| macOS / Linux | Any | Developed on macOS (Apple Silicon) |

### API Keys (for LLM coaching only)

- **Anthropic** — [console.anthropic.com](https://console.anthropic.com) → API Keys
- **OpenAI** — [platform.openai.com](https://platform.openai.com) → API Keys

The harvester and Stockfish analyzer work without API keys. You only need keys for the LLM coaching step.

## Installation

### 1. Clone the repository

```bash
git clone git@github.com:bleongcw/ArrakisEngine.git
cd ArrakisEngine
```

### 2. Install Stockfish

**Option A — Compile from source (recommended, ~2x faster):**

```bash
git clone https://github.com/official-stockfish/Stockfish.git
cd Stockfish/src
make -j profile-build COMP=clang ARCH=apple-silicon
sudo cp stockfish /usr/local/bin/stockfish
cd ../..
rm -rf Stockfish
```

**Option B — Homebrew (simpler):**

```bash
brew install stockfish
```

Verify the installation:

```bash
stockfish <<< "uci" | head -1
# Should print: Stockfish 18 by the Stockfish developers (see AUTHORS file)
```

### 3. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure API keys

Create a `.env` file in the project root:

```bash
# .env (gitignored — never committed)
ARRAKIS_ANTHROPIC_API_KEY=sk-ant-your-key-here
ARRAKIS_OPENAI_API_KEY=sk-your-key-here
```

### 5. Create your config.yaml

Copy the example template and fill in your details:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` to match your setup (this file is gitignored — your personal config stays local):

```yaml
players:
  - username: your_chess_com_username       # Chess.com username (required)
    lichess_username: your_lichess_id       # Lichess username (optional)
    fide_id: null                           # FIDE player ID (optional, e.g., 5871042)
    display_name: Player 1
    age: null
    rating: null
  - username: another_chess_com_username
    display_name: Player 2
    age: null
    rating: null

stockfish:
  path: /opt/homebrew/bin/stockfish   # or /usr/local/bin/stockfish
  depth: 22
  threads: 6
  hash_mb: 512

analysis:
  months_lookback: 6

coaching:
  default_provider: claude            # or "openai"
  anthropic_model: claude-opus-4-6
  openai_model: gpt-5.4               # or gpt-5.4-pro (requires Responses API)

database:
  path: data/chess_coach.db
```

**Stockfish path:** Defaults to `/opt/homebrew/bin/stockfish` (Homebrew). Use `/usr/local/bin/stockfish` if compiled from source. Run `which stockfish` to verify.

**Threads:** Set to your CPU core count minus 2 (e.g., 6 for an 8-core M-series chip) to leave headroom for other processes.

## CLI Commands

| Command | Description |
|---|---|
| `python main.py harvest` | Fetch games from Chess.com and Lichess for all configured players |
| `python main.py analyze` | Run Stockfish analysis on all pending games |
| `python main.py coach` | Generate LLM coaching insights (supports `--limit` and `--provider`) |
| `python main.py patterns` | Compute cross-game pattern statistics |
| `python main.py export-json` | Export database to JSON for the web dashboard |
| `python main.py report` | Generate Markdown coaching reports |
| `python main.py dashboard` | Launch the local web dashboard |
| `python main.py fide-update` | Update a player's FIDE rating |
| `python main.py run-all` | Run the full pipeline end-to-end |

### Command details

**Harvest games:**

```bash
# All configured players from all platforms
python main.py harvest

# Specific player only
python main.py harvest --player your_chess_com_username

# Filter by platform
python main.py harvest --platform chess.com
python main.py harvest --platform lichess

# Combine filters
python main.py harvest --player your_chess_com_username --platform lichess
```

> **Multi-platform:** Games are fetched from Chess.com (via monthly archives API) and Lichess (via PGN export API). Add `lichess_username` to your player config to enable Lichess harvesting.
>
> **Incremental by design:** The harvester deduplicates by `game_url` — it only fetches new games since your last harvest. Safe to run repeatedly without duplicating data. The dashboard shows which platform each game came from (♜ Chess.com / ♞ Lichess).

**Analyze with Stockfish:**

```bash
# Analyze all pending games (uses settings from config.yaml)
python main.py analyze
```

> Each move has a 10-second time limit to prevent hanging on complex positions. Analysis takes ~5–10 min per game with Homebrew Stockfish or ~3–5 min per game with a source-compiled binary. For large backlogs (400+ games), run overnight.

**Generate coaching insights:**

```bash
# Use default provider from config (Claude Opus 4.6)
python main.py coach

# Use a specific provider
python main.py coach --provider openai

# Limit batch size (recommended for rate limits)
python main.py coach --limit 5

# Combine provider and limit
python main.py coach --provider openai --limit 5
```

> **⚠️ LLM Cost Warning:** Each coaching call sends a detailed prompt (~3,000–7,000 tokens) and receives a structured response (~2,000–4,000 tokens). At current API pricing, coaching a single game costs approximately **$0.03–0.10 with Claude Opus 4.6** and **$0.02–0.08 with GPT-5.4**. For a backlog of 400+ games, this can add up to **$15–40 or more**. Start with `--limit 5` to verify quality and estimate your costs before running large batches. Monitor your API usage dashboards at [Anthropic Console](https://console.anthropic.com/) or [OpenAI Platform](https://platform.openai.com/usage).

> **Rate limits:** OpenAI's `gpt-5.4` has a 10,000 TPM limit (~1 game/min on free/low tiers). Use `--limit 5` per batch to avoid 429 errors. Claude typically has higher throughput — `--limit 10-20` is safe. The dashboard shows which model was used for each game's coaching (purple badge = Claude, green badge = OpenAI).

> **Dashboard coaching:** You can also coach individual games directly from the dashboard — click the 🟣 **Coach with Claude** or 🟢 **Coach with ChatGPT** button on any game's detail page. Results auto-refresh when complete.

**Update FIDE rating:**

```bash
# Update FIDE rating for a player
python main.py fide-update --player evanleongxinyu --rating 1544

# Set FIDE ID and rating together
python main.py fide-update --player evanleongxinyu --fide-id 5871042 --rating 1544
```

> FIDE ratings are updated manually via the CLI. You can also set `fide_id` in `config.yaml` to have it linked on first harvest. The dashboard links directly to the player's FIDE profile at `ratings.fide.com/profile/{fide_id}`.

**Generate reports:**

```bash
# Weekly report for a specific player
python main.py report --player your_chess_com_username --weekly

# Monthly report for all players, custom output directory
python main.py report --monthly --output reports/march
```

**Launch the dashboard:**

```bash
python main.py dashboard
# → http://localhost:8000

# Custom port
python main.py dashboard --port 3000
```

**Run the full pipeline:**

```bash
python main.py run-all
# Executes: harvest → analyze → coach → patterns → export-json
```

### Verbose logging

Add `-v` before the subcommand for debug output:

```bash
python main.py -v harvest
python main.py -v analyze
```

## Typical Workflow

### First-time setup

```bash
# 1. Fetch all games from the last 6 months
python main.py harvest

# 2. Run Stockfish analysis (let this run overnight for large backlogs)
python main.py analyze

# 3. Generate coaching insights
python main.py coach

# 4. Compute patterns and export
python main.py patterns
python main.py export-json

# 5. View results
python main.py dashboard
```

### Weekly routine

```bash
# Pull new games, analyze, coach, update patterns, export — all in one command
python main.py run-all

# Generate weekly reports for coaches
python main.py report --player your_chess_com_username --weekly

# Review in dashboard
python main.py dashboard
```

## How Analysis Works

### Stockfish Settings

| Setting | Value | Rationale |
|---|---|---|
| Depth | 22 | Catches all tactical errors at beginner-to-intermediate levels |
| Threads | 6 | Leaves 2 cores free on M-series chips |
| Hash | 512 MB | Sufficient for single-game analysis |
| Time limit | 10s/move | Prevents hanging on complex endgame positions |
| MultiPV | 1 | Best move only (keeps analysis focused) |

### Move Classification

Each move is classified by centipawn loss (how much worse it is than the engine's best move). Thresholds adapt to the player's tier — stricter for advanced players, looser for beginners:

| Classification | Beginner (<800) | Elementary (800–1200) | Intermediate (1200–1600) | Advanced (1600+) |
|---|---|---|---|---|
| Excellent | < 50cp | < 30cp | < 20cp | < 15cp |
| Good | < 100cp | < 50cp | < 40cp | < 30cp |
| Inaccuracy | < 200cp | < 100cp | < 70cp | < 60cp |
| Mistake | < 500cp | < 300cp | < 200cp | < 150cp |
| Blunder | 500+ | 300+ | 200+ | 150+ |

### Evaluation Capping

All engine evaluations are **capped at ±1000 centipawns** before computing centipawn loss, matching the industry standard used by Lichess and Chess.com. This prevents mate scores and extreme positions from distorting ACPL calculations. Mate-in-X scores are mapped to ±1000cp.

### Win Probability

Centipawn evaluations are converted to win probability using the [Lichess formula](https://lichess.org/page/accuracy):

```
win% = 50 + 50 × (2 / (1 + exp(-0.00368208 × cp)) - 1)
```

This makes evaluation swings more intuitive — a drop from 70% to 30% win probability is far more meaningful than "lost 200 centipawns."

### LLM Coaching Output

For each analyzed game, the LLM produces:

| Output | Audience | Description |
|---|---|---|
| **Game narrative** | Child | 2–3 paragraph story of what happened, encouraging tone |
| **Key lesson** | Child | Single most important takeaway |
| **Practical focus** | Child | One specific thing to practice |
| **Opening analysis** | Both | Opening name, quality rating, counter-move assessment, and tip |
| **Critical moments** | Both | 3–5 positions with what happened vs. what was better |
| **Player feedback** | Child | Personal letter with 3 actionable tips, growth mindset framing |
| **Coach notes** | Coach | Technical summary for lesson planning |

### Pattern Tracking

Patterns are aggregated across all games per player:

- **Opening performance** — win rate by opening name, split by color (All / White / Black)
- **ACPL trend** — per-game ACPL (±1000cp capped) averaged in weekly buckets; hover to see game count per week
- **Phase analysis** — error frequency and ACPL in opening (moves 1–15), middlegame (16–30), endgame (31+) — all using capped evaluations
- **Rating performance** — win rate vs. higher/lower/equal rated opponents
- **Move quality distribution** — percentage of excellent/good/inaccuracy/mistake/blunder moves
- **Time class stats** — win rate by rapid/blitz/bullet/daily

## Web Dashboard

The dashboard is a live web app served by a built-in Python HTTP server. It queries SQLite directly — no JSON export needed, and data updates in real-time as analysis and coaching complete.

**Features:**
- **Player selector** — toggle between configured players
- **Games list** — filterable by result, time control, coaching status (✅ Coached / ⏳ Pending / ❌ Error), and date range
- **Status columns** — separate Analysis and Coaching status icons per game for at-a-glance pipeline progress
- **Month/year filter** — filter games by month (e.g. "Mar 2026") alongside result, time control, and coaching status
- **Game analysis** — interactive chessboard with proper piece SVGs (lichess cburnett set), move-by-move eval chart, color-coded move list (green/blue/yellow/orange/red by classification)
- **Move quality summary** — per-game table showing counts of excellent, good, inaccuracy, mistake, and blunder moves for player vs opponent with proportional bars
- **Opening analysis** — LLM-generated assessment of the opening choice, quality rating, counter-move correctness, and tips
- **On-demand coaching** — 🟣 Coach with Claude / 🟢 Coach with ChatGPT buttons on each game, with auto-refresh on completion
- **Coaching model badge** — shows which LLM model generated the coaching (🟣 Claude / 🟢 OpenAI)
- **Patterns dashboard** — stat cards, ACPL trend line chart, opening performance split by color (All / ♔ White / ♚ Black), move quality donut chart, phase analysis bar chart
- **Player dashboard** — default landing page showing each player's profile with Chess.com, Lichess, and FIDE ratings, tier badge, and direct links to external profiles
- **FIDE integration** — optional FIDE ID links to `ratings.fide.com/profile/{id}`, manually updated via `fide-update` CLI command
- **Light/dark mode** — toggle with 🌙/☀️ button, persists across sessions
- **Live data** — dashboard reads from the database directly, so you can view results while analysis or coaching is still running

**Libraries used (all loaded from CDN):**
- [chessboard.js](https://chessboardjs.com/) — board rendering
- [chess.js](https://github.com/jhlywa/chess.js) — PGN parsing and move validation
- [Chart.js](https://www.chartjs.org/) — eval graphs and trend charts

## Project Structure

```
ArrakisEngine/
├── CLAUDE.md              # Project context for Claude Code
├── README.md              # This file
├── config.yaml.example    # Template config (copy to config.yaml)
├── config.yaml            # Your personal config (gitignored)
├── requirements.txt       # Python dependencies
├── .env                   # API keys (gitignored)
├── .gitignore
├── main.py                # CLI entry point — all commands
├── src/
│   ├── models.py          # SQLite schema (5 tables) and data helpers
│   ├── harvester.py       # Chess.com API game fetcher
│   ├── analyzer.py        # Stockfish move-by-move analysis engine
│   ├── coach.py           # LLM coaching layer (Claude / OpenAI via Responses API)
│   ├── patterns.py        # Cross-game pattern detection
│   ├── export.py          # JSON export for dashboard
│   ├── dashboard_server.py # Live dashboard HTTP server with SQLite API
│   └── report.py          # Markdown report generator
├── dashboard/
│   ├── index.html         # Web dashboard (served by dashboard_server.py)
│   ├── img/pieces/        # Lichess cburnett SVG chess pieces
│   └── data/              # Exported JSON (auto-generated, gitignored)
├── tests/                 # Test suite (56 tests)
│   ├── test_models.py
│   ├── test_harvester.py
│   ├── test_analyzer.py
│   ├── test_coach.py
│   ├── test_patterns.py
│   ├── test_export.py
│   └── test_report.py
├── data/
│   └── chess_coach.db     # SQLite database (auto-created, gitignored)
└── reports/               # Generated coach reports (gitignored)
```

### Database Schema

| Table | Purpose |
|---|---|
| `players` | Player profiles (username, display name, age, rating, FIDE ID/rating) |
| `games` | Game records with PGN, ratings, result, platform, ACPL, analysis/coaching status |
| `move_analysis` | Per-move Stockfish evaluation (capped centipawn, win prob, classification) |
| `game_coaching` | LLM-generated coaching output per game (narrative, feedback, opening analysis) |
| `player_patterns` | Aggregated pattern statistics per player per period |

## Running Tests

```bash
python -m pytest tests/ -v
```

All tests run against in-memory SQLite databases with mocked external APIs — no Stockfish binary or API keys needed.

## Troubleshooting

**"unable to open database file"**
The `data/` directory is created automatically. If you see this error, check that you're running commands from the project root directory.

**"No such file or directory: '/usr/local/bin/stockfish'"**
Update the `stockfish.path` in `config.yaml` to match your installation. Use `which stockfish` to find the correct path.

**"ARRAKIS_ANTHROPIC_API_KEY not set"**
Create a `.env` file in the project root with your API keys (see [Configure API keys](#4-configure-api-keys)).

**Analysis is very slow**
Homebrew Stockfish runs at ~4.4M nodes/sec vs ~9–14M nodes/sec for a source-compiled binary. Consider compiling from source (see [Install Stockfish](#2-install-stockfish)). Each move has a 10-second time limit to prevent hanging. You can also reduce depth in `config.yaml` — depth 18 is ~3x faster with minimal loss in accuracy for beginner-to-intermediate players.

**OpenAI 429 rate limit errors**
Your API tier has a tokens-per-minute cap (e.g. 10,000 TPM on free tier). Use `--limit 5` to batch and allow the 10-second delay between calls. Upgrading your OpenAI plan raises the limit. Alternatively, use `--provider claude`.

**Games show "error" analysis or coaching status**
Reset errored games and re-run:
```bash
# Reset analysis errors
python3 -c "
from src.models import init_db
conn = init_db('data/chess_coach.db')
conn.execute(\"UPDATE games SET analysis_status = 'pending' WHERE analysis_status = 'error'\")
conn.commit()
print('Reset', conn.total_changes, 'games')
conn.close()
"
python main.py analyze

# Reset coaching errors
python3 -c "
from src.models import init_db
conn = init_db('data/chess_coach.db')
conn.execute(\"UPDATE games SET coaching_status = 'pending' WHERE coaching_status = 'error'\")
conn.commit()
print('Reset', conn.total_changes, 'games')
conn.close()
"
python main.py coach --limit 5
```

**"database is locked"**
SQLite only allows one writer at a time. Stop the analyzer before running harvest or coach in another terminal. The dashboard (read-only) can run concurrently without issues.

## License

Private repository. All rights reserved.
