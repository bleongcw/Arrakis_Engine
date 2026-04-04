"use client";

import { usePlayerContext } from "@/app/providers";
import { PlayerCard } from "@/components/player-card";
import { PipelineControlPanel } from "@/components/pipeline-control-panel";

export default function DashboardPage() {
  const { players, loading } = usePlayerContext();

  if (loading) {
    return (
      <div className="space-y-6">
        {[1, 2].map((i) => (
          <div
            key={i}
            className="h-48 rounded-lg bg-muted animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (players.length === 0) {
    return (
      <div className="space-y-6">
        <PipelineControlPanel />
        <div className="text-center py-20 text-muted-foreground">
          <p className="text-lg">No players configured.</p>
          <p className="text-sm mt-2">
            Go to{" "}
            <a href="/settings" className="text-blue-600 dark:text-blue-400 underline">
              Settings
            </a>{" "}
            to add players, then run the pipeline.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PipelineControlPanel />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {players.map((player) => (
          <PlayerCard key={player.id} player={player} />
        ))}
      </div>
    </div>
  );
}
