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
} from "./types";

const BASE = "/api";

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.text();
      detail = ` — ${body.substring(0, 200)}`;
    } catch {}
    throw new Error(`API error: ${res.status} ${res.statusText}${detail}`);
  }
  return res.json();
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

export async function fetchPatterns(player: string): Promise<{ stats: PatternStats; trend_summary?: string }> {
  return fetchJSON<{ stats: PatternStats; trend_summary?: string }>(
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
  provider: "claude" | "openai" = "claude"
): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE}/trend-summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player, provider }),
  });
  if (!res.ok) throw new Error(`Trend summary API error: ${res.status}`);
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

export async function triggerPipelineRunAll(player?: string) {
  return postPipeline("run-all", player ? { player } : {});
}

export async function triggerPipelineCoach(provider?: "claude" | "openai", player?: string) {
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
  data: { anthropic_key?: string; openai_key?: string }
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
  provider: "claude" | "openai"
): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE}/coach`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_id: gameId, provider }),
  });
  if (!res.ok) throw new Error(`Coach API error: ${res.status}`);
  return res.json();
}
