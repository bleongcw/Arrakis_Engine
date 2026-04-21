"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { Player } from "@/lib/types";

interface RemovePlayerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  player: Player | null;
  onConfirm: (playerId: number) => Promise<void>;
}

export function RemovePlayerDialog({
  open,
  onOpenChange,
  player,
  onConfirm,
}: RemovePlayerDialogProps) {
  const [removing, setRemoving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async () => {
    if (!player) return;
    setRemoving(true);
    setError(null);
    try {
      await onConfirm(player.id);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove player.");
    } finally {
      setRemoving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Remove Player</DialogTitle>
          <DialogDescription>
            Archive <strong>{player?.display_name || player?.username}</strong>?
            Game history will be preserved. You can re-add the player later.
          </DialogDescription>
        </DialogHeader>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <DialogFooter>
          <DialogClose
            render={
              <Button variant="outline" disabled={removing}>
                Cancel
              </Button>
            }
          />
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={removing}
          >
            {removing ? "Removing..." : "Remove"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
