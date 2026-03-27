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
            <>
              {/* Backdrop to catch mouse leave */}
              <div className="fixed inset-0 z-40" onMouseEnter={() => setShowInfo(false)} />
              <div className="fixed z-50 w-[320px] p-4 rounded-lg border bg-card text-card-foreground shadow-xl text-sm"
                   style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>
                <div className="flex justify-between items-start mb-2">
                  <p className="font-semibold">Average Centipawn Loss (ACPL)</p>
                  <button
                    onClick={() => setShowInfo(false)}
                    className="text-muted-foreground hover:text-foreground text-lg leading-none ml-2"
                  >×</button>
                </div>
                <p className="mb-2 text-muted-foreground text-xs">
                  Measures how much your moves deviate from the engine&apos;s best
                  move, averaged across all moves. 1 centipawn = 1/100th of a pawn.
                </p>
                <p className="font-medium text-xs mb-1">Calculation:</p>
                <p className="text-xs text-muted-foreground mb-2 font-mono">
                  loss = |best eval − your eval|<br />
                  ACPL = Σ losses ÷ moves
                </p>
                <p className="font-medium text-xs mb-1">Benchmarks:</p>
                <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-muted-foreground mb-2">
                  <span>10–20</span><span>Super GM</span>
                  <span>20–30</span><span>Master (2200+)</span>
                  <span>30–50</span><span>Expert (1800–2200)</span>
                  <span>50–100</span><span>Intermediate</span>
                  <span>100–200</span><span>Beginner</span>
                  <span>200+</span><span>Just starting</span>
                </div>
                <p className="text-xs font-medium text-green-600 dark:text-green-400">
                  ↓ Lower is better. Downward trend = improving!
                </p>
                <p className="text-[10px] text-muted-foreground italic mt-1">
                  Varies by time control &amp; engine depth. Compare like with like.
                </p>
              </div>
            </>
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
