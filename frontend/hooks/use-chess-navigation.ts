"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { Chess } from "chess.js";

export function useChessNavigation(pgn: string, playerColor: "white" | "black") {
  const [moveIndex, setMoveIndex] = useState(-1);

  // Parse PGN into array of FENs
  const { fens, moves } = useMemo(() => {
    const chess = new Chess();
    try {
      chess.loadPgn(pgn);
    } catch {
      return { fens: [chess.fen()], moves: [] as string[] };
    }
    const history = chess.history();
    chess.reset();

    const fenList = [chess.fen()];
    for (const move of history) {
      chess.move(move);
      fenList.push(chess.fen());
    }

    return { fens: fenList, moves: history };
  }, [pgn]);

  const currentFen = fens[moveIndex + 1] || fens[0];

  const goToStart = useCallback(() => setMoveIndex(-1), []);
  const goToEnd = useCallback(() => setMoveIndex(moves.length - 1), [moves.length]);
  const goForward = useCallback(
    () => setMoveIndex((i) => Math.min(i + 1, moves.length - 1)),
    [moves.length]
  );
  const goBack = useCallback(() => setMoveIndex((i) => Math.max(i - 1, -1)), []);
  const goToMove = useCallback((idx: number) => setMoveIndex(idx), []);

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        goBack();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        goForward();
      } else if (e.key === "Home") {
        e.preventDefault();
        goToStart();
      } else if (e.key === "End") {
        e.preventDefault();
        goToEnd();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [goBack, goForward, goToStart, goToEnd]);

  return {
    currentFen,
    moveIndex,
    totalMoves: moves.length,
    moves,
    goToStart,
    goToEnd,
    goForward,
    goBack,
    goToMove,
    boardOrientation: playerColor as "white" | "black",
  };
}
