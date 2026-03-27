"use client";

import { useEffect, useState, useRef } from "react";

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
  const [ChessboardComponent, setChessboardComponent] = useState<React.ComponentType<any> | null>(null);
  const positionRef = useRef(position);
  positionRef.current = position;

  // Dynamically import on mount
  useEffect(() => {
    import("react-chessboard").then((mod) => {
      setChessboardComponent(() => mod.Chessboard);
    });
  }, []);

  if (!ChessboardComponent) {
    return (
      <div
        style={{ width: boardWidth, height: boardWidth }}
        className="bg-muted rounded animate-pulse"
      />
    );
  }

  return (
    <div style={{ width: boardWidth, height: boardWidth }}>
      <ChessboardComponent
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
