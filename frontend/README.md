# Arrakis Engine — Frontend

Next.js 16 + React 19 + TypeScript + Tailwind CSS + shadcn/ui (Base UI primitives) +
Recharts. The frontend half of [Arrakis Engine](../README.md).

This directory is the dashboard UI. It runs on **port 3000** in dev and calls the
Python API backend on **port 8000** for all data. **Both servers must be running** —
see the main [README](../README.md#two-server-setup--both-must-be-running) for the
two-server setup.

## Quick start

```bash
pnpm install
pnpm dev
# → http://localhost:3000
```

In a second terminal, start the backend:

```bash
cd ..
python main.py dashboard
# → API on http://localhost:8000
```

Then open `http://localhost:3000` in your browser.

## Build

```bash
pnpm build       # production build
pnpm start       # run production build
pnpm lint        # eslint
```

CI builds against Node 24 + pnpm 10. See `.github/workflows/ci.yml`.

## Project structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout (header + nav + theme)
│   ├── providers.tsx           # ThemeProvider + PlayerProvider
│   ├── dashboard/page.tsx      # All-players overview + pipeline control
│   ├── settings/page.tsx       # Players, Stockfish, API keys, coaching
│   └── [player]/               # Player-scoped routes
│       ├── games/              # List + detail + side-by-side compare
│       ├── patterns/           # 16 charts + Self-Analysis section
│       ├── hunt/               # Hunter Mode (opponent prep)
│       └── reports/            # Weekly / monthly coaching reports
├── components/
│   ├── game-detail/            # ChessBoard, MoveControls, eval chart, coaching
│   ├── patterns/               # 16 visualization components + Self-Analysis
│   ├── hunter/                 # OpponentSearch, TargetedPrep
│   ├── settings/               # Players, Analysis, ApiKeys, Coaching sections
│   └── ui/                     # shadcn/ui primitives (Card, Button, Dialog, …)
├── hooks/
│   └── use-chess-navigation.ts # PGN → FENs via chess.js
├── lib/
│   ├── api.ts                  # Typed REST client
│   ├── types.ts                # Shared types (PatternStats, OpponentProfile, …)
│   └── providers.ts            # 8 LLM provider metadata (slug, name, color)
└── public/data/
    ├── openings.json           # 3,690-entry Lichess CC0 opening book
    └── traps.json              # 102-entry curated beginner-trap library
```

## Conventions worth knowing

- **`useChessNavigation` is the canonical move-list source.** Don't regex-parse
  PGN bodies in components — chess.com's annotation braces (`{[%clk 0:09:55]}`)
  poison naive parsing. Consume `nav.moves` from the hook instead. (v1.4.5
  lesson.)
- **Info modals use `createPortal`.** `Card` has `overflow: hidden` which clips
  in-flow tooltips and overlays. Mirror the pattern in `components/patterns/
  danger-zones.tsx`.
- **`DialogClose` from Base UI renders as a `<button>`.** Wrapping a `<Button>`
  inside it produces nested buttons (hydration error). Use the `render` prop
  pattern instead — see `components/settings/player-form-dialog.tsx`. (v1.0.2.)
- **Lichess analysis deep links use FEN, not PGN.** Format:
  `https://lichess.org/analysis/standard/<URL-encoded final FEN>`. Use
  `useChessNavigation`'s `endFen`. (v1.4.5.)

## Notes

This is **not the Next.js you might know from before**. v16 has breaking changes
and conventions that may differ from older training data. When in doubt, read
the relevant guide in `node_modules/next/dist/docs/`. See [`AGENTS.md`](AGENTS.md).
