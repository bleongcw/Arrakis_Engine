# Arrakis Engine Roadmap

*Updated 2026-05-18 — current release v1.6.0*

This is the public-facing roadmap. The full release history is in
[CHANGELOG.md](CHANGELOG.md); architectural details are in
[docs/architecture.md](docs/architecture.md).

---

## What's shipped

### Core platform (v1.0.0, 2026-04-06)
First public open-source release under AGPL-3.0. 8 LLM providers, 16 pattern
visualizations, full pipeline (harvest → analyze → patterns → coach), settings UI,
240 tests.

### Coaching depth (v1.3.0, 2026-04-26)
Configurable coaching history injection (default 5, range 1–20) so the coach
adapts depth based on the player's history. Per-game token cost documented per
provider.

### Self-Analysis on the Patterns page (v1.4.0, 2026-04-26)
- **Fix Your Openings** — losses by opening, paired with strengths, split by
  White/Black with study links
- **Trap Patterns** — recognizes ~100 well-known named opening traps (Stafford,
  Fried Liver, Englund, Halloween, Cochrane, Wayward Queen Attack, Latvian,
  Damiano, Traxler, etc.) using the Lichess CC0 chess-openings dataset.
  "Your Arsenal" (winning traps) and "You Fall For" (losing traps) panels.
- **Trap row click-to-expand (v1.4.3)** — mini chess board with step-through
  controls, links to your actual games, and "Study on Lichess" deep links.

### Hunter Mode — opponent prep (v1.4.1+)
- **Backend (v1.4.1)** — fetch an opponent's recent public games from chess.com
  or lichess (no Stockfish, kept fast). REST API at `/api/hunt/profile`.
- **UI (v1.4.2)** — `/[player]/hunt` page with opponent search and Their
  Weaknesses / Their Strengths layout.
- **Click-to-expand opening rows (v1.4.4)** — mini-board, "Game N of 5" flip
  controls, annotated move list with deviation from book theory highlighted in
  orange.
- **Local accumulating PGN cache (v1.4.4)** — opponent games persist locally
  across refreshes; sliding window default 6 months; optional hard cap.

### Single-command serve (v1.5.0, 2026-04-26)
- **`python main.py serve`** — one command launches both backend (port 8000)
  AND Next.js frontend (port 3000) together. Spawns `pnpm dev` in its own
  process group, waits for the Next.js ready line, prints a unified banner
  with both URLs, and Ctrl+C stops both servers cleanly (SIGTERM → 5s grace
  → SIGKILL on the whole process group).
- Frontend stdout is line-prefixed with `[frontend]` so compile errors stay
  legible inline.
- Existing `dashboard` command kept (API-only mode for custom frontends,
  debugging, scripted pipelines), now with a hint pointing at `serve`.
- Optional flags: `--port`, `--frontend-port`, `--install`.
- New `src/dev_runner.py` module + 30 tests covering the orchestration.

### Frontend test infrastructure (v1.6.0, 2026-05-18)
- **Vitest harness** — jsdom + Testing Library + `@testing-library/jest-dom`
  matchers wired into the `frontend/` workspace. **66 frontend tests
  across 7 files**, sub-second full run.
- **Chess helper sweep** — `parseMoveText`, `lichessAnalysisUrl`, and the
  opening-matching helpers (`normalizeOpeningName`, `findCanonicalLine`,
  `findDeviationIndex`, `LibraryOpening`) extracted from three components
  into `frontend/lib/chess/`. Three component callers (`targeted-prep`,
  `opening-explorer`, `you-fall-for`) now import from the shared module.
- **v1.4.5 regression locks** at three layers:
  - Helper-level: `lichess.test.ts` asserts the
    `/analysis/standard/{FEN}` URL form and forbids the `?pgn=` form.
  - Hook-level: `use-chess-navigation.test.ts` asserts chess.com
    `{[%clk ...]}` annotations never leak into the moves array.
  - Component-level: all three component tests assert the same Lichess
    URL form on the actual rendered `<a>`.
- **CI gate** — `.github/workflows/ci.yml` runs `pnpm test:run` between
  install and build in the frontend job so regressions fail fast.

### Polish & bug fixes
- v1.0.1, v1.0.2 — UI fixes (opening explorer, dialog hydration)
- v1.3.1 — silenced client-disconnect log noise
- v1.3.2 — clearer two-server startup messaging
- v1.4.5 — Hunt Mode bug-fix batch (chess.com clock annotations broke move list,
  canonical-line lookup missed punctuation differences, autofill suppression on
  opponent input)

---

## Reasoning models requirement

Arrakis Engine requires **reasoning models** for coaching analysis. Chess coaching
demands multi-step reasoning: evaluating positions, understanding strategic themes,
connecting patterns across games, and generating age-appropriate explanations.
Non-reasoning models produce shallow, generic feedback.

### Supported providers

