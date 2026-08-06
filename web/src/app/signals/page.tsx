"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import PoliticianAvatar from "@/components/politician-avatar";

export default function SignalsPage() {
  const [signals, setSignals] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/signals?min_score=0&limit=50").then(r => r.json()).then(d => setSignals(d.signals || []));
  }, []);

  const tierStyle = (s: number) => s >= 76
    ? "border-[var(--negative)]/20 bg-[var(--negative-soft)]" : s >= 51
    ? "border-[var(--warning)]/20 bg-[var(--warning)]/5" : s >= 26
    ? "border-[var(--accent)]/20 bg-[var(--accent-soft)]" : "bg-[var(--bg-card)] border-[var(--border-color)]";

  const tierText = (s: number) => s >= 76 ? "text-[var(--negative)]" : s >= 51 ? "text-[var(--warning)]" : s >= 26 ? "text-[var(--accent)]" : "text-[var(--text-muted)]";

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 animate-fade-up">
      <div className="flex items-center gap-3 mb-2">
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Signals</h1>
        <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-[var(--negative-soft)] text-[var(--negative)]">{signals.length} flagged</span>
      </div>
      <p className="text-sm text-[var(--text-muted)] mb-8">Trades flagged by suspicion scoring</p>

      <div className="space-y-2">
        {signals.map((t: any, i: number) => (
          <div key={i} className={cn("flex items-center gap-4 px-5 py-3 rounded-xl border transition-all", tierStyle(t.score || 0))}>
            <PoliticianAvatar name={t.politician_name} bioguideId={t.politician_bioguide_id} party={t.politician_party} size="sm" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-[var(--text-primary)] truncate">{t.politician_name}</div>
              <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                <span className="font-mono text-[var(--accent)]">{t.ticker}</span>
                <span className="truncate">{t.asset_name}</span>
              </div>
            </div>
            <div className="text-sm text-[var(--text-muted)] font-mono">{t.value_range}</div>
            <div className={cn("text-2xl font-black w-16 text-right", tierText(t.score || 0))}>{t.score || 0}</div>
            <div className="text-[10px] text-[var(--text-subtle)] uppercase w-20 text-right">{(t.tag || "").replace("_", " ")}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
