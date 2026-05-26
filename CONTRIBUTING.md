# Contributing to ArrakisEngine

Thank you for your interest in contributing to ArrakisEngine! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ArrakisEngine.git
   cd ArrakisEngine
   ```
3. **Set up** the development environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   pip install -r requirements-dev.txt
   cd frontend && pnpm install && cd ..
   ```
4. **Copy** the example config:
   ```bash
   cp config.yaml.example config.yaml
   # Edit config.yaml with your Stockfish path and player details
   ```
5. **Create a branch** for your feature or fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Running Tests

**428 tests total**: 362 backend (pytest, three tiers via `pyproject.toml`
markers) + 66 frontend (Vitest, v1.6.0+).

**Backend (pytest):**

```bash
# Default: ~318 unit tests, no external deps (~14s)
pytest

# Specific file
pytest tests/test_models.py -v

# Tier 2: integration tests requiring Stockfish
pytest -m integration

# Tier 3: live tests requiring at least one LLM API key (~$0.05/run)
pytest -m live

# Full pipeline E2E (Stockfish + LLM)
pytest -m "integration and live"

# Everything across all tiers (~5 min)
pytest --override-ini "addopts="
```

When adding a test that mocks a function imported locally inside another
function, **patch the source module, not the consumer** — e.g.
`@patch("src.coach.coach_pending")`, not the calling module's reference.

**Frontend (Vitest, v1.6.0+):**

```bash
cd frontend
pnpm test:run       # single-shot — what CI runs
pnpm test           # watch mode while developing
```

66 tests covering the shared chess helpers (`lib/chess/`), the
`use-chess-navigation` hook (including the v1.4.5 clock-comment leak
guard), and three component smoke suites. Sub-second full run. CI runs
`pnpm test:run` automatically between install and build.

### Running the App

**Single-command (recommended for end-user-style testing):**

```bash
python main.py serve
```

This spawns both backend (port 8000) and frontend (port 3000) together,
prints a unified banner with both URLs, and Ctrl+C stops both cleanly. The
frontend's stdout is prefixed with `[frontend]` so Next.js compile errors
remain readable inline with backend logs. Pass `--install` if you haven't
run `pnpm install` yet.

**Manual two-terminal mode** is useful when developing — independent terminals
keep each server's hot-reload output visually separate:

```bash
# Terminal 1: Python API backend on port 8000
python main.py dashboard

# Terminal 2: Next.js frontend on port 3000
cd frontend && pnpm dev
```

Open `http://localhost:3000` in your browser. The frontend calls back to the
backend on port 8000 for all data.

### Frontend build check

Before pushing frontend changes:

```bash
cd frontend
pnpm test:run    # v1.6.0+ — Vitest gate; CI runs this before build
pnpm build
```

CI runs this on Node 24 + pnpm 10 + Python 3.11/3.12.

### Code Style

- Python: Follow PEP 8 conventions
- TypeScript/React: Follow existing patterns in the codebase
- Use meaningful variable names and add docstrings to functions
- Keep functions focused and reasonably sized

## Submitting Changes

1. **Commit** your changes with clear, descriptive messages
2. **Push** to your fork
3. **Open a Pull Request** against the `main` branch
4. **Describe** what your PR does and why

### PR Guidelines

- Keep PRs focused on a single feature or fix
- Include tests for new functionality
- Ensure all existing tests pass
- Update documentation if needed

## Contributor License Agreement (CLA)

By submitting a pull request, you agree to the following:

- You grant the project maintainer (Bernard Leong) a perpetual, worldwide, non-exclusive, royalty-free, irrevocable license to use, modify, and distribute your contributions under any license.
- This is necessary because ArrakisEngine uses a dual-licensing model (AGPL-3.0 open source + commercial license). The CLA ensures the maintainer can continue to offer both options.
- You confirm that you have the right to submit the contribution and that it does not violate any third-party rights.

## Dual-licensing model

The ArrakisEngine codebase is **dual-licensed**:

1. **Public license — AGPL-3.0.** This is what you and any other user receives when you clone the repository. Under AGPL-3.0, you are free to use, modify, and redistribute the code, but if you provide a modified version as a hosted service over a network, you must release the source code of your modifications under AGPL-3.0 as well. This is the strongest copyleft license that is still OSI-approved.

2. **Commercial license — held by the maintainer.** The maintainer (Bernard Leong) is the sole copyright holder of all original code in the repository, and via the CLA above, also holds a relicensing grant for all contributed code. This means the maintainer reserves the right to offer the same codebase under a separate commercial license — for example, in a closed-source commercial product (Atreides, the planned commercial version) — without releasing that product's source code.

Practically, this means contributions made under the CLA may be incorporated into the commercial version of ArrakisEngine without a corresponding source release of that commercial product. Your contributions to the open-source project remain under AGPL-3.0 for everyone else who uses the open-source codebase. The commercial relicensing right is a one-way grant FROM contributors TO the maintainer; it doesn't change the terms under which the open-source version is distributed.

If you have questions about how a specific contribution would be treated under the dual-licensing model — or you'd prefer to contribute only under AGPL-3.0 with no commercial relicensing — open a discussion before submitting the PR.

### Features reserved for the commercial version (Atreides)

Some features are planned for the **commercial Atreides version only** and will not land in the open-source AGPL-3.0 repository. As of v1.12.0 this list includes:

- **Tournament-game support via photo upload + OCR.** Take a snapshot of a hand-written tournament scoresheet, extract the moves via a vision LLM, render the game on an interactive chessboard, and (commercial flavor) feed the game through the full Stockfish analyzer + LLM coach + trajectory pipeline alongside chess.com and lichess games.

These features rely on infrastructure (Vision-LLM API budget, OCR error-correction UX, multi-image stitching for long games, possibly cloud-side image handling) that doesn't fit the single-user local-first AGPL release. The public roadmap continues with v1.13.0+ features focused on the Journal, coaching prompt quality, and existing analyzer/coach improvements; tournament support lives elsewhere.

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests
- Include steps to reproduce for bugs
- Include your OS, Python version, and Stockfish version

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating.

## Questions?

Open a GitHub Discussion or Issue if you have questions about contributing.
