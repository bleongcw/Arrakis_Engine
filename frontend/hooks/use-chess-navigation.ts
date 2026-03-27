"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { Chess } from "chess.js";

export function useChessNavigation(pgn: string, playerColor: "white" | "black") {
  const [moveIndex, setMoveIndex] = useState(-1);

  // Parse PGN into array of FENs
  const { fens, moves } = useMemo(() => {
    if (!pgn || pgn.trim() === "") {
      return { fens: [new Chess().fen()], moves: [] as string[] };
    }

    const chess = new Chess();

    // Try loading PGN — chess.js v1.0+ throws on failure
    try {
      chess.loadPgn(pgn);
    } catch (e) {
      console.warn("Failed to load PGN:", e);
      return { fens: [chess.fen()], moves: [] as string[] };
    }

    const history = chess.history();
    if (history.length === 0) {
      console.warn("PGN loaded but no moves found");
      return { fens: [chess.fen()], moves: [] as string[] };
    }

    // Rebuild FEN for each position
    chess.reset();
    const fenList = [chess.fen()];
    for (const move of history) {
      try {
        chess.move(move);
        fenList.push(chess.fen());
      } catch (e) {
        console.warn(`Failed to replay move ${move}:`, e);
        break;
      }
    }

    return { fens: fenList, moves: history };
  }, [pgn]);

  // Reset move index when PGN changes
  useEffect(() => {
    setMoveIndex(-1);
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
      // Don't intercept if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
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
