import { lichessAnalysisUrl } from "@/lib/chess/lichess";

// v1.4.5 regression lock — Lichess analysis links must use the
// /analysis/standard/<fen-with-underscores> form, NOT the ?pgn=<...> form
// which does not reliably load specific positions.

describe("lichessAnalysisUrl", () => {
  it("produces the exact /analysis/standard/<fen-with-underscores> form for the starting position", () => {
    expect(
      lichessAnalysisUrl(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      ),
    ).toBe(
      "https://lichess.org/analysis/standard/rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR_w_KQkq_-_0_1",
    );
  });

  it("replaces every space in the FEN with an underscore", () => {
    const url = lichessAnalysisUrl("a b c d e f");
    expect(url).toBe("https://lichess.org/analysis/standard/a_b_c_d_e_f");
    expect(url).not.toContain(" ");
  });

  it("uses the /analysis/standard/ path, never the ?pgn= form", () => {
    // The load-bearing v1.4.5 lesson: ?pgn= does NOT work for deep-linking
    // specific positions. If anyone reverts to it, this test breaks.
    const url = lichessAnalysisUrl(
      "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    );
    expect(url).toMatch(/^https:\/\/lichess\.org\/analysis\/standard\//);
    expect(url).not.toContain("?pgn=");
    expect(url).not.toContain("?fen=");
  });

  it("handles an empty FEN by producing the base /analysis/standard/ path", () => {
    expect(lichessAnalysisUrl("")).toBe(
      "https://lichess.org/analysis/standard/",
    );
  });

  it("handles a mid-game FEN with multiple spaces", () => {
    expect(
      lichessAnalysisUrl(
        "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
      ),
    ).toBe(
      "https://lichess.org/analysis/standard/r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R_w_KQkq_-_2_3",
    );
  });
});
