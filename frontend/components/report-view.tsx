"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ReportData } from "@/lib/types";

const QUALITY_COLORS: Record<string, string> = {
  excellent: "text-emerald-600 dark:text-emerald-400",
  good: "text-blue-600 dark:text-blue-400",
  inaccuracy: "text-yellow-600 dark:text-yellow-400",
  mistake: "text-orange-600 dark:text-orange-400",
  blunder: "text-red-600 dark:text-red-400",
};

export function ReportView({ data }: { data: ReportData }) {
  if (data.no_games) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          No games played in this period.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6 report-content">
      {/* Header */}
      <div className="text-center space-y-1 print:mb-8">
        <h2 className="text-2xl font-bold">Chess Coaching Report: {data.player_name}</h2>
        <p className="text-muted-foreground">
          {data.period_start} to {data.period_end} &middot; Generated {data.generated_at}
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Games" value={data.total_games} />
        <StatCard
          label="Results"
          value={`${data.wins}W / ${data.losses}L / ${data.draws}D`}
        />
        <StatCard label="Win Rate" value={`${data.win_rate}%`} />
        <StatCard
          label="Rating Change"
          value={data.rating_change || "N/A"}
          sub={data.start_rating && data.end_rating
            ? `${data.start_rating} → ${data.end_rating}`
            : undefined
          }
        />
      </div>

      {/* Time Control Stats */}
      {data.time_class_stats && data.time_class_stats.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Results by Time Control</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time Control</TableHead>
                  <TableHead className="text-center">Games</TableHead>
                  <TableHead className="text-center">W</TableHead>
                  <TableHead className="text-center">L</TableHead>
                  <TableHead className="text-center">D</TableHead>
                  <TableHead className="text-center">Win%</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.time_class_stats.map((tc) => (
                  <TableRow key={tc.time_class}>
                    <TableCell className="font-medium capitalize">{tc.time_class}</TableCell>
                    <TableCell className="text-center">{tc.games}</TableCell>
                    <TableCell className="text-center">{tc.wins}</TableCell>
                    <TableCell className="text-center">{tc.losses}</TableCell>
                    <TableCell className="text-center">{tc.draws}</TableCell>
                    <TableCell className="text-center">{tc.win_rate}%</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Game-by-Game Results */}
      {data.game_list && data.game_list.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Game-by-Game Results</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Color</TableHead>
                  <TableHead>Opponent</TableHead>
                  <TableHead className="text-center">Result</TableHead>
                  <TableHead className="text-center">ACPL</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.game_list.map((g, i) => (
                  <TableRow key={i}>
                    <TableCell className="text-sm">{g.date}</TableCell>
                    <TableCell className="capitalize">{g.color}</TableCell>
                    <TableCell>{g.opponent_username || g.opponent_rating || "?"}</TableCell>
                    <TableCell className="text-center">
                      <Badge variant={g.result === "win" ? "default" : g.result === "loss" ? "destructive" : "secondary"}>
                        {g.result.toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">{g.acpl ?? "N/A"}</TableCell>
                    <TableCell className="capitalize">{g.time_class}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* ACPL Analysis */}
      <Card>
        <CardHeader><CardTitle className="text-base">Average Centipawn Loss (ACPL)</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <p className="text-2xl font-bold">{data.period_acpl ?? "N/A"}</p>
          {data.acpl_interpretation && (
            <p className="text-sm text-muted-foreground">{data.acpl_interpretation}</p>
          )}
        </CardContent>
      </Card>

      {/* Move Quality */}
      {data.move_quality && (
        <Card>
          <CardHeader><CardTitle className="text-base">Move Quality Distribution</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-5 gap-3">
              {["excellent", "good", "inaccuracy", "mistake", "blunder"].map((cls) => {
                const mq = data.move_quality![cls];
                return (
                  <div key={cls} className="text-center">
                    <p className={`text-xl font-bold ${QUALITY_COLORS[cls]}`}>{mq.count}</p>
                    <p className="text-xs text-muted-foreground capitalize">{cls}</p>
                    <p className="text-xs text-muted-foreground">{mq.pct}%</p>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Phase Analysis */}
      {data.phase_analysis && (
        <Card>
          <CardHeader><CardTitle className="text-base">Game Phase Analysis</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-3 gap-4">
              {["opening", "middlegame", "endgame"].map((phase) => {
                const pd = data.phase_analysis![phase];
                const isWorst = phase === data.worst_phase;
                return (
                  <div key={phase} className={`text-center p-3 rounded-lg ${isWorst ? "bg-red-50 dark:bg-red-950/20 ring-1 ring-red-200 dark:ring-red-800" : "bg-muted/50"}`}>
                    <p className="text-lg font-bold">{pd.acpl ?? "N/A"}</p>
                    <p className="text-xs text-muted-foreground capitalize">{phase} ACPL</p>
                    <p className="text-xs text-muted-foreground">{pd.moves} moves</p>
                    {isWorst && <p className="text-xs text-red-600 dark:text-red-400 mt-1 font-medium">Focus area</p>}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Improvement Areas */}
      {data.improvement_areas && data.improvement_areas.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Top Improvement Areas</CardTitle></CardHeader>
          <CardContent>
            <ol className="space-y-3">
              {data.improvement_areas.map((area, i) => (
                <li key={i} className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary text-sm font-bold flex items-center justify-center">
                    {i + 1}
                  </span>
                  <div>
                    <p className="font-medium text-sm">{area.area}</p>
                    <p className="text-sm text-muted-foreground">{area.detail}</p>
                  </div>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {/* Critical Positions */}
      {data.critical_positions && data.critical_positions.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Critical Positions to Review</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-4">
              {data.critical_positions.map((cp, i) => (
                <div key={i} className="border-l-2 border-primary/30 pl-4 space-y-1">
                  <p className="text-sm font-medium">
                    Game on {cp.date} (vs {cp.opponent_rating || "?"}) — Move {cp.move_number} ({cp.side})
                  </p>
                  <p className="text-sm text-muted-foreground">{cp.what_happened}</p>
                  <p className="text-sm text-emerald-600 dark:text-emerald-400">Better: {cp.what_was_better}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recommendations */}
      {data.recommendations && data.recommendations.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Coaching Recommendations</CardTitle></CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {data.recommendations.map((rec, i) => (
                <li key={i} className="flex gap-2 text-sm">
                  <span className="text-primary">&#x2022;</span>
                  {rec}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Footer */}
      <p className="text-xs text-center text-muted-foreground print:mt-8">
        Report generated by Arrakis Engine
      </p>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <Card>
      <CardContent className="pt-4 pb-3 text-center">
        <p className="text-xl font-bold">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </CardContent>
    </Card>
  );
}
