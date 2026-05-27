// TypeScript interfaces matching the Python API response shapes

export type Provider = "claude" | "openai" | "gemini" | "grok" | "mistral" | "deepseek" | "qwen" | "ollama";

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

/** v1.6.0: meta captured at coaching time — history depth, prompt size,
 *  model. Persists so the UI can show "Based on N recent games" stamps
 *  on the coaching panel and so we can correlate coaching quality with
 *  prompt context after the fact.
 *  v1.8.0: extended with trajectory injection diagnostics. */
export interface CoachingMeta {
  history_games_injected: number;
  history_tokens_estimate: number;
  prompt_tokens_estimate: number;
  provider: string;
  model: string;
  /** v1.8.0+: true if the per-player trajectory block was injected
   *  into the coaching prompt (requires populated player_patterns
   *  AND coaching_trajectory_enabled). Pre-v1.8.0 briefs lack this. */
  trajectory_injected?: boolean;
  /** v1.8.0+: how stale the player_patterns row was at coaching time.
   *  null when trajectory was skipped. */
  trajectory_age_days?: number | null;
  /** v1.8.0+: the weakest phase the coach saw, for tooltip context. */
  trajectory_weakest_phase?: string | null;
  /** v1.8.0+: improving / flat / declining / insufficient_data. */
  trajectory_trend_direction?: string | null;
  /** v1.8.0+: rough size of the injected trajectory block. */
  trajectory_tokens_estimate?: number;
  /** v1.13.2+: true iff the LLM's player_feedback contained all 5 required
   *  v1.13.0 markdown headings. False when the LLM (often an older or
   *  non-reasoning model) ignored the structured-output spec. */
  feedback_structure_compliant?: boolean;
  /** v1.13.2+: list of required heading names the LLM omitted, e.g.
   *  ["♔ Endgame", "🎯 Top 3 Improvements"]. Empty when compliant. */
  feedback_missing_headings?: string[];
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
  /** v1.6.0+: coaching meta. Older briefs (pre-v1.6.0) have this null. */
  meta?: CoachingMeta | null;
  coaching_meta_json?: string | null;
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
  // v1.4.0 Self-Analysis
  loss_openings?: LossOpeningAnalysis;
  strong_openings?: LossOpeningAnalysis;
  trap_falls?: TrapEntry[];
  your_arsenal?: TrapEntry[];
}

// ── v1.4.0 Self-Analysis types ────────────────────────────────────────────

export interface LossOpeningEntry {
  name: string;
  total: number;
  wins: number;
  losses: number;
  draws: number;
  /** Loss rate (or win rate, depending on which list this entry came from). */
  rate: number;
  recent_game_ids: number[];
}

export interface LossOpeningAnalysis {
  white: LossOpeningEntry[];
  black: LossOpeningEntry[];
}

// ── v1.4.1 / v1.4.2 Hunter Mode types ────────────────────────────────────

/** A representative game for an opening — used by the v1.4.4 expand-on-click
 *  UI to render a step-through mini-board of an actual opponent game. */
export interface OpponentRepresentativeGame {
  pgn: string;
  date_played: string | null;
  /** Opponent's color in this game ("white" or "black"). Drives board orientation. */
  opponent_color: "white" | "black" | null;
  game_url: string | null;
}

/** A single opening entry in an opponent's profile. */
export interface OpponentOpeningEntry {
  name: string;
  total: number;
  wins: number;
  losses: number;
  draws: number;
  /** Loss rate (in `weaknesses`) or win rate (in `strengths`). */
  rate: number;
  /** v1.4.4: ECO code (A00–E99) extracted from PGN headers. */
  eco?: string | null;
  /** v1.4.4: up to 5 most-recent games where the opponent had this outcome.
   *  Drives the click-to-expand mini-board UI. */
  representative_games?: OpponentRepresentativeGame[];
}

export interface OpponentOpeningSplit {
  white: OpponentOpeningEntry[];
  black: OpponentOpeningEntry[];
}

