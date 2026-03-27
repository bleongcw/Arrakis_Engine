"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";

interface TacticalMissData {
  total_opportunities: number;
  missed: number;
  found: number;
  miss_rate: number;
  find_rate: number;
  miss_by_phase: { opening: number; middlegame: number; endgame: number };
  opportunities_by_phase: { opening: number; middlegame: number; endgame: number };
}

export function TacticalMisses({ data }: { data: TacticalMissData }) {
  if (!data || data.total_opportunities === 0) {
    return <p className="text-sm text-muted-foreground">No data available.</p>;
  }

  const phaseData = [
    {
      phase: "Opening",
      missed: data.miss_by_phase.opening,
      found: data.opportunities_by_phase.opening - data.miss_by_phase.opening,
    },
    {
      phase: "Middlegame",
      missed: data.miss_by_phase.middlegame,
      found: data.opportunities_by_phase.middlegame - data.miss_by_phase.middlegame,
    },
    {
      phase: "Endgame",
      missed: data.miss_by_phase.endgame,
      found: data.opportunities_by_phase.endgame - data.miss_by_phase.endgame,
    },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Tactical Awareness
        </h3>
        <div className="text-right">
          <span className="text-2xl font-bold text-red-500">{data.miss_rate}%</span>
          <span className="text-xs text-muted-foreground ml-1">miss rate</span>
        </div>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        {data.missed} of {data.total_opportunities} tactical opportunities missed
        ({data.found} found). Lower miss rate = sharper tactical vision.
      </p>

      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={phaseData} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11 }} className="fill-muted-foreground" />
          <YAxis dataKey="phase" type="category" tick={{ fontSize: 12 }} width={90} className="fill-muted-foreground" />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "6px",
              color: "hsl(var(--card-foreground))",
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="found" name="Found" fill="#22c55e" stackId="tactics" />
          <Bar dataKey="missed" name="Missed" fill="#ef4444" stackId="tactics" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
