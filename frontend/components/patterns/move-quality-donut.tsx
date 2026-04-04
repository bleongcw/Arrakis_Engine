"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, Label } from "recharts";

interface MoveQualityData {
  count: number;
  pct: number;
}

interface MoveQualityDonutProps {
  data: {
    excellent: number | MoveQualityData;
    good: number | MoveQualityData;
    inaccuracy: number | MoveQualityData;
    mistake: number | MoveQualityData;
    blunder: number | MoveQualityData;
    total_moves?: number;
  };
}

const COLORS = [
  { name: "Excellent", key: "excellent", color: "#22c55e" },
  { name: "Good", key: "good", color: "#3b82f6" },
  { name: "Inaccuracy", key: "inaccuracy", color: "#eab308" },
  { name: "Mistake", key: "mistake", color: "#f97316" },
  { name: "Blunder", key: "blunder", color: "#ef4444" },
];

function extractCount(val: number | MoveQualityData | undefined): number {
  if (val === undefined || val === null) return 0;
  if (typeof val === "number") return val;
  return val.count || 0;
}

function InfoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div
        className="relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl w-[340px] p-5 text-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Move Quality</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">×</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Each move is compared to Stockfish&apos;s best move. The centipawn loss (how much worse your move was) determines its quality:
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><span className="inline-block w-2 h-2 rounded-full bg-[#22c55e] mr-1.5" />
            <strong>Excellent</strong> — less than 30cp loss (near-engine move)</li>
          <li><span className="inline-block w-2 h-2 rounded-full bg-[#3b82f6] mr-1.5" />
            <strong>Good</strong> — less than 50cp loss (solid play)</li>
          <li><span className="inline-block w-2 h-2 rounded-full bg-[#eab308] mr-1.5" />
            <strong>Inaccuracy</strong> — less than 100cp loss (small slip)</li>
          <li><span className="inline-block w-2 h-2 rounded-full bg-[#f97316] mr-1.5" />
            <strong>Mistake</strong> — less than 300cp loss (notable error)</li>
          <li><span className="inline-block w-2 h-2 rounded-full bg-[#ef4444] mr-1.5" />
            <strong>Blunder</strong> — 300cp+ loss (game-changing error)</li>
        </ul>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-3">
          1 centipawn (cp) = 1/100th of a pawn. 100cp ≈ losing a pawn.
        </p>
      </div>
    </div>,
    document.body
  );
}

export function MoveQualityDonut({ data }: MoveQualityDonutProps) {
  const rawData = COLORS.map((c) => ({
    name: c.name,
    value: extractCount(data[c.key as keyof typeof data] as number | MoveQualityData),
    color: c.color,
  })).filter((d) => d.value > 0);

  const total = rawData.reduce((sum, d) => sum + d.value, 0);
  const chartData = rawData.map((d) => ({
    ...d,
    pct: total > 0 ? ((d.value / total) * 100).toFixed(1) : "0",
  }));

  const [showInfo, setShowInfo] = useState(false);

  if (chartData.length === 0) {
    return (
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Move Quality Distribution
        </h3>
        <p className="text-sm text-muted-foreground py-8 text-center">No data available.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Move Quality Distribution
        </h3>
        <button
          onClick={() => setShowInfo(true)}
          className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors"
          title="What do these categories mean?"
        >&#9432;</button>
      </div>
      {showInfo && <InfoModal onClose={() => setShowInfo(false)} />}
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="45%"
            innerRadius={55}
            outerRadius={95}
            paddingAngle={2}
            dataKey="value"
          >
            {chartData.map((entry, idx) => (
              <Cell key={idx} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
            }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            formatter={(value: any, name: any) => [
              `${Number(value).toLocaleString()} moves (${total > 0 ? ((Number(value) / total) * 100).toFixed(1) : 0}%)`,
              name,
            ]}
          />
          <Legend
            layout="horizontal"
            verticalAlign="bottom"
            align="center"
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            formatter={(value: any) => {
              const item = chartData.find((d) => d.name === value);
              return `${value}: ${item?.value.toLocaleString()} (${item?.pct || 0}%)`;
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
