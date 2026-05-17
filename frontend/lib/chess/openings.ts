/** A single entry in the Lichess opening library (`/data/openings.json`). */
export interface LibraryOpening {
  eco: string;
  name: string;
  /** PGN move text, e.g. "1. e4 e5 2. Nf3 Nc6". */
  moves: string;
}

/** Normalize an opening name for fuzzy comparison.
 *
 *  Strips punctuation (apostrophes, hyphens, colons, commas, periods),
 *  the special "..." used by chess.com to denote black-move continuations,
 *  lowercases everything, and collapses internal whitespace.
 *
 *  After normalization, "Caro-Kann Defense: Advance, Short Variation"
 *  and "Caro Kann Defense Advance Short Variation" become identical.
 */
export function normalizeOpeningName(name: string): string {
  return name
    .replace(/\.{3}/g, " ")
    .replace(/[:,'""\-.]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

/** Look up the canonical opening line for a given opening name from the
 *  Lichess library. Returns the deepest matching entry by name (longest
 *  name match) so "Italian Game: Two Knights Defense" beats "Italian Game".
 *
 *  Matching strategy (in order):
 *  1. Exact match on raw name.
 *  2. Exact match on normalized name (handles punctuation differences
 *     between chess.com's verbose names and Lichess's canonical form).
 *  3. Fuzzy: longest entry whose normalized name is a prefix of the
 *     game's normalized name (or vice versa). Picks the longest match
 *     to prefer specific variations over generic openings.
 */
export function findCanonicalLine(
  openingName: string,
  library: LibraryOpening[],
): LibraryOpening | null {
  if (!openingName || library.length === 0) return null;

  const exact = library.find((e) => e.name === openingName);
  if (exact) return exact;

  const target = normalizeOpeningName(openingName);
  if (!target) return null;

  let best: LibraryOpening | null = null;
  let bestLen = 0;
  for (const e of library) {
    const candidate = normalizeOpeningName(e.name);
    if (!candidate) continue;
    if (candidate === target) return e;
    if (target.startsWith(candidate) || candidate.startsWith(target)) {
      const matchLen = Math.min(candidate.length, target.length);
      if (matchLen > bestLen) {
        best = e;
        bestLen = matchLen;
      }
    }
  }
  return best;
}

/** Return the ply index (0-based) where two move lists first differ.
 *  Returns `-1` if `gameMoves` matches `bookMoves` for the entire shared
 *  length (i.e. no deviation within the overlap). Mirrors the JS
 *  `indexOf` / `findIndex` "not found" convention.
 */
export function findDeviationIndex(
  gameMoves: string[],
  bookMoves: string[],
): number {
  const len = Math.min(gameMoves.length, bookMoves.length);
  for (let i = 0; i < len; i++) {
    if (gameMoves[i] !== bookMoves[i]) return i;
  }
  return -1;
}
