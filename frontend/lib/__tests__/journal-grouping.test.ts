import { describe, it, expect } from "vitest";
import { bucketForDate, groupEntriesByDay } from "../journal-grouping";
import type { JournalEntry } from "../api";

// Anchor "now" to a known weekday so This-week / Last-week boundaries are
// deterministic. 2026-05-26 is a Tuesday → 1 day past Monday → days-since-monday = 1.
// That means "This week" includes only Tue (today) + Mon (yesterday-ish).
// "Last week" runs Mon-Sun the prior week.
const now = new Date("2026-05-26T14:00:00Z");

function entry(id: number, created_at: string, kind = "review", platform = "chess.com"): JournalEntry {
  return {
    id,
    player_id: 1,
    kind,
    platform,
    body: `entry ${id}`,
    refs: [],
    provider: null,
    metadata: {},
    created_at,
  };
}

describe("bucketForDate", () => {
  it("returns Today for the current calendar day", () => {
    expect(bucketForDate("2026-05-26 09:00:00", now)).toBe("Today");
    expect(bucketForDate("2026-05-26 23:59:59", now)).toBe("Today");
  });

  it("returns Yesterday for the prior calendar day", () => {
    expect(bucketForDate("2026-05-25 14:00:00", now)).toBe("Yesterday");
  });

  it("returns This week for older days in the same ISO week", () => {
    // 2026-05-26 is Tuesday (days-since-Mon=1). So Monday 2026-05-25 falls
    // in "Yesterday" (dayDiff=1, matches Yesterday case before This week).
    // We need a "This week" case that's NOT Today or Yesterday. With
    // days-since-Monday=1 and Yesterday consuming dayDiff=1, no third
    // day qualifies for "This week" on a Tuesday — this is correct
    // behavior. Verify a Friday anchor instead:
    const fri = new Date("2026-05-29T14:00:00Z"); // Friday
    // Tuesday 2026-05-26 → dayDiff=3 → "This week" (Mon-anchor allows up to 4)
    expect(bucketForDate("2026-05-26 10:00:00", fri)).toBe("This week");
  });

  it("returns Last week for the prior ISO week", () => {
    // 7 days back from Tuesday 2026-05-26 is Tuesday 2026-05-19 → "Last week"
    expect(bucketForDate("2026-05-19 10:00:00", now)).toBe("Last week");
  });

  it("returns Earlier for anything older than last week", () => {
    expect(bucketForDate("2026-05-10 10:00:00", now)).toBe("Earlier");
    expect(bucketForDate("2025-01-01 10:00:00", now)).toBe("Earlier");
  });

  it("returns Earlier for invalid input rather than crashing", () => {
    expect(bucketForDate("not-a-date", now)).toBe("Earlier");
  });
});

describe("groupEntriesByDay", () => {
  it("returns empty array for no entries", () => {
    expect(groupEntriesByDay([], now)).toEqual([]);
  });

  it("groups entries into ordered buckets", () => {
    const entries: JournalEntry[] = [
      entry(1, "2026-05-26 13:00:00"),  // Today
      entry(2, "2026-05-25 09:00:00"),  // Yesterday
      entry(3, "2026-05-19 10:00:00"),  // Last week
      entry(4, "2026-04-01 10:00:00"),  // Earlier
    ];
    const buckets = groupEntriesByDay(entries, now);
    expect(buckets.map((b) => b.label)).toEqual([
      "Today", "Yesterday", "Last week", "Earlier",
    ]);
    expect(buckets[0].entries[0].id).toBe(1);
    expect(buckets[1].entries[0].id).toBe(2);
  });

  it("drops empty buckets", () => {
    const entries: JournalEntry[] = [
      entry(1, "2026-05-26 13:00:00"),  // Today only
    ];
    const buckets = groupEntriesByDay(entries, now);
    expect(buckets).toHaveLength(1);
    expect(buckets[0].label).toBe("Today");
  });

  it("preserves input order within each bucket", () => {
    // Input newest-first: 3pm, 1pm, 9am — all Today
    const entries: JournalEntry[] = [
      entry(3, "2026-05-26 15:00:00"),
      entry(2, "2026-05-26 13:00:00"),
      entry(1, "2026-05-26 09:00:00"),
    ];
    const buckets = groupEntriesByDay(entries, now);
    expect(buckets[0].entries.map((e) => e.id)).toEqual([3, 2, 1]);
  });

  it("handles multiple entries spread across all buckets", () => {
    const entries: JournalEntry[] = [
      entry(1, "2026-05-26 14:00:00"),  // Today
      entry(2, "2026-05-26 09:00:00"),  // Today
      entry(3, "2026-05-25 12:00:00"),  // Yesterday
      entry(4, "2026-05-19 10:00:00"),  // Last week
      entry(5, "2026-05-18 10:00:00"),  // Last week
      entry(6, "2026-04-01 10:00:00"),  // Earlier
    ];
    const buckets = groupEntriesByDay(entries, now);
    expect(buckets.map((b) => `${b.label}:${b.entries.length}`)).toEqual([
      "Today:2", "Yesterday:1", "Last week:2", "Earlier:1",
    ]);
  });
});
