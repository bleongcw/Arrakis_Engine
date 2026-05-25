import { parseTrendSummary } from "@/lib/summary";

describe("parseTrendSummary", () => {
  // ── Nil / empty cases ────────────────────────────────────

  it("returns [] for null", () => {
    expect(parseTrendSummary(null)).toEqual([]);
  });

  it("returns [] for undefined", () => {
    expect(parseTrendSummary(undefined)).toEqual([]);
  });

  it("returns [] for empty string", () => {
    expect(parseTrendSummary("")).toEqual([]);
  });

  it("returns [] for whitespace-only string", () => {
    expect(parseTrendSummary("   \n\n  ")).toEqual([]);
  });

  // ── Plain text with REAL newlines ────────────────────────

  it("splits prose on real \\n\\n", () => {
    const text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph.";
    expect(parseTrendSummary(text)).toEqual([
      "First paragraph.",
      "Second paragraph.",
      "Third paragraph.",
    ]);
  });

  it("tolerates blank-line whitespace between paragraphs", () => {
    const text = "First.\n  \nSecond.";
    expect(parseTrendSummary(text)).toEqual(["First.", "Second."]);
  });

  it("trims each paragraph", () => {
    const text = "  First.  \n\n  Second.  ";
    expect(parseTrendSummary(text)).toEqual(["First.", "Second."]);
  });

  // ── JSON {paragraphs: [...]} ─────────────────────────────

  it("extracts paragraphs array from JSON form", () => {
    const json = JSON.stringify({ paragraphs: ["one", "two", "three"] });
    expect(parseTrendSummary(json)).toEqual(["one", "two", "three"]);
  });

  it("flattens string values from a generic JSON object", () => {
    const json = JSON.stringify({ a: "one", b: "two" });
    expect(parseTrendSummary(json)).toEqual(["one", "two"]);
  });

  it("falls back to text split when JSON.parse fails", () => {
    // Starts with `{` but isn't valid JSON.
    const text = "{not really json}\n\nsecond paragraph";
    expect(parseTrendSummary(text)).toEqual([
      "{not really json}",
      "second paragraph",
    ]);
  });

  // ── v1.8.2 regression lock: literal `\n\n` escape leak ──

  it("v1.8.2 — normalizes literal \\n\\n (4 chars) into real paragraph breaks", () => {
    // This is the exact shape the user screenshotted: the string contains
    // backslash-n-backslash-n as four characters, NOT real newlines.
    // The pre-fix splitter on real `\n\n` saw zero matches and rendered
    // one giant paragraph with visible `\n\n` in the UI.
    const buggy =
      "First paragraph with stats.\\n\\nSecond paragraph improvements.\\n\\nThird paragraph practice goals.";
    expect(parseTrendSummary(buggy)).toEqual([
      "First paragraph with stats.",
      "Second paragraph improvements.",
      "Third paragraph practice goals.",
    ]);
  });

  it("v1.8.2 — verbatim Evan Leong summary from the bug report splits into 4 paragraphs", () => {
    // Verbatim payload pattern from Bernard's screenshot: real prose with
    // literal `\n\n` between Amazon-style paragraph 1 (progress), paragraph 2
    // (biggest area), paragraph 3 (3 practice goals), paragraph 4 (encouragement).
    const buggy =
      "Evan Leong, you are making solid progress. Over your last 573 games, you won 320 times, with a 55.8% win rate.\\n\\n" +
      "The biggest area for you to improve is the middlegame. Your middlegame ACPL is 77.8.\\n\\n" +
      "Here are 3 practice goals for you: First, do 10 puzzle positions every day. Second, after each game, find just one mistake. Third, pick a simple opening setup.\\n\\n" +
      "You are already showing strong fighting spirit, Evan Leong, and your comeback rate of 35.8% shows you do not give up easily.";
    const result = parseTrendSummary(buggy);
    expect(result).toHaveLength(4);
    expect(result[0]).toMatch(/^Evan Leong, you are making solid progress/);
    expect(result[1]).toMatch(/^The biggest area/);
    expect(result[2]).toMatch(/^Here are 3 practice goals/);
    expect(result[3]).toMatch(/^You are already showing strong fighting spirit/);
    // No literal escape sequence may survive in any paragraph.
    for (const p of result) {
      expect(p).not.toContain("\\n");
    }
  });

  it("v1.8.2 — normalizes literal \\r\\n\\r\\n (Windows-style escape leak)", () => {
    const buggy = "First.\\r\\n\\r\\nSecond.";
    expect(parseTrendSummary(buggy)).toEqual(["First.", "Second."]);
  });

  it("v1.8.2 — normalizes literal \\n inside JSON-extracted paragraphs", () => {
    // JSON layer parsed fine but each paragraph value carries escaped newlines.
    const json = JSON.stringify({
      paragraphs: ["intro line one\\nintro line two", "second paragraph"],
    });
    const result = parseTrendSummary(json);
    expect(result).toEqual(["intro line one\nintro line two", "second paragraph"]);
    expect(result[0]).not.toContain("\\n");
  });

  it("v1.8.2 — mixed real and literal newlines both normalize", () => {
    const mixed = "First.\n\nSecond.\\n\\nThird.";
    expect(parseTrendSummary(mixed)).toEqual(["First.", "Second.", "Third."]);
  });
});
