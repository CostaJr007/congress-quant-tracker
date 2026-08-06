"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Cell, LineChart, Line,
} from "recharts";
import { fetchPolitician, ApiError } from "@/lib/api";
import { formatCurrency, scoreColor, partyColor, cn } from "@/lib/utils";
import TradeRow from "@/components/trade-row";
import { ErrorState, EmptyState } from "@/components/states";
import PoliticianAvatar from "@/components/politician-avatar";

export default function PoliticianDetail() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!id) return;
    const name = decodeURIComponent(id).replace(/-/g, " ");
    setLoading(true);
    setError(null);
    try {
      setData(await fetchPolitician(name));
    } catch (e) {
      setError(e instanceof ApiError ? "Politician not found" : "Backend offline");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [id]);

  if (loading) return <div className="p-8 animate-pulse space-y-4"><div className="h-8 w-64 bg-card rounded" /><div className="grid grid-cols-5 gap-4">{[...Array(5)].map((_, i) => <div key={i} className="h-20 rounded-2xl bg-card border border-border" />)}</div><div className="h-64 rounded-2xl bg-card border border-border" /></div>;
  if (error) return <div className="p-8"><ErrorState message={error} onRetry={load} /></div>;
  if (!data.name) return <div className="p-8"><EmptyState title="Politician not found" /></div>;

  const scoreBars = (data.recent_trades || []).slice(0, 24).map((t: any, i: number) => ({
    i: i + 1, score: t.score || 0, date: t.transaction_date,
  }));

  const trend = (data.score_trend || []).slice(-12).map((m: any) => ({
    ...m, label: m.month?.slice(5) + "/" + m.month?.slice(2, 4),
  }));

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-8 flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <PoliticianAvatar
            name={data.name}
            party={data.party}
            bioguideId={data.bioguide_id}
            photoUrl={data.photo_url}
            size="lg"
            rounded="2xl"
          />
          <div>
            <h1 className="text-2xl font-bold text-fg">{data.name}</h1>
            <p className="text-fg-muted text-sm">
              <span className={cn("font-semibold", partyColor(data.party))}>{data.party || ""}</span>
              {data.state_district && <span> · {data.state_district}</span>}
              {data.chamber && <span> · {data.chamber}</span>}
            </p>
            {data.committees?.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {data.committees.map((c: string) => (
                  <span key={c} className="px-2 py-0.5 rounded bg-surface-2 border border-border text-[11px] text-fg-muted">
                    {c}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="text-right">
          <div className={cn("text-3xl font-bold", scoreColor(data.avg_score))}>{data.avg_score?.toFixed(1)}</div>
          <div className="text-xs text-fg-muted">avg suspicion score</div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Kpi label="Total Trades" value={data.total_trades} />
        <Kpi label="Volume" value={formatCurrency(data.total_volume || 0)} />
        <Kpi label="Assets" value={data.unique_assets} />
        <Kpi label="Buy / Sell" value={`${data.buy_count ?? 0} / ${data.sell_count ?? 0}`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Activity summary */}
        <div className="rounded-2xl bg-card border border-border p-5">
          <h3 className="text-sm font-semibold text-fg mb-3">Signals</h3>
          <div className="space-y-2 text-sm">
            <Row label="High Alerts" value={data.high_alert ?? 0} className="text-red-500" />
            <Row label="Suspicious" value={data.suspicious ?? 0} className="text-orange-500" />
            <Row label="Noteworthy" value={data.noteworthy ?? 0} className="text-blue-500" />
          </div>
          <h3 className="text-sm font-semibold text-fg mt-6 mb-3">Top Assets</h3>
          <div className="space-y-1.5">
            {(data.top_assets || []).map((a: any) => (
              <Link key={a.ticker} href={`/stocks/${a.ticker}`} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-surface-2/50 transition-colors">
                <span className="text-xs font-mono font-semibold text-accent w-14">{a.ticker}</span>
                <span className="text-xs text-fg-muted truncate">{a.name}</span>
                <span className="ml-auto text-xs text-fg-subtle">{a.trades}</span>
              </Link>
            ))}
            {(data.top_assets || []).length === 0 && <div className="text-xs text-fg-subtle">No assets yet</div>}
          </div>
        </div>

        {/* Score trend */}
        <div className="rounded-2xl bg-card border border-border p-5 lg:col-span-2">
          <h3 className="text-sm font-semibold text-fg mb-4">Suspicion Trend</h3>
          {trend.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trend} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="label" tick={{ fill: "#5e6673", fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fill: "#5e6673", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    background: "#1e2329", border: "1px solid rgba(255,255,255,0.07)",
                    borderRadius: "8px", color: "#fff", fontSize: "12px",
                  }}
                />
                <Line type="monotone" dataKey="avg_score" name="avg score" stroke="#f59e0b" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-sm text-fg-subtle h-[200px] flex items-center justify-center">Not enough history</div>
          )}
        </div>
      </div>

      {/* Per-trade score bars */}
      {scoreBars.length > 0 && (
        <div className="rounded-2xl bg-card border border-border p-5 mb-8">
          <h3 className="text-sm font-semibold text-fg mb-4">Recent Trade Scores</h3>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={scoreBars} margin={{ top: 0, right: 0, left: -25, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis dataKey="i" hide />
              <YAxis domain={[0, 100]} tick={{ fill: "#5e6673", fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: "#1e2329", border: "1px solid rgba(255,255,255,0.07)", borderRadius: "8px", color: "#fff", fontSize: "12px" }}
              />
              <Bar dataKey="score" radius={[3, 3, 0, 0]} maxBarSize={28}>
                {scoreBars.map((b: any) => (
                  <Cell key={b.i} fill={b.score >= 76 ? "#fb2c36" : b.score >= 51 ? "#f59e0b" : b.score >= 26 ? "#3080ff" : "#3a414a"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <h3 className="text-sm font-semibold text-fg mb-4">Recent Trades</h3>
      <div className="space-y-2">
        {(data.recent_trades || []).map((trade: any) => (
          <TradeRow key={trade.id ?? trade.ticker + trade.transaction_date} trade={trade} showPolitician={false} />
        ))}
        {(data.recent_trades || []).length === 0 && <EmptyState title="No trades yet" />}
      </div>
    </div>
  );
}

// tiny helper kept for readability
function Row({ label, value, className }: { label: string; value: number; className: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-fg-muted">{label}</span>
      <span className={cn("font-semibold", className)}>{value}</span>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl bg-card border border-border p-4">
      <div className="text-xs text-fg-muted mb-1">{label}</div>
      <div className="text-xl font-bold text-fg">{value}</div>
    </div>
  );
}