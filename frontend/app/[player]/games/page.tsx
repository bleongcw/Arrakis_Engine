"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { usePlayerContext } from "@/app/providers";
import { fetchGames } from "@/lib/api";
import { GamesFilters } from "@/components/games-filters";
import { GamesTable } from "@/components/games-table";
import type { GameListItem } from "@/lib/types";

export default function GamesPage() {
  const { player } = useParams<{ player: string }>();
  const router = useRouter();
  const { loading: playerLoading } = usePlayerContext();
  const [allGames, setAllGames] = useState<GameListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    result: "all",
    timeClass: "all",
    coaching: "all",
    month: "all",
    platform: "all",
  });
  const [compareMode, setCompareMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  useEffect(() => {
    if (!player) return;
    setLoading(true);
    fetchGames(player)
      .then(setAllGames)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [player]);

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

  const handleToggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleCompare = () => {
    if (selectedIds.length === 2 && player) {
      router.push(`/${player}/games/compare?games=${selectedIds[0]},${selectedIds[1]}`);
    }
  };

  const toggleCompareMode = () => {
    setCompareMode((prev) => !prev);
    setSelectedIds([]);
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
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm text-muted-foreground">
          {filteredGames.length} game{filteredGames.length !== 1 ? "s" : ""}
          {filters.result !== "all" || filters.timeClass !== "all" || filters.coaching !== "all" || filters.month !== "all" || filters.platform !== "all"
            ? " (filtered)"
            : ""}
        </div>
        <div className="flex items-center gap-2">
          {compareMode && selectedIds.length === 2 && (
            <button
              onClick={handleCompare}
              className="px-3 py-1.5 rounded-md text-xs font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            >
              Compare Selected &rarr;
            </button>
          )}
          {compareMode && selectedIds.length > 0 && selectedIds.length < 2 && (
            <span className="text-xs text-muted-foreground">
              Select 1 more game
            </span>
          )}
          <button
            onClick={toggleCompareMode}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              compareMode
                ? "bg-muted text-foreground ring-1 ring-border"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {compareMode ? "Cancel Compare" : "Compare"}
          </button>
        </div>
      </div>
      <GamesTable
        games={filteredGames}
        compareMode={compareMode}
        selectedIds={selectedIds}
        onToggleSelect={handleToggleSelect}
      />
    </div>
  );
}
