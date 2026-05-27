// ArrakisEngine — Chess Coaching AI
// Copyright (C) 2026 Bernard Leong
// Licensed under AGPL-3.0. See LICENSE file.

/**
 * v1.13.0: Parser for the structured `player_feedback` field on
 * `game_coaching`.
 *
 * Starting in v1.13.0 the coaching prompt instructs the LLM to produce
 * `player_feedback` as a single string with 5 markdown sections in this
 * order:
 *
 *   ## ♟ Opening
 *   ...
 *   ## ⚔ Middlegame
 *   ...
 *   ## ♔ Endgame
 *   ...
 *   ## 🪤 Watch Out For (Trap Awareness)
 *   ...
 *   ## 🎯 Top 3 Improvements
 *   ...
 *
 * This parser splits on `^## ` lines and returns ordered sections so the
 * UI can render styled headings per section.
 *
 * Backward-compat: pre-v1.13.0 coached games have freeform freeform
 * `player_feedback` text with no `## ` headings. The parser detects that
 * and returns a single section with empty heading + the full text as one
 * paragraph — the UI renders that as a flat block, matching the
 * pre-v1.13.0 look.
 *
 * Also handles the v1.8.2 OpenAI Responses-API escape leak (literal
 * `\n` sequences arriving as two characters instead of real newlines)
 * via the shared `unescapeNewlines` helper from `summary.ts`.
 */

import { unescapeNewlines } from "./summary";

export interface FeedbackSection {
  /** The heading text without the leading `## ` (empty for legacy entries). */
  heading: string;
  /** Body paragraphs — already split on blank lines, each trimmed. */
  body: string[];
}

export function parseSectionedFeedback(
  text: string | null | undefined,
): FeedbackSection[] {
  if (!text) return [];
  // Normalize escape leaks BEFORE splitting on headings, so the regex
  // matches `## Heading` whether or not the LLM newlines are real.
  const normalized = unescapeNewlines(text).trim();
  if (!normalized) return [];

  // No `## ` headings → legacy single-block fallback. Return one section
  // with empty heading and the full text as one paragraph (paragraphs
  // inside still split on blank-line boundaries).
  if (!/^##\s+/m.test(normalized)) {
    return [
      {
        heading: "",
        body: splitParagraphs(normalized),
      },
    ];
  }

  // Split on `## ` headings. Capture the heading text on each line.
  // Anything BEFORE the first heading is dropped (rare; would only
  // happen if the LLM ignored the spec and put a preamble in).
  const sections: FeedbackSection[] = [];
  const headingRegex = /^##\s+(.+)$/gm;
  const headings: { heading: string; start: number; end: number }[] = [];
  let match: RegExpExecArray | null;
  while ((match = headingRegex.exec(normalized)) !== null) {
    headings.push({
      heading: match[1].trim(),
      start: match.index,
      end: match.index + match[0].length,
    });
  }

  for (let i = 0; i < headings.length; i++) {
    const h = headings[i];
    const bodyStart = h.end;
    const bodyEnd = i + 1 < headings.length ? headings[i + 1].start : normalized.length;
    const bodyText = normalized.slice(bodyStart, bodyEnd).trim();
    sections.push({
      heading: h.heading,
      body: splitParagraphs(bodyText),
    });
  }

  return sections;
}

function splitParagraphs(text: string): string[] {
  return text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
}
