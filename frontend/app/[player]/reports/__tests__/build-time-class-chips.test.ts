import { describe, it, expect } from "vitest";
import { buildTimeClassChips } from "../page";
import type { ReportData } from "@/lib/types";

/** v1.24.2: data-driven Reports time-class chips (adds Blitz automatically). */
function report(classes: string[]): ReportData {
  return {
    time_class_stats: classes.map((tc) => ({
      time_class: tc,
      games: 1,
      wins: 1,
      losses: 0,
      draws: 0,
      win_rate: 100,
    })),
  } as unknown as ReportData;
}

describe("buildTimeClassChips", () => {
  it("surfaces Blitz when the player has blitz games", () => {
    const { chips } = buildTimeClassChips(report(["rapid", "daily", "blitz"]));
    expect(chips.map((c) => c.key)).toContain("blitz");
    expect(chips.find((c) => c.key === "blitz")?.label).toBe("Blitz");
  });

  it("orders chips canonically (bullet→blitz→rapid→daily) with All last", () => {
    const { chips } = buildTimeClassChips(
      report(["daily", "rapid", "blitz", "bullet"]),
    );
    expect(chips.map((c) => c.key)).toEqual([
      "bullet",
      "blitz",
      "rapid",
      "daily",
      "all",
    ]);
  });

  it("defaults to Rapid when the player has rapid games", () => {
    expect(
      buildTimeClassChips(report(["blitz", "rapid", "daily"])).defaultKey,
    ).toBe("rapid");
  });

  it("falls back to the first available class when there is no rapid", () => {
    expect(buildTimeClassChips(report(["blitz", "daily"])).defaultKey).toBe(
      "blitz",
    );
  });

  it("handles an empty report — only the All chip, default 'all'", () => {
    const { chips, defaultKey } = buildTimeClassChips(report([]));
    expect(chips.map((c) => c.key)).toEqual(["all"]);
    expect(defaultKey).toBe("all");
  });

  it("capitalizes unknown/future time classes for their label", () => {
    const { chips } = buildTimeClassChips(report(["rapid", "correspondence"]));
    expect(chips.find((c) => c.key === "correspondence")?.label).toBe(
      "Correspondence",
    );
  });
});
