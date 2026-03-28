"use client";

import { useState, useRef, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from "recharts";
import { createPortal } from "react-dom";

interface ACPLTrendChartProps {
  data: Array<{ week: string; acpl: number; games: number }>;
}

function ACPLInfoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/30" />
      {/* Card */}
      <div
        className="relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl w-[340px] p-5 text-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">
            Average Centipawn Loss (ACPL)
          </h4>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1"
          >
            ×
          </button>
        </div>

        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Measures how much your moves deviate from the engine&apos;s best move,
          averaged across all moves in a game. One centipawn = 1/100th of a
          pawn.
        </p>

        <h5 className="font-semibold text-xs text-zinc-800 dark:text-zinc-200 mb-1">
          Calculation
        </h5>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3 font-mono bg-zinc-100 dark:bg-zinc-800 p-2 rounded">
          loss = |best eval − your eval|
          <br />
          ACPL = sum(losses) ÷ total moves
        </p>

        <h5 className="font-semibold text-xs text-zinc-800 dark:text-zinc-200 mb-1">
          Benchmarks by level
        </h5>
        <table className="w-full text-xs mb-3">
          <tbody className="text-zinc-600 dark:text-zinc-400">
            <tr>
              <td className="py-0.5 font-mono">10–20</td>
              <td>Super Grandmaster</td>
            </tr>
            <tr>
              <td className="py-0.5 font-mono">20–30</td>
              <td>Master (2200+)</td>
            </tr>
            <tr>
              <td className="py-0.5 font-mono">30–50</td>
              <td>Expert (1800–2200)</td>
            </tr>
            <tr>
              <td className="py-0.5 font-mono">50–100</td>
              <td>Intermediate (1200–1800)</td>
            </tr>
            <tr>
              <td className="py-0.5 font-mono">100–200</td>
              <td>Beginner / Elementary</td>
            </tr>
            <tr>
              <td className="py-0.5 font-mono">200+</td>
              <td>Just starting out</td>
            </tr>
          </tbody>
        </table>

        <p className="text-xs font-semibold text-green-600 dark:text-green-400 mb-1">
          ↓ Lower is better — a downward trend means improving!
        </p>
        <p className="text-[10px] text-zinc-400 italic">
          Note: ACPL varies by time control (blitz tends higher) and engine
          depth. Compare like with like.
        </p>
      </div>
    </div>,
    document.body
  );
}

export function ACPLTrendChart({ data }: ACPLTrendChartProps) {
  const [showInfo, setShowInfo] = useState(false);

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          ACPL Trend
        </h3>
        <button
          onClick={() => setShowInfo(true)}
          className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors"
          title="What is ACPL?"
        >
          ⓘ
        </button>
      </div>

      {showInfo && <ACPLInfoModal onClose={() => setShowInfo(false)} />}

      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis
            dataKey="week"
            tick={{ fontSize: 11 }}
            className="fill-muted-foreground"
          />
          <YAxis tick={{ fontSize: 11 }} className="fill-muted-foreground" />
          <RechartsTooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "6px",
              color: "hsl(var(--card-foreground))",
            }}
            formatter={(value: any) => [`${value} ACPL`, "Average"]}
            labelFormatter={(label: any) => `Week of ${label}`}
          />
          <Line
            type="monotone"
            dataKey="acpl"
            stroke="#1e40af"
            strokeWidth={2}
            dot={{ fill: "#1e40af", r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
