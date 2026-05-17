import { renderHook, act } from "@testing-library/react";
import { useChessNavigation } from "@/hooks/use-chess-navigation";

describe("useChessNavigation — empty / invalid input", () => {
  it("safely handles an empty PGN", () => {
    const { result } = renderHook(() => useChessNavigation("", "white"));
    expect(result.current.moves).toEqual([]);
    expect(result.current.totalMoves).toBe(0);
    expect(result.current.moveIndex).toBe(-1);
    expect(result.current.fens.length).toBe(1);
  });

  it("safely handles a whitespace-only PGN", () => {
    const { result } = renderHook(() => useChessNavigation("   \n  ", "white"));
    expect(result.current.moves).toEqual([]);
    expect(result.current.fens.length).toBe(1);
  });

  it("safely handles malformed PGN without throwing", () => {
    const { result } = renderHook(() =>
      useChessNavigation("this is not a real pgn", "white"),
    );
    expect(result.current.moves).toEqual([]);
  });
});

describe("useChessNavigation — PGN parsing", () => {
  it("parses a basic PGN into SAN moves", () => {
    const { result } = renderHook(() =>
      useChessNavigation("1. e4 e5 2. Nf3 Nc6", "white"),
    );
    expect(result.current.moves).toEqual(["e4", "e5", "Nf3", "Nc6"]);
    expect(result.current.totalMoves).toBe(4);
  });

  it("v1.4.5 regression: clock comments {[%clk ...]} do NOT leak into moves", () => {
    // chess.com PGNs embed per-move clock annotations. Before v1.4.5 a
    // regex-based parser was bleeding these into the moves array. chess.js
    // strips them; this test locks that behavior in.
    const pgnWithClocks =
      "1. e4 {[%clk 0:05:00]} e5 {[%clk 0:05:00]} 2. Nf3 {[%clk 0:04:55]} Nc6 {[%clk 0:04:50]}";
    const { result } = renderHook(() =>
      useChessNavigation(pgnWithClocks, "white"),
    );
    expect(result.current.moves).toEqual(["e4", "e5", "Nf3", "Nc6"]);
    for (const move of result.current.moves) {
      expect(move).not.toContain("[%clk");
      expect(move).not.toContain("}");
    }
  });

  it("FEN array length = moves.length + 1 (off-by-one guard)", () => {
    const { result } = renderHook(() =>
      useChessNavigation("1. e4 e5 2. Nf3", "white"),
    );
    expect(result.current.fens.length).toBe(result.current.moves.length + 1);
  });

  it("endFen is the position after the last move regardless of moveIndex", () => {
    const { result } = renderHook(() =>
      useChessNavigation("1. e4 e5 2. Nf3 Nc6", "white"),
    );
    const endAtStart = result.current.endFen;
    act(() => result.current.goToEnd());
    expect(result.current.endFen).toBe(endAtStart);
    expect(result.current.currentFen).toBe(endAtStart);
  });
});

describe("useChessNavigation — navigation boundaries", () => {
  it("goBack at start stays at -1 (no underflow)", () => {
    const { result } = renderHook(() =>
      useChessNavigation("1. e4 e5", "white"),
    );
    expect(result.current.moveIndex).toBe(-1);
    act(() => result.current.goBack());
    expect(result.current.moveIndex).toBe(-1);
  });

  it("goForward at the last move stays at moves.length - 1 (no overflow)", () => {
    const { result } = renderHook(() =>
      useChessNavigation("1. e4 e5", "white"),
    );
    act(() => result.current.goToEnd());
    expect(result.current.moveIndex).toBe(1);
    act(() => result.current.goForward());
    expect(result.current.moveIndex).toBe(1);
  });

  it("goToStart resets moveIndex to -1", () => {
    const { result } = renderHook(() =>
      useChessNavigation("1. e4 e5", "white"),
    );
    act(() => result.current.goToEnd());
    act(() => result.current.goToStart());
    expect(result.current.moveIndex).toBe(-1);
  });

  it("goToEnd advances to the last move's index", () => {
    const { result } = renderHook(() =>
      useChessNavigation("1. e4 e5 2. Nf3", "white"),
    );
    act(() => result.current.goToEnd());
    expect(result.current.moveIndex).toBe(2);
  });
});

describe("useChessNavigation — board orientation", () => {
  it("playerColor 'black' → boardOrientation 'black'", () => {
    const { result } = renderHook(() => useChessNavigation("", "black"));
    expect(result.current.boardOrientation).toBe("black");
  });

  it("playerColor 'white' → boardOrientation 'white'", () => {
    const { result } = renderHook(() => useChessNavigation("", "white"));
    expect(result.current.boardOrientation).toBe("white");
  });
});

describe("useChessNavigation — keyboard handler", () => {
  it("ArrowRight advances the move index when no input is focused", () => {
    const { result } = renderHook(() =>
      useChessNavigation("1. e4 e5", "white"),
    );
    expect(result.current.moveIndex).toBe(-1);
    act(() => {
      window.dispatchEvent(
        new KeyboardEvent("keydown", { key: "ArrowRight" }),
      );
    });
    expect(result.current.moveIndex).toBe(0);
  });

  it("ArrowLeft retreats the move index when no input is focused", () => {
    const { result } = renderHook(() =>
      useChessNavigation("1. e4 e5", "white"),
    );
    act(() => result.current.goToEnd());
    expect(result.current.moveIndex).toBe(1);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft" }));
    });
    expect(result.current.moveIndex).toBe(0);
  });

  it("ArrowRight is ignored when an <input> is focused (typing guard)", () => {
    const { result } = renderHook(() =>
      useChessNavigation("1. e4 e5", "white"),
    );
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();
    try {
      act(() => {
        input.dispatchEvent(
          new KeyboardEvent("keydown", {
            key: "ArrowRight",
            bubbles: true,
          }),
        );
      });
      expect(result.current.moveIndex).toBe(-1);
    } finally {
      document.body.removeChild(input);
    }
  });

  it("ArrowRight is ignored when a <textarea> is focused (typing guard)", () => {
    const { result } = renderHook(() =>
      useChessNavigation("1. e4 e5", "white"),
    );
    const textarea = document.createElement("textarea");
    document.body.appendChild(textarea);
    textarea.focus();
    try {
      act(() => {
        textarea.dispatchEvent(
          new KeyboardEvent("keydown", {
            key: "ArrowRight",
            bubbles: true,
          }),
        );
      });
      expect(result.current.moveIndex).toBe(-1);
    } finally {
      document.body.removeChild(textarea);
    }
  });
});
