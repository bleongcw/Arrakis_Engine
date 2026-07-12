import { describe, it, expect } from "vitest";
import { PLATFORM_META, platformMeta } from "../platforms";

describe("platformMeta", () => {
  it("labels the known online platforms", () => {
    expect(platformMeta("chess.com").label).toBe("Chess.com");
    expect(platformMeta("lichess").label).toBe("Lichess");
  });

  it("labels competition games (v1.25.0) with the trophy", () => {
    expect(platformMeta("competition")).toEqual({ icon: "🏆", label: "Competition" });
  });

  it("falls back to Chess.com for unknown/legacy/null platforms", () => {
    expect(platformMeta(null)).toBe(PLATFORM_META["chess.com"]);
    expect(platformMeta(undefined)).toBe(PLATFORM_META["chess.com"]);
    expect(platformMeta("myspace-chess")).toBe(PLATFORM_META["chess.com"]);
  });
});
