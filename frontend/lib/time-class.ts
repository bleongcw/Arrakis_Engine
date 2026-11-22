// ArrakisEngine — Chess Coaching AI
// Copyright (C) 2026 Bernard Leong
// Licensed under AGPL-3.0. See LICENSE file.

/**
 * Display names for a game's stored `time_class` — one source of truth for
 * every place a time control is shown.
 *
 * v1.34.1: the long time control is shown as "Standard" (FIDE's name for it).
 * Only the label changes: the stored value, API value and filter key stay
 * `classical`, which is what Lichess and the PGN importer produce.
 */

const DISPLAY_NAMES: Record<string, string> = {
  classical: "standard",
};

/** Lowercase display name, e.g. "rapid", "standard". */
export function timeClassName(
  timeClass: string | null | undefined,
  fallback = "?",
): string {
  if (!timeClass) return fallback;
  return DISPLAY_NAMES[timeClass] ?? timeClass;
}

/** Capitalised display label, e.g. "Rapid", "Standard". */
export function timeClassLabel(
  timeClass: string | null | undefined,
  fallback = "?",
): string {
  const name = timeClassName(timeClass, fallback);
  return name.charAt(0).toUpperCase() + name.slice(1);
}
