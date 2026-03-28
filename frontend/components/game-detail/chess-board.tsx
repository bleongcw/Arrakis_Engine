"use client";

import { useMemo, useRef, useState, useEffect } from "react";
import Image from "next/image";

interface ChessBoardProps {
  position: string; // FEN string
  orientation: "white" | "black";
  boardWidth?: number; // If set, uses fixed width. If omitted, auto-sizes to fill container.
  maxWidth?: number;
}

// Map FEN characters to piece image filenames (lichess cburnett set)
const PIECE_FILES: Record<string, string> = {
  K: "wK", Q: "wQ", R: "wR", B: "wB", N: "wN", P: "wP",
  k: "bK", q: "bQ", r: "bR", b: "bB", n: "bN", p: "bP",
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
  boardWidth: fixedWidth,
  maxWidth = 400,
}: ChessBoardProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [measuredWidth, setMeasuredWidth] = useState(fixedWidth ?? maxWidth);

  useEffect(() => {
    if (fixedWidth) return; // Skip ResizeObserver when width is explicitly set
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setMeasuredWidth(Math.min(w, maxWidth));
    });
    ro.observe(el);
    // Initial measurement
    setMeasuredWidth(Math.min(el.clientWidth, maxWidth));
    return () => ro.disconnect();
  }, [fixedWidth, maxWidth]);

  const boardWidth = fixedWidth ?? measuredWidth;
  const board = useMemo(() => fenToBoard(position), [position]);
  const squareSize = boardWidth / 8;
  const isFlipped = orientation === "black";
  const pieceSize = squareSize * 0.85;

  const files = ["a", "b", "c", "d", "e", "f", "g", "h"];
  const ranks = ["8", "7", "6", "5", "4", "3", "2", "1"];

  const displayRanks = isFlipped ? [...ranks].reverse() : ranks;
  const displayFiles = isFlipped ? [...files].reverse() : files;

  return (
    <div ref={containerRef} className={fixedWidth ? "" : "w-full"}>
    <div
      style={{ width: boardWidth, height: boardWidth, position: "relative", margin: fixedWidth ? undefined : "0 auto" }}
      className="rounded-md shadow-lg overflow-hidden select-none"
    >
      {displayRanks.map((rank, rowIdx) => {
        const boardRow = isFlipped ? 7 - rowIdx : rowIdx;
        return displayFiles.map((file, colIdx) => {
          const boardCol = isFlipped ? 7 - colIdx : colIdx;
          const isLight = (boardRow + boardCol) % 2 === 0;
          const piece = board[boardRow]?.[boardCol];
          const pieceFile = piece ? PIECE_FILES[piece] : null;

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
              }}
            >
              {pieceFile && (
                <Image
                  src={`/pieces/${pieceFile}.svg`}
                  alt={pieceFile}
                  width={pieceSize}
                  height={pieceSize}
                  style={{
                    filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.3))",
                    pointerEvents: "none",
                  }}
                  priority
                  unoptimized
                />
              )}
              {/* Rank label on left edge */}
              {colIdx === 0 && (
                <span
                  style={{
                    position: "absolute",
                    top: 2,
                    left: 3,
                    fontSize: 10,
                    fontWeight: 700,
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
                    fontWeight: 700,
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
    </div>
  );
}
