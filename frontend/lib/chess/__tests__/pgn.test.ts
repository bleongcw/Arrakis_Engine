import { parseMoveText } from "@/lib/chess/pgn";

describe("parseMoveText", () => {
  it("strips numeric move prefixes with a space", () => {
    expect(parseMoveText("1. e4 e5 2. Nf3 Nc6")).toEqual([
      "e4",
      "e5",
      "Nf3",
      "Nc6",
    ]);
  });

  it("strips numeric move prefixes without a space", () => {
    expect(parseMoveText("1.e4 e5 2.Nf3 Nc6")).toEqual([
      "e4",
      "e5",
      "Nf3",
      "Nc6",
    ]);
  });

  it("strips the 1-0 result marker", () => {
    expect(parseMoveText("1.e4 e5 2.Nf3 Nc6 1-0")).toEqual([
      "e4",
      "e5",
      "Nf3",
      "Nc6",
    ]);
  });

  it("strips the 0-1 result marker", () => {
    expect(parseMoveText("1.e4 e5 0-1")).toEqual(["e4", "e5"]);
  });

  it("strips the 1/2-1/2 result marker", () => {
    expect(parseMoveText("1.e4 e5 1/2-1/2")).toEqual(["e4", "e5"]);
  });

  it("strips the * (game-in-progress) result marker", () => {
    expect(parseMoveText("1.e4 e5 *")).toEqual(["e4", "e5"]);
  });

  it("returns [] on an empty string", () => {
    expect(parseMoveText("")).toEqual([]);
  });

  it("returns [] on a whitespace-only string", () => {
    expect(parseMoveText("   \t  \n  ")).toEqual([]);
  });

  it("returns [] when only prefixes and result markers are present", () => {
    expect(parseMoveText("1. 2. 3. 1-0")).toEqual([]);
  });

  it("tolerates irregular whitespace between moves", () => {
    expect(parseMoveText("  1.   e4    e5   2.\tNf3 ")).toEqual([
      "e4",
      "e5",
      "Nf3",
    ]);
  });

  it("preserves SAN annotations (check, mate, capture)", () => {
    expect(parseMoveText("1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6 4.Qxf7#")).toEqual([
      "e4",
      "e5",
      "Bc4",
      "Nc6",
      "Qh5",
      "Nf6",
      "Qxf7#",
    ]);
  });
});
