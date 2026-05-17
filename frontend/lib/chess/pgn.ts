/** Strip move-number prefixes and PGN result markers from a SAN move
 *  string and return a flat array of moves.
 *
 *  Examples:
 *    "1. e4 e5 2. Nf3"          -> ["e4", "e5", "Nf3"]
 *    "1.e4 e5 2.Nf3 Nc6 1-0"    -> ["e4", "e5", "Nf3", "Nc6"]
 *
 *  Strips:
 *    - Numeric move prefixes (`\d+\.`)
 *    - Result markers (`1-0`, `0-1`, `1/2-1/2`, `*`)
 *
 *  This is the canonical version. The opening-explorer copy previously
 *  omitted result-marker stripping, but canonical book lines don't contain
 *  them so the merge is additive.
 */
export function parseMoveText(moveText: string): string[] {
  return moveText
    .replace(/\d+\./g, " ")
    .replace(/(1-0|0-1|1\/2-1\/2|\*)/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}
