// ArrakisEngine — Chess Coaching AI
// Copyright (C) 2026 Bernard Leong
// Licensed under AGPL-3.0. See LICENSE file.

/**
 * Parser for `trend_summary` strings stored on `player_patterns` (also reused
 * for Journal Recent Form Review entries since v1.10.0).
 *
 * Backend stores whatever the LLM returns verbatim. The shape varies:
 *  - Plain prose with real `\n\n` paragraph breaks (Claude, Gemini, DeepSeek).
 *  - JSON `{"paragraphs": [...]}` (older Claude runs).
 *  - JSON array `["para 1", "para 2", ...]` (v1.14.1 — observed on gpt-5.5-pro
 *    Journal reviews; the LLM serializes the multi-paragraph output as a JSON
 *    list instead of plain prose).
 *  - Plain prose where `\n` arrives as the **two-character** escape sequence
 *    `\` + `n` instead of a real newline (some ChatGPT / Responses API
 *    runs). Splitting on real `"\n\n"` then silently produces one giant
 *    paragraph with literal `\n\n` text leaking into the UI — the v1.8.2 bug.
 *
 * The fix: normalize literal `\n` sequences to real newlines *before*
 * splitting, and also inside each JSON-extracted paragraph in case the
 * escape leaked through the JSON layer too. v1.14.1 adds the JSON-array
 * branch (previously fell through to plain-text path which leaked the
 * brackets and quotes into the rendered card).
 */
export function parseTrendSummary(summary: string | null | undefined): string[] {
  if (!summary) return [];
  const trimmed = summary.trim();

  let candidates: string[] = [];

  if (trimmed.startsWith("{")) {
    try {
      const parsed: unknown = JSON.parse(trimmed);
      if (parsed && typeof parsed === "object") {
        const obj = parsed as Record<string, unknown>;
        if (Array.isArray(obj.paragraphs)) {
          candidates = obj.paragraphs.filter((v): v is string => typeof v === "string");
        } else {
          candidates = Object.values(obj)
            .flat()
            .filter((v): v is string => typeof v === "string");
        }
      }
    } catch {
      // Fall through to the plain-text path.
    }
  } else if (trimmed.startsWith("[")) {
    // v1.14.1: JSON array of paragraph strings. gpt-5.5-pro emits this shape
    // for Journal Recent Form Review entries.
    try {
      const parsed: unknown = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        candidates = parsed.filter((v): v is string => typeof v === "string");
      }
    } catch {
      // Fall through to the plain-text path.
    }
  }

  if (candidates.length === 0) {
    const normalized = unescapeNewlines(trimmed);
    candidates = normalized.split(/\n\s*\n/);
  }

  return candidates
    .map((p) => unescapeNewlines(p).trim())
    .filter(Boolean);
}

/**
 * Replace the two-character sequence `\` + `n` (and `\` + `r\n`) with real
 * newlines. Leaves already-real newlines untouched.
 *
 * Exported so other parsers handling LLM-produced text (v1.13.0 feedback
 * section parser, etc.) can reuse the same normalization.
 */
export function unescapeNewlines(s: string): string {
  return s.replace(/\\r\\n/g, "\n").replace(/\\n/g, "\n");
}
