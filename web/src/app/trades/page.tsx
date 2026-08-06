"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import PoliticianAvatar from "@/components/politician-avatar";

export default function TradesPage() {
  const [trades, setTrades] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/trades?limit=100").then(r => r.json()).then(setTrades);
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 animate-fade-up">
      <h1 className="text-2xl font-bold text-[var(--text-primary)] mb-1">Trade Feed</h1>
      <p className="text-sm text-[var(--text-muted)] mb-8">{trades.length} recent trades</p>
      <div className="space-y-1.5">
        {trades.map((t: any, i: number) => (
          <div key={i} className="flex items-center gap-3 px-5 py-3 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--border-hover)] transition-all">
            <PoliticianAvatar name={t.politician_name} bioguideId={t.politician_bioguide_id} party={t.politician_party} size="sm" />
            <div className="flex-1 min-w-0">
              <Link href={`/politicians?id=${encodeURIComponent(t.politician_name)}`} className="text-sm font-medium text-[var(--text-primary)] hover:text-[var(--accent)] block truncate">{t.politician_name}</Link>
              <div className="flex items-center gap-2 text-xs">
                <Link href={`/stocks/${t.ticker}`} className="font-mono text-[var(--accent)] hover:underline">{t.ticker}</Link>
                <span className="text-[var(--text-muted)] truncate max-w-[180px]">{t.asset_name}</span>
              </div>
            </div>
            <span className={cn("text-[10px] font-semibold px-2 py-0.5 rounded-md",
              t.transaction_type === "buy" ? "bg-[var(--positive-soft)] text-[var(--positive)]" : "bg-[var(--negative-soft)] text-[var(--negative)]"
            )}>{t.transaction_type?.toUpperCase()}</span>
            <span className="text-sm text-[var(--text-muted)] text-right w-24 font-mono">{t.value_range}</span>
            <span className="text-xs text-[var(--text-subtle)] text-right w-20">{t.trade_date}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
