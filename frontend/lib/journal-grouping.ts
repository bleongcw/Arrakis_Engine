/**
 * v1.11.0: Group journal entries into calendar-flavored buckets.
 *
 * Buckets (in order):
 *   - "Today"        — entries dated to the current local calendar day
 *   - "Yesterday"    — entries dated to the prior local calendar day
 *   - "This week"    — older than yesterday but within the current ISO week
 *   - "Last week"    — within the prior ISO week
 *   - "Earlier"      — anything older
 *
 * Buckets with no entries are dropped, so a fresh-install Journal with only
 * one entry shows just one bucket (e.g. "Today") rather than five empty headers.
 */

import type { JournalEntry } from "@/lib/api";

export interface DayBucket {
  /** Label to render as the section header */
  label: string;
  /** Entries in this bucket, newest first */
  entries: JournalEntry[];
}

const DAY_MS = 24 * 60 * 60 * 1000;

const BUCKET_ORDER = [
  "Today",
  "Yesterday",
  "This week",
  "Last week",
  "Earlier",
] as const;

type BucketLabel = (typeof BUCKET_ORDER)[number];

/**
 * Assign one bucket label to an entry based on its created_at.
 * Anchor is "now" so this is deterministic per call.
 *
 * Handles SQLite's 'YYYY-MM-DD HH:MM:SS' (no timezone) format by treating
 * it as UTC, matching how the relative-time helper parses dates.
 */
export function bucketForDate(input: string | Date, now: Date = new Date()): BucketLabel {
  const date = typeof input === "string" ? parseSqlOrIsoDate(input) : input;
  if (!date || isNaN(date.getTime())) return "Earlier";

  const startOfToday = startOfDay(now);
  const startOfDate = startOfDay(date);
  const dayDiff = Math.round((startOfToday.getTime() - startOfDate.getTime()) / DAY_MS);

  if (dayDiff <= 0) return "Today";
  if (dayDiff === 1) return "Yesterday";

  // "This week" / "Last week" use ISO week boundaries (Mon-Sun) so the buckets
  // shift cleanly. dayDiff is in days from today; combine with today's
  // day-of-week to find which week-block we're in.
  const todayDow = (startOfToday.getDay() + 6) % 7; // 0=Mon, 6=Sun
  const daysSinceMonday = todayDow;
  if (dayDiff <= daysSinceMonday) return "This week";
  if (dayDiff <= daysSinceMonday + 7) return "Last week";
  return "Earlier";
}

/**
 * Group a list of entries into ordered day-buckets.
 *
 * Entries within each bucket retain their input order (so newest-first input
 * → newest-first per bucket). Empty buckets are dropped.
 */
export function groupEntriesByDay(
  entries: JournalEntry[],
  now: Date = new Date(),
): DayBucket[] {
  const map = new Map<BucketLabel, JournalEntry[]>();
  for (const e of entries) {
    const label = bucketForDate(e.created_at, now);
    const arr = map.get(label) ?? [];
    arr.push(e);
    map.set(label, arr);
  }
  return BUCKET_ORDER
    .filter((l) => map.has(l) && (map.get(l) as JournalEntry[]).length > 0)
    .map((l) => ({ label: l, entries: map.get(l) as JournalEntry[] }));
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function parseSqlOrIsoDate(s: string): Date | null {
  if (!s) return null;
  const trimmed = s.trim();
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(trimmed)) {
    const d = new Date(trimmed);
    return isNaN(d.getTime()) ? null : d;
  }
  const sqlMatch = trimmed.match(
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?$/,
  );
  if (sqlMatch) {
    const [, y, mo, d, h, mi, se] = sqlMatch;
    return new Date(
      Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(se)),
    );
  }
  const dateOnly = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (dateOnly) {
    const [, y, mo, d] = dateOnly;
    return new Date(Date.UTC(Number(y), Number(mo) - 1, Number(d)));
  }
  const d = new Date(trimmed);
  return isNaN(d.getTime()) ? null : d;
}