| Provider | Model | Type | Status |
|---|---|---|---|
| Anthropic | `claude-opus-4-7` | Cloud / Reasoning | Active |
| OpenAI | `gpt-5.5-pro-2026-04-23` | Cloud / Reasoning | Active |
| Google | `gemini-2.5-pro` | Cloud / Reasoning | Active |
| xAI | `grok-3` | Cloud / Reasoning | Active |
| Mistral | `mistral-medium-latest` | Cloud / Reasoning | Active |
| DeepSeek | `deepseek-reasoner` | Cloud / Reasoning | Active |
| Alibaba | `qwen3-235b-a22b` | Cloud / Reasoning | Active |
| Ollama | `deepseek-r1:8b` | Local / Reasoning | Active |

All providers are available in the CLI (`--provider`), the dashboard pipeline
panel, per-game coaching buttons, and the Settings page. Adding a new provider
is a registration in `src/llm_providers.py` plus a metadata entry in
`frontend/lib/providers.ts`.

### Why non-reasoning models don't work

Models without chain-of-thought (standard chat models, small instruction-tuned
models) fail at chess coaching because they:

- Miss tactical sequences requiring look-ahead
- Generate generic advice not grounded in the actual position
- Cannot maintain coherent analysis across 30+ move games
- Produce inconsistent JSON structure

This is a hard requirement enforced by the provider abstraction, not a preference.

---

## Ollama / local models

Ollama is fully integrated as a local provider. It uses the OpenAI-compatible
API endpoint at `http://localhost:11434/v1` with no API key required.

**Default model:** `deepseek-r1:8b` (lightweight, ~5 GB RAM, good for testing)

### Recommended local models

| Model | Size | RAM | Quality | Speed (M3 Max) |
|---|---|---|---|---|
| `deepseek-r1:8b` | 8B | ~5 GB | Good for testing | ~30 tok/s |
| `deepseek-r1:14b` | 14B | ~9 GB | Moderate coaching | ~20 tok/s |
| `deepseek-r1:32b` | 32B | ~20 GB | Strong coaching | ~15 tok/s |
| `qwen3:8b` | 8B | ~5 GB | Good JSON reliability | ~30 tok/s |

### Local-model caveats

- **Quality gap**: Open-source reasoning models may not match frontier model depth,
  especially for nuanced coaching tone adjustments
- **Speed**: ~60-90 s per game coaching with 32B models on M3 Max
- **Memory**: 32B models need ~20 GB RAM
- **JSON reliability**: Smaller models may need retry logic for structured output
- **Coaching history depth**: With Ollama 8B, keep `coaching_history_count: 5`
  (default) — higher values may overflow the context window

---

## Where things are headed

### Near-term polish

Every release in the v1.4.x line has been bug-fix-driven. The rhythm is:
ship a feature → use it for a few hours → batch the bugs → ship a `.x` with
the fixes. Expect more of this on Hunter Mode + Self-Analysis as they get
real-world miles.

### Coaching depth experiments

- **Coaching feedback loop** — let the user mark a brief as "useful" / "not
  useful" per game; feed that signal into prompt selection or future tone.
- **Per-player tone preferences** — different siblings have different
  communication styles; let coaching tone be set per player, not per session.
- **Recurring weakness escalation** — when a pattern persists across N games,
  surface it more prominently rather than repeating the same advice.

### Pattern depth

- **Time-series view** of any pattern — generalize the trend pattern from ACPL
  + rating progression to all 20 metrics.
- **Position-type tagging** — classify positions by structural feature
  (isolated pawn, opposite-side castling) so coaching can reference them.
- **Opening prep mode** — instead of just analyzing what was played, suggest
  what to study next based on opening repertoire gaps.

### Hunter Mode extensions

- **Trap detection on opponent games** — apply the v1.4.0 trap library to the
  opponent's accumulated games, surface "their favourite trap to play" /
  "their favourite trap to fall for".
- **Tournament prep mode** — multi-opponent batch profiles for an upcoming
  event with combined target-opening analysis.

### Frontend polish

- **Mobile** — core pages are mobile-ready as of v1.18.2 (viewport meta tag
  added; breakpoints fire at 1:1 scale). Dense chart grids (Patterns,
  Hunter Mode) still squeeze on narrow screens and would benefit from a
  dedicated mobile-layout pass — single-column stacking, larger tap targets.
- **Onboarding** — currently a chess parent has to know to add a player, set
  up an API key, and run the pipeline. A guided first-run flow would help.

### Coach-facing surfaces (longer-term)

- **Coach view** — UI optimized for the coach (technical, batch view across
  students)
- **Shareable game review links** — read-only public link for a coach to
  review a kid's game without their own instance

---

## Things explicitly NOT planned

- **Cloud / SaaS hosted version** — Arrakis is intentionally local. Privacy
  for kids' game data is the whole point.
- **Built-in puzzle trainer** — Lichess and chess.com already do this well.
- **Live game integration** — analysis is post-hoc by design.
- **Native mobile app** — responsive web is sufficient.

---

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and the test
contract. The pattern computation pipeline (`src/patterns.py`) is the easiest
place to add a new metric — see "Where to look when…" in
[docs/architecture.md](docs/architecture.md).
