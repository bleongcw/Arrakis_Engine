"use client";

import Link from "next/link";
import { useState, useEffect, useMemo } from "react";
import { ChessBoard } from "@/components/game-detail/chess-board";
import { MoveControls } from "@/components/game-detail/move-controls";
import { useChessNavigation } from "@/hooks/use-chess-navigation";
import { Badge } from "@/components/ui/badge";
import type { OpeningGameEntry, OpeningBookEntry } from "@/lib/types";

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

function parseMoveText(moveText: string): string[] {
  // Parse "1.e4 e5 2.Nf3 Nc6" into ["e4", "e5", "Nf3", "Nc6"]
  return moveText
    .replace(/\d+\./g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

function findBookMatch(
  openingMoves: string,
  book: OpeningBookEntry[]
): { eco: string; name: string; bookMoves: string[]; deviationIndex: number } | null {
  const playerMoves = parseMoveText(openingMoves);
  if (playerMoves.length === 0) return null;

  // Find the longest matching book opening
  let bestMatch: OpeningBookEntry | null = null;
  let bestMatchLen = 0;

  for (const entry of book) {
    const bookMoves = parseMoveText(entry.moves);
    let matchLen = 0;
    for (let i = 0; i < Math.min(bookMoves.length, playerMoves.length); i++) {
      if (bookMoves[i] === playerMoves[i]) {
        matchLen = i + 1;
      } else {
        break;
      }
    }
    if (matchLen > bestMatchLen) {
      bestMatchLen = matchLen;
      bestMatch = entry;
    }
  }

  if (!bestMatch) return null;

  const bookMoves = parseMoveText(bestMatch.moves);
  // Find deviation point: where player departs from book
  let deviationIndex = -1;
  for (let i = 0; i < Math.min(bookMoves.length, playerMoves.length); i++) {
    if (bookMoves[i] !== playerMoves[i]) {
      deviationIndex = i;
      break;
    }
  }

  return {
    eco: bestMatch.eco,
    name: bestMatch.name,
    bookMoves,
    deviationIndex,
  };
}

export function OpeningExplorer({
  openingName,
  openingMoves,
  gameList,
  playerUsername,
  boardOrientation,
}: OpeningExplorerProps) {
  const nav = useChessNavigation(openingMoves, boardOrientation);
  const [showAll, setShowAll] = useState(false);
  const [book, setBook] = useState<OpeningBookEntry[]>([]);

  useEffect(() => {
    fetch("/data/openings.json")
      .then((r) => r.json())
      .then(setBook)
      .catch(() => {});
  }, []);

  const bookMatch = useMemo(
    () => (book.length > 0 ? findBookMatch(openingMoves, book) : null),
    [openingMoves, book]
  );

  const playerMoves = useMemo(() => parseMoveText(openingMoves), [openingMoves]);

  const visibleGames = showAll ? gameList : gameList.slice(0, 5);
  const hasMore = gameList.length > 5;

  // Render moves with book comparison indicators
  function renderAnnotatedMoves() {
    if (!bookMatch) {
      return (
        <p className="text-sm font-mono leading-relaxed">
          {openingMoves || "No moves available"}
        </p>
      );
    }

    const { bookMoves, deviationIndex } = bookMatch;
    const parts: React.ReactNode[] = [];
    let moveNum = 1;

    for (let i = 0; i < playerMoves.length; i++) {
      const isWhiteMove = i % 2 === 0;
      if (isWhiteMove) {
        parts.push(
          <span key={`num-${moveNum}`} className="text-muted-foreground">
            {moveNum}.
          </span>
        );
      }

      const inBook = i < bookMoves.length && playerMoves[i] === bookMoves[i];
      const isDeviation = deviationIndex >= 0 && i === deviationIndex;

      parts.push(
        <span
          key={`move-${i}`}
          className={
            isDeviation
              ? "text-orange-500 font-bold"
              : inBook
                ? "text-emerald-600 dark:text-emerald-400"
                : ""
          }
          title={
            isDeviation && i < bookMoves.length
              ? `Book move: ${bookMoves[i]}`
              : inBook
                ? "Book move"
                : undefined
          }
        >
          {isDeviation && (
            <span className="text-orange-400 text-[10px] align-super mr-0.5">!</span>
          )}
          {inBook && (
            <span className="text-emerald-400 text-[10px] align-super mr-0.5">{"\u2713"}</span>
          )}
          {playerMoves[i]}
        </span>
      );
      parts.push(<span key={`space-${i}`}> </span>);

      if (!isWhiteMove) moveNum++;
    }

    return <p className="text-sm font-mono leading-relaxed">{parts}</p>;
  }

  return (
    <div className="border rounded-lg bg-muted/30 p-4">
      <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-4">
        {/* Left: Board + controls */}
        <div>
          <ChessBoard
            position={nav.currentFen}
            orientation={nav.boardOrientation}
            maxWidth={280}
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
          {/* ECO badge + Opening moves display */}
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Opening Moves
              </h4>
              {bookMatch && (
                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                  {bookMatch.eco} — {bookMatch.name}
                </Badge>
              )}
            </div>
            {renderAnnotatedMoves()}
            {bookMatch && bookMatch.deviationIndex >= 0 && bookMatch.deviationIndex < bookMatch.bookMoves.length && (
              <p className="text-xs text-orange-500 mt-1">
                Deviation at move {Math.floor(bookMatch.deviationIndex / 2) + 1}: played{" "}
                <span className="font-mono font-bold">{playerMoves[bookMatch.deviationIndex]}</span>
                , book is{" "}
                <span className="font-mono font-bold">{bookMatch.bookMoves[bookMatch.deviationIndex]}</span>
              </p>
            )}
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
                    <span className="text-muted-foreground w-36 shrink-0">{g.date || "\u2014"}</span>
                    <span className="text-muted-foreground shrink-0">vs</span>
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
