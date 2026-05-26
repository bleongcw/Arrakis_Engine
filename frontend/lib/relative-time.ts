/**
 * v1.11.0: Live-updating relative timestamps for the Journal feed.
 *
 * Plain helper: `getRelativeTime(date)` returns "just now" / "5 minutes ago" /
 * "today, 14:23" / "yesterday" / "3 days ago" / etc.
 *
 * Hook: `useLiveRelativeTime(date)` returns the same string but re-renders
 * every 60 seconds so an entry generated at 14:23 visibly transitions from
 * "just now" → "5 minutes ago" → "today" → "yesterday" without a page reload.
 *
 * Locale-agnostic: uses the user's browser locale for time formatting.
 */

import { useEffect, useState } from "react";

const MINUTE_MS = 60 * 1000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;
const WEEK_MS = 7 * DAY_MS;
const MONTH_MS = 30 * DAY_MS; // approximate — fine for "N months ago"
const YEAR_MS = 365 * DAY_MS;

/**
 * Convert a Date (or ISO/SQL string) to a human-friendly relative-time
 * string anchored to the current moment.
 *
 * Boundaries:
 *   - <60s          → "just now"
 *   - <60 min       → "N minutes ago"   (1 → "1 minute ago")
 *   - same calendar day → "today, HH:MM"
 *   - previous calendar day → "yesterday"
 *   - <7 days       → "N days ago"
 *   - <4 weeks      → "N weeks ago"
 *   - <12 months    → "N months ago"
 *   - else          → "N years ago"
 *
 * Future dates (rare — clock skew) return "just now".
 */
export function getRelativeTime(input: Date | string, now: Date = new Date()): string {
  const date = typeof input === "string" ? parseSqlOrIsoDate(input) : input;
  if (!date || isNaN(date.getTime())) return "";

  const diffMs = now.getTime() - date.getTime();
  if (diffMs < MINUTE_MS) return "just now";
  if (diffMs < HOUR_MS) {
    const mins = Math.floor(diffMs / MINUTE_MS);
    return mins === 1 ? "1 minute ago" : `${mins} minutes ago`;
  }

  // Calendar-day comparisons (not strict-24h) so "yesterday" works even if
  // the entry was generated 2h ago crossing midnight.
  const startOfToday = startOfDay(now);
  const startOfDate = startOfDay(date);
  const dayDiff = Math.round((startOfToday.getTime() - startOfDate.getTime()) / DAY_MS);

  if (dayDiff === 0) {
    return `today, ${formatHHMM(date)}`;
  }
  if (dayDiff === 1) return "yesterday";
  if (dayDiff < 7) return `${dayDiff} days ago`;
  if (diffMs < 4 * WEEK_MS) {
    const weeks = Math.floor(diffMs / WEEK_MS);
    return weeks === 1 ? "1 week ago" : `${weeks} weeks ago`;
  }
  if (diffMs < YEAR_MS) {
    const months = Math.floor(diffMs / MONTH_MS);
    return months === 1 ? "1 month ago" : `${months} months ago`;
  }
  const years = Math.floor(diffMs / YEAR_MS);
  return years === 1 ? "1 year ago" : `${years} years ago`;
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function formatHHMM(d: Date): string {
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

/**
 * SQLite's `datetime('now')` returns 'YYYY-MM-DD HH:MM:SS' (space-separated,
 * no timezone). JavaScript's Date() parses these as LOCAL time on some
 * browsers and UTC on others — which causes "today" entries to display as
 * "yesterday" or vice versa across timezones.
 *
 * This parser:
 *   - Treats SQL-style 'YYYY-MM-DD HH:MM:SS' as UTC (matches SQLite behavior)
 *   - Falls through to native Date() for proper ISO strings ending in Z or
 *     containing +HH:MM offsets
 */
function parseSqlOrIsoDate(s: string): Date | null {
  if (!s) return null;
  const trimmed = s.trim();
  // ISO with timezone marker → native parser
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(trimmed)) {
    const d = new Date(trimmed);
    return isNaN(d.getTime()) ? null : d;
  }
  // SQLite 'YYYY-MM-DD HH:MM:SS' — treat as UTC
  const sqlMatch = trimmed.match(
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?$/,
  );
  if (sqlMatch) {
    const [, y, mo, d, h, mi, se] = sqlMatch;
    return new Date(
      Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(se)),
    );
  }
  // Plain YYYY-MM-DD (no time) — treat midnight UTC
  const dateOnly = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (dateOnly) {
    const [, y, mo, d] = dateOnly;
    return new Date(Date.UTC(Number(y), Number(mo) - 1, Number(d)));
  }
  // Last resort — native parser
  const d = new Date(trimmed);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * React hook: returns the live-updating relative-time string for `date`.
 * Re-renders every 60 seconds so the label transitions naturally over time.
 *
 * Tick interval is a constant per-page (single setInterval shared across
 * mounted hooks via the `__tickKey` state, which each instance owns
 * independently — React batches updates so the cost is minimal).
 */
export function useLiveRelativeTime(input: Date | string): string {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), MINUTE_MS);
    return () => clearInterval(id);
  }, []);
  return getRelativeTime(input);
}
