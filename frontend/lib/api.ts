import type {
  Player,
  GameListItem,
  GameDetail,
  PatternStats,
  StatusResponse,
  ReportData,
  PipelineState,
  ScheduleState,
  SettingsData,
  AnalysisSettings,
  CoachingSettings,
  OpponentProfile,
  HuntPlatform,
  Tournament,
  TournamentOpponent,
  TournamentPrep,
} from "./types";

const BASE = "/api";

async function fetchJSON<T>(url: string): Promise<T> {
  // v1.22.5: the backend returns 503 ("Database is busy") while a long
  // analysis holds the SQLite write lock. That's explicitly retryable, so a
  // transient blip during a Run All shouldn't crash the whole page with the
  // Next.js error overlay — retry a couple of times with a short backoff
  // before surfacing it. Non-503 errors (real 4xx/5xx) still throw at once.
  let lastDetail = "";
  let lastStatus = 0;
  let lastStatusText = "";
  for (let attempt = 0; attempt < 3; attempt++) {
    const res = await fetch(url);
    if (res.ok) return res.json();

    let detail = "";
    try {
      detail = ` — ${(await res.text()).substring(0, 200)}`;
    } catch {}
    lastDetail = detail;
    lastStatus = res.status;
    lastStatusText = res.statusText;

    if (res.status === 503 && attempt < 2) {
      await new Promise((r) => setTimeout(r, 500 * (attempt + 1)));
      continue;
    }
    break;
  }
  throw new Error(`API error: ${lastStatus} ${lastStatusText}${lastDetail}`);
}

export async function fetchPlayers(): Promise<Player[]> {
  return fetchJSON<Player[]>(`${BASE}/players`);
}

export async function fetchGames(player?: string): Promise<GameListItem[]> {
  const params = player ? `?player=${encodeURIComponent(player)}` : "";
  return fetchJSON<GameListItem[]>(`${BASE}/games${params}`);
}

export async function fetchGameDetail(id: number): Promise<GameDetail> {
  return fetchJSON<GameDetail>(`${BASE}/games/${id}`);
}

/** Set a game's player / opponent rating (v1.25.1). Over-the-board PGNs carry
 *  no Elo, so ratings are entered by hand. A number sets, `null` clears
 *  (unrated), an omitted field is left unchanged. */
export async function updateGameRatings(
  gameId: number,
  ratings: { player_rating?: number | null; opponent_rating?: number | null }
): Promise<{
  game_id: number;
  player_rating: number | null;
  opponent_rating: number | null;
}> {
  const res = await fetch(`${BASE}/games/${gameId}/ratings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(ratings),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Update failed: ${res.status}`);
  return data;
}

/** Reclassify a game's category/type (v1.26.2). Setting platform="competition"
 *  also strips the competition name/venue from the stored PGN (privacy). */
export async function updateGameClassification(
  gameId: number,
  input: { platform?: string; time_class?: string | null; date_played?: string | null }
): Promise<{
  game_id: number;
  platform: string;
  time_class: string | null;
  date_played: string | null;
}> {
  const res = await fetch(`${BASE}/games/${gameId}/classification`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Update failed: ${res.status}`);
  return data;
}

export async function fetchPatterns(player: string): Promise<{
  stats: PatternStats;
  trend_summary?: string;
  /** v1.9.0+: LLM narrative across the last N coached games. */
  recent_form_review?: string | null;
  /** v1.9.0+: ISO timestamp of the last review generation. */
  recent_form_review_updated_at?: string | null;
}> {
  return fetchJSON(
    `${BASE}/patterns?player=${encodeURIComponent(player)}`
  );
}

export async function fetchStatus(): Promise<StatusResponse> {
  return fetchJSON<StatusResponse>(`${BASE}/status`);
}

export async function fetchReport(
  player: string,
  period: "weekly" | "monthly" = "monthly"
): Promise<ReportData> {
  return fetchJSON<ReportData>(
    `${BASE}/report?player=${encodeURIComponent(player)}&period=${period}`
  );
}

export async function triggerTrendSummary(
  player: string,
  provider: string = "claude"
): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE}/trend-summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player, provider }),
  });
  if (!res.ok) throw new Error(`Trend summary API error: ${res.status}`);
  return res.json();
}

/** v1.9.0: Trigger the Recent Form Review (LLM narrative across last N games).
 *  v1.10.0: now accepts an optional `platform` to scope the review. */
export async function triggerRecentFormReview(
  player: string,
  provider: string = "openai",
  window: number = 10,
  platform?: string
): Promise<{ status: string; message: string; window: number; platform?: string }> {
  const res = await fetch(`${BASE}/journal/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player, provider, window, platform }),
  });
  if (!res.ok) throw new Error(`Journal review API error: ${res.status}`);
  return res.json();
}

