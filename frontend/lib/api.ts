import type {
  Player,
  GameListItem,
  GameDetail,
  PatternStats,
  StatusResponse,
  ReportData,
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
