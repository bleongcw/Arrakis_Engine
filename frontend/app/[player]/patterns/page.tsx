"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { usePlayerContext } from "@/app/providers";
import { fetchPatterns, fetchGames } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { RatingProgressionChart } from "@/components/patterns/rating-progression-chart";
import { ACPLTrendChart } from "@/components/patterns/acpl-trend-chart";
import { MoveQualityDonut } from "@/components/patterns/move-quality-donut";
import { PhasePerformance } from "@/components/patterns/phase-performance";
import { OpeningPerformance } from "@/components/patterns/opening-performance";
import { DangerZones } from "@/components/patterns/danger-zones";
import { EndgameConversion } from "@/components/patterns/endgame-conversion";
import { TimeControlPerformance } from "@/components/patterns/time-control-performance";
import { CriticalPositions } from "@/components/patterns/critical-positions";
import { ComebackCollapse } from "@/components/patterns/comeback-collapse";
import { OpeningACPL } from "@/components/patterns/opening-acpl";
import { TacticalMisses } from "@/components/patterns/tactical-misses";
import { RepertoireConsistency } from "@/components/patterns/repertoire-consistency";
import { OpeningRepertoireTracker } from "@/components/patterns/opening-repertoire-tracker";
import { TimePressure } from "@/components/patterns/time-pressure";
import { TrendSummary } from "@/components/patterns/trend-summary";
import type { PatternStats, GameListItem } from "@/lib/types";

export default function PatternsPage() {
  const { player } = useParams<{ player: string }>();
  const { loading: playerLoading } = usePlayerContext();
  const [stats, setStats] = useState<PatternStats | null>(null);
  const [games, setGames] = useState<GameListItem[]>([]);
  const [trendSummary, setTrendSummary] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadPatterns = useCallback(() => {
    if (!player) return;
    setLoading(true);
    Promise.all([
      fetchPatterns(player),
      fetchGames(player),
    ])
      .then(([patternData, gamesData]: [any, GameListItem[]]) => {
        setStats(patternData.stats);
        setTrendSummary(patternData.trend_summary || null);
        setGames(gamesData);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [player]);

  useEffect(() => {
    loadPatterns();
  }, [loadPatterns]);

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

  const accuracy = stats.accuracy as any;
  const consistency = stats.consistency as any;

  return (
    <div className="space-y-6">
      {/* Coaching Trend Summary */}
      {player && (
        <TrendSummary
          summary={trendSummary}
          player={player}
          onSummaryGenerated={loadPatterns}
        />
      )}

      {/* Overview Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard
          label="Total Games"
          value={stats.total_games}
          tooltip="Number of analyzed games in the database"
        />
        <StatCard
          label="Win Rate"
          value={`${stats.results.win_rate.toFixed(1)}%`}
          subtitle={`${stats.results.wins}W / ${stats.results.losses}L / ${stats.results.draws}D`}
          tooltip="Percentage of games won across all time controls"
        />
        <StatCard
          label="Accuracy"
          value={accuracy ? `${accuracy.overall_pct}%` : "—"}
          subtitle={
            accuracy
              ? `${accuracy.best_moves}/${accuracy.total_moves} best moves`
              : undefined
          }
          tooltip="Percentage of moves matching Stockfish's top engine choice"
        />
        <StatCard
          label="Avg ACPL"
          value={consistency ? consistency.mean_acpl : "—"}
          subtitle={
            consistency
              ? `Best: ${consistency.best_acpl} / Worst: ${consistency.worst_acpl}`
              : undefined
          }
          tooltip="Average Centipawn Loss per move. Lower is better — under 50 is good, under 25 is strong"
        />
        <StatCard
          label="Consistency"
          value={consistency ? consistency.rating : "—"}
          subtitle={
            consistency ? `σ = ${consistency.std_dev}` : undefined
          }
          tooltip="How consistent your play is game-to-game. σ (standard deviation) measures variation in ACPL — lower means more consistent"
        />
        <StatCard
          label="vs Higher Rated"
          value={`${stats.rating_performance?.vs_higher?.win_rate?.toFixed(0) || 0}%`}
          subtitle={`${stats.rating_performance?.vs_higher?.games || 0} games`}
          tooltip="Win rate against opponents rated higher than you"
        />
      </div>

      {/* Rating Progression - full width */}
      {games.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <RatingProgressionChart games={games} />
          </CardContent>
        </Card>
      )}

      {/* ACPL Trend - full width */}
      <Card>
        <CardContent className="pt-6">
          <ACPLTrendChart data={stats.acpl_trend || []} />
        </CardContent>
      </Card>

      {/* Move Quality + Danger Zones side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardContent className="pt-6">
            <MoveQualityDonut data={stats.move_quality} />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <DangerZones data={stats.danger_zones as any} />
          </CardContent>
        </Card>
      </div>

      {/* Phase Performance + Endgame Conversion side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardContent className="pt-6">
            <PhasePerformance data={stats.phase_analysis} />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <EndgameConversion data={stats.endgame_conversion as any} />
          </CardContent>
        </Card>
      </div>

      {/* Critical Positions + Tactical Misses side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardContent className="pt-6">
            <CriticalPositions data={stats.critical_positions as any} />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <TacticalMisses data={stats.tactical_misses as any} />
          </CardContent>
        </Card>
      </div>

      {/* Comeback/Collapse + Repertoire Consistency side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardContent className="pt-6">
            <ComebackCollapse data={stats.comeback_collapse as any} />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <RepertoireConsistency data={stats.repertoire_consistency as any} />
          </CardContent>
        </Card>
      </div>

      {/* Opening Repertoire Tracker - full width */}
      {stats.opening_repertoire && (
        <Card>
          <CardContent className="pt-6">
            <OpeningRepertoireTracker data={stats.opening_repertoire} />
          </CardContent>
        </Card>
      )}

      {/* Time Control Performance - full width */}
      <Card>
        <CardContent className="pt-6">
          <TimeControlPerformance
            data={stats.time_control_performance as any}
          />
        </CardContent>
      </Card>

      {/* Time Pressure Analysis - full width */}
      {stats.time_pressure && (
        <Card>
          <CardContent className="pt-6">
            <TimePressure data={stats.time_pressure} />
          </CardContent>
        </Card>
      )}


      {/* Opening Quality Analysis - full width */}
      <Card>
        <CardContent className="pt-6">
          <OpeningACPL data={stats.opening_acpl as any} />
        </CardContent>
      </Card>

      {/* Opening Win Rate Performance - full width */}
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
  tooltip,
}: {
  label: string;
  value: string | number;
  subtitle?: string;
  tooltip?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-5 pb-4">
        <div className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
          {label}
          {tooltip && (
            <span
              title={tooltip}
              className="cursor-help text-muted-foreground/60 hover:text-muted-foreground transition-colors"
            >
              &#9432;
            </span>
          )}
        </div>
        <div className="text-2xl font-bold mt-1">{value}</div>
        {subtitle && (
          <div className="text-xs text-muted-foreground mt-1">{subtitle}</div>
        )}
      </CardContent>
    </Card>
  );
}
