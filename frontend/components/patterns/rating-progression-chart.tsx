"use client";

import { useState, useMemo, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from "recharts";
import { createPortal } from "react-dom";
import type { GameListItem } from "@/lib/types";

interface RatingProgressionChartProps {
  games: GameListItem[];
}

const TIME_CLASSES = ["all", "rapid", "blitz", "bullet", "daily"] as const;

const RESULT_COLORS: Record<string, string> = {
  win: "#22c55e",
  loss: "#ef4444",
  draw: "#f59e0b",
};

interface ChartDataPoint {
  date: string;
  rating: number;
  result: string;
  opponent: string;
  opponentRating: number | null;
  movingAvg: number | null;
}

function computeMovingAverage(data: ChartDataPoint[], window: number) {
  return data.map((point, idx) => {
    if (idx < window - 1) return { ...point, movingAvg: null };
    const slice = data.slice(idx - window + 1, idx + 1);
    const avg = Math.round(slice.reduce((sum, p) => sum + p.rating, 0) / window);
    return { ...point, movingAvg: avg };
  });
}

function RatingInfoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/30" />
      <div
        className="relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl w-[340px] p-5 text-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">
            Rating Progression
          </h4>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1"
          >
            &times;
          </button>
        </div>

        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Shows your rating after each game over time. Each dot is one game,
          colored by result.
        </p>

        <h5 className="font-semibold text-xs text-zinc-800 dark:text-zinc-200 mb-1">
          Dot colors
        </h5>
        <div className="flex gap-4 text-xs text-zinc-600 dark:text-zinc-400 mb-3">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" /> Win
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" /> Loss
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" /> Draw
          </span>
        </div>

        <h5 className="font-semibold text-xs text-zinc-800 dark:text-zinc-200 mb-1">
          Trend line
        </h5>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">
          The dashed line shows a 10-game moving average to smooth out
          short-term swings and reveal the overall trend.
        </p>

        <p className="text-xs font-semibold text-blue-600 dark:text-blue-400">
          &uarr; Higher is better &mdash; an upward trend means improving!
        </p>
      </div>
    </div>,
    document.body
  );
}

// Custom dot to color by result
function ResultDot(props: any) {
  const { cx, cy, payload } = props;
  if (cx == null || cy == null) return null;
  const fill = RESULT_COLORS[payload?.result] || "#94a3b8";
  return <circle cx={cx} cy={cy} r={4} fill={fill} stroke="#fff" strokeWidth={1.5} />;
}

export function RatingProgressionChart({ games }: RatingProgressionChartProps) {
  const [showInfo, setShowInfo] = useState(false);
  const [timeClass, setTimeClass] = useState<string>("all");

  const chartData = useMemo(() => {
    let filtered = games.filter(
      (g) => g.player_rating != null && g.date_played
    );
    if (timeClass !== "all") {
      filtered = filtered.filter((g) => g.time_class === timeClass);
    }
    // Sort ascending by date
    filtered.sort((a, b) =>
      (a.date_played || "").localeCompare(b.date_played || "")
    );

    const points: ChartDataPoint[] = filtered.map((g) => ({
      date: g.date_played || "",
      rating: g.player_rating!,
      result: g.result,
      opponent: g.opponent_username || "?",
      opponentRating: g.opponent_rating,
      movingAvg: null,
    }));

    return computeMovingAverage(points, 10);
  }, [games, timeClass]);

  // Compute Y-axis domain with padding
  const [yMin, yMax] = useMemo(() => {
    if (chartData.length === 0) return [0, 1600];
    const ratings = chartData.map((d) => d.rating);
    const min = Math.min(...ratings);
    const max = Math.max(...ratings);
    const pad = Math.max(30, Math.round((max - min) * 0.1));
    return [Math.floor((min - pad) / 10) * 10, Math.ceil((max + pad) / 10) * 10];
  }, [chartData]);

  if (games.filter((g) => g.player_rating != null).length === 0) {
    return null;
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Rating Progression
        </h3>
        <button
          onClick={() => setShowInfo(true)}
          className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors"
          title="What is this chart?"
        >
          &#9432;
        </button>
      </div>

      {showInfo && <RatingInfoModal onClose={() => setShowInfo(false)} />}

      {/* Time class filter */}
      <div className="flex gap-1 mb-3 flex-wrap">
        {TIME_CLASSES.map((tc) => (
          <button
            key={tc}
            onClick={() => setTimeClass(tc)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              timeClass === tc
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {tc === "all" ? "All" : tc.charAt(0).toUpperCase() + tc.slice(1)}
          </button>
        ))}
      </div>

      {chartData.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-8">
          No rated games for this time control.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              className="fill-muted-foreground"
              tickFormatter={(v: string) => {
                if (!v) return "";
                const parts = v.split("-");
                return parts.length >= 2 ? `${parts[1]}/${parts[2] || ""}` : v;
              }}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              className="fill-muted-foreground"
              domain={[yMin, yMax]}
            />
            <RechartsTooltip
              contentStyle={{
                background: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "6px",
                color: "hsl(var(--card-foreground))",
              }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload as ChartDataPoint;
                return (
                  <div className="bg-card border border-border rounded-md p-2 text-xs shadow-lg">
                    <p className="font-medium">{d.date}</p>
                    <p>
                      Rating: <span className="font-bold">{d.rating}</span>
                    </p>
                    <p>
                      vs {d.opponent}{" "}
                      {d.opponentRating ? `(${d.opponentRating})` : ""}
                    </p>
                    <p
                      className="font-medium capitalize"
                      style={{ color: RESULT_COLORS[d.result] || "#94a3b8" }}
                    >
                      {d.result}
                    </p>
                    {d.movingAvg && (
                      <p className="text-muted-foreground mt-1">
                        10-game avg: {d.movingAvg}
                      </p>
                    )}
                  </div>
                );
              }}
            />
            {/* Rating line */}
            <Line
              type="monotone"
              dataKey="rating"
              stroke="#94a3b8"
              strokeWidth={1}
              dot={<ResultDot />}
              activeDot={{ r: 6 }}
            />
            {/* Moving average trend line */}
            <Line
              type="monotone"
              dataKey="movingAvg"
              stroke="#3b82f6"
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
