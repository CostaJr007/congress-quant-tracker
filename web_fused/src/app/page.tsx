"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area, Cell,
} from "recharts";
import { fetchDashboard, ApiError } from "@/lib/api";
import { formatCurrency, politicianHref, partyColor, cn } from "@/lib/utils";
import KpiCard from "@/components/kpi-card";
import { EmptyState, ErrorState } from "@/components/states";
import PoliticianAvatar from "@/components/politician-avatar";
import TradeGroupList from "@/components/trade-group-list";

const TAGS = [
  { key: "routine", label: "Routine", color: "#5e6673" },
  { key: "noteworthy", label: "Noteworthy", color: "#3080ff" },
  { key: "suspicious", label: "Suspicious", color: "#f59e0b" },
  { key: "high_alert", label: "High Alert", color: "#fb2c36" },
];

export default function Dashboard() {
  const [data, setData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchDashboard());
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "Backend offline. Start API: uv run python server/api_server.py",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) return <DashboardSkeleton />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data.total_trades) {
    return (
      <EmptyState
        title="No data yet"
        hint="Run scripts/daily_update.py or: uv run python scripts/rescore.py"
      />
    );
  }

  const signalData = TAGS.map((t) => ({
    name: t.label,
    count: data.signal_distribution?.[t.key] ?? 0,
    fill: t.color,
  }));
  const totalFlagged =
    (data.high_alert_count || 0) +
    (data.suspicious_count || 0) +
    (data.noteworthy_count || 0);

  const monthLabel = (m: string) => {
    const [, mo] = m.split("-");
    const names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return names[Number(mo) - 1] || m;
  };
  const activityData = (data.activity_by_month || []).map((a: any) => ({
    ...a,
    label: monthLabel(a.month),
  }));

  const partySplit = data.party_split || {};
  const partyTotal = Object.values(partySplit).reduce((a: number, b: any) => a + Number(b), 0) as number;

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="mb-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-fg mb-1">Dashboard</h1>
            <p className="text-fg-muted text-sm">
              Congressional trading intelligence
              {data.data_age_days != null && (
                <span className="text-fg-subtle"> · freshest public filing {data.data_age_days}d ago</span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-fg-subtle">
            <span className="w-1.5 h-1.5 rounded-full bg-positive animate-pulse" />
            <span>
              {data.total_trades?.toLocaleString()} trades · {data.unique_politicians} members ·{" "}
              {data.unique_assets?.toLocaleString()} assets
            </span>
          </div>
        </div>
      </div>

      {/* KPI Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <KpiCard label="Total Trades" value={data.total_trades?.toLocaleString()} delta={data.deltas?.trades} />
        <KpiCard label="Est. Volume" value={formatCurrency(data.total_volume)} delta={data.deltas?.volume} />
        <KpiCard label="Politicians" value={data.unique_politicians} />
        <KpiCard
          label="Flagged Signals"
          value={totalFlagged.toLocaleString()}
          suffix={data.avg_score != null ? `· avg ${Number(data.avg_score).toFixed(1)}` : undefined}
        />
      </div>

      {/* Buy/Sell + Party quick stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <MiniStat label="Buys" value={data.buy_count?.toLocaleString()} tone="positive" />
        <MiniStat label="Sells" value={data.sell_count?.toLocaleString()} tone="negative" />
        <MiniStat label="Democrats" value={partySplit.D ?? 0} tone="blue" />
        <MiniStat label="Republicans" value={partySplit.R ?? 0} tone="red" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Signal Distribution */}
        <div className="rounded-2xl bg-card border border-border p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-fg">Signal Distribution</h3>
            <Link href="/signals" className="text-xs text-accent hover:underline">{totalFlagged} flagged →</Link>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={signalData} layout="vertical" margin={{ left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" tick={{ fill: "#b7bdc8", fontSize: 11 }} width={82} />
              <Tooltip
                contentStyle={{
                  background: "#1e2329", border: "1px solid rgba(255,255,255,0.07)",
                  borderRadius: "8px", color: "#fff", fontSize: "12px",
                }}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={16}>
                {signalData.map((d, i) => <Cell key={i} fill={d.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          {partyTotal > 0 && (
            <div className="mt-3 pt-3 border-t border-border text-[11px] text-fg-subtle flex justify-between">
              <span>Party trade share</span>
              <span>
                D {Math.round(((partySplit.D || 0) / partyTotal) * 100)}% · R{" "}
                {Math.round(((partySplit.R || 0) / partyTotal) * 100)}%
              </span>
            </div>
          )}
        </div>

        {/* Monthly activity with buys/sells */}
        <div className="rounded-2xl bg-card border border-border p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-fg">Trading Activity (12 mo)</h3>
            <div className="flex gap-3 text-[11px] text-fg-subtle">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-positive" /> Buys</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-negative" /> Sells</span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={activityData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gBuy" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00bb7f" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#00bb7f" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gSell" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#fb2c36" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#fb2c36" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="label" tick={{ fill: "#5e6673", fontSize: 11 }} />
              <YAxis tick={{ fill: "#5e6673", fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  background: "#1e2329", border: "1px solid rgba(255,255,255,0.07)",
                  borderRadius: "8px", color: "#fff", fontSize: "12px",
                }}
              />
              <Area type="monotone" dataKey="buys" name="Buys" stroke="#00bb7f"
                    fill="url(#gBuy)" strokeWidth={2} />
              <Area type="monotone" dataKey="sells" name="Sells" stroke="#fb2c36"
                    fill="url(#gSell)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top politicians + top tickers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="rounded-2xl bg-card border border-border p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-fg">Top Politicians by Trades</h3>
            <Link href="/politicians" className="text-xs text-accent hover:underline">View all →</Link>
          </div>
          <div className="space-y-1">
            {(data.top_politicians || []).map((p: any, idx: number) => (
              <Link key={p.name} href={politicianHref(p.name)} className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-surface-2/50 transition-colors group">
                <span className="text-[10px] text-fg-subtle w-4">{idx + 1}</span>
                <PoliticianAvatar
                  name={p.name}
                  party={p.party}
                  bioguideId={p.bioguide_id}
                  photoUrl={p.photo_url}
                  size="xs"
                  rounded="full"
                />
                <span className={cn("text-xs font-bold w-4", partyColor(p.party))}>{p.party}</span>
                <span className="text-sm text-fg group-hover:text-accent truncate">{p.name}</span>
                <span className="ml-auto text-xs text-fg-subtle">{p.trades} trades</span>
                <span className="text-xs text-fg-muted w-16 text-right font-mono">{formatCurrency(p.total_volume)}</span>
              </Link>
            ))}
            {(data.top_politicians || []).length === 0 && (
              <div className="text-sm text-fg-subtle py-4 text-center">No politicians yet</div>
            )}
          </div>
        </div>

        <div className="rounded-2xl bg-card border border-border p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-fg">Most Traded Assets</h3>
            <Link href="/stocks" className="text-xs text-accent hover:underline">View all →</Link>
          </div>
          <div className="space-y-1">
            {(data.top_tickers || []).map((s: any, idx: number) => (
              <Link key={s.ticker} href={`/stocks/${s.ticker}`} className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-surface-2/50 transition-colors group">
                <span className="text-[10px] text-fg-subtle w-4">{idx + 1}</span>
                <span className="text-sm font-mono font-semibold text-accent w-14">{s.ticker}</span>
                <span className="text-xs text-fg-muted truncate">{s.name}</span>
                <span className="ml-auto text-xs text-fg-subtle">{s.trades} trades</span>
                <span className="text-xs text-fg-muted w-16 text-right font-mono">{formatCurrency(s.total_volume)}</span>
              </Link>
            ))}
            {(data.top_tickers || []).length === 0 && (
              <div className="text-sm text-fg-subtle py-4 text-center">No assets yet</div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Trades — grouped when many share same filer + filing date */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-fg">Recent Disclosures</h3>
          <p className="text-[11px] text-fg-subtle mt-0.5">
            Multiple trades from the same filing are collapsed — click to expand
          </p>
        </div>
        <Link href="/trades" className="text-xs text-accent hover:underline">View all →</Link>
      </div>
      <TradeGroupList
        trades={data.recent_trades || []}
        minGroupSize={3}
        empty={<EmptyState title="No trades yet" />}
      />
    </div>
  );
}

function MiniStat({
  label, value, tone,
}: { label: string; value: string | number; tone?: "positive" | "negative" | "blue" | "red" }) {
  const toneClass =
    tone === "positive" ? "text-positive" :
    tone === "negative" ? "text-negative" :
    tone === "blue" ? "text-blue-400" :
    tone === "red" ? "text-red-400" : "text-fg";
  return (
    <div className="rounded-xl bg-card/60 border border-border px-4 py-3">
      <div className="text-[10px] uppercase tracking-wider text-fg-subtle mb-0.5">{label}</div>
      <div className={cn("text-lg font-bold", toneClass)}>{value}</div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="max-w-7xl mx-auto px-6 py-8 animate-pulse">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 rounded-2xl bg-card border border-border" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="h-56 rounded-2xl bg-card border border-border" />
        <div className="h-56 rounded-2xl bg-card border border-border lg:col-span-2" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="h-56 rounded-2xl bg-card border border-border" />
        <div className="h-56 rounded-2xl bg-card border border-border" />
      </div>
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-14 rounded-xl bg-card border border-border" />
        ))}
      </div>
    </div>
  );
}
