"use client";

import { cn } from "@/lib/utils";
import type { MoveAnalysis } from "@/lib/types";

const CLASSIFICATION_COLORS: Record<string, string> = {
  excellent: "bg-green-500/20 text-green-400",
  good: "bg-blue-500/20 text-blue-400",
  inaccuracy: "bg-yellow-500/20 text-yellow-400",
  mistake: "bg-orange-500/20 text-orange-400",
  blunder: "bg-red-500/20 text-red-400",
};

interface MoveListProps {
  moves: MoveAnalysis[];
  playerColor: "white" | "black";
  currentMoveIndex: number;
  onMoveClick: (index: number) => void;
}

export function MoveList({ moves, playerColor, currentMoveIndex, onMoveClick }: MoveListProps) {
  // Group moves into pairs (white + black per move number)
  const moveNumbers = [...new Set(moves.map((m) => m.move_number))];

  return (
    <div className="max-h-[400px] overflow-y-auto space-y-0.5 text-sm">
      {moveNumbers.map((num) => {
        const whiteMv = moves.find((m) => m.move_number === num && m.side === "white");
        const blackMv = moves.find((m) => m.move_number === num && m.side === "black");
        const whiteIdx = whiteMv ? moves.indexOf(whiteMv) : -1;
        const blackIdx = blackMv ? moves.indexOf(blackMv) : -1;

        return (
          <div key={num} className="flex gap-1">
            <span className="w-8 text-right text-muted-foreground text-xs pt-1">
              {num}.
            </span>
            {whiteMv && (
              <button
                className={cn(
                  "px-1.5 py-0.5 rounded text-xs font-mono cursor-pointer transition-colors",
                  whiteIdx === currentMoveIndex && "ring-2 ring-[#1e40af]",
                  whiteMv.classification
                    ? CLASSIFICATION_COLORS[whiteMv.classification]
                    : "hover:bg-muted"
                )}
                onClick={() => onMoveClick(whiteIdx)}
              >
                {whiteMv.move_played}
              </button>
            )}
            {blackMv && (
              <button
                className={cn(
                  "px-1.5 py-0.5 rounded text-xs font-mono cursor-pointer transition-colors",
                  blackIdx === currentMoveIndex && "ring-2 ring-[#1e40af]",
                  blackMv.classification
                    ? CLASSIFICATION_COLORS[blackMv.classification]
                    : "hover:bg-muted"
                )}
                onClick={() => onMoveClick(blackIdx)}
              >
                {blackMv.move_played}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
