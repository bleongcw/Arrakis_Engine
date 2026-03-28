"use client";

import { useEffect, useState, useRef } from "react";
import { usePlayerContext } from "@/app/providers";
import { fetchReport } from "@/lib/api";
import { ReportView } from "@/components/report-view";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ReportData } from "@/lib/types";

export default function ReportsPage() {
  const { currentPlayer, selectedPlayer, loading: playerLoading } = usePlayerContext();
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState<"weekly" | "monthly">("monthly");
  const reportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!currentPlayer) return;
    setLoading(true);
    fetchReport(currentPlayer, period)
      .then(setReport)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [currentPlayer, period]);

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
        <div className="flex gap-2">
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
        <Button variant="outline" size="sm" onClick={handleExportPDF}>
          Export PDF
        </Button>
      </div>

      {/* Report content */}
      <div ref={reportRef}>
        <ReportView data={report} />
      </div>
    </div>
  );
}
