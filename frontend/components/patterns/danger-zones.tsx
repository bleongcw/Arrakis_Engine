"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
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

const BLUNDER_COLOR = "#dc2626";  // distinct red
const MISTAKE_COLOR = "#facc15";  // yellow — clearly different from red

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const blunders = payload.find((p: any) => p.dataKey === "blunders")?.value || 0;
  const mistakes = payload.find((p: any) => p.dataKey === "mistakes")?.value || 0;
  const total = payload[0]?.payload?.total_moves || 0;
  const errorRate = payload[0]?.payload?.error_rate || 0;

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-lg shadow-lg p-3 text-sm">
      <p className="font-semibold mb-1">Moves {label}</p>
      <div className="space-y-0.5 text-xs">
        <p>
          <span className="inline-block w-3 h-3 rounded-sm mr-1.5" style={{ backgroundColor: BLUNDER_COLOR }} />
          Blunders: <strong>{blunders}</strong>
        </p>
        <p>
          <span className="inline-block w-3 h-3 rounded-sm mr-1.5" style={{ backgroundColor: MISTAKE_COLOR }} />
          Mistakes: <strong>{mistakes}</strong>
        </p>
        <p className="text-muted-foreground pt-1 border-t mt-1">
          {total} total moves · {errorRate}% error rate
        </p>
      </div>
    </div>
  );
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

      {/* Custom legend */}
      <div className="flex items-center gap-4 mb-2 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: BLUNDER_COLOR }} />
          <span>Blunders</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: MISTAKE_COLOR }} />
          <span>Mistakes</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data.histogram} barCategoryGap="15%">
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
          <XAxis
            dataKey="range"
            tick={{ fontSize: 10 }}
            className="fill-muted-foreground"
            interval={0}
            angle={-45}
            textAnchor="end"
            height={50}
          />
          <YAxis
            tick={{ fontSize: 11 }}
            className="fill-muted-foreground"
            allowDecimals={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(128,128,128,0.1)" }} />
          <Bar dataKey="blunders" fill={BLUNDER_COLOR} stackId="errors" />
          <Bar dataKey="mistakes" fill={MISTAKE_COLOR} stackId="errors" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
