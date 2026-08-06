"use client";

import { useEffect, useState, useCallback } from "react";
import { cn, partyColor, fmtDollar } from "@/lib/utils";
import PoliticianAvatar from "@/components/politician-avatar";
import { Search } from "lucide-react";

export default function PoliticiansPage() {
  const [politicians, setPoliticians] = useState<any[]>([]);
  const [filtered, setFiltered] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [detail, setDetail] = useState<any>(null);

  useEffect(() => {
    fetch("/api/politicians/top?limit=100").then(r => r.json()).then(d => {
      setPoliticians(d); setFiltered(d);
    });
  }, []);

  useEffect(() => {
    if (!search.trim()) { setFiltered(politicians); return; }
    const q = search.toLowerCase();
    setFiltered(politicians.filter((p: any) =>
      p.name?.toLowerCase().includes(q) || p.party?.toLowerCase().includes(q) || p.chamber?.toLowerCase().includes(q)
    ));
  }, [search, politicians]);

  const showDetail = useCallback(async (name: string) => {
    try {
      const r = await fetch(`/api/politicians/search?q=${encodeURIComponent(name)}`);
      const data = await r.json();
      if (data?.[0]) {
        const d = await fetch(`/api/politicians/${data[0].id}`).then(r => r.json());
        setDetail(d);
      }
    } catch {}
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 animate-fade-up">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Politicians</h1>
          <p className="text-sm text-[var(--text-muted)]">{filtered.length} members tracked</p>
        </div>
        <div className="relative w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
          <input type="text" placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 text-sm bg-[var(--bg-elevated)] border border-[var(--border-color)] rounded-xl text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)]/40 transition-all" />
        </div>
      </div>

      {/* Detail panel */}
      {detail && (
        <div className="mb-8 p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-color)] animate-fade-up"
          style={{ boxShadow: "0 0 0 1px rgba(20,184,166,0.1), 0 8px 32px rgba(0,0,0,0.4)" }}>
          <div className="flex items-center gap-4 mb-6">
            <PoliticianAvatar name={detail.politician?.name} bioguideId={detail.politician?.bioguide_id} party={detail.politician?.party} size="lg" />
            <div className="flex-1">
              <h2 className="text-xl font-bold text-[var(--text-primary)]">{detail.politician?.name}</h2>
              <p className="text-sm text-[var(--text-muted)]">
                <span className={partyColor(detail.politician?.party)}>{detail.politician?.party}</span> · {detail.politician?.chamber?.toUpperCase()} · {detail.politician?.state}
              </p>
            </div>
            <button onClick={() => setDetail(null)} className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] px-3 py-1.5 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-color)]">Close</button>
          </div>
          <div className="grid grid-cols-4 gap-4 mb-6">
            <MiniStat label="Trades" value={detail.trades?.length || 0} />
            <MiniStat label="Sectors" value={detail.sector_exposure?.length || 0} />
            <MiniStat label="Committees" value={detail.politician?.committees?.split(",")?.length || 0} />
            <MiniStat label="Buy Ratio" value={detail.buy_sell_ratio ? Math.round(detail.buy_sell_ratio * 100) + "%" : "—"} />
          </div>
          {detail.trades?.length > 0 && (
            <div className="space-y-1">
              <h4 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3">Recent Trades</h4>
              {detail.trades.slice(0, 6).map((t: any, i: number) => (
                <div key={i} className="flex items-center gap-3 text-xs py-2 px-3 rounded-lg bg-[var(--bg-elevated)]">
                  <span className="font-mono font-semibold text-[var(--accent)] w-16">{t.ticker}</span>
                  <span className={cn("font-medium", t.transaction_type === "buy" ? "text-[var(--positive)]" : "text-[var(--negative)]")}>{t.transaction_type?.toUpperCase()}</span>
                  <span className="text-[var(--text-muted)]">{t.value_range}</span>
                  <span className="ml-auto text-[var(--text-subtle)]">{t.trade_date}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Card Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filtered.map((p: any, i: number) => (
          <button key={i} onClick={() => showDetail(p.name)}
            className="text-left glass-card p-5 hover:border-[var(--accent)]/20 transition-all group">
            <div className="flex items-center gap-1 mb-3">
              <span className={cn("text-[10px] font-bold", partyColor(p.party))}>{p.party}</span>
              <span className="text-[10px] text-[var(--text-subtle)]">·</span>
              <span className="text-[10px] text-[var(--text-muted)]">{p.state || p.chamber?.toUpperCase()}</span>
            </div>
            <div className="flex items-center gap-3 mb-4">
              <PoliticianAvatar name={p.name} bioguideId={p.bioguide_id} party={p.party} size="sm" />
              <h3 className="text-[var(--text-primary)] font-semibold text-sm truncate group-hover:text-[var(--accent)] transition-colors">{p.name}</h3>
            </div>
            <div className="grid grid-cols-2 gap-3 pt-3 border-t border-[var(--border-color)]">
              <div><div className="text-[10px] text-[var(--text-muted)]">Trades</div><div className="text-sm font-bold text-[var(--text-primary)]">{p.trade_count || p.trades}</div></div>
              <div><div className="text-[10px] text-[var(--text-muted)]">Volume</div><div className="text-sm font-bold text-[var(--text-primary)]">{fmtDollar(p.total_volume || 0)}</div></div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-[var(--bg-elevated)] p-3">
      <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-0.5">{label}</div>
      <div className="text-lg font-bold text-[var(--text-primary)]">{value}</div>
    </div>
  );
}
