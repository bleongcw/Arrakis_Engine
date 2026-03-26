"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";
import type { MoveAnalysis } from "@/lib/types";

interface EvalChartProps {
  moves: MoveAnalysis[];
  playerColor: "white" | "black";
}

const CLASSIFICATION_BAR_COLORS: Record<string, string> = {
  blunder: "#ef4444",
  mistake: "#f97316",
  inaccuracy: "#eab308",
  good: "#3b82f6",
  excellent: "#22c55e",
};

export function EvalChart({ moves, playerColor }: EvalChartProps) {
  const data = moves.map((m, idx) => {
    const cp = m.eval_after_cp ?? 0;
    const pawns = Math.max(-5, Math.min(5, cp / 100));
    return {
      idx,
      move: `${m.move_number}${m.side === "black" ? "..." : "."}`,
      eval: playerColor === "white" ? pawns : -pawns,
      classification: m.classification || "good",
    };
  });

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
        <XAxis dataKey="move" tick={false} />
        <YAxis domain={[-5, 5]} tick={{ fontSize: 11 }} />
        <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
        <Bar dataKey="eval" radius={[2, 2, 0, 0]}>
          {data.map((entry, idx) => (
            <Cell
              key={idx}
              fill={entry.eval >= 0 ? "#4ade80" : "#f87171"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
