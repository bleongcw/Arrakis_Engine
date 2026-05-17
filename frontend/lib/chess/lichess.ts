/** Build a Lichess analysis deep link from a FEN string.
 *
 *  Format: `https://lichess.org/analysis/standard/<fen-with-underscores>`
 *
 *  v1.4.5 lesson: this is the reliable deep-link path that loads a
 *  specific board position into the Lichess analysis board (with cloud
 *  eval + opening explorer). Do NOT use `?pgn=` — that form does not
 *  reliably load positions and was the regression fixed in v1.4.5.
 */
export function lichessAnalysisUrl(fen: string): string {
  return `https://lichess.org/analysis/standard/${fen.replace(/ /g, "_")}`;
}
