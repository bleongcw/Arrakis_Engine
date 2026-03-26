"use client";

import dynamic from "next/dynamic";

const Chessboard = dynamic(
  () => import("react-chessboard").then((mod) => mod.Chessboard),
  { ssr: false }
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
  return (
    <div style={{ width: boardWidth, height: boardWidth }}>
      <Chessboard
        options={{
          position,
          boardOrientation: orientation,
          allowDragging: false,
          boardStyle: {
            borderRadius: "4px",
            boxShadow: "0 2px 10px rgba(0,0,0,0.2)",
          },
        }}
      />
    </div>
  );
}
