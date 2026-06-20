"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { usePlayerContext } from "@/app/providers";
import { fetchGames } from "@/lib/api";
import { GamesFilters } from "@/components/games-filters";
import { GamesTable } from "@/components/games-table";
import { ExportPgnButton } from "@/components/export-pgn-button";
import type { GameListItem } from "@/lib/types";

type SelectMode = "none" | "compare" | "export";

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
  const [selectMode, setSelectMode] = useState<SelectMode>("none");
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
    games.sort((a, b) => (b.date_played || "").localeCompare(a.date_played || ""));
    return games;
  }, [allGames, filters]);

  const isFiltered =
    filters.result !== "all" || filters.timeClass !== "all" || filters.coaching !== "all" ||
    filters.month !== "all" || filters.platform !== "all";

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleToggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const setMode = (mode: SelectMode) => {
    setSelectMode((prev) => (prev === mode ? "none" : mode));
    setSelectedIds([]);
  };

  const handleCompare = () => {
    if (selectedIds.length === 2 && player) {
      router.push(`/${player}/games/compare?games=${selectedIds[0]},${selectedIds[1]}`);
    }
  };

  // In export mode, default to the full filtered set when nothing is ticked.
  const exportIds = selectedIds.length > 0 ? selectedIds : filteredGames.map((g) => g.id);
  const exportLabel = selectedIds.length > 0 ? "Export selected" : "Export all filtered";

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
      <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
        <div className="text-sm text-muted-foreground">
          {filteredGames.length} game{filteredGames.length !== 1 ? "s" : ""}
          {isFiltered ? " (filtered)" : ""}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {selectMode === "compare" && selectedIds.length === 2 && (
            <button
              onClick={handleCompare}
              className="px-3 py-1.5 rounded-md text-xs font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            >
              Compare Selected &rarr;
            </button>
          )}
          {selectMode === "compare" && selectedIds.length > 0 && selectedIds.length < 2 && (
            <span className="text-xs text-muted-foreground">Select 1 more game</span>
          )}

          {selectMode === "export" && (
            <>
              <button
                onClick={() => setSelectedIds(filteredGames.map((g) => g.id))}
                className="px-2 py-1.5 rounded-md text-xs font-medium bg-muted text-muted-foreground hover:bg-muted/80"
              >
                Select all
              </button>
              {selectedIds.length > 0 && (
                <button
                  onClick={() => setSelectedIds([])}
                  className="px-2 py-1.5 rounded-md text-xs font-medium bg-muted text-muted-foreground hover:bg-muted/80"
                >
                  Clear
                </button>
              )}
              <ExportPgnButton gameIds={exportIds} label={exportLabel} />
            </>
          )}

          <button
            onClick={() => setMode("compare")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              selectMode === "compare"
                ? "bg-muted text-foreground ring-1 ring-border"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {selectMode === "compare" ? "Cancel Compare" : "Compare"}
          </button>
          <button
            onClick={() => setMode("export")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              selectMode === "export"
                ? "bg-muted text-foreground ring-1 ring-border"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {selectMode === "export" ? "Cancel Export" : "Export"}
          </button>
        </div>
      </div>
      <GamesTable
        games={filteredGames}
        selectable={selectMode !== "none"}
        maxSelectable={selectMode === "compare" ? 2 : undefined}
        selectedIds={selectedIds}
        onToggleSelect={handleToggleSelect}
      />
    </div>
  );
}
