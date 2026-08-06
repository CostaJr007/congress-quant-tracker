"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { fetchStock, ApiError } from "@/lib/api";
import { formatCurrency, politicianHref, scoreColor, partyColor, cn } from "@/lib/utils";
import TradeRow from "@/components/trade-row";
import { ErrorState, EmptyState } from "@/components/states";

export default function StockDetail() {
  const { ticker } = useParams<{ ticker: string }>();
  const [data, setData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    try {
      setData(await fetchStock(ticker));
    } catch (e) {
      setError(e instanceof ApiError ? "Asset not found" : "Backend offline");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [ticker]);

  if (loading) {
    return (
      <div className="p-8 animate-pulse space-y-4">
        <div className="h-8 w-48 bg-card rounded" />
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-20 rounded-2xl bg-card border border-border" />
          ))}
        </div>
        <div className="h-56 rounded-2xl bg-card border border-border" />
      </div>
    );
  }
  if (error) return <div className="p-8"><ErrorState message={error} onRetry={load} /></div>;
  if (!data.ticker) return <div className="p-8"><EmptyState title="Asset not found" /></div>;

  const trend = (data.volume_trend || []).slice(-12).map((m: any) => ({
    ...m,
    label: m.month ? `${m.month.slice(5)}/${m.month.slice(2, 4)}` : "",
  }));

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-fg font-mono">{data.ticker}</h1>
          <p className="text-fg-muted text-sm">
            {data.name}
            {data.sector && <span className="text-fg-subtle"> · {data.sector}</span>}
            {data.industry && <span className="text-fg-subtle"> · {data.industry}</span>}
          </p>
        </div>
        <div className="text-right">
          <div className={cn("text-3xl font-bold", scoreColor(data.avg_score))}>
            {Number(data.avg_score || 0).toFixed(1)}
          </div>
          <div className="text-xs text-fg-muted">avg suspicion score</div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Kpi label="Total Trades" value={data.total_trades ?? data.trades ?? 0} />
        <Kpi label="Volume" value={formatCurrency(data.total_volume || 0)} />
        <Kpi label="Politicians" value={data.unique_politicians ?? 0} />
        <Kpi label="Buy / Sell" value={`${data.buy_count ?? 0} / ${data.sell_count ?? 0}`} />
      </div>

      {trend.length > 0 && (
        <div className="rounded-2xl bg-card border border-border p-5 mb-8">
          <h3 className="text-sm font-semibold text-fg mb-4">Buy / Sell Activity</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={trend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="label" tick={{ fill: "#5e6673", fontSize: 11 }} />
              <YAxis tick={{ fill: "#5e6673", fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  background: "#1e2329",
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderRadius: "8px",
                  color: "#fff",
                  fontSize: "12px",
                }}
              />
              <Bar dataKey="buys" name="Buys" fill="#00bb7f" radius={[3, 3, 0, 0]} maxBarSize={18} />
              <Bar dataKey="sells" name="Sells" fill="#fb2c36" radius={[3, 3, 0, 0]} maxBarSize={18} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {data.politicians?.length > 0 && (
        <div className="mb-8">
          <h3 className="text-sm font-semibold text-fg mb-3">
            Politicians Trading {data.ticker}
          </h3>
          <div className="flex flex-wrap gap-2">
            {data.politicians.map((p: any) => {
              const name = typeof p === "string" ? p : p.name;
              const party = typeof p === "string" ? "" : p.party;
              const trades = typeof p === "string" ? null : p.trades;
              return (
                <Link
                  key={name}
                  href={politicianHref(name)}
                  className="px-3 py-1.5 rounded-lg bg-surface-2 text-xs border border-border hover:text-accent hover:border-accent/30 transition-colors flex items-center gap-2"
                >
                  {party && (
                    <span className={cn("font-bold", partyColor(party))}>{party}</span>
                  )}
                  <span className="text-fg-muted">{name}</span>
                  {trades != null && (
                    <span className="text-fg-subtle">{trades}</span>
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      )}

      <h3 className="text-sm font-semibold text-fg mb-4">Recent Trades</h3>
      <div className="space-y-2">
        {(data.recent_trades || []).map((trade: any) => (
          <TradeRow
            key={trade.id ?? trade.ticker + trade.transaction_date}
            trade={trade}
          />
        ))}
        {(data.recent_trades || []).length === 0 && <EmptyState title="No trades yet" />}
      </div>
    </div>
  );
}

function Kpi({
  label, value, valueClass,
}: { label: string; value: string | number; valueClass?: string }) {
  return (
    <div className="rounded-2xl bg-card border border-border p-4">
      <div className="text-xs text-fg-muted mb-1">{label}</div>
      <div className={cn("text-xl font-bold text-fg", valueClass)}>{value}</div>
    </div>
  );
}