/** v1.10.0: chronological journal entries for a player.
 *  Returns entries newest-first plus a per-platform count map for the chip row. */
export interface JournalEntry {
  id: number;
  player_id: number;
  kind: "review" | "note" | string;
  platform: string;
  body: string | null;
  refs: number[];
  provider: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export async function fetchJournal(
  player: string,
  opts?: { platform?: string; kind?: string; limit?: number }
): Promise<{
  username: string;
  entries: JournalEntry[];
  platform_counts: Record<string, number>;
}> {
  const params = new URLSearchParams({ player });
  if (opts?.platform) params.set("platform", opts.platform);
  if (opts?.kind) params.set("kind", opts.kind);
  if (opts?.limit) params.set("limit", String(opts.limit));
  return fetchJSON(`${BASE}/journal?${params.toString()}`);
}

/** v1.12.0: Parent-authored journal note. No LLM call. */
export async function createJournalNote(
  player: string,
  body: string,
  platform: string = "chess.com"
): Promise<{ entry: JournalEntry }> {
  const res = await fetch(`${BASE}/journal/note`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player, body, platform }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Create note failed: ${res.status}`);
  }
  return res.json();
}

/** v1.12.0: Edit an existing note's body. Reviews are not editable. */
export async function updateJournalNote(
  entryId: number,
  body: string
): Promise<{ entry: JournalEntry }> {
  const res = await fetch(`${BASE}/journal/note/${entryId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Update note failed: ${res.status}`);
  }
  return res.json();
}

/** v1.12.0: Delete a note. Reviews are not deletable through this path. */
export async function deleteJournalNote(
  entryId: number
): Promise<{ status: string; id: number }> {
  const res = await fetch(`${BASE}/journal/note/${entryId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Delete note failed: ${res.status}`);
  }
  return res.json();
}

// ── Pipeline API ─────────────────────────────────────────

export async function fetchPipelineStatus(): Promise<PipelineState> {
  return fetchJSON<PipelineState>(`${BASE}/pipeline/status`);
}

async function postPipeline(
  endpoint: string,
  body: Record<string, unknown> = {}
): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE}/pipeline/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 409) {
    const data = await res.json();
    throw new Error(data.error || "Another task is already running.");
  }
  if (res.status === 404) {
    throw new Error(
      "Pipeline endpoint not found. Please restart the dashboard server (python main.py dashboard)."
    );
  }
  if (!res.ok) throw new Error(`Pipeline API error: ${res.status}`);
  return res.json();
}

export async function triggerPipelineHarvest(player?: string) {
  return postPipeline("harvest", player ? { player } : {});
}

export async function triggerPipelineAnalyze() {
  return postPipeline("analyze");
}

export async function triggerPipelinePatterns(player?: string) {
  return postPipeline("patterns", player ? { player } : {});
}

export async function triggerPipelineRunAll(provider?: string, player?: string) {
  const body: Record<string, unknown> = {};
  if (provider) body.provider = provider;
  if (player) body.player = player;
  return postPipeline("run-all", body);
}

export async function triggerPipelineCoach(provider?: string, player?: string) {
  const body: Record<string, unknown> = {};
  if (provider) body.provider = provider;
  if (player) body.player = player;
  return postPipeline("coach", body);
}

export async function cancelPipeline(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE}/pipeline/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  // Don't throw on 400 — task may have already finished
  return res.json();
}

// ── Schedule API ─────────────────────────────────────────

export async function fetchScheduleStatus(): Promise<ScheduleState> {
  return fetchJSON<ScheduleState>(`${BASE}/schedule/status`);
}

export async function toggleSchedule(enabled: boolean): Promise<ScheduleState> {
  const res = await fetch(`${BASE}/schedule/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error(`Schedule API error: ${res.status}`);
  return res.json();
}

export async function updateScheduleInterval(hours: number): Promise<ScheduleState> {
  const res = await fetch(`${BASE}/schedule/interval`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hours }),
  });
  if (!res.ok) throw new Error(`Schedule API error: ${res.status}`);
  return res.json();
}

