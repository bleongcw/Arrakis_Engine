"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { HuntPlatform } from "@/lib/types";

interface OpponentSearchProps {
  initialOpponent?: string;
  initialPlatform?: HuntPlatform;
  onSearch: (opponent: string, platform: HuntPlatform) => void;
  loading?: boolean;
}

export function OpponentSearch({
  initialOpponent = "",
  initialPlatform = "chess.com",
  onSearch,
  loading = false,
}: OpponentSearchProps) {
  const [opponent, setOpponent] = useState(initialOpponent);
  const [platform, setPlatform] = useState<HuntPlatform>(initialPlatform);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = opponent.trim();
    if (!trimmed) return;
    onSearch(trimmed, platform);
  };

  return (
    <form
      onSubmit={handleSubmit}
      // autoComplete="off" on the form helps Safari + Firefox treat
      // contained inputs as non-credential. Combined with non-credential
      // label/id/name and password-manager opt-out attributes below,
      // suppresses the iCloud Keychain / 1Password / LastPass dropdowns
      // that otherwise appear on this field.
      autoComplete="off"
      className="flex flex-col sm:flex-row gap-2 items-stretch sm:items-end"
    >
      <div className="flex-1 space-y-1">
        <label htmlFor="opponent-handle" className="text-xs font-medium text-muted-foreground">
          Opponent handle
        </label>
        <Input
          id="opponent-handle"
          name="opponent-handle"
          type="text"
          value={opponent}
          onChange={(e) => setOpponent(e.target.value)}
          placeholder="e.g. MagnusCarlsen"
          autoComplete="off"
          spellCheck={false}
          disabled={loading}
          // Password-manager opt-out hints
          data-1p-ignore="true"
          data-lpignore="true"
          data-form-type="other"
        />
      </div>
      <div className="space-y-1">
        <label htmlFor="platform" className="text-xs font-medium text-muted-foreground">
          Platform
        </label>
        <Select
          value={platform}
          onValueChange={(v) => v && setPlatform(v as HuntPlatform)}
        >
          <SelectTrigger className="w-full sm:w-36" id="platform">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="chess.com">chess.com</SelectItem>
            <SelectItem value="lichess">lichess</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <Button type="submit" disabled={loading || !opponent.trim()}>
        {loading ? "Hunting..." : "Hunt Mode"}
      </Button>
    </form>
  );
}
