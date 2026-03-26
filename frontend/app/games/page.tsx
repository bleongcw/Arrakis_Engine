"use client";

import { useEffect, useState, useMemo } from "react";
import { usePlayerContext } from "@/app/providers";
import { fetchGames } from "@/lib/api";
import { GamesFilters } from "@/components/games-filters";
import { GamesTable } from "@/components/games-table";
import type { GameListItem } from "@/lib/types";

export default function GamesPage() {
  const { currentPlayer, loading: playerLoading } = usePlayerContext();
  const [allGames, setAllGames] = useState<GameListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    result: "all",
    timeClass: "all",
    coaching: "all",
    month: "all",
    platform: "all",
  });

  useEffect(() => {
    if (!currentPlayer) return;
    setLoading(true);
    fetchGames(currentPlayer)
      .then(setAllGames)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [currentPlayer]);

  const filteredGames = useMemo(() => {
    let games = [...allGames];
    if (filters.result !== "all") games = games.filter((g) => g.result === filters.result);
    if (filters.timeClass !== "all") games = games.filter((g) => g.time_class === filters.timeClass);
    if (filters.coaching !== "all") games = games.filter((g) => g.coaching_status === filters.coaching);
    if (filters.month !== "all") games = games.filter((g) => g.date_played?.startsWith(filters.month));
    if (filters.platform !== "all") games = games.filter((g) => (g.platform || "chess.com") === filters.platform);
    // Sort by latest date first
    games.sort((a, b) => (b.date_played || "").localeCompare(a.date_played || ""));
    return games;
  }, [allGames, filters]);

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  if (playerLoading || loading) {
    return <div className="h-96 rounded-lg bg-muted animate-pulse" />;
  }

  return (
    <div>
      <GamesFilters
        games={allGames}
        filters={filters}
        onFilterChange={handleFilterChange}
      />
      <div className="text-sm text-muted-foreground mb-3">
        {filteredGames.length} game{filteredGames.length !== 1 ? "s" : ""}
        {filters.result !== "all" || filters.timeClass !== "all" || filters.coaching !== "all" || filters.month !== "all" || filters.platform !== "all"
          ? " (filtered)"
          : ""}
      </div>
      <GamesTable games={filteredGames} />
    </div>
  );
}
