import { describe, it, expect } from "vitest";
import { parseSectionedFeedback } from "../feedback-sections";

const FIVE_SECTION_FIXTURE = `## ♟ Opening
You played the Italian Game. Your opening was textbook through move 4.

## ⚔ Middlegame
Move 18 was a mistake — you traded your good bishop for an inactive knight.

## ♔ Endgame
The endgame conversion was clean — you found 32.Re7 quickly.

## 🪤 Watch Out For (Trap Awareness)
Watch out for the Fried Liver Attack — if your opponent had played 4.Ng5...

## 🎯 Top 3 Improvements
1. Find one knight outpost before move 15.
2. Trade off your worst-placed piece first.
3. Activate your rooks before move 20.`;

describe("parseSectionedFeedback", () => {
  it("returns empty array for null/undefined/empty input", () => {
    expect(parseSectionedFeedback(null)).toEqual([]);
    expect(parseSectionedFeedback(undefined)).toEqual([]);
    expect(parseSectionedFeedback("")).toEqual([]);
    expect(parseSectionedFeedback("   \n  \t")).toEqual([]);
  });

  it("parses 5-section v1.13.0 input into 5 ordered sections", () => {
    const sections = parseSectionedFeedback(FIVE_SECTION_FIXTURE);
    expect(sections).toHaveLength(5);
    expect(sections[0].heading).toBe("♟ Opening");
    expect(sections[1].heading).toBe("⚔ Middlegame");
    expect(sections[2].heading).toBe("♔ Endgame");
    expect(sections[3].heading).toBe("🪤 Watch Out For (Trap Awareness)");
    expect(sections[4].heading).toBe("🎯 Top 3 Improvements");
  });

  it("each section has a non-empty body", () => {
    const sections = parseSectionedFeedback(FIVE_SECTION_FIXTURE);
    for (const s of sections) {
      expect(s.body.length).toBeGreaterThan(0);
    }
  });

  it("opening section body contains the Italian Game text", () => {
    const sections = parseSectionedFeedback(FIVE_SECTION_FIXTURE);
    expect(sections[0].body[0]).toContain("Italian Game");
  });

  it("legacy single-paragraph input returns 1 section with empty heading", () => {
    const legacy = "Evan, you played a great game! Your knight on e5 was excellent.";
    const sections = parseSectionedFeedback(legacy);
    expect(sections).toHaveLength(1);
    expect(sections[0].heading).toBe("");
    expect(sections[0].body[0]).toContain("Evan");
  });

  it("legacy multi-paragraph input splits into paragraphs inside one section", () => {
    const legacy = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph.";
    const sections = parseSectionedFeedback(legacy);
    expect(sections).toHaveLength(1);
    expect(sections[0].heading).toBe("");
    expect(sections[0].body).toHaveLength(3);
  });

  it("handles v1.8.2 escape-leak: literal \\n\\n sequences from OpenAI Responses API", () => {
    // Simulate the bug: real string contains backslash-n-backslash-n instead of newlines
    const leaked =
      "## ♟ Opening\\nYou played Italian.\\n\\n## ⚔ Middlegame\\nMove 18 mistake.";
    const sections = parseSectionedFeedback(leaked);
    expect(sections).toHaveLength(2);
    expect(sections[0].heading).toBe("♟ Opening");
    expect(sections[0].body[0]).toContain("Italian");
    // No literal `\n` should leak into any body
    for (const s of sections) {
      for (const p of s.body) {
        expect(p).not.toContain("\\n");
      }
    }
  });

  it("ignores preamble text before the first heading (graceful)", () => {
    const withPreamble = "Some intro text.\n\n## ♟ Opening\nReal section.";
    const sections = parseSectionedFeedback(withPreamble);
    // Only the real section is returned; preamble dropped
    expect(sections).toHaveLength(1);
    expect(sections[0].heading).toBe("♟ Opening");
  });

  it("accepts bonus headings beyond the spec (forward-compat)", () => {
    const withBonus =
      FIVE_SECTION_FIXTURE + "\n\n## 🎁 Bonus Section\nLLM added an extra.";
    const sections = parseSectionedFeedback(withBonus);
    expect(sections).toHaveLength(6);
    expect(sections[5].heading).toBe("🎁 Bonus Section");
  });

  it("section bodies preserve internal paragraph breaks", () => {
    const multiPara = `## ♟ Opening
First paragraph of opening.

Second paragraph of opening.

## ⚔ Middlegame
Middlegame text.`;
    const sections = parseSectionedFeedback(multiPara);
    expect(sections[0].body).toHaveLength(2);
    expect(sections[1].body).toHaveLength(1);
  });

  it("trims whitespace from headings and body paragraphs", () => {
    const padded = "##   ♟ Opening   \n   Body with padding.   ";
    const sections = parseSectionedFeedback(padded);
    expect(sections[0].heading).toBe("♟ Opening");
    expect(sections[0].body[0]).toBe("Body with padding.");
  });
});
