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
}

const RESULT_COLORS = {
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

export function GamesTable({ games }: GamesTableProps) {
  const router = useRouter();
  const { currentPlayer } = usePlayerContext();

  return (
    <Table>
      <TableHeader>
        <TableRow>
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
        {games.map((g, idx) => (
          <TableRow
            key={g.id}
            className="cursor-pointer hover:bg-muted/50"
            onClick={() => router.push(`/${currentPlayer}/games/${g.id}`)}
          >
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
        ))}
      </TableBody>
    </Table>
  );
}
