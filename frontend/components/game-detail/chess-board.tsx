"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";

const ReactChessboard = dynamic(
  () => import("react-chessboard").then((mod) => mod.Chessboard),
  {
    ssr: false,
    loading: () => (
      <div className="w-[400px] h-[400px] bg-muted rounded animate-pulse" />
    ),
  }
);

interface ChessBoardProps {
  position: string;
  orientation: "white" | "black";
  boardWidth?: number;
}

export function ChessBoard({
  position,
  orientation,
  boardWidth = 400,
}: ChessBoardProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div
        style={{ width: boardWidth, height: boardWidth }}
        className="bg-muted rounded animate-pulse"
      />
    );
  }

  return (
    <div style={{ width: boardWidth, height: boardWidth }}>
      <ReactChessboard
        id="analysis-board"
        position={position}
        boardOrientation={orientation}
        arePiecesDraggable={false}
        boardWidth={boardWidth}
        animationDuration={150}
        customBoardStyle={{
          borderRadius: "4px",
          boxShadow: "0 2px 10px rgba(0,0,0,0.2)",
        }}
      />
    </div>
  );
}
