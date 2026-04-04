"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { TimePressureStats } from "@/lib/types";

interface TimePressureProps {
  data: TimePressureStats | null | undefined;
}

function ScoreBadge({ score }: { score: number }) {
  let color = "text-red-500";
  let label = "Poor";
  if (score >= 80) {
    color = "text-emerald-500";
    label = "Excellent";
  } else if (score >= 60) {
    color = "text-blue-500";
    label = "Good";
  } else if (score >= 40) {
    color = "text-yellow-500";
    label = "Fair";
  }
  return (
    <span className={`font-bold ${color}`}>
      {score}/100 — {label}
    </span>
  );
}

function TimePressureInfoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl w-[340px] p-5 text-sm" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Time Pressure</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">×</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Analyzes your clock usage and how time pressure affects your play:
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><strong>Time Management Score</strong> — Overall rating (0-100) of how well you distribute time across the game.</li>
          <li><strong>Time Trouble Rate</strong> — Percentage of games where you dropped below 30 seconds.</li>
          <li><strong>Phase Time</strong> — Average seconds per move in opening, middlegame, and endgame.</li>
          <li><strong>Blunder Comparison</strong> — Compares blunder rate when comfortable vs under time pressure.</li>
        </ul>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-3">
          Only includes games with clock data. A big gap between comfortable and pressure blunder rates means time management is a key area to improve.
        </p>
      </div>
    </div>,
    document.body
  );
}

export function TimePressure({ data }: TimePressureProps) {
  const [showInfo, setShowInfo] = useState(false);

  if (!data) return null;

  const phaseData = [
    { name: "Opening", seconds: data.phase_avg_time.opening },
    { name: "Middle", seconds: data.phase_avg_time.middlegame },
    { name: "Endgame", seconds: data.phase_avg_time.endgame },
  ];

  const blunderComparison = [
    {
      name: "Comfortable",
      rate: data.blunder_rate_comfortable,
      moves: data.moves_comfortable,
      fill: "#3b82f6",
    },
    {
      name: "Under Pressure",
      rate: data.blunder_rate_under_pressure,
      moves: data.moves_under_pressure,
      fill: "#ef4444",
    },
  ];

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Time Pressure Analysis
        </h3>
        <button onClick={() => setShowInfo(true)} className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors" title="What does this analyze?">&#9432;</button>
      </div>
      {showInfo && <TimePressureInfoModal onClose={() => setShowInfo(false)} />}

      {/* Score + Key Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="text-center">
          <p className="text-xs text-muted-foreground">Time Management</p>
          <p className="text-lg mt-1">
            <ScoreBadge score={data.time_management_score} />
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-muted-foreground">Time Trouble Rate</p>
          <p className="text-2xl font-bold mt-1">{data.time_trouble_rate}%</p>
          <p className="text-xs text-muted-foreground">of games &lt;30s</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-muted-foreground">Avg Move Time</p>
          <p className="text-2xl font-bold mt-1">{data.avg_time_per_move}s</p>
        </div>
        <div className="text-center">
          <p className="text-xs text-muted-foreground">Games Tracked</p>
          <p className="text-2xl font-bold mt-1">{data.games_with_clocks}</p>
        </div>
      </div>

      {/* Charts side by side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Phase Time Distribution */}
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-2">
            Avg Time per Move by Phase (seconds)
          </p>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={phaseData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={65} tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(val) => [`${val}s`, "Avg time"]}
                contentStyle={{ fontSize: 12 }}
              />
              <Bar dataKey="seconds" fill="#6366f1" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Blunder Rate Comparison */}
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-2">
            Blunder Rate: Comfortable vs Under Pressure
          </p>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={blunderComparison}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(val, _name, props) => [
                  `${val}% (${(props as { payload?: { moves?: number } })?.payload?.moves ?? 0} moves)`,
                  "Blunder rate",
                ]}
                contentStyle={{ fontSize: 12 }}
              />
              <Bar dataKey="rate" radius={[4, 4, 0, 0]}>
                {blunderComparison.map((entry, idx) => (
                  <Cell key={idx} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
