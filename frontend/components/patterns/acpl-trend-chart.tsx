"use client";

import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from "recharts";

interface ACPLTrendChartProps {
  data: Array<{ week: string; acpl: number; games: number }>;
}

export function ACPLTrendChart({ data }: ACPLTrendChartProps) {
  const [showInfo, setShowInfo] = useState(false);

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          ACPL Trend
        </h3>
        <div className="relative inline-block">
          <span
            className="text-sm text-muted-foreground cursor-help select-none"
            onMouseEnter={() => setShowInfo(true)}
            onMouseLeave={() => setShowInfo(false)}
          >
            ⓘ
          </span>
          {showInfo && (
            <div className="absolute left-0 top-6 z-50 w-[340px] p-4 rounded-lg border bg-card text-card-foreground shadow-lg text-sm">
              <p className="font-semibold mb-2">Average Centipawn Loss (ACPL)</p>
              <p className="mb-2 text-muted-foreground">
                Measures how much your moves deviate from the engine&apos;s best
                move, averaged across all moves in a game. One centipawn = 1/100th
                of a pawn.
              </p>
              <p className="font-medium mb-1">How it&apos;s calculated:</p>
              <p className="text-xs text-muted-foreground mb-2">
                For each move: loss = |best move eval − your move eval|<br />
                ACPL = sum of all losses ÷ number of moves
              </p>
              <p className="font-medium mb-1">Benchmarks by level:</p>
              <ul className="text-xs text-muted-foreground space-y-0.5 mb-2">
                <li>• 10–20: Super Grandmaster</li>
                <li>• 20–30: Master (2200+)</li>
                <li>• 30–50: Expert (1800–2200)</li>
                <li>• 50–100: Intermediate (1200–1800)</li>
                <li>• 100–200: Beginner / Elementary</li>
                <li>• 200+: Just starting out</li>
              </ul>
              <p className="font-medium text-green-600 dark:text-green-400 mb-1">
                Lower is better.
              </p>
              <p className="text-xs text-muted-foreground italic">
                A downward trend means you&apos;re improving! Note: ACPL varies by
                time control (blitz tends higher) and engine depth.
              </p>
            </div>
          )}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis
            dataKey="week"
            tick={{ fontSize: 11 }}
            className="fill-muted-foreground"
          />
          <YAxis tick={{ fontSize: 11 }} className="fill-muted-foreground" />
          <RechartsTooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "6px",
              color: "hsl(var(--card-foreground))",
            }}
            formatter={(value: number) => [`${value} ACPL`, "Average"]}
            labelFormatter={(label: string) => `Week of ${label}`}
          />
          <Line
            type="monotone"
            dataKey="acpl"
            stroke="#1e40af"
            strokeWidth={2}
            dot={{ fill: "#1e40af", r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
