"use client";

import { useEffect, useState } from "react";
import { usePlayerContext } from "@/app/providers";
import { fetchPatterns } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { ACPLTrendChart } from "@/components/patterns/acpl-trend-chart";
import { MoveQualityDonut } from "@/components/patterns/move-quality-donut";
import { OpeningPerformance } from "@/components/patterns/opening-performance";
import type { PatternStats } from "@/lib/types";

export default function PatternsPage() {
  const { currentPlayer, loading: playerLoading } = usePlayerContext();
  const [stats, setStats] = useState<PatternStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentPlayer) return;
    setLoading(true);
    fetchPatterns(currentPlayer)
      .then((data) => setStats(data.stats))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [currentPlayer]);

  if (playerLoading || loading) {
    return <div className="h-96 rounded-lg bg-muted animate-pulse" />;
  }

  if (!stats) {
    return (
      <div className="text-center py-20 text-muted-foreground">
        <p>No pattern data available.</p>
        <p className="text-sm mt-2">
          Run <code>python main.py patterns</code> to generate stats.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Games"
          value={stats.total_games}
        />
        <StatCard
          label="Win Rate"
          value={`${stats.results.win_rate.toFixed(1)}%`}
          subtitle={`${stats.results.wins}W / ${stats.results.losses}L / ${stats.results.draws}D`}
        />
        <StatCard
          label="vs Higher Rated"
          value={`${stats.rating_performance?.vs_higher?.win_rate?.toFixed(0) || 0}%`}
          subtitle={`${stats.rating_performance?.vs_higher?.games || 0} games`}
        />
        <StatCard
          label="vs Lower Rated"
          value={`${stats.rating_performance?.vs_lower?.win_rate?.toFixed(0) || 0}%`}
          subtitle={`${stats.rating_performance?.vs_lower?.games || 0} games`}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardContent className="pt-6">
            <ACPLTrendChart data={stats.acpl_trend || []} />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <MoveQualityDonut data={stats.move_quality} />
          </CardContent>
        </Card>
      </div>

      {/* Opening Performance */}
      <Card>
        <CardContent className="pt-6">
          <OpeningPerformance openings={stats.openings || {}} />
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  label,
  value,
  subtitle,
}: {
  label: string;
  value: string | number;
  subtitle?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="text-xs text-muted-foreground uppercase tracking-wider">
          {label}
        </div>
        <div className="text-3xl font-bold mt-1">{value}</div>
        {subtitle && (
          <div className="text-sm text-muted-foreground mt-1">{subtitle}</div>
        )}
      </CardContent>
    </Card>
  );
}
