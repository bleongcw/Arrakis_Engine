// ArrakisEngine — Chess Coaching AI
// Copyright (C) 2026 Bernard Leong
// Licensed under AGPL-3.0. See LICENSE file.
//
// v1.18.3: date-axis formatting helpers for the rating progression
// chart. Extracted so the formatting logic is unit-testable
// independently of the Recharts render tree.

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/**
 * Parse a `date_played` string from the DB into epoch milliseconds.
 *
 * The DB stores `"2025-10-01 10:28:12"` (space-separated, no timezone).
 * `new Date("2025-10-01 10:28:12")` is parsed as LOCAL time by V8,
 * which is what we want for a personal-use single-timezone app.
 * Returns NaN for empty/unparseable input so callers can filter.
 */
export function parsePlayedDate(dateStr: string | null | undefined): number {
  if (!dateStr) return NaN;
  // Normalize the space separator to 'T' so Safari (which is stricter
  // than V8 about the space form) parses it consistently.
  const iso = dateStr.includes("T") ? dateStr : dateStr.replace(" ", "T");
  return new Date(iso).getTime();
}

/**
 * Format an epoch-ms tick for the rating chart's time-scaled X-axis.
 *
 * Convention (borrowed from finance charts): show the month
 * abbreviation, and append a 2-digit year ONLY at January — so the
 * year appears exactly at year boundaries without repeating on every
 * tick. Unambiguous across a multi-year span, uncluttered within one.
 *
 *   Oct 2025 → "Oct"
 *   Jan 2026 → "Jan '26"
 *   May 2026 → "May"
 */
export function formatAxisTick(ms: number): string {
  if (!Number.isFinite(ms)) return "";
  const d = new Date(ms);
  const month = MONTHS[d.getMonth()];
  if (d.getMonth() === 0) {
    // January — anchor the year here.
    const yy = String(d.getFullYear()).slice(-2);
    return `${month} '${yy}`;
  }
  return month;
}

/**
 * Format an epoch-ms value for the tooltip / brush — full readable
 * date, no time-of-day clutter. "Oct 1, 2025".
 */
export function formatTooltipDate(ms: number): string {
  if (!Number.isFinite(ms)) return "";
  const d = new Date(ms);
  return `${MONTHS[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}
