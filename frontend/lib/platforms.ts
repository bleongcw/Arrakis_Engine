// ArrakisEngine — Chess Coaching AI
// Copyright (C) 2026 Bernard Leong
// Licensed under AGPL-3.0. See LICENSE file.

/**
 * Game-origin ("platform") display metadata — one source of truth for the icon
 * and label shown wherever a game's source appears. v1.25.0 adds "competition"
 * for uploaded over-the-board tournament PGNs (not on chess.com / lichess).
 */

export interface PlatformMeta {
  icon: string;
  label: string;
}

export const PLATFORM_META: Record<string, PlatformMeta> = {
  "chess.com": { icon: "♜", label: "Chess.com" }, // ♜
  lichess: { icon: "♞", label: "Lichess" }, // ♞
  competition: { icon: "🏆", label: "Competition" }, // 🏆
};

/** Metadata for a game's platform, defaulting to Chess.com for unknown/legacy. */
export function platformMeta(platform: string | null | undefined): PlatformMeta {
  return (platform && PLATFORM_META[platform]) || PLATFORM_META["chess.com"];
}
