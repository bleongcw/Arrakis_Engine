import { describe, it, expect } from "vitest";
import { getRelativeTime } from "../relative-time";

const now = new Date("2026-05-26T14:00:00Z"); // anchor for all tests

describe("getRelativeTime", () => {
  it("returns 'just now' for under 1 minute ago", () => {
    expect(getRelativeTime(new Date("2026-05-26T13:59:30Z"), now)).toBe("just now");
    expect(getRelativeTime(new Date("2026-05-26T14:00:00Z"), now)).toBe("just now");
  });

  it("returns '1 minute ago' (singular) for 1 min", () => {
    expect(getRelativeTime(new Date("2026-05-26T13:58:30Z"), now)).toBe("1 minute ago");
  });

  it("returns 'N minutes ago' (plural) for >1 min", () => {
    expect(getRelativeTime(new Date("2026-05-26T13:35:00Z"), now)).toBe("25 minutes ago");
    expect(getRelativeTime(new Date("2026-05-26T13:05:00Z"), now)).toBe("55 minutes ago");
  });

  it("returns 'today, HH:MM' for same calendar day, >1 hour ago", () => {
    expect(getRelativeTime(new Date("2026-05-26T09:30:00Z"), now)).toMatch(/^today, \d{2}:\d{2}$/);
  });

  it("returns 'yesterday' for the prior calendar day", () => {
    // Noon UTC on the prior day → "yesterday" in any reasonable timezone
    // (UTC-12 through UTC+12, which covers all populated regions). Avoids
    // boundary edge cases where times near midnight could be "today" in one
    // timezone and "yesterday" in another.
    expect(getRelativeTime(new Date("2026-05-25T12:00:00Z"), now)).toBe("yesterday");
  });

  it("returns 'N days ago' for 2-6 days back", () => {
    expect(getRelativeTime(new Date("2026-05-23T14:00:00Z"), now)).toBe("3 days ago");
    expect(getRelativeTime(new Date("2026-05-20T14:00:00Z"), now)).toBe("6 days ago");
  });

  it("returns '1 week ago' / 'N weeks ago' for 7-27 days", () => {
    expect(getRelativeTime(new Date("2026-05-19T00:00:00Z"), now)).toBe("1 week ago");
    expect(getRelativeTime(new Date("2026-05-05T00:00:00Z"), now)).toBe("3 weeks ago");
  });

  it("returns '1 month ago' / 'N months ago' for 4-11 weeks", () => {
    expect(getRelativeTime(new Date("2026-04-20T00:00:00Z"), now)).toBe("1 month ago");
    expect(getRelativeTime(new Date("2026-02-20T00:00:00Z"), now)).toBe("3 months ago");
  });

  it("returns 'N years ago' for >12 months", () => {
    expect(getRelativeTime(new Date("2025-01-01T00:00:00Z"), now)).toBe("1 year ago");
    expect(getRelativeTime(new Date("2023-01-01T00:00:00Z"), now)).toMatch(/^[23] years ago$/);
  });

  it("returns 'just now' for future dates (clock skew)", () => {
    expect(getRelativeTime(new Date("2026-05-26T14:30:00Z"), now)).toBe("just now");
  });

  it("returns empty string for invalid input", () => {
    expect(getRelativeTime("not-a-date", now)).toBe("");
    expect(getRelativeTime("", now)).toBe("");
  });

  it("parses SQLite-style 'YYYY-MM-DD HH:MM:SS' without crashing", () => {
    // The "today"/"yesterday" output depends on the test machine's local
    // timezone (which is intentional — users see day labels in THEIR frame).
    // So we assert with a multi-day gap that's safe across all timezones.
    // 3 days before the UTC anchor is always "3 days ago" no matter the TZ
    // (worst-case TZ shift ±14h still leaves >2 day gap).
    expect(getRelativeTime("2026-05-23 14:00:00", now)).toBe("3 days ago");
    // 30 seconds before the anchor is "just now" in any timezone
    expect(getRelativeTime("2026-05-26 13:59:30", now)).toBe("just now");
  });

  it("parses YYYY-MM-DD (date-only) without crashing", () => {
    // Date-only "2026-05-23" → midnight UTC → 3+ days before May 26 anchor
    expect(getRelativeTime("2026-05-23", now)).toBe("3 days ago");
  });

  it("respects timezone-marked ISO strings via native Date parser", () => {
    // 2026-05-23T14:00:00Z is exactly 3 days before the May 26 14:00 anchor
    expect(getRelativeTime("2026-05-23T14:00:00Z", now)).toBe("3 days ago");
  });
});
