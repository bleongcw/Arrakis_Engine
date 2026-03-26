"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from "recharts";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ACPLTrendChartProps {
  data: Array<{ week: string; acpl: number; games: number }>;
}

export function ACPLTrendChart({ data }: ACPLTrendChartProps) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          ACPL Trend
        </h3>
        <Tooltip>
          <TooltipTrigger>
            <span className="text-sm text-muted-foreground cursor-help">
              {"\u24D8"}
            </span>
          </TooltipTrigger>
          <TooltipContent className="max-w-[340px] text-sm">
            <p className="font-semibold mb-2">Average Centipawn Loss (ACPL)</p>
            <p className="mb-2">
              Measures how much your moves deviate from the engine&apos;s best
              move, averaged across all moves. Lower is better.
            </p>
            <p className="mb-1 font-medium">Benchmarks:</p>
            <ul className="text-xs space-y-0.5 mb-2">
              <li>10-20: Super Grandmaster</li>
              <li>20-30: Master (2200+)</li>
              <li>30-50: Expert</li>
              <li>50-100: Intermediate</li>
              <li>100-200: Beginner/Elementary</li>
            </ul>
            <p className="text-xs italic">
              A downward trend means you&apos;re improving!
            </p>
          </TooltipContent>
        </Tooltip>
      </div>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="week" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <RechartsTooltip
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
            }}
            formatter={(value) => [`${value} ACPL`, "Average"]}
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
