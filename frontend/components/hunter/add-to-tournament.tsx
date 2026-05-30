"use client";

// ArrakisEngine — Chess Coaching AI
// Copyright (C) 2026 Bernard Leong
// Licensed under AGPL-3.0. See LICENSE file.

import { useCallback, useEffect, useState } from "react";
import { listTournaments, addTournamentOpponent } from "@/lib/api";
import type { Tournament, HuntPlatform } from "@/lib/types";

/**
 * v1.21.0 Hunt → Tournament bridge. While scouting one opponent in Hunt,
 * drop them straight onto a saved tournament roster. Keeps the
 * single-opponent and multi-opponent flows connected.
 */
export function AddToTournament({
  player,
  opponent,
  platform,
}: {
  player: string;
  opponent: string;
  platform: HuntPlatform;
}) {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selectedId, setSelectedId] = useState<number | "">("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listTournaments(player)
      .then((d) => {
        if (!active) return;
        setTournaments(d.tournaments || []);
        if (d.tournaments?.length) setSelectedId(d.tournaments[0].id);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [player]);

  const handleAdd = useCallback(async () => {
    if (selectedId === "") return;
    setMessage(null);
    try {
      await addTournamentOpponent(Number(selectedId), opponent, platform);
      const name = tournaments.find((t) => t.id === selectedId)?.name ?? "roster";
      setMessage(`Added ${opponent} to "${name}".`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Add failed.");
    }
  }, [selectedId, opponent, platform, tournaments]);

  if (tournaments.length === 0) {
    return (
      <p className="text-xs text-muted-foreground" data-testid="add-to-tournament-empty">
        No tournaments yet — create one on the{" "}
        <a href={`/${player}/tournament`} className="text-primary hover:underline">
          Tournament
        </a>{" "}
        tab to add opponents to a roster.
      </p>
    );
  }

  return (
    <div
      className="flex items-center gap-2 flex-wrap"
      data-testid="add-to-tournament"
    >
      <span className="text-xs text-muted-foreground">Add to tournament:</span>
      <select
        value={selectedId}
        onChange={(e) => setSelectedId(Number(e.target.value))}
        className="text-xs px-2 py-1 rounded-md border border-border bg-background"
      >
        {tournaments.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </select>
      <button
        onClick={handleAdd}
        className="text-xs px-3 py-1 rounded-md bg-primary text-primary-foreground font-medium"
      >
        Add {opponent}
      </button>
      {message && (
        <span className="text-xs text-muted-foreground" data-testid="add-to-tournament-msg">
          {message}
        </span>
      )}
    </div>
  );
}
