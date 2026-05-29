// ArrakisEngine — Chess Coaching AI
// Copyright (C) 2026 Bernard Leong
// Licensed under AGPL-3.0. See LICENSE file.
//
// v1.15.0: shared motif identifier → emoji + label map.
//
// Previously inlined in `components/game-detail/coaching-panels.tsx` as
// `MOTIF_LABELS`. Lifted here so the v1.15.0 `<MotifThemes>` Patterns
// card and any future motif-aware UI surface share one source of truth
// for the visual representation of motif identifiers.
//
// v1.17.0 added 4 entries: back_rank_mate, deflection,
// overloaded_defender, zugzwang.

export type MotifMeta = { icon: string; label: string };

export const MOTIF_LABELS: Record<string, MotifMeta> = {
  // v1.14.0 originals
  fork: { icon: "🍴", label: "fork" },
  pin: { icon: "📌", label: "pin" },
  skewer: { icon: "🗡", label: "skewer" },
  discovered_check: { icon: "💥", label: "discovered check" },
  mate_threat: { icon: "🎯", label: "mate threat" },
  removing_defender: { icon: "🛡", label: "removing defender" },
  hanging_piece: { icon: "🎁", label: "hanging piece" },
  trapped_piece: { icon: "🪤", label: "trapped piece" },
  // v1.17.0 additions
  back_rank_mate: { icon: "🏰", label: "back-rank mate" },
  deflection: { icon: "↗️", label: "deflection" },
  overloaded_defender: { icon: "🤹", label: "overloaded defender" },
  // zugzwang: avoid 🪤 (used by trapped_piece). ⛓ = "chained,
  // no good move" captures the spirit.
  zugzwang: { icon: "⛓", label: "zugzwang" },
};

/**
 * Resolve a motif identifier to its display meta. Falls back to a
 * bullet icon + raw id when the identifier isn't known — defensive
 * against future motifs the frontend hasn't been updated for yet.
 */
export function motifLabel(id: string): MotifMeta {
  return MOTIF_LABELS[id] ?? { icon: "•", label: id };
}
