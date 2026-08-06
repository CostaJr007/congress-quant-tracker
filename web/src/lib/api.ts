const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api";

export type Politician = {
  id: number;
  name: string;
  chamber: "house" | "senate";
  party: "D" | "R" | "I";
  state: string;
  district: string | null;
  committees: string | null;
  trade_count?: number;
};

export type Trade = {
  id: number;
  ticker: string;
  asset_name: string | null;
  transaction_type: "buy" | "sell" | "exchange";
  trade_date: string;
  filing_date: string | null;
  value_min: number | null;
  value_max: number | null;
  value_range: string | null;
  politician_name?: string;
  politician_party?: string;
  politician_chamber?: string;
};

export type SectorVolume = {
  sector: string;
  trade_count: number;
  unique_politicians: number;
  unique_tickers: number;
  total_value_max: number;
};

export type PartyStat = {
  party: string;
  politicians: number;
  total_trades: number;
  buys: number;
  sells: number;
};

export type LeaderboardEntry = {
  politician_id: number;
  name: string;
  party: string;
  chamber: string;
  state: string;
  trade_count: number;
};

export type ApiResponse<T> = {
  data: T;
  error?: string;
};

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function getDashboardStats() {
  return apiFetch<{
    politicians: number;
    trades: number;
    options: number;
    companies: number;
  }>("/stats");
}

export async function getLatestTrades(limit = 20) {
  return apiFetch<Trade[]>(`/trades?limit=${limit}`);
}

export async function getTopPoliticians(limit = 20) {
  return apiFetch<LeaderboardEntry[]>(`/politicians/top?limit=${limit}`);
}

export async function getHotTickers(limit = 12) {
  return apiFetch<{ ticker: string; trade_count: number; buy_pct: number }[]>(
    `/tickers/hot?limit=${limit}`
  );
}

export async function getPartySummary() {
  return apiFetch<Record<string, PartyStat>>("/parties/summary");
}

export async function getPartySectorExposure() {
  return apiFetch<{
    party: string;
    sector: string;
    trade_count: number;
    total_buy_value: number;
    total_sell_value: number;
  }[]>("/parties/sectors");
}

export async function getSectorVolumes() {
  return apiFetch<SectorVolume[]>("/sectors");
}

export async function getTickerInfo(ticker: string) {
  return apiFetch<{
    ticker: string;
    sector: string | null;
    total_trades: number;
    buys: number;
    sells: number;
    unique_politicians: number;
    party_breakdown: Record<string, number>;
    top_buyers: { name: string; party: string; trade_count: number }[];
  }>(`/tickers/${ticker}`);
}

export async function getPoliticianDetail(id: number) {
  return apiFetch<{
    politician: Politician;
    trades: Trade[];
    sector_exposure: { sector: string; trade_count: number }[];
    buy_sell_ratio: { buys: number; sells: number; buy_pct: number; sell_pct: number };
  }>(`/politicians/${id}`);
}

export async function searchPoliticians(query: string) {
  return apiFetch<Politician[]>(`/politicians/search?q=${query}`);
}

export async function getAiInsight(query: string) {
  return apiFetch<{ insight: string }>(`/ai/insight?q=${encodeURIComponent(query)}`);
}
