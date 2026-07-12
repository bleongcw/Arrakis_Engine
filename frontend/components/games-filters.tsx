"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { GameListItem } from "@/lib/types";

interface GamesFiltersProps {
  games: GameListItem[];
  filters: {
    result: string;
    timeClass: string;
    coaching: string;
    month: string;
    platform: string;
  };
  onFilterChange: (key: string, value: string) => void;
}

export function GamesFilters({ games, filters, onFilterChange }: GamesFiltersProps) {
  // Extract unique time classes and months from data
  const timeClasses = [...new Set(games.map((g) => g.time_class).filter(Boolean))] as string[];
  const months = [
    ...new Set(
      games
        .map((g) => g.date_played?.substring(0, 7))
        .filter(Boolean)
    ),
  ].sort().reverse() as string[];

  return (
    <div className="flex flex-wrap gap-3 mb-4">
      <Select value={filters.result} onValueChange={(v) => onFilterChange("result", v ?? "all")}>
        <SelectTrigger className="w-[140px]"><SelectValue placeholder="All Results" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Results</SelectItem>
          <SelectItem value="win">Wins</SelectItem>
          <SelectItem value="loss">Losses</SelectItem>
          <SelectItem value="draw">Draws</SelectItem>
        </SelectContent>
      </Select>

      <Select value={filters.timeClass} onValueChange={(v) => onFilterChange("timeClass", v ?? "all")}>
        <SelectTrigger className="w-[160px]"><SelectValue placeholder="All Time Controls" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Time Controls</SelectItem>
          {timeClasses.map((tc) => (
            <SelectItem key={tc} value={tc}>{tc}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={filters.coaching} onValueChange={(v) => onFilterChange("coaching", v ?? "all")}>
        <SelectTrigger className="w-[170px]"><SelectValue placeholder="All Coaching Status" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Coaching</SelectItem>
          <SelectItem value="complete">Coached</SelectItem>
          <SelectItem value="pending">Pending</SelectItem>
          <SelectItem value="error">Error</SelectItem>
        </SelectContent>
      </Select>

      <Select value={filters.month} onValueChange={(v) => onFilterChange("month", v ?? "all")}>
        <SelectTrigger className="w-[150px]"><SelectValue placeholder="All Months" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Months</SelectItem>
          {months.map((m) => (
            <SelectItem key={m} value={m}>{m}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={filters.platform} onValueChange={(v) => onFilterChange("platform", v ?? "all")}>
        <SelectTrigger className="w-[150px]"><SelectValue placeholder="All Platforms" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Platforms</SelectItem>
          <SelectItem value="chess.com">{"\u265C"} Chess.com</SelectItem>
          <SelectItem value="lichess">{"\u265E"} Lichess</SelectItem>
          <SelectItem value="competition">{"\uD83C\uDFC6"} Competition</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
