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

export interface OpeningGameEntry {
  game_id: number;
  date: string | null;
  opponent: string;
  result: string;
}

export interface OpeningEntry {
  name: string;
  games: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  opening_moves?: string;
  game_list?: OpeningGameEntry[];
}

export interface TimePressureStats {
  games_with_clocks: number;
  time_trouble_rate: number;
  avg_time_per_move: number;
  phase_avg_time: {
    opening: number;
    middlegame: number;
    endgame: number;
  };
  blunder_rate_under_pressure: number;
  blunder_rate_comfortable: number;
  moves_under_pressure: number;
  moves_comfortable: number;
  time_management_score: number;
}

export interface OpeningBookEntry {
  eco: string;
  name: string;
  moves: string;
}

export interface OpeningRepertoireEntry {
  name: string;
  eco: string;
  games: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  trend: "improving" | "declining" | "stable";
  acpl: number;
  color: "white" | "black" | "both";
}

export interface OpeningRepertoireFocus {
  name: string;
  eco: string;
  games: number;
  win_rate: number;
  acpl: number;
  reason: string;
  suggestion: string;
}

export interface OpeningRepertoireData {
  openings: OpeningRepertoireEntry[];
  eco_distribution: Record<string, number>;
  focus_areas: OpeningRepertoireFocus[];
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
  openings: {
    all?: OpeningEntry[];
    white?: OpeningEntry[];
    black?: OpeningEntry[];
  };
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
  // Phase 1 advanced metrics
  accuracy?: { overall_pct: number; best_moves: number; total_moves: number };
  consistency?: { std_dev: number; mean_acpl: number; best_acpl: number; worst_acpl: number; total_games: number; rating: string };
  danger_zones?: unknown;
  endgame_conversion?: unknown;
  time_control_performance?: unknown;
  // Phase 2 deeper insights
  critical_positions?: unknown;
  comeback_collapse?: unknown;
  opening_acpl?: unknown;
  opening_repertoire?: OpeningRepertoireData;
  tactical_misses?: unknown;
  repertoire_consistency?: unknown;
  // Time pressure
  time_pressure?: TimePressureStats | null;
}

export interface ReportData {
  player_name: string;
  period: string;
  period_start: string;
  period_end: string;
  generated_at: string;
  total_games: number;
  no_games: boolean;
  wins?: number;
  losses?: number;
  draws?: number;
  win_rate?: number;
  avg_opp_rating?: number | null;
  start_rating?: number | null;
  end_rating?: number | null;
  rating_change?: string | null;
  time_class_stats?: Array<{
    time_class: string;
    games: number;
    wins: number;
    losses: number;
    draws: number;
    win_rate: number;
  }>;
  game_list?: Array<{
    game_id: number;
    game_url: string | null;
    date: string | null;
    color: string;
    opponent_rating: number | null;
    opponent_username: string | null;
    result: string;
    acpl: number | null;
    time_class: string | null;
  }>;
  period_acpl?: number | null;
  acpl_interpretation?: string | null;
  move_quality?: Record<string, { count: number; pct: number }>;
  phase_analysis?: Record<string, { acpl: number | null; moves: number }>;
  worst_phase?: string | null;
  improvement_areas?: Array<{ area: string; detail: string }>;
  critical_positions?: Array<{
    game_id: number;
    game_url: string | null;
    date: string | null;
    opponent_rating: number | null;
    opponent_username: string | null;
    move_number: number | null;
    side: string | null;
    what_happened: string;
    what_was_better: string;
  }>;
  recommendations?: string[];
}

export interface PipelineState {
  task: "harvest" | "analyze" | "patterns" | "run_all" | null;
  status: "running" | "complete" | "error" | "idle";
  progress: string;
  detail: {
    current_step?: number;
    total_steps?: number;
    games_processed?: number;
    games_total?: number;
  } | null;
  result: Record<string, number> | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
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
