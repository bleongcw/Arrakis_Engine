"use client";

import { useMemo } from "react";

interface ChessBoardProps {
  position: string; // FEN string
  orientation: "white" | "black";
  boardWidth?: number;
}

// Unicode chess pieces
const PIECE_CHARS: Record<string, string> = {
  K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙",
  k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟",
};

function fenToBoard(fen: string): (string | null)[][] {
  const rows = fen.split(" ")[0].split("/");
  return rows.map((row) => {
    const cells: (string | null)[] = [];
    for (const ch of row) {
      if (ch >= "1" && ch <= "8") {
        for (let i = 0; i < parseInt(ch); i++) cells.push(null);
      } else {
        cells.push(ch);
      }
    }
    return cells;
  });
}

export function ChessBoard({
  position,
  orientation,
  boardWidth = 400,
}: ChessBoardProps) {
  const board = useMemo(() => fenToBoard(position), [position]);
  const squareSize = boardWidth / 8;
  const isFlipped = orientation === "black";

  const files = ["a", "b", "c", "d", "e", "f", "g", "h"];
  const ranks = ["8", "7", "6", "5", "4", "3", "2", "1"];

  const displayRanks = isFlipped ? [...ranks].reverse() : ranks;
  const displayFiles = isFlipped ? [...files].reverse() : files;

  return (
    <div
      style={{ width: boardWidth, height: boardWidth, position: "relative" }}
      className="rounded shadow-lg overflow-hidden select-none"
    >
      {displayRanks.map((rank, rowIdx) => {
        const boardRow = isFlipped ? 7 - rowIdx : rowIdx;
        return displayFiles.map((file, colIdx) => {
          const boardCol = isFlipped ? 7 - colIdx : colIdx;
          const isLight = (boardRow + boardCol) % 2 === 0;
          const piece = board[boardRow]?.[boardCol];

          return (
            <div
              key={`${rank}${file}`}
              style={{
                position: "absolute",
                left: colIdx * squareSize,
                top: rowIdx * squareSize,
                width: squareSize,
                height: squareSize,
                background: isLight ? "#f0d9b5" : "#b58863",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: squareSize * 0.75,
                lineHeight: 1,
                userSelect: "none",
              }}
            >
              {piece && (
                <span
                  style={{
                    textShadow: piece === piece.toUpperCase()
                      ? "0 0 2px rgba(0,0,0,0.3)"
                      : "0 0 2px rgba(255,255,255,0.3)",
                    filter: piece === piece.toUpperCase()
                      ? "drop-shadow(0 1px 1px rgba(0,0,0,0.2))"
                      : "drop-shadow(0 1px 1px rgba(0,0,0,0.4))",
                  }}
                >
                  {PIECE_CHARS[piece]}
                </span>
              )}
              {/* Rank label on left edge */}
              {colIdx === 0 && (
                <span
                  style={{
                    position: "absolute",
                    top: 2,
                    left: 3,
                    fontSize: 10,
                    fontWeight: 600,
                    color: isLight ? "#b58863" : "#f0d9b5",
                    fontFamily: "sans-serif",
                  }}
                >
                  {rank}
                </span>
              )}
              {/* File label on bottom edge */}
              {rowIdx === 7 && (
                <span
                  style={{
                    position: "absolute",
                    bottom: 1,
                    right: 3,
                    fontSize: 10,
                    fontWeight: 600,
                    color: isLight ? "#b58863" : "#f0d9b5",
                    fontFamily: "sans-serif",
                  }}
                >
                  {file}
                </span>
              )}
            </div>
          );
        });
      })}
    </div>
  );
}
