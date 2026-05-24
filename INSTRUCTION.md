# Arrakis Engine — Installation Guide for Chess Parents

*A friendly walkthrough for getting Arrakis Engine running on your
machine. Aimed at parents and coaches who aren't full-time developers
but can follow terminal instructions.*

If you'd rather read the developer-flavoured version, see
[README.md](README.md) (which has the same install steps plus a lot of
architecture context). This file is the **simpler path**: just install,
just first-run, just what to do when something doesn't work.

---

## What you'll have at the end

After ~30 minutes, running on your own laptop:

1. A local web dashboard at `http://localhost:3000` showing your kid's
   chess games, Stockfish analysis, and AI-generated coaching after
   every game.
2. A pattern-tracking page showing trends over weeks — *"his middlegame
   ACPL has climbed 12 points this month, here's why"* — not just
   single-game summaries.
3. A coach who writes a short personal letter to your child after
   every game, in age-appropriate language, that remembers what was
   said last week and builds on it.

All data stays on your machine. No cloud storage, no telemetry, no
chess.com or Lichess account credentials needed (just usernames).

---

## Before you start — what you need

| Thing | Why | Where |
|---|---|---|
| **macOS or Linux laptop** | Tested on macOS (Apple Silicon). Linux works too. Windows will need WSL2. | — |
| **Python 3.11 or 3.12** | The backend is Python. | `python3 --version` to check; install via `brew install python@3.12` or [python.org](https://python.org) |
| **Stockfish 16+** | The chess engine that does the analysis. | `brew install stockfish` (see Step 2 below for a faster build) |
| **Node.js 24 + pnpm 10** | The web dashboard is Next.js. | `brew install node`, then `corepack enable && corepack prepare pnpm@10 --activate` |
| **An OpenAI API key** | For the AI coaching layer. ChatGPT (GPT-5.5 Pro) is the recommended default — strong reasoning, reliable JSON output. | [platform.openai.com](https://platform.openai.com) → API Keys. Budget ~$5–10/month for a kid playing 5–10 rated games per week. |
| **A chess.com or Lichess username** | What gets analyzed. You don't need passwords — only public-game data is pulled. | Your kid's existing account |

Other LLM providers (Claude, Gemini, Grok, Mistral, DeepSeek, Qwen,
Ollama for free local coaching) are supported — see "Swapping
providers later" at the bottom. But for first install, **ChatGPT keeps
it simple**.

---

## Step 1 — Get the code

```bash
git clone git@github.com:bleongcw/Arrakis_Engine.git
cd Arrakis_Engine
```

If you don't have `git`: install Xcode Command Line Tools (`xcode-select
--install` on macOS), or download the latest release zip from the
[releases page](https://github.com/bleongcw/Arrakis_Engine/releases) and
unzip it.

---

## Step 2 — Install Stockfish

The chess engine is a separate program from Arrakis itself.

**Easy option — Homebrew:**

```bash
brew install stockfish
```

After install, verify with:

```bash
stockfish <<< "uci" | head -1
# Should print: Stockfish 18 by the Stockfish developers
```

**Faster option — build from source (~2x faster on Apple Silicon):**

```bash
git clone https://github.com/official-stockfish/Stockfish.git
cd Stockfish/src
make -j profile-build COMP=clang ARCH=apple-silicon
sudo cp stockfish /usr/local/bin/stockfish
cd ../..
rm -rf Stockfish
```

The Homebrew path is fine to start. If you analyze hundreds of games
and want it faster, come back and build from source.

---

## Step 3 — Set up Python

From inside the `Arrakis_Engine` folder:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

This creates a `venv/` folder (gitignored) and installs everything
Arrakis needs into it — Stockfish wrapper, OpenAI SDK, web server,
etc. **You'll need to `source venv/bin/activate` every time you open a
new terminal to use Arrakis.**

---

## Step 4 — Get your OpenAI API key

1. Go to [platform.openai.com](https://platform.openai.com).
2. Create an account if you don't have one.
3. Add a payment method (required to use the API, even on the free
   tier).
4. Go to **API Keys** in the sidebar → **Create new secret key**.
5. Copy the key — it starts with `sk-...`. You only see it once.
6. **Recommended: set a monthly spending limit** in Billing → Usage
   limits. For a chess kid playing 5–10 games per week, $10/month is
   plenty.

Now create a `.env` file in the Arrakis_Engine folder:

```bash
# .env — never committed to git
ARRAKIS_OPENAI_API_KEY=sk-your-key-here
```

That's the only key you need for the recommended setup.

---

## Step 5 — Create your config

Copy the example config and edit it:

```bash
cp config.yaml.example config.yaml
```

Open `config.yaml` in any text editor. The two sections you need to
change are `players` and `coaching`:

```yaml
players:
  - username: your_kid_chesscom_username   # required
    lichess_username: ""                   # optional, leave blank if no Lichess account
    display_name: Your Kid's Name          # what shows in the dashboard
    age: 9                                 # age in years
    rating: 1100                           # current rating (rough estimate is fine)

coaching:
  default_provider: openai                  # ← pick OpenAI (ChatGPT) as default
  openai_model: gpt-5.5-pro-2026-04-23      # recommended reasoning model
  coaching_history_count: 5                 # how many recent games the coach "remembers"
  coaching_trajectory_enabled: true         # v1.8.0 — let the coach see player's 30-day trends
```

You can add more kids — just add another `- username: ...` block under
`players`.

Leave the other sections (`stockfish`, `analysis`, `database`,
`schedule`) at their defaults. You can tune them later.

---

## Step 6 — Set up the web dashboard

The dashboard is a Next.js app in the `frontend/` folder.

```bash
cd frontend
corepack pnpm install
cd ..
```

(If `corepack` isn't found: `npm install -g corepack && corepack
enable`.)

This downloads the frontend dependencies — takes 1–2 minutes the first
time. Subsequent runs are fast.

---

## Step 7 — First run

From the Arrakis_Engine folder, with the virtualenv activated:

```bash
python main.py serve
```

You'll see a banner like:

```
🏰 Arrakis Engine running

   📡 Frontend UI:    http://localhost:3000   ← open this
   🔌 API backend:    http://localhost:8000
   📊 Live data from: data/chess_coach.db

Press Ctrl+C to stop both servers.
```

Open **http://localhost:3000** in your browser. You should see the
dashboard with your kid's player card (no games yet — that's next).

---

## Step 8 — Pull, analyze, and coach your first batch

From the dashboard, you can click "Run Full Pipeline" on the player
card. Or from a new terminal (leave `serve` running):

```bash
source venv/bin/activate    # remember: every new terminal
python main.py run-all
```

This runs four steps in order:

1. **Harvest** — pulls the last 6 months of games from chess.com /
   Lichess. (~10 seconds for ~50 games.)
2. **Analyze** — runs Stockfish on every move. **This is the slow
   step.** ~30–60 seconds per game on Apple Silicon. A 50-game batch
   takes ~30–60 minutes.
3. **Patterns** — aggregates trends across all analyzed games.
   (Pure Python, ~5 seconds.)
4. **Coach** — calls OpenAI to generate the per-game coaching brief
   for any uncoached games. ~30 seconds per game. **This is where the
   API charges show up.**

You can leave it running and check back. The dashboard updates live.

---

## Step 9 — What to look at

Once the pipeline finishes, open the dashboard:

- **`/dashboard`** — player cards, pipeline status, quick stats.
- **`/<your_kid>/games`** — list of every game with result + analysis
  state. Click any game to see the board, eval graph, and the coach's
  feedback.
- **`/<your_kid>/patterns`** — the trend page. ACPL over time, weakest
  phase (opening / middlegame / endgame), opening repertoire, tactical
  miss rate, and an LLM-generated coaching summary you can regenerate
  with the "Refresh AI Summary" button.

The single most useful page after a few games is **the per-game
coaching panel** — scroll past the board, you'll see "Game Story",
"Key Lesson", "Practice Focus", and "Feedback to the Player". The
last one is the personal letter to your kid.

---

## Daily / weekly usage

After the first install, the typical loop is just:

```bash
cd Arrakis_Engine
source venv/bin/activate
python main.py serve
```

Open the dashboard, click "Run Full Pipeline" on any player card to
refresh games. Or run from CLI without the dashboard:

```bash
python main.py run-all
```

If you want it to run automatically every 6 hours, set
`schedule.enabled: true` in `config.yaml` and add `--background` to
the serve command. The scheduler will harvest + analyze + coach in the
background.

---

## Troubleshooting

### "stockfish: command not found"
Run `brew install stockfish`, then edit `config.yaml` and set
`stockfish.path` to the output of `which stockfish`.

### "OPENAI_API_KEY not set" or 401 from OpenAI
- Confirm the `.env` file uses `ARRAKIS_OPENAI_API_KEY=...` (note the
  `ARRAKIS_` prefix — this avoids collisions with other tools).
- Restart `python main.py serve` after editing `.env` — environment
  variables are read at startup.

### Coaching fails with a 429 / rate limit
You're hitting the OpenAI rate limit. Arrakis already backs off
automatically (30s → 60s → 120s) and retries up to 3 times. If it
still fails:
- Check your OpenAI Usage page — you may have hit your monthly limit.
- Lower `coaching_history_count` from 10 to 5 in `config.yaml` to
  shrink each prompt.
- For free local coaching, see "Swapping providers" below.

### Frontend won't start: "pnpm: command not found"
```bash
npm install -g corepack
corepack enable
corepack prepare pnpm@10 --activate
```

### `python main.py serve` says "port 8000 already in use"
Something else is using that port. Either stop the other thing, or
run `python main.py serve --port 8001`.

### The dashboard shows "No games analyzed yet"
You haven't run the pipeline. Click "Run Full Pipeline" on the player
card, or run `python main.py run-all` from the terminal.

### The "Feedback to the Player" reads generically and doesn't reference past games
Make sure `coaching_history_count` is ≥ 5 and
`coaching_trajectory_enabled: true` in `config.yaml`. The trajectory
injection (v1.8.0+) is what makes feedback aware of your kid's measured
30-day trends. After updating the config, re-coach a recent game from
the per-game coaching panel — the small "📚 N recent games in
context" and "📊 30-day trajectory (Nd old)" badges next to "Game
Story" tell you whether it actually went through.

---

## Swapping providers later

ChatGPT is the recommended starter, but Arrakis supports 8 providers.
Edit `config.yaml`:

```yaml
coaching:
  default_provider: claude       # or gemini / grok / mistral / deepseek / qwen / ollama
```

Add the matching API key to `.env`:

```bash
ARRAKIS_ANTHROPIC_API_KEY=sk-ant-...
ARRAKIS_GOOGLE_API_KEY=...
# etc — see config.yaml.example for the full list
```

For **free local coaching** with no API key:

```bash
brew install ollama
ollama pull deepseek-r1:8b
ollama serve   # leave this running in another terminal
```

```yaml
coaching:
  default_provider: ollama
  ollama_model: deepseek-r1:8b
  # Trim trajectory injection to save context on small local models:
  coaching_trajectory_enabled: false   # optional, set true if you have ≥ 14B
```

The coaching quality drops noticeably on 8B local models compared to
cloud APIs, but it's free and your data never leaves the machine.

---

## Upgrading

```bash
cd Arrakis_Engine
git pull
source venv/bin/activate
pip install -r requirements.txt    # may add new deps
cd frontend && corepack pnpm install && cd ..
```

After upgrading from v1.7.0 → v1.7.1 or later, run
`python main.py backfill-acpl --force` once to refresh historical ACPL
scores with the mate-transition fix. After v1.7.4 also re-run
`python main.py patterns` to refresh aggregations across all the
widgets that previously used the broken inline formula.

After v1.8.0, the per-game coaching prompt automatically includes the
player's 30-day trajectory snapshot. No migration needed — newly
coached games pick it up automatically; existing coached briefs are
unchanged unless you re-coach them.

See [CHANGELOG.md](CHANGELOG.md) for the full release history.

---

## Cost expectations

For a single kid playing 5–10 rated games per week, coached with
GPT-5.5 Pro:

| Step | Frequency | Cost |
|---|---|---|
| Harvesting games | Per pipeline run | Free (public chess.com / Lichess API) |
| Stockfish analysis | Per game | Free (local) |
| OpenAI coaching | Per game | ~$0.05–0.15 |
| Trend summary | On demand | ~$0.10 |
| **Monthly total** | ~30 games | **~$2–5** |

For a family with three kids playing across multiple platforms,
budget $10–15/month. Setting a hard spending limit in your OpenAI
account is recommended either way.

---

## Where to get help

- **CHANGELOG.md** — what changed between versions (very useful when
  something stops working after `git pull`)
- **README.md** — developer-flavoured overview with architecture
  context
- **docs/architecture.md** — how the pieces fit together internally
- **GitHub Issues** —
  [github.com/bleongcw/Arrakis_Engine/issues](https://github.com/bleongcw/Arrakis_Engine/issues)

Happy coaching. ♟
