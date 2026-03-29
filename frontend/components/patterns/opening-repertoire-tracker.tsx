"use client";

import { useState, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  Cell,
} from "recharts";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { OpeningRepertoireData } from "@/lib/types";

interface OpeningRepertoireTrackerProps {
  data: OpeningRepertoireData;
}

const ECO_LABELS: Record<string, string> = {
  A: "Flank",
  B: "Semi-Open",
  C: "Open",
  D: "Closed",
  E: "Indian",
};

const ECO_COLORS: Record<string, string> = {
  A: "#6366f1",
  B: "#f59e0b",
  C: "#22c55e",
  D: "#3b82f6",
  E: "#ec4899",
};

const TREND_DISPLAY: Record<string, { icon: string; color: string; label: string }> = {
  improving: { icon: "\u2191", color: "text-green-500", label: "Improving" },
  declining: { icon: "\u2193", color: "text-red-500", label: "Declining" },
  stable: { icon: "\u2192", color: "text-muted-foreground", label: "Stable" },
};

type SortKey = "games" | "win_rate" | "acpl" | "trend";
type ColorFilter = "all" | "white" | "black";

export function OpeningRepertoireTracker({ data }: OpeningRepertoireTrackerProps) {
  const [colorFilter, setColorFilter] = useState<ColorFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("games");
  const [sortAsc, setSortAsc] = useState(false);

  // ECO distribution chart data
  const ecoChartData = useMemo(() => {
    return ["A", "B", "C", "D", "E"]
      .map((letter) => ({
        eco: letter,
        label: `${letter} - ${ECO_LABELS[letter] || ""}`,
        games: data.eco_distribution[letter] || 0,
        color: ECO_COLORS[letter] || "#94a3b8",
      }))
      .filter((d) => d.games > 0);
  }, [data.eco_distribution]);

  // Filtered and sorted openings
  const filteredOpenings = useMemo(() => {
    let openings = data.openings;
    if (colorFilter !== "all") {
      openings = openings.filter(
        (o) => o.color === colorFilter || o.color === "both"
      );
    }

    const trendOrder = { improving: 1, stable: 2, declining: 3 };
    openings = [...openings].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "games") cmp = a.games - b.games;
      else if (sortKey === "win_rate") cmp = a.win_rate - b.win_rate;
      else if (sortKey === "acpl") cmp = a.acpl - b.acpl;
      else if (sortKey === "trend")
        cmp = (trendOrder[a.trend] || 2) - (trendOrder[b.trend] || 2);
      return sortAsc ? cmp : -cmp;
    });

    return openings;
  }, [data.openings, colorFilter, sortKey, sortAsc]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return "";
    return sortAsc ? " \u25B2" : " \u25BC";
  };

  return (
    <div>
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4">
        Opening Repertoire
      </h3>

      {/* ECO Distribution Chart */}
      {ecoChartData.length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-muted-foreground mb-2">
            Games by ECO classification
          </p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={ecoChartData} layout="horizontal">
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11 }}
                className="fill-muted-foreground"
              />
              <YAxis
                tick={{ fontSize: 11 }}
                className="fill-muted-foreground"
                allowDecimals={false}
              />
              <RechartsTooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "6px",
                  color: "hsl(var(--card-foreground))",
                }}
                formatter={(value) => [`${value} games`, "Games"]}
              />
              <Bar dataKey="games" radius={[4, 4, 0, 0]}>
                {ecoChartData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Color filter tabs */}
      <div className="flex gap-1 mb-3">
        {(["all", "white", "black"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setColorFilter(tab)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              colorFilter === tab
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {tab === "all" ? "All" : tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Opening table with trends */}
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Opening</TableHead>
              <TableHead className="hidden sm:table-cell">ECO</TableHead>
              <TableHead
                className="text-center cursor-pointer select-none"
                onClick={() => handleSort("games")}
              >
                Games{sortIndicator("games")}
              </TableHead>
              <TableHead
                className="text-center cursor-pointer select-none"
                onClick={() => handleSort("win_rate")}
              >
                Win%{sortIndicator("win_rate")}
              </TableHead>
              <TableHead
                className="text-center cursor-pointer select-none hidden sm:table-cell"
                onClick={() => handleSort("trend")}
              >
                Trend{sortIndicator("trend")}
              </TableHead>
              <TableHead
                className="text-center cursor-pointer select-none hidden md:table-cell"
                onClick={() => handleSort("acpl")}
              >
                ACPL{sortIndicator("acpl")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredOpenings.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground py-6">
                  No openings for this filter.
                </TableCell>
              </TableRow>
            ) : (
              filteredOpenings.map((o) => {
                const trend = TREND_DISPLAY[o.trend] || TREND_DISPLAY.stable;
                return (
                  <TableRow key={`${o.name}-${o.color}`}>
                    <TableCell className="text-sm font-medium max-w-[200px] truncate">
                      {o.name}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground font-mono hidden sm:table-cell">
                      {o.eco || "\u2014"}
                    </TableCell>
                    <TableCell className="text-center text-sm">{o.games}</TableCell>
                    <TableCell className="text-center text-sm">
                      <span
                        className={
                          o.win_rate >= 60
                            ? "text-green-500 font-medium"
                            : o.win_rate < 40
                            ? "text-red-500 font-medium"
                            : ""
                        }
                      >
                        {o.win_rate}%
                      </span>
                    </TableCell>
                    <TableCell className={`text-center hidden sm:table-cell ${trend.color}`}>
                      <span title={trend.label}>
                        {trend.icon} {trend.label}
                      </span>
                    </TableCell>
                    <TableCell className="text-center text-sm hidden md:table-cell">
                      {o.acpl > 0 ? o.acpl : "\u2014"}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Focus Areas */}
      {data.focus_areas.length > 0 && (
        <div className="mt-6">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            Focus Areas
          </h4>
          <div className="space-y-3">
            {data.focus_areas.map((fa, i) => (
              <div
                key={i}
                className="border-l-2 border-amber-400 dark:border-amber-500 pl-4 py-1"
              >
                <p className="text-sm font-medium">
                  {fa.name}
                  {fa.eco && (
                    <span className="ml-2 text-xs text-muted-foreground font-mono">
                      {fa.eco}
                    </span>
                  )}
                </p>
                <p className="text-xs text-muted-foreground">
                  {fa.games} games &middot; {fa.win_rate}% win rate &middot;
                  ACPL {fa.acpl}
                </p>
                <p className="text-xs text-red-500 dark:text-red-400 mt-0.5">
                  {fa.reason}
                </p>
                <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-0.5">
                  {fa.suggestion}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
