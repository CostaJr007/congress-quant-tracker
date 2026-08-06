const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Trade {
  id?: number;
  representative: string;
  party?: string;
  state_district?: string;
  chamber?: string;
  owner?: string;
  ticker?: string;
  asset?: string;
  asset_type?: string;
  transaction_type?: string;
  transaction_date?: string;
  notification_date?: string;
  amount?: string;
  amount_min?: number;
  amount_max?: number;
  sector?: string;
  industry?: string;
  current_price?: number;
  price_change_pct?: number;
  score: number;
  tag: string;
  reason?: string;
}

export interface Politician {
  name: string;
  slug?: string;
  party?: string;
  chamber?: string;
  state_district?: string;
  trades: number;
  total_volume: number;
  avg_score: number;
  buys?: number;
  sells?: number;
  rank?: number;
}

export interface Stock {
  ticker: string;
  name: string;
  asset_type?: string;
  sector?: string;
  industry?: string;
  current_price?: number;
  trades: number;
  total_volume: number;
  buys?: number;
  sells?: number;
  unique_politicians: number;
  avg_score: number;
}

export interface DashboardData {
  total_trades: number;
  total_volume: number;
  unique_politicians: number;
  unique_assets: number;
  avg_score: number;
  avg_win_rate: number;
  buy_count: number;
  sell_count: number;
  high_alert_count: number;
  suspicious_count: number;
  noteworthy_count: number;
  signal_distribution: Record<string, number>;
  activity_by_month: { month: string; count: number }[];
  deltas: { trades: number | null; volume: number | null };
  top_politicians: Politician[];
  top_tickers: { ticker: string; name: string; trades: number; total_volume: number }[];
  recent_trades: Trade[];
  data_age_days: number | null;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(endpoint: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, { signal });
  if (!res.ok) {
    throw new ApiError(res.status, `API error ${res.status} on ${endpoint}`);
  }
  return res.json();
}

export function fetchDashboard(signal?: AbortSignal) {
  return request<DashboardData>("/api/dashboard", signal);
}

export interface TradesResponse {
  trades: Trade[];
  total: number;
  limit: number;
  offset: number;
}

export function fetchTrades(params?: Record<string, string>, signal?: AbortSignal) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return request<TradesResponse>(`/api/trades${qs}`, signal);
}

export interface TradeMonth {
  month: string; // YYYY-MM
  year: number;
  month_num: number;
  label: string;
  count: number;
}

export function fetchTradeMonths(by: "filing" | "trade" = "filing", signal?: AbortSignal) {
  return request<{ by: string; months: TradeMonth[]; total_months: number }>(
    `/api/trades/months?by=${by}`,
    signal,
  );
}

export interface MarketBar {
  date: string;
  close: number;
}

export interface TradePerformance {
  ticker: string;
  price_at_trade: number | null;
  price_at_trade_date: string | null;
  price_now: number | null;
  price_now_date: string | null;
  change_pct: number | null;
  change_abs: number | null;
  direction: "up" | "down" | "flat" | null;
  pnl_mid_est: number | null;
  shares: {
    shares_est: number;
    shares_min_est?: number;
    shares_max_est?: number;
    value_mid?: number;
    note?: string;
  } | null;
  chart: MarketBar[];
  source: string;
  error?: string | null;
}

export function fetchTradePerformance(tradeId: number, signal?: AbortSignal) {
  return request<{ trade: Trade; performance: TradePerformance }>(
    `/api/trades/${tradeId}/performance`,
    signal,
  );
}

export function fetchMarket(ticker: string, params?: Record<string, string>, signal?: AbortSignal) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return request<{
    ticker: string;
    bars: MarketBar[];
    latest: { date: string; price: number } | null;
    change_pct_window: number | null;
    source: string;
  }>(`/api/market/${encodeURIComponent(ticker)}${qs}`, signal);
}

export interface PoliticiansResponse {
  politicians: Politician[];
  total: number;
  limit: number;
  offset: number;
}

export function fetchPoliticians(params?: Record<string, string>, signal?: AbortSignal) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return request<PoliticiansResponse>(`/api/politicians${qs}`, signal);
}

export function fetchPolitician(name: string, signal?: AbortSignal) {
  return request<Record<string, any>>(`/api/politicians/${encodeURIComponent(name)}`, signal);
}

export interface StocksResponse {
  stocks: Stock[];
  total: number;
  limit: number;
  offset: number;
}

export function fetchStocks(params?: Record<string, string>, signal?: AbortSignal) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return request<StocksResponse>(`/api/stocks${qs}`, signal);
}

export function fetchStock(ticker: string, signal?: AbortSignal) {
  return request<Record<string, any>>(`/api/stocks/${encodeURIComponent(ticker)}`, signal);
}

export interface LeaderboardResponse {
  leaderboard: Politician[];
  total: number;
}

export function fetchLeaderboard(params?: Record<string, string>, signal?: AbortSignal) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return request<LeaderboardResponse>(`/api/leaderboard${qs}`, signal);
}

export interface SignalsResponse {
  signals: Trade[];
  total: number;
  tag: string;
}

export function fetchSignals(params?: Record<string, string>, signal?: AbortSignal) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return request<SignalsResponse>(`/api/signals${qs}`, signal);
}

export interface SearchResponse {
  politicians: Politician[];
  tickers: Stock[];
}

export function fetchSearch(q: string, signal?: AbortSignal) {
  return request<SearchResponse>(`/api/search?q=${encodeURIComponent(q)}`, signal);
}

export interface MetaResponse {
  chambers: string[];
  parties: string[];
  states: string[];
  data_age_days: number | null;
  total_trades: number;
  total_options?: number;
  last_update?: {
    status?: string;
    started_at?: string;
    completed_at?: string;
    records_processed?: number;
  } | null;
  version?: string;
}

export function fetchMeta(signal?: AbortSignal) {
  return request<MetaResponse>("/api/meta", signal);
}