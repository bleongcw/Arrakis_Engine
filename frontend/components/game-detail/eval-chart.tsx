"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
  Tooltip,
} from "recharts";
import type { MoveAnalysis } from "@/lib/types";

interface EvalChartProps {
  moves: MoveAnalysis[];
  playerColor: "white" | "black";
}

const CLASSIFICATION_COLORS: Record<string, string> = {
  excellent: "#22c55e",
  good: "#3b82f6",
  inaccuracy: "#eab308",
  mistake: "#f97316",
  blunder: "#ef4444",
};

export function EvalChart({ moves, playerColor }: EvalChartProps) {
  const data = moves.map((m) => {
    const cp = m.eval_after_cp ?? 0;
    const pawns = Math.max(-5, Math.min(5, cp / 100));
    const adjustedEval = playerColor === "white" ? pawns : -pawns;
    const color = CLASSIFICATION_COLORS[m.classification || "good"] || "#3b82f6";

    return {
      move: `${m.move_number}${m.side === "black" ? "..." : "."}`,
      eval: adjustedEval,
      color,
      classification: m.classification || "good",
      side: m.side,
      movePlayed: m.move_played,
      cpLoss: m.swing_cp,
    };
  });

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
        <XAxis dataKey="move" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
        <YAxis domain={[-5, 5]} ticks={[-5, -3, -1, 1, 3, 5]} tick={{ fontSize: 11 }} />
        <ReferenceLine y={0} stroke="#666" strokeWidth={1} />
        <Tooltip
          contentStyle={{
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            fontSize: "12px",
          }}
        />
        <Bar dataKey="eval" radius={[2, 2, 0, 0]}>
          {data.map((entry, idx) => (
            <Cell key={idx} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
