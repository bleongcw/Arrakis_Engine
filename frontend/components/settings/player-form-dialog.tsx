"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import type { Player } from "@/lib/types";

interface PlayerFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  player?: Player | null;
  onSubmit: (data: PlayerFormData) => Promise<void>;
}

export interface PlayerFormData {
  username: string;
  display_name: string;
  age: number | null;
  lichess_username: string;
  fide_id: string;
  fide_rating: number | null;
}

export function PlayerFormDialog({
  open,
  onOpenChange,
  player,
  onSubmit,
}: PlayerFormDialogProps) {
  const isEdit = !!player;
  const [form, setForm] = useState<PlayerFormData>({
    username: "",
    display_name: "",
    age: null,
    lichess_username: "",
    fide_id: "",
    fide_rating: null,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      if (player) {
        setForm({
          username: player.username,
          display_name: player.display_name || "",
          age: player.age,
          lichess_username: player.lichess_username || "",
          fide_id: player.fide_id ? String(player.fide_id) : "",
          fide_rating: player.fide_rating,
        });
      } else {
        setForm({
          username: "",
          display_name: "",
          age: null,
          lichess_username: "",
          fide_id: "",
          fide_rating: null,
        });
      }
      setError(null);
    }
  }, [open, player]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.username.trim()) {
      setError("Chess.com username is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit(form);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Player" : "Add Player"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update player details. Username cannot be changed."
              : "Add a new player to track. The Chess.com username is required."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">Chess.com Username *</Label>
            <Input
              id="username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              disabled={isEdit}
              placeholder="e.g. your_chess_com_username"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="display_name">Display Name</Label>
            <Input
              id="display_name"
              value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              placeholder="e.g. Player 1"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="age">Age</Label>
              <Input
                id="age"
                type="number"
                min={1}
                max={120}
                value={form.age ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    age: e.target.value ? Number(e.target.value) : null,
                  })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="lichess_username">Lichess Username</Label>
              <Input
                id="lichess_username"
                value={form.lichess_username}
                onChange={(e) =>
                  setForm({ ...form, lichess_username: e.target.value })
                }
                placeholder="e.g. evleong"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="fide_id">FIDE ID</Label>
              <Input
                id="fide_id"
                value={form.fide_id}
                onChange={(e) => setForm({ ...form, fide_id: e.target.value })}
                placeholder="e.g. 12345678"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fide_rating">FIDE Rating</Label>
              <Input
                id="fide_rating"
                type="number"
                min={0}
                max={3000}
                value={form.fide_rating ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    fide_rating: e.target.value ? Number(e.target.value) : null,
                  })
                }
              />
            </div>
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <DialogFooter>
            <DialogClose
              render={
                <Button type="button" variant="outline" disabled={saving}>
                  Cancel
                </Button>
              }
            />
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : isEdit ? "Save Changes" : "Add Player"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
