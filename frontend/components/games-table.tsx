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
          <TableHead className="w-[40px]">#</TableHead>
          <TableHead>Date</TableHead>
          <TableHead className="text-center">Platform</TableHead>
          <TableHead className="text-center">Color</TableHead>
          <TableHead>Player</TableHead>
          <TableHead>Opponent</TableHead>
          <TableHead>Result</TableHead>
          <TableHead>Time</TableHead>
          <TableHead className="text-center">Analysis</TableHead>
          <TableHead className="text-center">Coaching</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {games.map((g, idx) => (
          <TableRow
            key={g.id}
            className="cursor-pointer hover:bg-muted/50"
            onClick={() => router.push(`/${currentPlayer}/games/${g.id}`)}
          >
            <TableCell className="text-muted-foreground text-xs">
              {idx + 1}
            </TableCell>
            <TableCell>{g.date_played || "\u2014"}</TableCell>
            <TableCell className="text-center" title={g.platform === "lichess" ? "Lichess" : "Chess.com"}>
              {g.platform === "lichess" ? "\u265E" : "\u265C"}
            </TableCell>
            <TableCell className="text-center">
              {g.player_color === "white" ? "\u2654" : "\u265A"}
            </TableCell>
            <TableCell>
              {g.display_name || g.username} ({g.player_rating || "?"})
            </TableCell>
            <TableCell>
              {g.opponent_username || "?"} ({g.opponent_rating || "?"})
            </TableCell>
            <TableCell className={cn("font-medium", RESULT_COLORS[g.result])}>
              {g.result.toUpperCase()}
            </TableCell>
            <TableCell>{g.time_class || "?"}</TableCell>
            <TableCell className="text-center" title={g.analysis_status}>
              {STATUS_ICONS[g.analysis_status] || "\u23F3"}
            </TableCell>
            <TableCell className="text-center" title={g.coaching_status}>
              {STATUS_ICONS[g.coaching_status] || "\u23F3"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
