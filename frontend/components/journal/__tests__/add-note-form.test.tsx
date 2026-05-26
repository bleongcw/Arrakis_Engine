import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AddNoteForm } from "../add-note-form";
import * as api from "@/lib/api";

describe("AddNoteForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("starts collapsed showing only an Add Note button", () => {
    render(<AddNoteForm player="evan" onCreated={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Add Note/ })).toBeInTheDocument();
    // textarea should not be rendered yet
    expect(screen.queryByLabelText(/Note body/i)).not.toBeInTheDocument();
  });

  it("opens the form when Add Note is clicked", () => {
    render(<AddNoteForm player="evan" onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Add Note/ }));
    expect(screen.getByLabelText(/Note body/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Post note/ })).toBeInTheDocument();
  });

  it("disables Post button when body is empty", () => {
    render(<AddNoteForm player="evan" onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Add Note/ }));
    const postBtn = screen.getByRole("button", { name: /Post note/ });
    expect(postBtn).toBeDisabled();
  });

  it("enables Post button when body has content", () => {
    render(<AddNoteForm player="evan" onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Add Note/ }));
    fireEvent.change(screen.getByLabelText(/Note body/i), {
      target: { value: "Tournament win!" },
    });
    expect(screen.getByRole("button", { name: /Post note/ })).not.toBeDisabled();
  });

  it("calls createJournalNote and onCreated on submit", async () => {
    const onCreated = vi.fn();
    const createSpy = vi.spyOn(api, "createJournalNote").mockResolvedValue({
      entry: {
        id: 42,
        player_id: 1,
        kind: "note",
        platform: "chess.com",
        body: "Round 3 win!",
        refs: [],
        provider: null,
        metadata: {},
        created_at: new Date().toISOString(),
      },
    });

    render(<AddNoteForm player="evan" onCreated={onCreated} />);
    fireEvent.click(screen.getByRole("button", { name: /Add Note/ }));
    fireEvent.change(screen.getByLabelText(/Note body/i), {
      target: { value: "Round 3 win!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Post note/ }));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith("evan", "Round 3 win!", "chess.com");
    });
    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledTimes(1);
    });
    expect(onCreated.mock.calls[0][0]).toMatchObject({ id: 42, kind: "note" });
  });

  it("displays server error and does NOT call onCreated on failure", async () => {
    const onCreated = vi.fn();
    vi.spyOn(api, "createJournalNote").mockRejectedValue(
      new Error("rate limited"),
    );

    render(<AddNoteForm player="evan" onCreated={onCreated} />);
    fireEvent.click(screen.getByRole("button", { name: /Add Note/ }));
    fireEvent.change(screen.getByLabelText(/Note body/i), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Post note/ }));

    await waitFor(() => {
      expect(screen.getByText("rate limited")).toBeInTheDocument();
    });
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("closes the form when Cancel is clicked, dropping any text", () => {
    render(<AddNoteForm player="evan" onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Add Note/ }));
    fireEvent.change(screen.getByLabelText(/Note body/i), {
      target: { value: "draft" },
    });
    // Two "Cancel" elements exist: the × icon (aria-label="Cancel") in the
    // header and the explicit text button. Target the text variant.
    fireEvent.click(screen.getByText("Cancel"));
    // Form is now collapsed
    expect(screen.queryByLabelText(/Note body/i)).not.toBeInTheDocument();
    // Re-opening shows an empty textarea
    fireEvent.click(screen.getByRole("button", { name: /Add Note/ }));
    expect((screen.getByLabelText(/Note body/i) as HTMLTextAreaElement).value).toBe("");
  });

  it("rejects whitespace-only body (treated as empty)", () => {
    render(<AddNoteForm player="evan" onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Add Note/ }));
    fireEvent.change(screen.getByLabelText(/Note body/i), {
      target: { value: "   \n  " },
    });
    expect(screen.getByRole("button", { name: /Post note/ })).toBeDisabled();
  });

  it("shows a character counter that updates as user types", () => {
    render(<AddNoteForm player="evan" onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Add Note/ }));
    fireEvent.change(screen.getByLabelText(/Note body/i), {
      target: { value: "hello" },
    });
    expect(screen.getByText(/5 \/ 4000/)).toBeInTheDocument();
  });
});
