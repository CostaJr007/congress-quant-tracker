"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { fetchStocks, ApiError } from "@/lib/api";
import { formatCurrency, scoreColor } from "@/lib/utils";
import { EmptyState, ErrorState } from "@/components/states";
import { cn } from "@/lib/utils";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

const ASSET_FILTERS = [
  { value: "", label: "All" },
  { value: "stock", label: "Stocks" },
  { value: "etf", label: "ETFs" },
  { value: "option_call", label: "Call Options" },
  { value: "option_put", label: "Put Options" },
  { value: "crypto", label: "Crypto" },
];

export default function StocksPage() {
  const [data, setData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const debouncedQ = useDebouncedValue(q, 300);
  const [assetType, setAssetType] = useState("");
  const [sortBy, setSortBy] = useState("trades");
  const [offset, setOffset] = useState(0);
  const LIMIT = 25;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {
        limit: String(LIMIT), offset: String(offset), sort_by: sortBy,
      };
      if (debouncedQ) params.q = debouncedQ;
      if (assetType) params.asset_type = assetType;
      setData(await fetchStocks(params));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Backend offline");
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, assetType, sortBy, offset]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setOffset(0); }, [debouncedQ, assetType, sortBy]);

  const total = data.total ?? 0;
  const stocks = data.stocks || [];

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-fg mb-1">Stocks &amp; Assets</h1>
          <p className="text-fg-muted text-sm">{total.toLocaleString()} tickers tracked</p>
        </div>

        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search ticker or name…"
          className="bg-surface-2/70 border border-border rounded-lg px-3 py-2 text-sm text-fg placeholder:text-fg-subtle focus:outline-none focus:border-accent/50 w-56"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        <div className="flex gap-1.5">
          {ASSET_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setAssetType(f.value)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border",
                assetType === f.value
                  ? "bg-accent/15 text-accent border-accent/20"
                  : "bg-surface-2 text-fg-muted hover:text-fg border-border",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-1.5 text-xs">
          <span className="text-fg-subtle">Sort</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-surface-2/70 border border-border rounded-lg px-3 py-1.5 text-xs text-fg focus:outline-none focus:border-accent/50"
          >
            <option value="trades">Most trades</option>
            <option value="volume">Most volume</option>
            <option value="politicians">Most politicians</option>
            <option value="score">Highest score</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-card border border-border animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : stocks.length === 0 ? (
        <EmptyState title="No assets match your filters" />
      ) : (
        <>
          <div className="space-y-2">
            {stocks.map((stock: any) => (
              <Link
                key={stock.ticker}
                href={`/stocks/${stock.ticker}`}
                className="flex items-center gap-4 px-5 py-4 rounded-xl bg-card border border-border hover:border-accent/30 transition-all group"
              >
                <div className="w-14">
                  <div className="text-sm font-bold text-fg font-mono group-hover:text-accent transition-colors">
                    {stock.ticker}
                  </div>
                  <div className="text-[10px] uppercase tracking-wide text-fg-subtle mt-0.5">
                    {stock.asset_type || "asset"}
                  </div>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="text-sm text-fg truncate">{stock.name}</div>
                  <div className="text-xs text-fg-muted truncate">
                    {[stock.sector, stock.industry].filter(Boolean).join(" · ") || "—"}
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  <Stat label="Trades" value={stock.trades} />
                  <Stat label="Politicians" value={stock.unique_politicians} />
                  <Stat label="Volume" value={formatCurrency(stock.total_volume)} />
                  {stock.current_price != null && (
                    <Stat label="Price" value={formatCurrency(stock.current_price)} mono />
                  )}
                  <div className={scoreColor(stock.avg_score)}>
                    <div className="text-lg font-bold">{stock.avg_score?.toFixed(1)}</div>
                    <div className="text-xs">avg score</div>
                  </div>
                </div>
              </Link>
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

function Stat({ label, value, mono }: { label: string; value: string | number; mono?: boolean }) {
  return (
    <div className="text-center">
      <div className={cn("text-sm font-semibold text-fg", mono && "font-mono")}>{value}</div>
      <div className="text-xs text-fg-muted">{label}</div>
    </div>
  );
}