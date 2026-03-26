"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { MoveAnalysis } from "@/lib/types";

interface MoveQualitySummaryProps {
  moves: MoveAnalysis[];
  playerColor: "white" | "black";
  playerName: string;
}

const CLASSIFICATIONS = ["excellent", "good", "inaccuracy", "mistake", "blunder"] as const;

const CLASS_CONFIG: Record<string, { icon: string; color: string; barColor: string; label: string }> = {
  excellent: { icon: "\u2728", color: "text-green-500", barColor: "bg-green-500", label: "EXCELLENT" },
  good: { icon: "\uD83D\uDC4D", color: "text-blue-500", barColor: "bg-blue-500", label: "GOOD" },
  inaccuracy: { icon: "\u26A0\uFE0F", color: "text-yellow-500", barColor: "bg-yellow-500", label: "INACCURACY" },
  mistake: { icon: "\u274C", color: "text-orange-500", barColor: "bg-orange-500", label: "MISTAKE" },
  blunder: { icon: "\uD83D\uDCA5", color: "text-red-500", barColor: "bg-red-500", label: "BLUNDER" },
};

export function MoveQualitySummary({ moves, playerColor, playerName }: MoveQualitySummaryProps) {
  const playerMoves = moves.filter((m) => m.side === playerColor);
  const opponentMoves = moves.filter((m) => m.side !== playerColor);

  const count = (list: MoveAnalysis[], cls: string) =>
    list.filter((m) => m.classification === cls).length;

  const playerTotal = playerMoves.length;
  const opponentTotal = opponentMoves.length;
  const maxCount = Math.max(
    ...CLASSIFICATIONS.map((c) => Math.max(count(playerMoves, c), count(opponentMoves, c))),
    1
  );

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Move Quality Summary</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Header row */}
        <div className="grid grid-cols-[100px_repeat(5,1fr)_60px] gap-1 text-xs font-semibold mb-2 text-center">
          <div />
          {CLASSIFICATIONS.map((c) => (
            <div key={c} className={CLASS_CONFIG[c].color}>
              {CLASS_CONFIG[c].icon} {CLASS_CONFIG[c].label}
            </div>
          ))}
          <div className="text-muted-foreground">TOTAL</div>
        </div>

        {/* Player row */}
        <div className="grid grid-cols-[100px_repeat(5,1fr)_60px] gap-1 items-center mb-1">
          <div className="text-xs font-medium truncate">
            You ({playerColor})
          </div>
          {CLASSIFICATIONS.map((c) => {
            const n = count(playerMoves, c);
            const pct = maxCount > 0 ? (n / maxCount) * 100 : 0;
            return (
              <div key={c} className="text-center">
                <div className="text-sm font-bold">{n}</div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className={`h-full rounded-full ${CLASS_CONFIG[c].barColor}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
          <div className="text-center text-sm font-bold">{playerTotal}</div>
        </div>

        {/* Opponent row */}
        <div className="grid grid-cols-[100px_repeat(5,1fr)_60px] gap-1 items-center mb-3">
          <div className="text-xs font-medium text-muted-foreground truncate">Opponent</div>
          {CLASSIFICATIONS.map((c) => {
            const n = count(opponentMoves, c);
            const pct = maxCount > 0 ? (n / maxCount) * 100 : 0;
            return (
              <div key={c} className="text-center">
                <div className="text-sm font-bold text-muted-foreground">{n}</div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className={`h-full rounded-full ${CLASS_CONFIG[c].barColor} opacity-50`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
          <div className="text-center text-sm font-bold text-muted-foreground">{opponentTotal}</div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground border-t pt-2">
          <span><span className="inline-block w-3 h-3 rounded bg-green-500 mr-1" />Excellent (&lt;30cp)</span>
          <span><span className="inline-block w-3 h-3 rounded bg-blue-500 mr-1" />Good (&lt;50cp)</span>
          <span><span className="inline-block w-3 h-3 rounded bg-yellow-500 mr-1" />Inaccuracy (&lt;100cp)</span>
          <span><span className="inline-block w-3 h-3 rounded bg-orange-500 mr-1" />Mistake (&lt;300cp)</span>
          <span><span className="inline-block w-3 h-3 rounded bg-red-500 mr-1" />Blunder (300+cp)</span>
        </div>
      </CardContent>
    </Card>
  );
}
