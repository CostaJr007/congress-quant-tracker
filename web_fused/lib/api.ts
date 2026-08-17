import { qs } from "./format";
import type {
  AnalyzeOverview,
  Dashboard,
  LeaderboardResponse,
  PoliticianDetail,
  PoliticiansResponse,
  SearchResponse,
  SignalsResponse,
  StockDetail,
  StocksResponse,
  TradeMonthsResponse,
  TradesResponse,
} from "./types";

const SERVER_API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function apiPath(path: string): string {
  if (typeof window === "undefined") {
    return path.startsWith("http") ? path : `${SERVER_API}${path}`;
  }
  return path;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(apiPath(path), {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || res.statusText || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  dashboard: () => getJson<Dashboard>("/api/dashboard"),
  trades: (params: Record<string, string | number | undefined | null>) =>
    getJson<TradesResponse>(`/api/trades${qs(params)}`),
  tradeMonths: () => getJson<TradeMonthsResponse>("/api/trades/months"),
  politicians: (params: Record<string, string | number | undefined | null>) =>
    getJson<PoliticiansResponse>(`/api/politicians${qs(params)}`),
  politician: (name: string) =>
    getJson<PoliticianDetail>(`/api/politicians/${encodeURIComponent(name)}`),
  stocks: (params: Record<string, string | number | undefined | null>) =>
    getJson<StocksResponse>(`/api/stocks${qs(params)}`),
  stock: (ticker: string) =>
    getJson<StockDetail>(`/api/stocks/${encodeURIComponent(ticker)}`),
  signals: (params: Record<string, string | number | undefined | null>) =>
    getJson<SignalsResponse>(`/api/signals${qs(params)}`),
  leaderboard: (params: Record<string, string | number | undefined | null>) =>
    getJson<LeaderboardResponse>(`/api/leaderboard${qs(params)}`),
  search: (q: string) => getJson<SearchResponse>(`/api/search${qs({ q })}`),
  analyzeOverview: () => getJson<AnalyzeOverview>("/api/analyze/overview"),
};
