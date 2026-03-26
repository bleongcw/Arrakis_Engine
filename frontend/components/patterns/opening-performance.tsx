"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Opening {
  name: string;
  games: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
}

interface OpeningPerformanceProps {
  openings: {
    all?: Opening[];
    white?: Opening[];
    black?: Opening[];
  } | Opening[];
}

function OpeningTable({ openings }: { openings: Opening[] }) {
  if (!openings || openings.length === 0) {
    return <p className="text-sm text-muted-foreground py-4">No data available.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Opening</TableHead>
          <TableHead className="text-right">Games</TableHead>
          <TableHead className="text-right">Wins</TableHead>
          <TableHead className="text-right">Losses</TableHead>
          <TableHead className="text-right">Win%</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {openings.map((o, i) => (
          <TableRow key={i}>
            <TableCell className="font-medium">{o.name}</TableCell>
            <TableCell className="text-right">{o.games}</TableCell>
            <TableCell className="text-right text-green-500">{o.wins}</TableCell>
            <TableCell className="text-right text-red-500">{o.losses}</TableCell>
            <TableCell className="text-right font-semibold">
              {o.win_rate.toFixed(0)}%
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function OpeningPerformance({ openings }: OpeningPerformanceProps) {
  // Handle both array and dict formats
  let allOpenings: Opening[] = [];
  let whiteOpenings: Opening[] = [];
  let blackOpenings: Opening[] = [];

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
          <OpeningTable openings={allOpenings} />
        </TabsContent>
        <TabsContent value="white">
          <OpeningTable openings={whiteOpenings} />
        </TabsContent>
        <TabsContent value="black">
          <OpeningTable openings={blackOpenings} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
