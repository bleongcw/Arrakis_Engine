"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from "recharts";

interface MoveQualityDonutProps {
  data: {
    excellent: number;
    good: number;
    inaccuracy: number;
    mistake: number;
    blunder: number;
  };
}

const COLORS = [
  { name: "Excellent", key: "excellent", color: "#22c55e" },
  { name: "Good", key: "good", color: "#3b82f6" },
  { name: "Inaccuracy", key: "inaccuracy", color: "#eab308" },
  { name: "Mistake", key: "mistake", color: "#f97316" },
  { name: "Blunder", key: "blunder", color: "#ef4444" },
];

export function MoveQualityDonut({ data }: MoveQualityDonutProps) {
  const chartData = COLORS.map((c) => ({
    name: c.name,
    value: data[c.key as keyof typeof data] || 0,
    color: c.color,
  })).filter((d) => d.value > 0);

  return (
    <div>
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        Move Quality Distribution
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={90}
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
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
