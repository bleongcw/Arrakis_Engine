import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { EntryCard } from "../entry-card";
import type { JournalEntry } from "@/lib/api";
import type { GameListItem } from "@/lib/types";
import * as api from "@/lib/api";

// `Element.prototype.scrollIntoView` is not implemented in jsdom — the
// EntryCard calls it when `pulseOnMount=true`. Mock it so the test runs.
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  vi.restoreAllMocks();
});

const baseEntry: JournalEntry = {
  id: 42,
  player_id: 1,
  kind: "review",
  platform: "chess.com",
  body: "First sentence of the review. Second sentence. Third sentence. Fourth.",
  refs: [100, 101],
  provider: "openai:gpt-5.5-pro-2026-04-23",
  metadata: {},
  // 1 hour ago relative to a fixed test moment — useLiveRelativeTime will
  // render "today, HH:MM" (rather than "just now" or "yesterday")
  created_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
};

const baseGames: GameListItem[] = [
  // Minimal stub matching just what EntryCard reads (id, result, player_color, date_played)
  { id: 100, result: "win", player_color: "white", date_played: "2026-05-26" } as GameListItem,
  { id: 101, result: "loss", player_color: "black", date_played: "2026-05-25" } as GameListItem,
];

describe("EntryCard", () => {
  it("renders expanded by default when defaultExpanded=true", () => {
    render(<EntryCard entry={baseEntry} player="evan" games={baseGames} defaultExpanded={true} />);
    expect(screen.getByText(/First sentence of the review/)).toBeInTheDocument();
    expect(screen.getByText(/Second sentence/)).toBeInTheDocument();
  });

  it("renders collapsed preview when defaultExpanded=false", () => {
    render(<EntryCard entry={baseEntry} player="evan" games={baseGames} defaultExpanded={false} />);
    // Preview shows the first sentence, but the full body paragraphs should NOT render
    expect(screen.getByText(/First sentence of the review/)).toBeInTheDocument();
    expect(screen.queryByText(/Second sentence/)).not.toBeInTheDocument();
  });

  it("expands when the collapsed preview is clicked", () => {
    render(<EntryCard entry={baseEntry} player="evan" games={baseGames} defaultExpanded={false} />);
    expect(screen.queryByText(/Second sentence/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/First sentence of the review/));
    expect(screen.getByText(/Second sentence/)).toBeInTheDocument();
  });

  it("toggles back to collapsed when the header is clicked again", () => {
    render(<EntryCard entry={baseEntry} player="evan" games={baseGames} defaultExpanded={true} />);
    const header = screen.getByRole("button", { name: /Review/ });
    fireEvent.click(header);
    expect(screen.queryByText(/Second sentence/)).not.toBeInTheDocument();
  });

  it("renders kind icon + label for review", () => {
    render(<EntryCard entry={baseEntry} player="evan" games={baseGames} />);
    expect(screen.getByText(/📖 Review/)).toBeInTheDocument();
  });

  it("renders kind icon + label for note (forward-compat for v1.12.0)", () => {
    const note = { ...baseEntry, kind: "note" };
    render(<EntryCard entry={note} player="evan" games={baseGames} />);
    expect(screen.getByText(/📝 Note/)).toBeInTheDocument();
  });

  it("renders platform badge", () => {
    render(<EntryCard entry={baseEntry} player="evan" games={baseGames} />);
    expect(screen.getByText("chess.com")).toBeInTheDocument();
  });

  it("renders model badge (just the model name, not the provider prefix)", () => {
    render(<EntryCard entry={baseEntry} player="evan" games={baseGames} />);
    expect(screen.getByText("gpt-5.5-pro-2026-04-23")).toBeInTheDocument();
  });

  it("renders referenced-game pills as links to /[player]/games/[id]", () => {
    render(<EntryCard entry={baseEntry} player="evan" games={baseGames} />);
    const game100Link = screen.getByText(/#100/).closest("a");
    const game101Link = screen.getByText(/#101/).closest("a");
    expect(game100Link?.getAttribute("href")).toBe("/evan/games/100");
    expect(game101Link?.getAttribute("href")).toBe("/evan/games/101");
  });

  it("renders no referenced-games row when refs is empty", () => {
    const entry = { ...baseEntry, refs: [] };
    render(<EntryCard entry={entry} player="evan" games={baseGames} />);
    expect(screen.queryByText(/Referenced games:/)).not.toBeInTheDocument();
  });

  it("scrolls into view + pulses when pulseOnMount=true", () => {
    render(
      <EntryCard
        entry={baseEntry}
        player="evan"
        games={baseGames}
        pulseOnMount={true}
      />,
    );
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it("does NOT scroll when pulseOnMount=false (default)", () => {
    render(<EntryCard entry={baseEntry} player="evan" games={baseGames} />);
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
  });
});

// ─── v1.12.0: edit + delete actions for notes ─────────────────────

const noteEntry: JournalEntry = {
  ...baseEntry,
  kind: "note",
  provider: null, // notes have no LLM provider
  body: "Round 3 of the Saturday tournament. Evan beat Sarah!",
};

describe("EntryCard — note edit/delete (v1.12.0)", () => {
  it("does NOT show Edit/Delete buttons on review entries", () => {
    render(<EntryCard entry={baseEntry} player="evan" games={baseGames} />);
    expect(screen.queryByRole("button", { name: /Edit note/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Delete note/ })).not.toBeInTheDocument();
  });

  it("shows Edit/Delete buttons on note entries", () => {
    render(<EntryCard entry={noteEntry} player="evan" games={baseGames} />);
    expect(screen.getByRole("button", { name: /Edit note/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Delete note/ })).toBeInTheDocument();
  });

  it("clicking Edit swaps the body for a textarea", () => {
    render(<EntryCard entry={noteEntry} player="evan" games={baseGames} />);
    fireEvent.click(screen.getByRole("button", { name: /Edit note/ }));
    const ta = screen.getByLabelText(/Edit note body/i) as HTMLTextAreaElement;
    expect(ta).toBeInTheDocument();
    expect(ta.value).toBe(noteEntry.body);
  });

  it("Save calls updateJournalNote and onChanged", async () => {
    const onChanged = vi.fn();
    const updateSpy = vi.spyOn(api, "updateJournalNote").mockResolvedValue({
      entry: { ...noteEntry, body: "Edited body." },
    });

    render(
      <EntryCard
        entry={noteEntry}
        player="evan"
        games={baseGames}
        onChanged={onChanged}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Edit note/ }));
    fireEvent.change(screen.getByLabelText(/Edit note body/i), {
      target: { value: "Edited body." },
    });
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(noteEntry.id, "Edited body.");
    });
    await waitFor(() => {
      expect(onChanged).toHaveBeenCalledTimes(1);
    });
  });

  it("Cancel restores the original body and exits edit mode", () => {
    render(<EntryCard entry={noteEntry} player="evan" games={baseGames} />);
    fireEvent.click(screen.getByRole("button", { name: /Edit note/ }));
    fireEvent.change(screen.getByLabelText(/Edit note body/i), {
      target: { value: "discarded edit" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Cancel/ }));
    // Edit mode dismissed
    expect(screen.queryByLabelText(/Edit note body/i)).not.toBeInTheDocument();
    // Original body still visible
    expect(screen.getByText(noteEntry.body!)).toBeInTheDocument();
  });

  it("Save is disabled when textarea is empty", () => {
    render(<EntryCard entry={noteEntry} player="evan" games={baseGames} />);
    fireEvent.click(screen.getByRole("button", { name: /Edit note/ }));
    fireEvent.change(screen.getByLabelText(/Edit note body/i), {
      target: { value: "   " },
    });
    expect(screen.getByRole("button", { name: /Save/ })).toBeDisabled();
  });

  it("Delete calls deleteJournalNote after user confirms", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const deleteSpy = vi.spyOn(api, "deleteJournalNote").mockResolvedValue({
      status: "deleted",
      id: noteEntry.id,
    });
    const onChanged = vi.fn();

    render(
      <EntryCard
        entry={noteEntry}
        player="evan"
        games={baseGames}
        onChanged={onChanged}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Delete note/ }));

    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith(noteEntry.id);
    });
    await waitFor(() => {
      expect(onChanged).toHaveBeenCalledTimes(1);
    });
  });

  it("Delete does NOT call API when user cancels the confirm", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const deleteSpy = vi.spyOn(api, "deleteJournalNote");
    const onChanged = vi.fn();

    render(
      <EntryCard
        entry={noteEntry}
        player="evan"
        games={baseGames}
        onChanged={onChanged}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Delete note/ }));

    expect(deleteSpy).not.toHaveBeenCalled();
    expect(onChanged).not.toHaveBeenCalled();
  });
});
