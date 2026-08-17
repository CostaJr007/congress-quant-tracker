export type Party = "D" | "R" | "I" | string | null;
export type Chamber = "House" | "Senate" | string | null;
export type Tag = "routine" | "noteworthy" | "suspicious" | "high_alert" | string | null;
export type TradeSide = "Purchase" | "Sale" | "buy" | "sell" | string | null;

export interface Trade {
  id: number;
  ticker: string | null;
  asset: string | null;
  transaction_type: TradeSide;
  transaction_date: string | null;
  notification_date: string | null;
  amount_min: number | null;
  amount_max: number | null;
  amount: string | null;
  asset_type: string | null;
  score: number;
  tag: Tag;
  reason: string | null;
  pdf_url: string | null;
  owner: string | null;
  sector: string | null;
  representative: string | null;
  party: Party;
  chamber: Chamber;
  state_district: string | null;
  bioguide_id: string | null;
  photo_url: string | null;
  current_price?: number | null;
  price_change_pct?: number | null;
  shares_est?: number | null;
  pnl_mid_est?: number | null;
}

export interface Politician {
  name: string;
  party: Party;
  chamber: Chamber;
  state?: string | null;
  district?: string | number | null;
  state_district: string | null;
  committees?: string[];
  bioguide_id: string | null;
  photo_url: string | null;
  trades: number;
  total_trades?: number;
  avg_score: number;
  total_volume: number;
  buys: number;
  sells: number;
  unique_assets: number;
}

export interface TopPolitician {
  name: string;
  party: Party;
  chamber: Chamber;
  bioguide_id: string | null;
  photo_url: string | null;
  trades: number;
  total_volume: number;
  avg_score: number;
}

export interface TopTicker {
  ticker: string;
  name: string;
  trades: number;
  total_volume: number;
}

export interface MonthActivity {
  month: string;
  count: number;
  buys: number;
  sells: number;
  volume: number;
}

export interface LastUpdate {
  status: string | null;
  started_at: string | null;
  completed_at: string | null;
  records_processed: number | null;
  error_message: string | null;
}

export interface Dashboard {
  total_trades: number;
  unique_politicians: number;
  total_politicians?: number;
  total_volume: number;
  unique_assets: number;
  avg_score: number;
  buy_count: number;
  sell_count: number;
  high_alert_count: number;
  suspicious_count: number;
  noteworthy_count: number;
  signal_distribution: Record<string, number>;
  activity_by_month: MonthActivity[];
  party_split: Record<string, number>;
  data_range: { min_date: string | null; max_date: string | null };
  data_age_days: number | null;
  last_update: LastUpdate | null;
  deltas: { trades: number | null; volume: number | null };
  top_politicians: TopPolitician[];
  top_tickers: TopTicker[];
  recent_trades: Trade[];
  total_options?: number;
}

export interface TradeMonth {
  month: string;
  year?: number;
  month_num?: number;
  label: string;
  count: number;
}

export interface TradesResponse {
  total: number;
  limit: number;
  offset: number;
  sort_by?: string;
  month?: string | null;
  trades: Trade[];
}

export interface TradeMonthsResponse {
  months: TradeMonth[];
  total_months?: number;
  by?: string;
}

export interface PoliticiansResponse {
  total: number;
  limit: number;
  offset: number;
  politicians: Politician[];
}

export interface PoliticianDetail {
  name: string;
  party: Party;
  chamber: Chamber;
  state: string | null;
  district: string | number | null;
  state_district: string | null;
  committees: string[];
  bioguide_id: string | null;
  photo_url: string | null;
  total_trades: number;
  trades: number;
  total_volume: number;
  unique_assets: number;
  buy_count: number;
  sell_count: number;
  buys: number;
  sells: number;
  avg_score: number;
  high_alert: number;
  suspicious: number;
  noteworthy: number;
  top_assets: { ticker: string; name: string; trades: number; volume: number }[];
  score_trend: {
    month: string;
    avg_score: number;
    buys?: number;
    sells?: number;
    count?: number;
  }[];
  recent_trades: Trade[];
  politician?: Politician;
}

export interface Stock {
  ticker: string;
  name: string;
  trades: number;
  total_volume: number;
  unique_politicians: number;
  avg_score: number;
  buys: number;
  sells: number;
  sector: string | null;
  industry?: string | null;
}

export interface StocksResponse {
  total: number;
  limit: number;
  offset: number;
  stocks: Stock[];
}

export interface StockDetail {
  ticker: string;
  name: string;
  sector: string | null;
  industry: string | null;
  total_trades: number;
  trades: number;
  total_volume: number;
  unique_politicians: number;
  buy_count: number;
  sell_count: number;
  avg_score: number;
  politicians: { name: string; party: Party; trades: number; volume: number }[];
  volume_trend: {
    month: string;
    buys: number;
    sells: number;
    volume: number;
    count: number;
  }[];
  recent_trades: Trade[];
}

export interface SignalsResponse {
  total: number;
  limit: number;
  offset: number;
  tag: string;
  signals: Trade[];
}

export interface LeaderboardRow {
  rank: number;
  name: string;
  party: Party;
  chamber: Chamber;
  state_district: string | null;
  photo_url: string | null;
  trades: number;
  total_volume: number;
  avg_score: number;
}

export interface LeaderboardResponse {
  total?: number;
  leaderboard: LeaderboardRow[];
}

export interface SearchResponse {
  politicians: Politician[];
  tickers: {
    ticker: string;
    name: string;
    trades: number;
    total_volume: number;
    unique_politicians: number;
    avg_score: number;
  }[];
}

export interface AnalyzeOverview {
  party?: unknown;
  sector?: unknown;
  options?: unknown;
  suspicious?: unknown;
  [key: string]: unknown;
}
