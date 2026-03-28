"use client";

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

export function TimePressure({ data }: TimePressureProps) {
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
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4">
        Time Pressure Analysis
      </h3>

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
