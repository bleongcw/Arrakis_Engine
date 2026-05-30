"use client";

// ArrakisEngine — Chess Coaching AI
// Copyright (C) 2026 Bernard Leong
// Licensed under AGPL-3.0. See LICENSE file.

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { usePlayerContext } from "@/app/providers";
import { Card, CardContent } from "@/components/ui/card";
import { OpponentSearch } from "@/components/hunter/opponent-search";
import { OpeningTargets } from "@/components/tournament/opening-targets";
import { OpponentCard } from "@/components/tournament/opponent-card";
import { MotifThemes } from "@/components/patterns/motif-themes";
import type { MotifSummaryData } from "@/components/patterns/motif-themes";
import {
  listTournaments,
  getTournament,
  createTournament,
  addTournamentOpponent,
  removeTournamentOpponent,
  deleteTournament,
  triggerTournamentPrep,
  fetchPipelineStatus,
} from "@/lib/api";
import type { Tournament, TournamentPrep, HuntPlatform } from "@/lib/types";

const PREP_TASK = "tournament_prep";

export default function TournamentPage() {
  const { player } = useParams<{ player: string }>();
  const { loading: playerLoading } = usePlayerContext();

  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selected, setSelected] = useState<TournamentPrep | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form
  const [newName, setNewName] = useState("");
  const [newDate, setNewDate] = useState("");

  // Prep job
  const [prepping, setPrepping] = useState(false);
  const [prepProgress, setPrepProgress] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadList = useCallback(async () => {
    if (!player) return;
    setLoading(true);
    try {
      const data = await listTournaments(player);
      setTournaments(data.tournaments || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tournaments.");
    } finally {
      setLoading(false);
    }
  }, [player]);

  useEffect(() => {
    loadList();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadList]);

  const openTournament = useCallback(async (id: number) => {
    setError(null);
    try {
      setSelected(await getTournament(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to open tournament.");
    }
  }, []);

  const reloadSelected = useCallback(async () => {
    if (selected) setSelected(await getTournament(selected.tournament.id));
  }, [selected]);

  const handleCreate = useCallback(async () => {
    if (!newName.trim()) return;
    setError(null);
    try {
      const t = await createTournament(player, newName.trim(), newDate || undefined);
      setNewName("");
      setNewDate("");
      await loadList();
      await openTournament(t.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed.");
    }
  }, [player, newName, newDate, loadList, openTournament]);

  const handleAddOpponent = useCallback(
    async (opponent: string, platform: HuntPlatform) => {
      if (!selected) return;
      setError(null);
      try {
        await addTournamentOpponent(selected.tournament.id, opponent, platform);
        await reloadSelected();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Add failed.");
      }
    },
    [selected, reloadSelected],
  );

  const handleRemoveOpponent = useCallback(
    async (opponentId: number) => {
      if (!selected) return;
      await removeTournamentOpponent(selected.tournament.id, opponentId);
      await reloadSelected();
    },
    [selected, reloadSelected],
  );

  const handleDelete = useCallback(
    async (id: number) => {
      await deleteTournament(id);
      setSelected(null);
      await loadList();
    },
    [loadList],
  );

  const runPrep = useCallback(async () => {
    if (!selected) return;
    setError(null);
    setPrepping(true);
    setPrepProgress("Starting…");
    try {
      await triggerTournamentPrep(selected.tournament.id);
    } catch (e) {
      setPrepping(false);
      setError(e instanceof Error ? e.message : "Prep failed to start.");
      return;
    }
    pollRef.current = setInterval(async () => {
      const s = await fetchPipelineStatus().catch(() => null);
      if (!s) return;
      if (s.task === PREP_TASK && s.status === "running") {
        setPrepProgress(s.progress || "Prepping…");
        return;
      }
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
      setPrepping(false);
      if (s.status === "error") setError(s.error || "Prep failed.");
      else reloadSelected();
    }, 2000);
  }, [selected, reloadSelected]);

  if (playerLoading || loading) {
    return <div className="h-96 rounded-lg bg-muted animate-pulse m-4" />;
  }

  return (
    <div className="max-w-6xl mx-auto px-3 sm:px-4 py-6 space-y-4">
      <Card>
        <CardContent className="pt-6 space-y-3">
          <div>
            <h1 className="text-2xl font-bold">Tournament Prep</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Build a roster of opponents for an upcoming event and prep the
              whole field at once — which openings to play, which to avoid, and
              where the field is tactically soft.
            </p>
          </div>
          {!selected && (
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Event name (e.g. Saturday Rapid — Mar 2026)"
                className="flex-1 px-3 py-2 rounded-md border border-border bg-background text-sm"
              />
              <input
                type="date"
                value={newDate}
                onChange={(e) => setNewDate(e.target.value)}
                className="px-3 py-2 rounded-md border border-border bg-background text-sm"
              />
              <button
                onClick={handleCreate}
                disabled={!newName.trim()}
                className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
              >
                Create
              </button>
            </div>
          )}
        </CardContent>
      </Card>

      {error && (
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* LIST VIEW */}
      {!selected && (
        <Card>
          <CardContent className="pt-6">
            {tournaments.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No tournaments yet. Create one above to start prepping.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {tournaments.map((t) => (
                  <li
                    key={t.id}
                    className="py-3 flex items-center justify-between gap-3"
                  >
                    <button
                      onClick={() => openTournament(t.id)}
                      className="text-left min-w-0 flex-1"
                    >
                      <div className="text-sm font-medium hover:underline">
                        {t.name}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {t.event_date ? `${t.event_date} · ` : ""}
                        {t.opponent_count ?? 0} opponents
                      </div>
                    </button>
                    <button
                      onClick={() => handleDelete(t.id)}
                      className="text-xs text-muted-foreground/60 hover:text-red-600"
                    >
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      {/* DETAIL VIEW */}
      {selected && (
        <>
          <Card>
            <CardContent className="pt-6 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <button
                    onClick={() => setSelected(null)}
                    className="text-xs text-muted-foreground hover:text-foreground mb-1"
                  >
                    ← All tournaments
                  </button>
                  <h2 className="text-xl font-bold">
                    {selected.tournament.name}
                  </h2>
                  {selected.tournament.event_date && (
                    <p className="text-xs text-muted-foreground">
                      {selected.tournament.event_date}
                    </p>
                  )}
                </div>
                <button
                  onClick={runPrep}
                  disabled={prepping || selected.opponents.length === 0}
                  className="text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground font-medium disabled:opacity-50"
                >
                  {prepping ? "Prepping…" : "Prep Roster"}
                </button>
              </div>
              {prepping && (
                <div
                  className="text-xs text-muted-foreground flex items-center gap-2"
                  data-testid="prep-progress"
                >
                  <span className="inline-block w-3 h-3 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                  {prepProgress}
                </div>
              )}
              <OpponentSearch onSearch={handleAddOpponent} />
              {selected.opponents.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">
                  Add opponents above to build the roster.
                </p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                  {selected.opponents.map((o) => (
                    <OpponentCard
                      key={o.id}
                      opponent={o}
                      player={player}
                      onRemove={handleRemoveOpponent}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <OpeningTargets
                targets={selected.opening_targets}
                cautions={selected.opening_cautions}
              />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  Field Blind Spots
                </h3>
                <span className="text-xs text-muted-foreground">
                  {selected.scan_coverage.scanned} of{" "}
                  {selected.scan_coverage.total} opponents deep-scanned
                </span>
              </div>
              {selected.field_blind_spots ? (
                <MotifThemes
                  data={selected.field_blind_spots as MotifSummaryData}
                />
              ) : (
                <p className="text-xs text-muted-foreground italic">
                  No opponents deep-scanned yet. Open an opponent in Hunt and run
                  a Deep Scan to populate the field&apos;s tactical blind spots.
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
