"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { cn, fmtDollar, partyColor } from "@/lib/utils";
import PoliticianAvatar from "@/components/politician-avatar";
import { TrendingUp, TrendingDown, Users, BarChart3, ArrowUpRight, Zap } from "lucide-react";

export default function HomePage() {
  const [stats, setStats] = useState<any>({});
  const [trades, setTrades] = useState<any[]>([]);
  const [leaders, setLeaders] = useState<any[]>([]);
  const [ticker, setTicker] = useState("");

  useEffect(() => {
    Promise.all([
      fetch("/api/stats").then(r => r.json()),
      fetch("/api/trades?limit=8").then(r => r.json()),
      fetch("/api/politicians/top?limit=6").then(r => r.json()),
      fetch("/api/signals?min_score=51&limit=5").then(r => r.json()),
    ]).then(([s, t, l, sig]) => {
      setStats(s); setTrades(t); setLeaders(l); setSignals(sig.signals || []);
    });
  }, []);

  const [signals, setSignals] = useState<any[]>([]);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 animate-fade-up">
      {/* Hero */}
      <div className="mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--accent-soft)] border border-[var(--accent)]/20 text-xs font-medium text-[var(--accent)] mb-6">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
          Live data from House & Senate disclosures
        </div>
        <h1 className="text-4xl lg:text-5xl font-extrabold tracking-tight text-[var(--text-primary)] leading-[1.1] mb-3">
          Congressional<br />
          <span className="gradient-text">Trading Intelligence</span>
        </h1>
        <p className="text-[var(--text-secondary)] text-lg max-w-xl leading-relaxed">
          Monitor every stock trade, options contract, and crypto move made by members of Congress. See who's buying before the market moves.
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
        {[
          { label: "Total Trades", value: (stats.trades || 0).toLocaleString(), icon: BarChart3, delta: "+12% this month" },
          { label: "Politicians", value: stats.politicians || 0, icon: Users, delta: "House & Senate" },
          { label: "Com panies Tracked", value: stats.companies || 0, icon: TrendingUp, delta: "25 tickers" },
          { label: "Options Trades", value: stats.options || 0, icon: Zap, delta: "75 contracts" },
        ].map((kpi, i) => (
          <div key={i} className="glass-card p-5 hover:border-[var(--accent)]/15 transition-all group">
            <div className="flex items-center justify-between mb-3">
              <kpi.icon className="w-4 h-4 text-[var(--text-muted)] group-hover:text-[var(--accent)] transition-colors" />
              <ArrowUpRight className="w-3 h-3 text-[var(--text-subtle)] opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <div className="text-2xl font-bold text-[var(--text-primary)] mb-1">{kpi.value}</div>
            <div className="text-xs text-[var(--text-muted)]">{kpi.label}</div>
            <div className="text-[10px] text-[var(--text-subtle)] mt-2">{kpi.delta}</div>
          </div>
        ))}
      </div>

      {/* Ticker Search */}
      <div className="mb-10">
        <div className="flex items-center gap-3">
          <div className="flex-1 max-w-md relative">
            <input
              type="text" placeholder="Search ticker... AAPL, NVDA, TSLA" value={ticker}
              onChange={e => setTicker(e.target.value)}
              className="w-full pl-4 pr-16 py-3 text-sm bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-xl text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)]/40 transition-all font-mono"
            />
            <Link href={ticker ? `/stocks/${ticker.toUpperCase()}` : "#"}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-1.5 text-xs font-semibold rounded-lg text-white transition-all"
              style={{ background: "var(--gradient-accent)" }}>
              Check
            </Link>
          </div>
        </div>
      </div>

      {/* Main Grid: Feed + Top + Signals */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Feed */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Latest Trades</h2>
            <Link href="/trades" className="text-xs text-[var(--accent)] hover:text-[var(--accent-hover)] transition-colors flex items-center gap-1">
              View all <ArrowUpRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="space-y-1.5">
            {trades.map((t: any, i: number) => (
              <div key={i} className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--border-hover)] transition-all">
                <PoliticianAvatar name={t.politician_name} bioguideId={t.politician_bioguide_id} party={t.politician_party} size="sm" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-[var(--text-primary)] truncate">{t.politician_name}</div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-mono font-medium text-[var(--accent)]">{t.ticker}</span>
                    <span className="text-[var(--text-muted)] truncate">{t.asset_name}</span>
                  </div>
                </div>
                <span className={cn("text-[10px] font-semibold px-2 py-0.5 rounded-md",
                  t.transaction_type === "buy" ? "bg-[var(--positive-soft)] text-[var(--positive)]" : "bg-[var(--negative-soft)] text-[var(--negative)]"
                )}>{t.transaction_type?.toUpperCase()}</span>
                <span className="text-xs text-[var(--text-muted)] w-16 text-right font-mono">{t.value_range}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Top Politicians */}
          <div>
            <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">Top Traders</h2>
            <div className="space-y-1.5">
              {leaders.map((p: any, i: number) => (
                <Link key={i} href={`/politicians?id=${encodeURIComponent(p.name)}`}
                  className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--border-hover)] transition-all group">
                  <span className={cn("text-xs font-bold w-5 text-right",
                    i === 0 ? "text-[var(--accent)]" : "text-[var(--text-muted)]"
                  )}>#{i + 1}</span>
                  <PoliticianAvatar name={p.name} bioguideId={p.bioguide_id} party={p.party} size="sm" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-[var(--text-primary)] truncate group-hover:text-[var(--accent)] transition-colors">{p.name}</div>
                    <div className={cn("text-[10px]", partyColor(p.party))}>{p.party} · {p.chamber}</div>
                  </div>
                  <span className="text-xs font-semibold text-[var(--text-secondary)]">{p.trade_count || p.trades}</span>
                </Link>
              ))}
            </div>
          </div>

          {/* Signals */}
          {signals.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">Flagged Signals</h2>
              <div className="space-y-1.5">
                {signals.map((t: any, i: number) => (
                  <div key={i} className="px-4 py-3 rounded-xl bg-[var(--bg-card)] border border-[var(--warning)]/20">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono text-xs font-semibold text-[var(--accent)]">{t.ticker}</span>
                      <span className="text-[10px] text-[var(--text-muted)]">{t.politician_name}</span>
                      <span className={cn("text-xs font-bold ml-auto", t.score >= 76 ? "text-[var(--negative)]" : "text-[var(--warning)]")}>
                        {t.score}
                      </span>
                    </div>
                    <div className="text-[10px] text-[var(--text-muted)] truncate">{t.reason}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
