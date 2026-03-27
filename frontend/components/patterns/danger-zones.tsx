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

interface DangerZoneData {
  histogram: Array<{
    range: string;
    blunders: number;
    mistakes: number;
    total_moves: number;
    blunder_rate: number;
    error_rate: number;
  }>;
  worst_zone: {
    range: string;
    blunder_rate: number;
  } | null;
  bucket_size: number;
}

export function DangerZones({ data }: { data: DangerZoneData }) {
  if (!data?.histogram?.length) {
    return <p className="text-sm text-muted-foreground">No data available.</p>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Danger Zones
        </h3>
        {data.worst_zone && (
          <span className="text-xs text-red-500 font-medium">
            Worst: moves {data.worst_zone.range} ({data.worst_zone.blunder_rate}%
            blunder rate)
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Where blunders and mistakes cluster by move number — reveals opening
        gaps, middlegame tactical weakness, or endgame fatigue.
      </p>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data.histogram}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis
            dataKey="range"
            tick={{ fontSize: 10 }}
            className="fill-muted-foreground"
            label={{
              value: "Move Range",
              position: "insideBottom",
              offset: -5,
              fontSize: 11,
              className: "fill-muted-foreground",
            }}
          />
          <YAxis
            tick={{ fontSize: 11 }}
            className="fill-muted-foreground"
            label={{
              value: "Count",
              angle: -90,
              position: "insideLeft",
              fontSize: 11,
              className: "fill-muted-foreground",
            }}
          />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "6px",
              color: "hsl(var(--card-foreground))",
            }}
            formatter={(value: number, name: string) => [
              value,
              name === "blunders" ? "Blunders" : "Mistakes",
            ]}
            labelFormatter={(label) => `Moves ${label}`}
          />
          <Legend
            wrapperStyle={{ fontSize: 12 }}
            formatter={(value) =>
              value === "blunders" ? "Blunders" : "Mistakes"
            }
          />
          <Bar dataKey="blunders" fill="#ef4444" stackId="errors" radius={[0, 0, 0, 0]} />
          <Bar dataKey="mistakes" fill="#f97316" stackId="errors" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
