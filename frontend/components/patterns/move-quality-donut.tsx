"use client";

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
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        Move Quality Distribution
      </h3>
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
