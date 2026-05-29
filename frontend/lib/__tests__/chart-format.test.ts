import { describe, it, expect } from "vitest";
import {
  parsePlayedDate,
  formatAxisTick,
  formatTooltipDate,
} from "@/lib/chart-format";

/** v1.18.3: date-axis formatting for the rating progression chart. */

describe("parsePlayedDate", () => {
  it("parses the DB space-separated format", () => {
    const ms = parsePlayedDate("2025-10-01 10:28:12");
    const d = new Date(ms);
    expect(d.getFullYear()).toBe(2025);
    expect(d.getMonth()).toBe(9); // October (0-indexed)
    expect(d.getDate()).toBe(1);
  });

  it("parses an already-ISO 'T' form", () => {
    const ms = parsePlayedDate("2026-05-29T11:10:18");
    expect(Number.isFinite(ms)).toBe(true);
    expect(new Date(ms).getFullYear()).toBe(2026);
  });

  it("returns NaN for null / empty", () => {
    expect(Number.isNaN(parsePlayedDate(null))).toBe(true);
    expect(Number.isNaN(parsePlayedDate(undefined))).toBe(true);
    expect(Number.isNaN(parsePlayedDate(""))).toBe(true);
  });

  it("orders chronologically (sanity for the time axis)", () => {
    const a = parsePlayedDate("2025-10-01 10:00:00");
    const b = parsePlayedDate("2026-05-29 11:00:00");
    expect(a).toBeLessThan(b);
  });
});

describe("formatAxisTick", () => {
  it("shows bare month abbreviation for non-January", () => {
    const oct = parsePlayedDate("2025-10-15 12:00:00");
    expect(formatAxisTick(oct)).toBe("Oct");
    const may = parsePlayedDate("2026-05-29 12:00:00");
    expect(formatAxisTick(may)).toBe("May");
  });

  it("anchors the year at January (finance-chart convention)", () => {
    const jan = parsePlayedDate("2026-01-08 12:00:00");
    expect(formatAxisTick(jan)).toBe("Jan '26");
  });

  it("never leaks a time-of-day component (the v1.18.3 bug)", () => {
    // The old formatter split on '-' and produced "10/01 10:28:12".
    const ms = parsePlayedDate("2025-10-01 10:28:12");
    const label = formatAxisTick(ms);
    expect(label).not.toMatch(/\d{2}:\d{2}/); // no HH:MM
    expect(label).toBe("Oct");
  });

  it("returns empty string for non-finite input", () => {
    expect(formatAxisTick(NaN)).toBe("");
  });
});

describe("formatTooltipDate", () => {
  it("formats a full readable date with no time", () => {
    const ms = parsePlayedDate("2025-10-01 10:28:12");
    expect(formatTooltipDate(ms)).toBe("Oct 1, 2025");
  });

  it("returns empty string for non-finite input", () => {
    expect(formatTooltipDate(NaN)).toBe("");
  });
});
