"use client";

import { cn } from "@/lib/utils";
import type { GameDetail } from "@/lib/types";

interface ComparisonSummaryProps {
  game1: GameDetail;
  game2: GameDetail;
}

const RESULT_COLORS: Record<string, string> = {
  win: "text-green-500",
  loss: "text-red-500",
  draw: "text-yellow-500",
};

function countClassification(
  moves: GameDetail["moves"],
  playerColor: string,
  classification: string
): number {
  return moves.filter(
    (m) => m.side === playerColor && m.classification === classification
  ).length;
}

function computeACPL(moves: GameDetail["moves"], playerColor: string): number | null {
  const playerMoves = moves.filter((m) => m.side === playerColor);
  if (playerMoves.length === 0) return null;
  const EVAL_CAP = 1000;
  let totalLoss = 0;
  for (const m of playerMoves) {
    const before = Math.max(-EVAL_CAP, Math.min(EVAL_CAP, m.eval_before_cp ?? 0));
    const after = Math.max(-EVAL_CAP, Math.min(EVAL_CAP, m.eval_after_cp ?? 0));
    if (playerColor === "white") {
      totalLoss += Math.max(0, before - after);
    } else {
      totalLoss += Math.max(0, after - before);
    }
  }
  return Math.round(totalLoss / playerMoves.length);
}

function getOpening(game: GameDetail): string {
  // Try to extract opening from PGN headers
  const pgn = game.game.pgn || "";
  const openingMatch = pgn.match(/\[Opening\s+"([^"]+)"\]/);
  if (openingMatch) return openingMatch[1];
  const ecoUrlMatch = pgn.match(/\[ECOUrl\s+"[^"]*\/([^"]+)"\]/);
  if (ecoUrlMatch) return ecoUrlMatch[1].replace(/-/g, " ");
  return "Unknown";
}

// Color the better value green, worse red. Lower is better for ACPL/blunders/mistakes.
function CompareCell({
  val1,
  val2,
  lowerIsBetter = false,
  formatFn,
}: {
  val1: number | null;
  val2: number | null;
  lowerIsBetter?: boolean;
  formatFn?: (v: number | null) => string;
}) {
  const fmt = formatFn || ((v: number | null) => (v != null ? String(v) : "\u2014"));
  if (val1 == null || val2 == null || val1 === val2) {
    return (
      <>
        <td className="px-3 py-2 text-center text-sm">{fmt(val1)}</td>
        <td className="px-3 py-2 text-center text-sm">{fmt(val2)}</td>
      </>
    );
  }
  const better1 = lowerIsBetter ? val1 < val2 : val1 > val2;
  return (
    <>
      <td className={cn("px-3 py-2 text-center text-sm font-medium", better1 ? "text-green-500" : "text-red-500")}>
        {fmt(val1)}
      </td>
      <td className={cn("px-3 py-2 text-center text-sm font-medium", !better1 ? "text-green-500" : "text-red-500")}>
        {fmt(val2)}
      </td>
    </>
  );
}

export function ComparisonSummary({ game1, game2 }: ComparisonSummaryProps) {
  const g1 = game1.game;
  const g2 = game2.game;

  const acpl1 = computeACPL(game1.moves, g1.player_color);
  const acpl2 = computeACPL(game2.moves, g2.player_color);

  const blunders1 = countClassification(game1.moves, g1.player_color, "blunder");
  const blunders2 = countClassification(game2.moves, g2.player_color, "blunder");

  const mistakes1 = countClassification(game1.moves, g1.player_color, "mistake");
  const mistakes2 = countClassification(game2.moves, g2.player_color, "mistake");

  const inaccuracies1 = countClassification(game1.moves, g1.player_color, "inaccuracy");
  const inaccuracies2 = countClassification(game2.moves, g2.player_color, "inaccuracy");

  const excellent1 = countClassification(game1.moves, g1.player_color, "excellent");
  const excellent2 = countClassification(game2.moves, g2.player_color, "excellent");

  const opening1 = getOpening(game1);
  const opening2 = getOpening(game2);

  const rows: Array<{
    label: string;
    v1: React.ReactNode;
    v2: React.ReactNode;
  }> = [
    {
      label: "Date",
      v1: g1.date_played || "\u2014",
      v2: g2.date_played || "\u2014",
    },
    {
      label: "Opening",
      v1: <span className="truncate max-w-[150px] inline-block">{opening1}</span>,
      v2: <span className="truncate max-w-[150px] inline-block">{opening2}</span>,
    },
    {
      label: "Color",
      v1: g1.player_color === "white" ? "\u2654 White" : "\u265A Black",
      v2: g2.player_color === "white" ? "\u2654 White" : "\u265A Black",
    },
    {
      label: "Opponent",
      v1: `${g1.opponent_username || "?"} (${g1.opponent_rating || "?"})`,
      v2: `${g2.opponent_username || "?"} (${g2.opponent_rating || "?"})`,
    },
    {
      label: "Result",
      v1: <span className={cn("font-medium", RESULT_COLORS[g1.result])}>{g1.result.toUpperCase()}</span>,
      v2: <span className={cn("font-medium", RESULT_COLORS[g2.result])}>{g2.result.toUpperCase()}</span>,
    },
    {
      label: "Time Control",
      v1: g1.time_class || "\u2014",
      v2: g2.time_class || "\u2014",
    },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="text-left px-3 py-2 text-xs uppercase tracking-wider text-muted-foreground">
              Metric
            </th>
            <th className="text-center px-3 py-2 text-xs uppercase tracking-wider text-muted-foreground">
              Game 1
            </th>
            <th className="text-center px-3 py-2 text-xs uppercase tracking-wider text-muted-foreground">
              Game 2
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-border/50">
              <td className="px-3 py-2 text-muted-foreground text-xs font-medium">
                {row.label}
              </td>
              <td className="px-3 py-2 text-center text-sm">{row.v1}</td>
              <td className="px-3 py-2 text-center text-sm">{row.v2}</td>
            </tr>
          ))}
          {/* Numeric comparison rows */}
          <tr className="border-b border-border/50">
            <td className="px-3 py-2 text-muted-foreground text-xs font-medium">ACPL</td>
            <CompareCell val1={acpl1} val2={acpl2} lowerIsBetter />
          </tr>
          <tr className="border-b border-border/50">
            <td className="px-3 py-2 text-muted-foreground text-xs font-medium">Excellent Moves</td>
            <CompareCell val1={excellent1} val2={excellent2} />
          </tr>
          <tr className="border-b border-border/50">
            <td className="px-3 py-2 text-muted-foreground text-xs font-medium">Blunders</td>
            <CompareCell val1={blunders1} val2={blunders2} lowerIsBetter />
          </tr>
          <tr className="border-b border-border/50">
            <td className="px-3 py-2 text-muted-foreground text-xs font-medium">Mistakes</td>
            <CompareCell val1={mistakes1} val2={mistakes2} lowerIsBetter />
          </tr>
          <tr className="border-b border-border/50">
            <td className="px-3 py-2 text-muted-foreground text-xs font-medium">Inaccuracies</td>
            <CompareCell val1={inaccuracies1} val2={inaccuracies2} lowerIsBetter />
          </tr>
        </tbody>
      </table>
    </div>
  );
}
