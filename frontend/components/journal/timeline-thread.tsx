"use client";

/** v1.11.0: Color-coded node that attaches an entry card to the vertical
 *  timeline rail running down the Journal feed.
 *
 * The rail itself isn't a separate DOM element — it's a left border on each
 * EntryCard that visually stitches into the next. The Node component renders
 * the colored dot positioned over that border, so the whole column reads as
 * a continuous timeline thread without absolute-positioning gymnastics.
 *
 * Node color encodes the entry kind so the eye can see "story rhythm":
 *   - 🟢 emerald = review        (v1.10.0+ — LLM-generated coaching reviews)
 *   - 🔵 blue    = note          (v1.12.0+ — parent-authored notes)
 *   - ⚪ gray    = unknown kinds (graceful fallback)
 */

const NODE_COLORS: Record<string, string> = {
  review: "bg-emerald-500 border-emerald-600",
  note: "bg-blue-500 border-blue-600",
  // v1.19.0: recurring-weakness alert — red to flag it stands out.
  weakness_alert: "bg-red-500 border-red-600",
};

const FALLBACK_COLOR = "bg-zinc-400 border-zinc-500";

export interface TimelineNodeProps {
  kind: string;
  /** Optional title for the dot (shown as native tooltip on hover) */
  title?: string;
}

/**
 * The colored dot that attaches an entry to the timeline rail.
 * Sized to overlap the 2px left border by ~6px on each side so it visually
 * sits ON the line rather than next to it.
 */
export function TimelineNode({ kind, title }: TimelineNodeProps) {
  const color = NODE_COLORS[kind] ?? FALLBACK_COLOR;
  return (
    <span
      aria-hidden
      title={title}
      className={
        "absolute left-0 top-3 -translate-x-1/2 " +
        "w-3 h-3 rounded-full border-2 ring-2 ring-background " +
        color
      }
    />
  );
}
