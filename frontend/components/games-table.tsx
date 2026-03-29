"use client";

import { useRouter } from "next/navigation";
import { usePlayerContext } from "@/app/providers";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { GameListItem } from "@/lib/types";

interface GamesTableProps {
  games: GameListItem[];
  compareMode?: boolean;
  selectedIds?: number[];
  onToggleSelect?: (id: number) => void;
}

const RESULT_COLORS: Record<string, string> = {
  win: "text-green-500",
  loss: "text-red-500",
  draw: "text-yellow-500",
};

const STATUS_ICONS: Record<string, string> = {
  complete: "\u2705",
  analyzing: "\uD83D\uDD04",
  error: "\u274C",
  pending: "\u23F3",
};

export function GamesTable({
  games,
  compareMode = false,
  selectedIds = [],
  onToggleSelect,
}: GamesTableProps) {
  const router = useRouter();
  const { currentPlayer } = usePlayerContext();

  const selectedSet = new Set(selectedIds);
  const maxSelected = selectedIds.length >= 2;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {compareMode && (
            <TableHead className="w-[40px] text-center">&nbsp;</TableHead>
          )}
          <TableHead className="w-[40px] hidden sm:table-cell">#</TableHead>
          <TableHead>Date</TableHead>
          <TableHead className="text-center hidden md:table-cell">Platform</TableHead>
          <TableHead className="text-center hidden sm:table-cell">Color</TableHead>
          <TableHead className="hidden lg:table-cell">Player</TableHead>
          <TableHead>Opponent</TableHead>
          <TableHead>Result</TableHead>
          <TableHead className="hidden sm:table-cell">Time</TableHead>
          <TableHead className="text-center hidden md:table-cell">Analysis</TableHead>
          <TableHead className="text-center hidden md:table-cell">Coaching</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {games.map((g, idx) => {
          const isSelected = selectedSet.has(g.id);
          return (
            <TableRow
              key={g.id}
              className={cn(
                "cursor-pointer hover:bg-muted/50",
                isSelected && "bg-blue-50 dark:bg-blue-950/30"
              )}
              onClick={() => {
                if (compareMode && onToggleSelect) {
                  if (isSelected || !maxSelected) {
                    onToggleSelect(g.id);
                  }
                } else {
                  router.push(`/${currentPlayer}/games/${g.id}`);
                }
              }}
            >
              {compareMode && (
                <TableCell className="text-center">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    disabled={!isSelected && maxSelected}
                    onChange={() => onToggleSelect?.(g.id)}
                    onClick={(e) => e.stopPropagation()}
                    className="h-4 w-4 rounded border-gray-300 accent-blue-600"
                  />
                </TableCell>
              )}
              <TableCell className="text-muted-foreground text-xs hidden sm:table-cell">
                {idx + 1}
              </TableCell>
              <TableCell className="text-sm">{g.date_played || "\u2014"}</TableCell>
              <TableCell className="text-center hidden md:table-cell" title={g.platform === "lichess" ? "Lichess" : "Chess.com"}>
                {g.platform === "lichess" ? "\u265E" : "\u265C"}
              </TableCell>
              <TableCell className="text-center hidden sm:table-cell">
                {g.player_color === "white" ? "\u2654" : "\u265A"}
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                {g.display_name || g.username} ({g.player_rating || "?"})
              </TableCell>
              <TableCell className="text-sm">
                {g.opponent_username || "?"} ({g.opponent_rating || "?"})
              </TableCell>
              <TableCell className={cn("font-medium", RESULT_COLORS[g.result])}>
                {g.result.toUpperCase()}
              </TableCell>
              <TableCell className="hidden sm:table-cell">{g.time_class || "?"}</TableCell>
              <TableCell className="text-center hidden md:table-cell" title={g.analysis_status}>
                {STATUS_ICONS[g.analysis_status] || "\u23F3"}
              </TableCell>
              <TableCell className="text-center hidden md:table-cell" title={g.coaching_status}>
                {STATUS_ICONS[g.coaching_status] || "\u23F3"}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
