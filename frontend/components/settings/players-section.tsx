"use client";

import { useState } from "react";
import { usePlayerContext } from "@/app/providers";
import { SettingsSection } from "./settings-section";
import { PlayerFormDialog, type PlayerFormData } from "./player-form-dialog";
import { RemovePlayerDialog } from "./remove-player-dialog";
import { Button } from "@/components/ui/button";
import { createPlayer, updatePlayer, removePlayer } from "@/lib/api";
import type { Player } from "@/lib/types";

export function PlayersSection() {
  const { players, refreshPlayers } = usePlayerContext();
  const [formOpen, setFormOpen] = useState(false);
  const [editPlayer, setEditPlayer] = useState<Player | null>(null);
  const [removeTarget, setRemoveTarget] = useState<Player | null>(null);
  const [removeOpen, setRemoveOpen] = useState(false);

  const handleAdd = () => {
    setEditPlayer(null);
    setFormOpen(true);
  };

  const handleEdit = (player: Player) => {
    setEditPlayer(player);
    setFormOpen(true);
  };

  const handleRemoveClick = (player: Player) => {
    setRemoveTarget(player);
    setRemoveOpen(true);
  };

  const handleSubmit = async (data: PlayerFormData) => {
    if (editPlayer) {
      await updatePlayer(editPlayer.id, {
        display_name: data.display_name || null,
        age: data.age,
        lichess_username: data.lichess_username || null,
        fide_id: data.fide_id || null,
        fide_rating: data.fide_rating,
      });
    } else {
      await createPlayer({
        username: data.username.trim().toLowerCase(),
        display_name: data.display_name || undefined,
        age: data.age ?? undefined,
        lichess_username: data.lichess_username || undefined,
        fide_id: data.fide_id || undefined,
        fide_rating: data.fide_rating ?? undefined,
      });
    }
    await refreshPlayers();
  };

  const handleRemoveConfirm = async (playerId: number) => {
    await removePlayer(playerId);
    await refreshPlayers();
  };

  return (
    <SettingsSection
      title="Players"
      description="Manage players tracked by ArrakisEngine."
    >
      <div className="space-y-3">
        <Button onClick={handleAdd} size="sm">
          + Add Player
        </Button>

        {players.length === 0 && (
          <p className="text-sm text-muted-foreground py-4">
            No players configured yet. Add a player to get started.
          </p>
        )}

        <div className="space-y-2">
          {players.map((player) => (
            <div
              key={player.id}
              className="flex items-center justify-between rounded-lg border p-3"
            >
              <div className="min-w-0">
                <p className="font-medium text-sm truncate">
                  {player.display_name || player.username}
                </p>
                <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground mt-0.5">
                  {/* v1.16.1: slug + chess.com are now distinct fields —
                      slug drives URLs, username drives the chess.com API. */}
                  {player.slug && (
                    <span>URL: /{player.slug}/…</span>
                  )}
                  <span>Chess.com: {player.username}</span>
                  {player.lichess_username && (
                    <span>Lichess: {player.lichess_username}</span>
                  )}
                  {player.age && <span>Age: {player.age}</span>}
                  {player.fide_rating && (
                    <span>FIDE: {player.fide_rating}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0 ml-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleEdit(player)}
                >
                  Edit
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={() => handleRemoveClick(player)}
                >
                  Remove
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <PlayerFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        player={editPlayer}
        onSubmit={handleSubmit}
      />

      <RemovePlayerDialog
        open={removeOpen}
        onOpenChange={setRemoveOpen}
        player={removeTarget}
        onConfirm={handleRemoveConfirm}
      />
    </SettingsSection>
  );
}
