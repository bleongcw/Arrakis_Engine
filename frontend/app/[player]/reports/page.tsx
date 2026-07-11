"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { usePlayerContext } from "@/app/providers";
import { fetchReport } from "@/lib/api";
import { ReportView } from "@/components/report-view";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ReportData } from "@/lib/types";

// v1.24.2: the Reports time-class filter is DATA-DRIVEN — chips are derived
// from the time classes actually present in the report (report.py already
// aggregates every `time_class` in the DB), so Blitz/Bullet appear
// automatically when the player has those games. No hardcoded list to
// maintain; `report-view.tsx` already filters generically by class.
const TIME_CLASS_ORDER = ["bullet", "blitz", "rapid", "daily"];
const CLASS_LABELS: Record<string, string> = {
  bullet: "Bullet",
  blitz: "Blitz",
  rapid: "Rapid",
  daily: "Daily",
};

export function buildTimeClassChips(report: ReportData): {
  chips: { key: string; label: string }[];
  defaultKey: string;
} {
  const present = Array.from(
    new Set(
      (report.time_class_stats || [])
        .map((t) => t.time_class)
        .filter((tc): tc is string => Boolean(tc)),
    ),
  ).sort((a, b) => {
    // Canonical time-control order; unknown classes sort after, alphabetically.
    const ra = TIME_CLASS_ORDER.indexOf(a);
    const rb = TIME_CLASS_ORDER.indexOf(b);
    return (ra === -1 ? 99 : ra) - (rb === -1 ? 99 : rb) || a.localeCompare(b);
  });

  const chips = present.map((k) => ({
    key: k,
    label: CLASS_LABELS[k] ?? k.charAt(0).toUpperCase() + k.slice(1),
  }));
  chips.push({ key: "all", label: "All" });

  // Default to Rapid (product choice); fall back to the first class the player
  // actually has — or "All" — so the default view is never empty.
  const defaultKey = present.includes("rapid") ? "rapid" : present[0] ?? "all";
  return { chips, defaultKey };
}

export default function ReportsPage() {
  const { player } = useParams<{ player: string }>();
  const { loading: playerLoading } = usePlayerContext();
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState<"weekly" | "monthly">("monthly");
  const [timeClass, setTimeClass] = useState<string>("rapid");
  const reportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!player) return;
    setLoading(true);
    fetchReport(player, period)
      .then(setReport)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [player, period]);

  // Derive the filter chips + a sensible default from the loaded report.
  // MUST run before the loading / no-report early returns below (hooks can't
  // be conditional), so it tolerates a null report.
  const { chips, defaultKey } = useMemo(
    () =>
      report ? buildTimeClassChips(report) : { chips: [], defaultKey: "rapid" },
    [report],
  );

  // If the current selection isn't available in the loaded report (e.g. a
  // rapid-less player, or a period switch that dropped the class), fall back
  // to the default so the view is never empty.
  useEffect(() => {
    if (!report) return;
    if (!chips.some((c) => c.key === timeClass)) setTimeClass(defaultKey);
  }, [report, chips, defaultKey, timeClass]);

  const handleExportPDF = () => {
    window.print();
  };

  if (playerLoading || loading) {
    return (
      <div className="space-y-4">
        <div className="h-10 w-64 rounded bg-muted animate-pulse" />
        <div className="h-96 rounded-lg bg-muted animate-pulse" />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No report data available. Run analysis and coaching first.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Controls — hidden when printing */}
      <div className="flex items-center justify-between print:hidden">
        <div className="flex gap-4">
          {/* Period selector */}
          <div className="flex gap-1">
            {(["monthly", "weekly"] as const).map((p) => (
              <Button
                key={p}
                variant={period === p ? "default" : "outline"}
                size="sm"
                className={cn(
                  period === p && "bg-[#1e40af] text-white hover:bg-[#1e3a8a]"
                )}
                onClick={() => setPeriod(p)}
              >
                {p === "monthly" ? "Monthly" : "Weekly"}
              </Button>
            ))}
          </div>
          {/* Time class selector */}
          <div className="flex gap-1 border-l pl-4">
            {chips.map((tc) => (
              <Button
                key={tc.key}
                variant={timeClass === tc.key ? "default" : "outline"}
                size="sm"
                className={cn(
                  timeClass === tc.key && "bg-[#1e40af] text-white hover:bg-[#1e3a8a]"
                )}
                onClick={() => setTimeClass(tc.key)}
              >
                {tc.label}
              </Button>
            ))}
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={handleExportPDF}>
          Export PDF
        </Button>
      </div>

      {/* Report content */}
      <div ref={reportRef}>
        <ReportView data={report} timeClassFilter={timeClass} playerUsername={player} />
      </div>
    </div>
  );
}
