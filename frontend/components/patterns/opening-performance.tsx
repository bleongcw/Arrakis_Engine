"use client";

import { Fragment, useState, useEffect } from "react";
import { createPortal } from "react-dom";
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

function InfoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div
        className="relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl w-[340px] p-5 text-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Opening Performance</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">×</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Shows win rate for each opening you&apos;ve played, split by White and Black. Click any opening with a ▶ arrow to expand the Opening Explorer.
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><strong>Opening Explorer</strong> — Shows the opening moves on a board with your game history for that opening.</li>
          <li><strong>Win%</strong> — Your win percentage with that specific opening.</li>
        </ul>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-3">
          Focus on openings with many games but low win rates — those may need study or replacement.
        </p>
      </div>
    </div>,
    document.body
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

  const [showInfo, setShowInfo] = useState(false);

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Opening Performance
        </h3>
        <button
          onClick={() => setShowInfo(true)}
          className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors"
          title="What does this table show?"
        >&#9432;</button>
      </div>
      {showInfo && <InfoModal onClose={() => setShowInfo(false)} />}
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
