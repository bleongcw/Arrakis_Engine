"use client";

import Link from "next/link";
import { useState } from "react";
import { ChessBoard } from "@/components/game-detail/chess-board";
import { MoveControls } from "@/components/game-detail/move-controls";
import { useChessNavigation } from "@/hooks/use-chess-navigation";
import { Badge } from "@/components/ui/badge";
import type { OpeningGameEntry } from "@/lib/types";

interface OpeningExplorerProps {
  openingName: string;
  openingMoves: string;
  gameList: OpeningGameEntry[];
  playerUsername: string;
  boardOrientation: "white" | "black";
}

const RESULT_BADGE: Record<string, { variant: "default" | "destructive" | "secondary"; label: string }> = {
  win: { variant: "default", label: "W" },
  loss: { variant: "destructive", label: "L" },
  draw: { variant: "secondary", label: "D" },
};

export function OpeningExplorer({
  openingName,
  openingMoves,
  gameList,
  playerUsername,
  boardOrientation,
}: OpeningExplorerProps) {
  const nav = useChessNavigation(openingMoves, boardOrientation);
  const [showAll, setShowAll] = useState(false);

  const visibleGames = showAll ? gameList : gameList.slice(0, 5);
  const hasMore = gameList.length > 5;

  return (
    <div className="border rounded-lg bg-muted/30 p-4">
      <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-4">
        {/* Left: Board + controls */}
        <div>
          <ChessBoard
            position={nav.currentFen}
            orientation={nav.boardOrientation}
            boardWidth={280}
          />
          <MoveControls
            onStart={nav.goToStart}
            onBack={nav.goBack}
            onForward={nav.goForward}
            onEnd={nav.goToEnd}
          />
          <p className="text-xs text-muted-foreground text-center mt-1">
            Move {nav.moveIndex + 1} of {nav.totalMoves}
          </p>
        </div>

        {/* Right: Moves + game list */}
        <div className="space-y-4">
          {/* Opening moves display */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              Opening Moves
            </h4>
            <p className="text-sm font-mono leading-relaxed">
              {openingMoves || "No moves available"}
            </p>
          </div>

          {/* Game list */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
              Games ({gameList.length})
            </h4>
            <div className="space-y-1">
              {visibleGames.map((g) => {
                const badge = RESULT_BADGE[g.result] || RESULT_BADGE.draw;
                return (
                  <Link
                    key={g.game_id}
                    href={`/${playerUsername}/games/${g.game_id}`}
                    className="flex items-center gap-2 text-sm py-1 px-2 rounded hover:bg-muted/50 transition-colors group"
                  >
                    <span className="text-muted-foreground w-20 shrink-0">{g.date || "—"}</span>
                    <span className="text-muted-foreground">vs</span>
                    <span className="truncate group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors">
                      {g.opponent}
                    </span>
                    <Badge variant={badge.variant} className="ml-auto shrink-0 text-xs px-1.5 py-0">
                      {badge.label}
                    </Badge>
                  </Link>
                );
              })}
            </div>
            {hasMore && !showAll && (
              <button
                onClick={() => setShowAll(true)}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline mt-1 ml-2"
              >
                +{gameList.length - 5} more
              </button>
            )}
            {hasMore && showAll && (
              <button
                onClick={() => setShowAll(false)}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline mt-1 ml-2"
              >
                Show less
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
