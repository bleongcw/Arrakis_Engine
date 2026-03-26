"use client";

import { usePlayerContext } from "@/app/providers";
import { PlayerCard } from "@/components/player-card";

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
      <div className="text-center py-20 text-muted-foreground">
        <p className="text-lg">No players configured.</p>
        <p className="text-sm mt-2">
          Add players to <code>config.yaml</code> and run{" "}
          <code>python main.py harvest</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {players.map((player) => (
        <PlayerCard key={player.id} player={player} />
      ))}
    </div>
  );
}