// ── Player CRUD ─────────────────────────────────────────

export async function createPlayer(
  data: Record<string, unknown>
): Promise<{ status: string; id: number }> {
  const res = await fetch(`${BASE}/players`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (res.status === 409) {
    const body = await res.json();
    throw new Error(body.error || "Player already exists.");
  }
  if (!res.ok) throw new Error(`Create player failed: ${res.status}`);
  return res.json();
}

export async function updatePlayer(
  id: number,
  data: Record<string, unknown>
): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/players/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Update player failed: ${res.status}`);
  return res.json();
}

export async function removePlayer(
  id: number
): Promise<{ status: string; games_preserved: number }> {
  const res = await fetch(`${BASE}/players/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Remove player failed: ${res.status}`);
  return res.json();
}

// ── Settings API ────────────────────────────────────────

export async function fetchSettings(): Promise<SettingsData> {
  return fetchJSON<SettingsData>(`${BASE}/settings`);
}

export async function updateAnalysisSettings(
  data: Partial<AnalysisSettings>
): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/settings/analysis`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Settings update failed: ${res.status}`);
  }
  return res.json();
}

export async function updateCoachingSettings(
  data: Partial<CoachingSettings>
): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/settings/coaching`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Coaching settings update failed: ${res.status}`);
  }
  return res.json();
}

export async function updateApiKeys(
  data: {
    anthropic_key?: string;
    openai_key?: string;
    google_key?: string;
    xai_key?: string;
    mistral_key?: string;
    deepseek_key?: string;
    qwen_key?: string;
  }
): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/settings/api-keys`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`API key update failed: ${res.status}`);
  return res.json();
}

