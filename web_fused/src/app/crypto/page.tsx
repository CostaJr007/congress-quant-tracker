"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchStocks, ApiError } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { ErrorState, EmptyState } from "@/components/states";
import { cn } from "@/lib/utils";
import Link from "next/link";

export default function CryptoPage() {
  const [data, setData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchStocks({ asset_type: "crypto", sort_by: "volume", limit: "50" }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Backend offline");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const crypto = data.stocks || [];

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-fg mb-1">Crypto</h1>
        <p className="text-fg-muted text-sm">{data.total || 0} digital assets tracked in congressional disclosures</p>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-card border border-border animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : crypto.length === 0 ? (
        <EmptyState title="No crypto trades found" hint="Data will populate as the pipeline runs." />
      ) : (
        <div className="space-y-2">
          {crypto.map((c: any) => (
            <Link
              key={c.ticker}
              href={`/stocks/${c.ticker}`}
              className="flex items-center gap-6 px-5 py-4 rounded-xl bg-card border border-border hover:border-accent/30 transition-colors group"
            >
              <div className="w-14">
                <div className="text-sm font-bold text-fg font-mono group-hover:text-accent transition-colors">{c.ticker}</div>
                <div className="text-xs text-fg-muted truncate">{c.name}</div>
              </div>
              <div className="ml-auto flex items-center gap-8 text-sm">
                <div>
                  <div className="text-sm font-semibold text-fg">{c.trades}</div>
                  <div className="text-xs text-fg-muted">trades</div>
                </div>
                <div>
                  <div className="text-sm font-semibold text-fg">{c.unique_politicians}</div>
                  <div className="text-xs text-fg-muted">politicians</div>
                </div>
                <div>
                  <div className="text-sm font-semibold text-fg">{formatCurrency(c.total_volume)}</div>
                  <div className="text-xs text-fg-muted">volume</div>
                </div>
                {c.current_price != null && (
                  <div className={cn("text-right")}>
                    <div className="text-sm font-semibold text-fg font-mono">{formatCurrency(c.current_price)}</div>
                    <div className="text-xs text-fg-muted">price</div>
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}