export interface HunterMeta {
  cached: boolean;
  platform: "chess.com" | "lichess";
  username: string;
  fetched_at: string | null;
  /** v1.4.4: total games accumulated locally for this opponent
   *  (across all refreshes within the sliding window). May exceed
   *  total_games if some have been pruned but the cache profile is
   *  cached from a previous compute. Useful for the UI to show
   *  "10 games shown · 187 accumulated" stamps. */
  accumulated_games?: number;
}

export interface OpponentProfile {
  total_games: number;
  results: { wins: number; losses: number; draws: number; win_rate: number };
  /** Openings the opponent LOSES — the player's hunting targets. */
  weaknesses: OpponentOpeningSplit;
  /** Openings the opponent WINS — lines for the player to AVOID. */
  strengths: OpponentOpeningSplit;
  meta: HunterMeta;
  /** Server-returned error (when the request was rejected before fetching). */
  error?: string;
}

export type HuntPlatform = "chess.com" | "lichess";

// ─────────────────────────────────────────────────────────────────────────

export interface TrapEntry {
  name: string;
  eco?: string;
  /** How many times this trap appeared with the requested outcome
   *  (losses for `trap_falls`, wins for `your_arsenal`). */
  count: number;
  /** Total games where this trap was detected, regardless of outcome. */
  total: number;
  wins: number;
  losses: number;
  draws: number;
  /** Win rate across ALL games matching this trap (for context). */
  win_rate: number;
  /** Up to 5 most-recent dates where the requested outcome occurred. */
  recent_dates: string[];
  /** v1.4.3: up to 5 most-recent game IDs where the requested outcome
   *  occurred, newest-first. Used to link from a trap row back to the
   *  full game detail page. */
  recent_game_ids?: number[];
  frequency_label: "Rare" | "Occasional" | "Frequent";
  trend: "up" | "down" | "flat";
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

export interface ScheduleState {
  enabled: boolean;
  interval_hours: number;
  next_run_time: string | null;
  last_run_at: string | null;
  last_run_status: "success" | "error" | "skipped" | null;
  last_run_message: string | null;
}

export interface PipelineState {
  task: "harvest" | "analyze" | "patterns" | "run_all" | "coach" | null;
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
  triggered_by: "manual" | "schedule" | null;
}

export interface AnalysisSettings {
  stockfish_path: string;
  depth: number;
  threads: number;
  hash_mb: number;
  move_time_limit: number;
  months_lookback: number;
}

export interface ApiKeyStatus {
  anthropic_configured: boolean;
  anthropic_key_hint: string | null;
  openai_configured: boolean;
  openai_key_hint: string | null;
  google_configured: boolean;
  google_key_hint: string | null;
  xai_configured: boolean;
  xai_key_hint: string | null;
  mistral_configured: boolean;
  mistral_key_hint: string | null;
  deepseek_configured: boolean;
  deepseek_key_hint: string | null;
  qwen_configured: boolean;
  qwen_key_hint: string | null;
  ollama_configured: boolean;
}

export interface ProviderInfo {
  slug: Provider;
  display_name: string;
  group: "cloud" | "local";
  color: string;
  configured: boolean;
  model: string;
  env_var: string | null;
}

export interface CoachingSettings {
  default_provider: Provider;
  anthropic_model: string;
  openai_model: string;
  gemini_model: string;
  grok_model: string;
  mistral_model: string;
  deepseek_model: string;
  qwen_model: string;
  ollama_model: string;
  ollama_base_url: string;
  tone: "encouraging" | "balanced" | "technical";
  detail_level: "concise" | "standard" | "detailed";
  focus_areas: string[];
  custom_instructions: string;
  coaching_history_count: number;
}

export interface SettingsData {
  analysis: AnalysisSettings;
  api_keys: ApiKeyStatus;
  coaching: CoachingSettings;
  providers: ProviderInfo[];
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
