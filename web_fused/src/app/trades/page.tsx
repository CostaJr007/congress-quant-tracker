"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchTrades, ApiError } from "@/lib/api";
import TradeRow from "@/components/trade-row";
import { EmptyState, ErrorState } from "@/components/states";
import { cn } from "@/lib/utils";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

const TAG_FILTERS = [
  { value: "", label: "All" },
  { value: "routine", label: "Routine" },
  { value: "noteworthy", label: "Noteworthy" },
  { value: "suspicious", label: "Suspicious" },
  { value: "high_alert", label: "High Alert" },
];

const TYPE_FILTERS = [
  { value: "", label: "All Types" },
  { value: "Purchase", label: "Buys" },
  { value: "Sale", label: "Sells" },
];

const ASSET_FILTERS = [
  { value: "", label: "All Assets" },
  { value: "stock", label: "Stocks" },
  { value: "etf", label: "ETFs" },
  { value: "option_call", label: "Options · Calls" },
  { value: "option_put", label: "Options · Puts" },
  { value: "crypto", label: "Crypto" },
  { value: "bond", label: "Bonds" },
];

export default function TradesPage() {
  const [data, setData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const debouncedQ = useDebouncedValue(q, 300);
  const [tag, setTag] = useState("");
  const [type, setType] = useState("");
  const [assetType, setAssetType] = useState("");
  const [minScore, setMinScore] = useState("");
  const [sortBy, setSortBy] = useState("date");
  const [offset, setOffset] = useState(0);
  const LIMIT = 25;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {
        limit: String(LIMIT), offset: String(offset), sort_by: sortBy,
        enrich: "true",
      };
      if (debouncedQ) params.q = debouncedQ;
      if (tag) params.tag = tag;
      if (type) params.trade_type = type;
      if (assetType) params.asset_type = assetType;
      if (minScore) params.min_score = minScore;
      setData(await fetchTrades(params));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Backend offline");
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, tag, type, assetType, minScore, sortBy, offset]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setOffset(0); }, [debouncedQ, tag, type, assetType, minScore, sortBy]);

  const total = data.total ?? 0;
  const trades = data.trades || [];
  const hasFilters = Boolean(q || tag || type || assetType || minScore);

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-fg mb-1">Trades</h1>
          <p className="text-fg-muted text-sm">
            {total.toLocaleString()} trades
            <span className="text-fg-subtle"> · % since trade + ~shares estimated (disclosure ranges, not exact)</span>
          </p>
        </div>

        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search ticker, asset or member…"
          className="bg-surface-2/70 border border-border rounded-lg px-3 py-2 text-sm text-fg placeholder:text-fg-subtle focus:outline-none focus:border-accent/50 w-64"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        <div className="flex gap-1.5 flex-wrap">
          {TAG_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setTag(f.value)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border",
                tag === f.value
                  ? "bg-accent/15 text-accent border-accent/20"
                  : "bg-surface-2 text-fg-muted hover:text-fg border-border",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="bg-surface-2/70 border border-border rounded-lg px-3 py-1.5 text-xs text-fg focus:outline-none focus:border-accent/50"
        >
          {TYPE_FILTERS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
        </select>

        <select
          value={assetType}
          onChange={(e) => setAssetType(e.target.value)}
          className="bg-surface-2/70 border border-border rounded-lg px-3 py-1.5 text-xs text-fg focus:outline-none focus:border-accent/50"
        >
          {ASSET_FILTERS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
        </select>

        <select
          value={minScore}
          onChange={(e) => setMinScore(e.target.value)}
          className="bg-surface-2/70 border border-border rounded-lg px-3 py-1.5 text-xs text-fg focus:outline-none focus:border-accent/50"
        >
          <option value="">Any score</option>
          <option value="26">Score ≥ 26</option>
          <option value="51">Score ≥ 51</option>
          <option value="76">Score ≥ 76</option>
        </select>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="bg-surface-2/70 border border-border rounded-lg px-3 py-1.5 text-xs text-fg focus:outline-none focus:border-accent/50"
        >
          <option value="date">Newest disclosed</option>
          <option value="trade_date">Newest trade date</option>
          <option value="score">Highest score</option>
          <option value="volume">Largest amount</option>
        </select>

        {hasFilters && (
          <button
            onClick={() => { setQ(""); setTag(""); setType(""); setAssetType(""); setMinScore(""); setSortBy("date"); }}
            className="px-3 py-1.5 rounded-lg text-xs text-fg-subtle hover:text-fg"
          >
            Clear
          </button>
        )}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="h-14 rounded-xl bg-card border border-border animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : trades.length === 0 ? (
        <EmptyState title="No trades match your filters" />
      ) : (
        <>
          <div className="space-y-2">
            {trades.map((trade: any) => (
              <TradeRow key={trade.id ?? trade.ticker + trade.transaction_date} trade={trade} />
            ))}
          </div>

          {total > LIMIT && (
            <div className="flex items-center justify-center gap-4 mt-8">
              <button
                onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
                disabled={offset === 0}
                className="px-4 py-2 rounded-lg bg-surface-2 border border-border text-xs font-medium text-fg hover:bg-surface-2/60 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                ← Previous
              </button>
              <span className="text-xs text-fg-subtle">
                {offset + 1}–{Math.min(offset + LIMIT, total)} of {total}
              </span>
              <button
                onClick={() => setOffset((o) => o + LIMIT)}
                disabled={offset + LIMIT >= total}
                className="px-4 py-2 rounded-lg bg-surface-2 border border-border text-xs font-medium text-fg hover:bg-surface-2/60 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}