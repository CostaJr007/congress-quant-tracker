"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { cn, fmtDollar, partyColor } from "@/lib/utils";
import PoliticianAvatar from "@/components/politician-avatar";

export default function LeaderboardPage() {
  const [leaders, setLeaders] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/politicians/top?limit=25").then(r => r.json()).then(setLeaders);
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 animate-fade-up">
      <h1 className="text-2xl font-bold text-[var(--text-primary)] mb-1">Rankings</h1>
      <p className="text-sm text-[var(--text-muted)] mb-8">Top politicians by trading activity</p>

      <div className="space-y-1.5">
        {leaders.map((p: any, i: number) => (
          <Link key={i} href={`/politicians?id=${encodeURIComponent(p.name)}`}
            className="flex items-center gap-4 px-5 py-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--border-hover)] transition-all group">
            <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold",
              i === 0 ? "bg-[var(--accent)] text-white" :
              i === 1 ? "bg-[var(--accent-soft)] text-[var(--accent)]" :
              i === 2 ? "bg-[var(--bg-elevated)] text-[var(--text-secondary)]" :
              "bg-[var(--bg-elevated)] text-[var(--text-muted)]"
            )}>#{i + 1}</div>
            <PoliticianAvatar name={p.name} bioguideId={p.bioguide_id} party={p.party} size="sm" />
            <div className="flex-1">
              <div className="text-sm font-medium text-[var(--text-primary)] group-hover:text-[var(--accent)] transition-colors">{p.name}</div>
              <div className={cn("text-xs", partyColor(p.party))}>{p.party} · {p.chamber?.toUpperCase()} · {p.state}</div>
            </div>
            <div className="text-right"><div className="text-sm font-bold text-[var(--text-primary)]">{p.trade_count || p.trades}</div><div className="text-[10px] text-[var(--text-muted)]">trades</div></div>
            <div className="text-right w-24"><div className="text-sm text-[var(--text-muted)]">{fmtDollar(p.total_volume || 0)}</div><div className="text-[10px] text-[var(--text-subtle)]">volume</div></div>
          </Link>
        ))}
      </div>
    </div>
  );
}
