"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchTrades, fetchTradeMonths, ApiError, type TradeMonth } from "@/lib/api";
import { EmptyState, ErrorState } from "@/components/states";
import { cn } from "@/lib/utils";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import TradeGroupList from "@/components/trade-group-list";
import { CalendarDays } from "lucide-react";

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
  const [months, setMonths] = useState<TradeMonth[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const debouncedQ = useDebouncedValue(q, 300);
  const [tag, setTag] = useState("");
  const [type, setType] = useState("");
  const [assetType, setAssetType] = useState("");
  const [minScore, setMinScore] = useState("");
  const [sortBy, setSortBy] = useState("date");
  /** YYYY-MM or "" for all months */
  const [month, setMonth] = useState<string | null>(null); // null = not initialized yet
  const [offset, setOffset] = useState(0);
  const LIMIT = 40;

  const dateField = sortBy === "trade_date" || sortBy === "tx_date" ? "trade" : "filing";

  // Load available months; default to newest month
  useEffect(() => {
    const ctrl = new AbortController();
    fetchTradeMonths(dateField, ctrl.signal)
      .then((r) => {
        setMonths(r.months || []);
        setMonth((prev) => {
          if (prev === "") return ""; // user chose All
          if (prev && r.months?.some((m) => m.month === prev)) return prev;
          return r.months?.[0]?.month ?? "";
        });
      })
      .catch(() => setMonths([]));
    return () => ctrl.abort();
  }, [dateField]);

  const load = useCallback(async () => {
    if (month === null) return; // wait for months init
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {
        limit: String(LIMIT),
        offset: String(offset),
        sort_by: sortBy,
        enrich: "true",
        date_field: dateField,
      };
      if (month) params.month = month;
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
  }, [debouncedQ, tag, type, assetType, minScore, sortBy, offset, month, dateField]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setOffset(0); }, [debouncedQ, tag, type, assetType, minScore, sortBy, month]);

  const total = data.total ?? 0;
  const trades = data.trades || [];
  const hasFilters = Boolean(q || tag || type || assetType || minScore);
  const activeMonth = months.find((m) => m.month === month);
  // Group months by year for section headers
  const byYear = months.reduce<Record<number, TradeMonth[]>>((acc, m) => {
    (acc[m.year] ||= []).push(m);
    return acc;
  }, {});
  const years = Object.keys(byYear).map(Number).sort((a, b) => b - a);

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-fg mb-1">Trades</h1>
          <p className="text-fg-muted text-sm">
            {month
              ? <>
                  <span className="text-fg font-medium">{activeMonth?.label || month}</span>
                  {" · "}
                  {total.toLocaleString()} trades
                  {activeMonth ? ` of ${activeMonth.count.toLocaleString()} in this month` : ""}
                </>
              : <>{total.toLocaleString()} trades · all months</>
            }
            <span className="text-fg-subtle"> · grouped by filer when many on same day</span>
          </p>
        </div>

        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search ticker, asset or member…"
          className="bg-surface-2/70 border border-border rounded-lg px-3 py-2 text-sm text-fg placeholder:text-fg-subtle focus:outline-none focus:border-accent/50 w-64"
        />
      </div>

      {/* Month browser */}
      <div className="mb-5 rounded-2xl border border-border bg-card p-4">
        <div className="flex items-center gap-2 mb-3 text-xs text-fg-muted">
          <CalendarDays className="w-3.5 h-3.5 text-accent" />
          <span className="font-semibold text-fg">Browse by month</span>
          <span className="text-fg-subtle">
            ({dateField === "filing" ? "disclosure date" : "trade date"})
          </span>
        </div>

        <div className="flex flex-wrap gap-1.5 mb-3">
          <button
            type="button"
            onClick={() => setMonth("")}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
              month === ""
                ? "bg-accent/15 text-accent border-accent/30"
                : "bg-surface-2/60 text-fg-muted border-border hover:text-fg",
            )}
          >
            All months
          </button>
        </div>

        {years.map((year) => (
          <div key={year} className="mb-3 last:mb-0">
            <div className="text-[10px] uppercase tracking-wider text-fg-subtle mb-1.5 font-semibold">
              {year}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {byYear[year].map((m) => (
                <button
                  key={m.month}
                  type="button"
                  onClick={() => setMonth(m.month)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors inline-flex items-center gap-1.5",
                    month === m.month
                      ? "bg-accent/15 text-accent border-accent/30"
                      : "bg-surface-2/60 text-fg-muted border-border hover:text-fg hover:border-border",
                  )}
                >
                  <span>{m.label.replace(` ${year}`, "")}</span>
                  <span
                    className={cn(
                      "text-[10px] tabular-nums px-1.5 py-0.5 rounded-md",
                      month === m.month ? "bg-accent/20 text-accent" : "bg-background/60 text-fg-subtle",
                    )}
                  >
                    {m.count}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ))}

        {months.length === 0 && (
          <div className="text-xs text-fg-subtle">No month data yet — run the pipeline.</div>
        )}
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
            Clear filters
          </button>
        )}
      </div>

      {month === null || loading ? (
        <div className="space-y-2">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-14 rounded-xl bg-card border border-border animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : trades.length === 0 ? (
        <EmptyState
          title={month ? `No trades in ${activeMonth?.label || month}` : "No trades match your filters"}
        />
      ) : (
        <>
          {month && (
            <div className="mb-3 flex items-center gap-2 text-xs text-fg-muted">
              <span className="font-semibold text-fg">{activeMonth?.label || month}</span>
              <span>·</span>
              <span>{total.toLocaleString()} disclosures this month</span>
            </div>
          )}

          <TradeGroupList trades={trades} minGroupSize={3} />

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
