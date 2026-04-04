"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";

interface PhaseData {
  moves: number;
  acpl: number;
  blunders: number;
  mistakes: number;
  inaccuracies: number;
}

interface PhasePerformanceProps {
  data: {
    opening: PhaseData;
    middlegame: PhaseData;
    endgame: PhaseData;
  };
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
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Phase Performance</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">×</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Compares your play quality across the three phases of a chess game:
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><strong>Opening</strong> — First ~10 moves. Theory and preparation.</li>
          <li><strong>Middlegame</strong> — Moves ~10-30. Tactics and strategy.</li>
          <li><strong>Endgame</strong> — Final phase. Technique and precision.</li>
        </ul>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mt-3">
          Lower ACPL = better play. Compare phases to find where you lose the most centipawns — that&apos;s where to focus training.
        </p>
      </div>
    </div>,
    document.body
  );
}

export function PhasePerformance({ data }: PhasePerformanceProps) {
  const [showInfo, setShowInfo] = useState(false);

  if (!data || !data.opening) {
    return (
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Performance by Phase
        </h3>
        <p className="text-sm text-muted-foreground py-8 text-center">No phase data available.</p>
      </div>
    );
  }
  const chartData = [
    {
      phase: "Opening",
      ACPL: data.opening?.acpl || 0,
      Blunders: data.opening?.blunders || 0,
      Mistakes: data.opening?.mistakes || 0,
    },
    {
      phase: "Middlegame",
      ACPL: data.middlegame?.acpl || 0,
      Blunders: data.middlegame?.blunders || 0,
      Mistakes: data.middlegame?.mistakes || 0,
    },
    {
      phase: "Endgame",
      ACPL: data.endgame?.acpl || 0,
      Blunders: data.endgame?.blunders || 0,
      Mistakes: data.endgame?.mistakes || 0,
    },
  ];

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Performance by Phase
        </h3>
        <button
          onClick={() => setShowInfo(true)}
          className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors"
          title="What does this chart show?"
        >&#9432;</button>
      </div>
      {showInfo && <InfoModal onClose={() => setShowInfo(false)} />}
      <ResponsiveContainer width="100%" height={250}>
        <BarChart
          data={chartData}
          margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
          barCategoryGap="20%"
          barGap={4}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="phase" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
            }}
          />
          <Legend />
          <Bar dataKey="ACPL" name="ACPL" fill="#ef4444" radius={[2, 2, 0, 0]} barSize={30} />
          <Bar dataKey="Blunders" name="Blunders" fill="#f9a8d4" radius={[2, 2, 0, 0]} barSize={30} />
          <Bar dataKey="Mistakes" name="Mistakes" fill="#fb923c" radius={[2, 2, 0, 0]} barSize={30} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
