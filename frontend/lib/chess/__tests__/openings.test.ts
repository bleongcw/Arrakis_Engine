import {
  normalizeOpeningName,
  findCanonicalLine,
  findDeviationIndex,
  type LibraryOpening,
} from "@/lib/chess/openings";

describe("normalizeOpeningName", () => {
  it("lowercases the input", () => {
    expect(normalizeOpeningName("ITALIAN Game")).toBe("italian game");
  });

  it("strips colons, commas, hyphens, and apostrophes", () => {
    expect(
      normalizeOpeningName("Caro-Kann Defense: Advance, Short Variation"),
    ).toBe("caro kann defense advance short variation");
  });

  it("strips the chess.com '...' continuation marker", () => {
    expect(normalizeOpeningName("Ruy Lopez ...e5")).toBe("ruy lopez e5");
  });

  it("collapses internal whitespace", () => {
    expect(normalizeOpeningName("Italian   Game   Two   Knights")).toBe(
      "italian game two knights",
    );
  });

  it("returns an empty string for an empty input", () => {
    expect(normalizeOpeningName("")).toBe("");
  });

  it("returns an empty string when only punctuation is supplied", () => {
    expect(normalizeOpeningName(":-.,")).toBe("");
  });
});

const library: LibraryOpening[] = [
  { eco: "C50", name: "Italian Game", moves: "1. e4 e5 2. Nf3 Nc6 3. Bc4" },
  {
    eco: "C55",
    name: "Italian Game: Two Knights Defense",
    moves: "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6",
  },
  {
    eco: "B12",
    name: "Caro-Kann Defense: Advance Variation",
    moves: "1. e4 c6 2. d4 d5 3. e5",
  },
  { eco: "A00", name: "Polish Opening", moves: "1. b4" },
];

describe("findCanonicalLine", () => {
  it("matches exactly on raw name", () => {
    const result = findCanonicalLine("Italian Game", library);
    expect(result?.eco).toBe("C50");
  });

  it("matches on normalized name when punctuation differs", () => {
    // Library has "Caro-Kann Defense: Advance Variation".
    // Target uses different punctuation; normalized comparison should still match.
    const result = findCanonicalLine(
      "Caro Kann Defense Advance Variation",
      library,
    );
    expect(result?.eco).toBe("B12");
  });

  it("prefers the longer specific variation over the generic prefix", () => {
    // Target normalizes to "italian game two knights defense" which has BOTH
    // the generic "italian game" entry AND the "italian game two knights
    // defense" entry as prefix matches. The longer one must win.
    const result = findCanonicalLine(
      "Italian Game: Two Knights Defense",
      library,
    );
    expect(result?.eco).toBe("C55");
  });

  it("matches bidirectionally: library entry is a prefix of target", () => {
    // Library entry "Italian Game" is shorter than the target; it should
    // still match as a fallback when no longer entry overlaps.
    const result = findCanonicalLine("Italian Game with Some Suffix", [
      { eco: "C50", name: "Italian Game", moves: "1. e4 e5 2. Nf3 Nc6 3. Bc4" },
    ]);
    expect(result?.eco).toBe("C50");
  });

  it("returns null on an empty opening name", () => {
    expect(findCanonicalLine("", library)).toBeNull();
  });

  it("returns null on an empty library", () => {
    expect(findCanonicalLine("Italian Game", [])).toBeNull();
  });

  it("returns null when no entry overlaps the target", () => {
    expect(findCanonicalLine("Nonexistent Opening", library)).toBeNull();
  });
});

describe("findDeviationIndex", () => {
  it("returns 0 when the very first move differs", () => {
    expect(findDeviationIndex(["d4"], ["e4"])).toBe(0);
  });

  it("returns the index of the first differing move", () => {
    expect(
      findDeviationIndex(["e4", "e5", "Nf3", "d6"], ["e4", "e5", "Nf3", "Nc6"]),
    ).toBe(3);
  });

  it("returns -1 when game matches book for the entire shared length", () => {
    expect(
      findDeviationIndex(["e4", "e5", "Nf3"], ["e4", "e5", "Nf3", "Nc6"]),
    ).toBe(-1);
  });

  it("returns -1 when both arrays are empty", () => {
    expect(findDeviationIndex([], [])).toBe(-1);
  });

  it("returns -1 when book is empty (no overlap to compare)", () => {
    expect(findDeviationIndex(["e4", "e5"], [])).toBe(-1);
  });

  it("returns -1 when game is empty (no overlap to compare)", () => {
    expect(findDeviationIndex([], ["e4", "e5"])).toBe(-1);
  });
});
