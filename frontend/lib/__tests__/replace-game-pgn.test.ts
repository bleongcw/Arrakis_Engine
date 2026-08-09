import { describe, it, expect, vi, afterEach } from "vitest";
import { replaceGamePgn } from "@/lib/api";

// v1.32.0: replaceGamePgn PUTs the corrected PGN and surfaces the server's
// error message (e.g. the illegal-move ply) on failure.

afterEach(() => {
  vi.restoreAllMocks();
});

describe("replaceGamePgn", () => {
  it("PUTs to /api/games/{id}/pgn with the pgn body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "saved", game_id: 42, re_analyzing: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const out = await replaceGamePgn(42, { pgn: "1. e4 e5 *", player_color: "white" });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/games/42/pgn");
    expect(opts.method).toBe("PUT");
    expect(JSON.parse(opts.body)).toEqual({ pgn: "1. e4 e5 *", player_color: "white" });
    expect(out.re_analyzing).toBe(true);
  });

  it("throws with the server's error message on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: "Invalid move in PGN: illegal san: 'Qxe5'" }),
    }));

    await expect(replaceGamePgn(1, { pgn: "bad" })).rejects.toThrow(/illegal san/);
  });
});