export async function triggerCoaching(
  gameId: number,
  provider: string
): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE}/coach`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_id: gameId, provider }),
  });
  if (!res.ok) throw new Error(`Coach API error: ${res.status}`);
  return res.json();
}

// ── v1.4.2 Hunter Mode API ──────────────────────────────────────────────

/** Fetch an opponent's profile (cached or live, decided server-side). */
export async function fetchHunterProfile(
  opponent: string,
  platform: HuntPlatform
): Promise<OpponentProfile> {
  const params = new URLSearchParams({ opponent, platform });
  return fetchJSON<OpponentProfile>(`${BASE}/hunt/profile?${params}`);
}

/**
 * v1.20.0: kick off an opponent Deep Scan (Stockfish + motif detection over
 * their last N games). Runs as a background pipeline job — poll
 * fetchPipelineStatus() (task "hunt_scan") for progress.
 */
export async function triggerHuntScan(
  opponent: string,
  platform: HuntPlatform
): Promise<{ status: string; message: string }> {
  return postPipeline("hunt-scan", { opponent, platform });
}

// ── v1.21.0 Tournament Prep ──────────────────────────────────────────────

async function postTournament<T = unknown>(
  endpoint: string,
  body: Record<string, unknown>
): Promise<T> {
  const res = await fetch(`${BASE}/tournament/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Tournament ${endpoint} failed: ${res.status}`);
  }
  return res.json();
}

export async function listTournaments(
  player: string
): Promise<{ tournaments: Tournament[] }> {
  return fetchJSON(`${BASE}/tournaments?player=${encodeURIComponent(player)}`);
}

export async function getTournament(id: number): Promise<TournamentPrep> {
  return fetchJSON<TournamentPrep>(`${BASE}/tournament?id=${id}`);
}

export async function createTournament(
  player: string,
  name: string,
  event_date?: string,
  notes?: string
): Promise<Tournament & { opponents: TournamentOpponent[] }> {
  return postTournament("create", { player, name, event_date, notes });
}

export async function addTournamentOpponent(
  tournament_id: number,
  opponent: string,
  platform: HuntPlatform
): Promise<TournamentOpponent> {
  return postTournament("add-opponent", { tournament_id, opponent, platform });
}

export async function removeTournamentOpponent(
  tournament_id: number,
  opponent_id: number
): Promise<{ status: string }> {
  return postTournament("remove-opponent", { tournament_id, opponent_id });
}

export async function deleteTournament(
  tournament_id: number
): Promise<{ status: string }> {
  return postTournament("delete", { tournament_id });
}

/** Warm every opponent's profile cache (background job; poll pipeline status,
 *  task "tournament_prep"). */
export async function triggerTournamentPrep(
  tournament_id: number
): Promise<{ status: string; message: string }> {
  return postPipeline("tournament-prep", { tournament_id });
}

/** Force a fresh fetch of an opponent's profile (bypasses 24h cache). */
export async function refreshHunterProfile(
  opponent: string,
  platform: HuntPlatform
): Promise<OpponentProfile> {
  const res = await fetch(`${BASE}/hunt/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ opponent, platform }),
  });
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body.error || "";
    } catch {}
    throw new Error(detail || `Hunter refresh failed: ${res.status}`);
  }
  return res.json();
}

// ── PGN data I/O (v1.24.0) ───────────────────────────────

export interface ImportedGameSummary {
  game_id: number;
  created: boolean;
  result: string;
  player_color: string;
  moves: number;
  opponent: string | null;
  time_class: string | null;
}

export interface ImportPgnResult {
  game_id: number;
  created: boolean;
  status: string;
  result: string;
  player_color: string;
  moves: number;
  analyze: string;
  // v1.25.0 batch fields (competition / multi-game imports)
  games?: ImportedGameSummary[];
  created_count?: number;
  existing_count?: number;
  skipped?: string[];
}

/** Import a raw PGN for a player. `result` (win/loss/draw) is required when
 *  the PGN's own Result is undecided ("*"). For over-the-board competition
 *  games pass `platform: "competition"` (a multi-game file imports all games)
 *  and `time_class` (the game type: classical/rapid/blitz). */
export async function importPgn(input: {
  player: string;
  pgn: string;
  player_color?: "white" | "black";
  result?: "win" | "loss" | "draw";
  run_pipeline?: boolean;
  platform?: "competition";
  time_class?: "classical" | "rapid" | "blitz";
}): Promise<ImportPgnResult> {
  const res = await fetch(`${BASE}/import-pgn`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Import failed: ${res.status}`);
  return data as ImportPgnResult;
}

/** Export one or more games as a PGN file and trigger a browser download.
 *  Raw or annotated (engine evals + classification NAGs). */
export async function exportGamesToFile(
  ids: number[],
  annotated: boolean
): Promise<number> {
  const res = await fetch(`${BASE}/games/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids, annotated }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Export failed: ${res.status}`);

  const blob = new Blob([data.pgn], { type: "application/x-chess-pgn" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = data.filename || "games.pgn";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return data.count as number;
}
