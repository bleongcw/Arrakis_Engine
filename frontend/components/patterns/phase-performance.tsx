"use client";

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

export function PhasePerformance({ data }: PhasePerformanceProps) {
  console.log("PhasePerformance data:", JSON.stringify(data));
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
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        Performance by Phase
      </h3>
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
