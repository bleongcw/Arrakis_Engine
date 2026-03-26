// TypeScript interfaces matching the Python API response shapes

export interface Player {
  id: number;
  username: string;
  display_name: string | null;
  age: number | null;
  rating: number | null;
  fide_id: number | null;
  fide_rating: number | null;
  lichess_username: string | null;
  tier: string;
  tier_label: string;
  tier_icon: string;
  tier_description: string;
  latest_rating: number | null;
  chesscom_url: string;
  lichess_url: string | null;
  fide_url: string | null;
  chesscom_games: number;
  lichess_games: number;
}

export interface GameListItem {
  id: number;
  player_id: number;
  game_url: string;
  player_color: "white" | "black";
  player_rating: number | null;
  opponent_rating: number | null;
  opponent_username: string | null;
  result: "win" | "loss" | "draw";
  time_control: string | null;
  time_class: string | null;
  date_played: string | null;
  analysis_status: "pending" | "analyzing" | "complete" | "error";
  coaching_status: "pending" | "complete" | "error";
  platform: "chess.com" | "lichess";
  username: string;
  display_name: string | null;
  tier: string;
  tier_label: string;
  tier_icon: string;
}

export interface MoveAnalysis {
  id: number;
  game_id: number;
  move_number: number;
  side: "white" | "black";
  move_played: string;
  best_move: string | null;
  eval_before_cp: number | null;
  eval_after_cp: number | null;
  swing_cp: number | null;
  win_prob_before: number | null;
  win_prob_after: number | null;
  classification: "excellent" | "good" | "inaccuracy" | "mistake" | "blunder" | null;
  pv_line: string | null;
}

export interface OpeningAnalysis {
  opening_name: string;
  player_role: "white" | "black";
  opening_quality: "good" | "acceptable" | "poor";
  correct_counter_moves: boolean;
  opening_summary: string;
  opening_tip: string;
}

export interface CriticalMoment {
  move_number: number;
  side: "white" | "black";
  what_happened: string;
  what_was_better: string;
  move_played: string;
  best_move: string;
}

export interface GameCoaching {
  id: number;
  game_id: number;
  provider: string;
  narrative: string | null;
  key_lesson: string | null;
  practical_focus: string | null;
  player_feedback: string | null;
  critical_moments: CriticalMoment[] | null;
  critical_moments_json: string | null;
  opening_analysis: OpeningAnalysis | null;
  opening_analysis_json: string | null;
  coach_notes: string | null;
}

export interface GameDetail {
  game: GameListItem & {
    pgn: string;
    tier_description: string;
  };
  moves: MoveAnalysis[];
  coaching: GameCoaching | null;
}

export interface PatternStats {
  total_games: number;
  results: {
    wins: number;
    losses: number;
    draws: number;
    win_rate: number;
  };
  acpl_trend: Array<{
    week: string;
    acpl: number;
    games: number;
  }>;
  openings: Array<{
    opening: string;
    games: number;
    wins: number;
    losses: number;
    draws: number;
    win_rate: number;
    color?: string;
  }>;
  move_quality: {
    excellent: number;
    good: number;
    inaccuracy: number;
    mistake: number;
    blunder: number;
  };
  phase_analysis: {
    opening: { moves: number; acpl: number; blunders: number; mistakes: number; inaccuracies: number };
    middlegame: { moves: number; acpl: number; blunders: number; mistakes: number; inaccuracies: number };
    endgame: { moves: number; acpl: number; blunders: number; mistakes: number; inaccuracies: number };
  };
  rating_performance: {
    vs_higher: { games: number; wins: number; win_rate: number };
    vs_lower: { games: number; wins: number; win_rate: number };
    vs_similar: { games: number; wins: number; win_rate: number };
  };
}

export interface StatusResponse {
  total_games: number;
  analysis_pending: number;
  analyzing: number;
  analysis_complete: number;
  analysis_error: number;
  coaching_pending: number;
  coaching_complete: number;
  coaching_error: number;
}
