"use client";

import { Fragment, useState } from "react";
import { useParams } from "next/navigation";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { OpeningExplorer } from "./opening-explorer";
import type { OpeningEntry } from "@/lib/types";

interface OpeningPerformanceProps {
  openings: {
    all?: OpeningEntry[];
    white?: OpeningEntry[];
    black?: OpeningEntry[];
  } | OpeningEntry[];
}

function OpeningTable({
  openings,
  boardOrientation,
}: {
  openings: OpeningEntry[];
  boardOrientation: "white" | "black";
}) {
  const { player } = useParams<{ player: string }>();
  const [expandedOpening, setExpandedOpening] = useState<string | null>(null);

  if (!openings || openings.length === 0) {
    return <p className="text-sm text-muted-foreground py-4">No data available.</p>;
  }

  const toggleOpening = (name: string) => {
    setExpandedOpening((prev) => (prev === name ? null : name));
  };

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[20px]"></TableHead>
          <TableHead>Opening</TableHead>
          <TableHead className="text-right">Games</TableHead>
          <TableHead className="text-right">Wins</TableHead>
          <TableHead className="text-right">Losses</TableHead>
          <TableHead className="text-right">Win%</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {openings.map((o, i) => {
          const isExpanded = expandedOpening === o.name;
          const hasExplorer = o.opening_moves && o.game_list && o.game_list.length > 0;
          return (
            <Fragment key={`opening-${i}`}>
              <TableRow
                className={hasExplorer ? "cursor-pointer hover:bg-muted/50" : ""}
                onClick={() => hasExplorer && toggleOpening(o.name)}
              >
                <TableCell className="text-muted-foreground text-xs w-[20px] px-2">
                  {hasExplorer ? (isExpanded ? "▼" : "▶") : ""}
                </TableCell>
                <TableCell className="font-medium">{o.name}</TableCell>
                <TableCell className="text-right">{o.games}</TableCell>
                <TableCell className="text-right text-green-500">{o.wins}</TableCell>
                <TableCell className="text-right text-red-500">{o.losses}</TableCell>
                <TableCell className="text-right font-semibold">
                  {o.win_rate.toFixed(0)}%
                </TableCell>
              </TableRow>
              {isExpanded && hasExplorer && player && (
                <TableRow>
                  <TableCell colSpan={6} className="p-2">
                    <OpeningExplorer
                      openingName={o.name}
                      openingMoves={o.opening_moves!}
                      gameList={o.game_list!}
                      playerUsername={player}
                      boardOrientation={boardOrientation}
                    />
                  </TableCell>
                </TableRow>
              )}
            </Fragment>
          );
        })}
      </TableBody>
    </Table>
  );
}

export function OpeningPerformance({ openings }: OpeningPerformanceProps) {
  // Handle both array and dict formats
  let allOpenings: OpeningEntry[] = [];
  let whiteOpenings: OpeningEntry[] = [];
  let blackOpenings: OpeningEntry[] = [];

  if (Array.isArray(openings)) {
    allOpenings = openings;
  } else if (openings && typeof openings === "object") {
    allOpenings = openings.all || [];
    whiteOpenings = openings.white || [];
    blackOpenings = openings.black || [];
  }

  return (
    <div>
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        Opening Performance
      </h3>
      <Tabs defaultValue="all">
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="white">{"\u2654"} White</TabsTrigger>
          <TabsTrigger value="black">{"\u265A"} Black</TabsTrigger>
        </TabsList>
        <TabsContent value="all">
          <OpeningTable openings={allOpenings} boardOrientation="white" />
        </TabsContent>
        <TabsContent value="white">
          <OpeningTable openings={whiteOpenings} boardOrientation="white" />
        </TabsContent>
        <TabsContent value="black">
          <OpeningTable openings={blackOpenings} boardOrientation="black" />
        </TabsContent>
      </Tabs>
    </div>
  );
}
