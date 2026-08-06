"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchSignals, ApiError } from "@/lib/api";
import TradeRow from "@/components/trade-row";
import { EmptyState, ErrorState } from "@/components/states";
import { cn } from "@/lib/utils";

const TABS = [
  { value: "high_alert", label: "High Alert" },
  { value: "suspicious", label: "Suspicious" },
  { value: "noteworthy", label: "Noteworthy" },
];

export default function SignalsPage() {
  const [data, setData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState("high_alert");
  const [offset, setOffset] = useState(0);
  const LIMIT = 25;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchSignals({ tag: tab, limit: String(LIMIT), offset: String(offset) }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Backend offline");
    } finally {
      setLoading(false);
    }
  }, [tab, offset]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setOffset(0); }, [tab]);

  const total = data.total ?? 0;
  const signals = data.signals || [];

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-fg mb-1">Signals</h1>
        <p className="text-fg-muted text-sm">Flagged trades ranked by suspicion score</p>
      </div>

      <div className="flex gap-1.5 mb-6 bg-surface-2/50 border border-border rounded-xl p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={cn(
              "px-4 py-1.5 rounded-lg text-xs font-medium transition-colors",
              tab === t.value
                ? "bg-card text-fg shadow-sm border border-border"
                : "text-fg-muted hover:text-fg",
            )}
          >
            {t.label}
            {data.total != null && t.value === tab && <span className="ml-1.5 text-fg-subtle">{total}</span>}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-card border border-border animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : signals.length === 0 ? (
        <EmptyState title={`No ${tab.replace("_", " ")} trades yet`} />
      ) : (
        <>
          <div className="space-y-2">
            {signals.map((trade: any) => (
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