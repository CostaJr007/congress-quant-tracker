"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getInitials, fmtDollar } from "@/lib/utils";

export default function StockDetail() {
  const { ticker } = useParams<{ ticker: string }>();
  const [data, setData] = useState<any>({});

  useEffect(() => {
    if (ticker) fetch(`/api/tickers/${ticker}`).then(r => r.json()).then(setData);
  }, [ticker]);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 animate-fade-up">
      <div className="flex items-center gap-4 mb-2">
        <h1 className="text-3xl font-black font-mono">{data.ticker || ticker}</h1>
        <span className="gradient-text font-semibold text-sm">{data.sector}</span>
      </div>
      <p className="text-sm text-[var(--text-muted)] mb-8">{data.trades_count || 0} trades tracked</p>

      {data.party_breakdown && (
        <div className="grid grid-cols-2 gap-4 mb-8">
          {Object.entries(data.party_breakdown).map(([party, count]: any) => (
            <div key={party} className="glass-card p-4">
              <div className="text-xs text-[var(--text-muted)] uppercase tracking-wider mb-1">{party === "D" ? "Democrats" : "Republicans"}</div>
              <div className="text-2xl font-bold">{count} trades</div>
            </div>
          ))}
        </div>
      )}

      {data.top_buyers?.length > 0 && (
        <>
          <h3 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">Top Buyers</h3>
          <div className="space-y-1.5">
            {data.top_buyers.map((b: any, i: number) => (
              <div key={i} className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)]">
                <div className="w-8 h-8 rounded-lg bg-[var(--bg-elevated)] flex items-center justify-center text-xs font-bold text-[var(--text-muted)]">{getInitials(b.politician_name || "")}</div>
                <div>
                  <Link href={`/politicians?id=${encodeURIComponent(b.politician_name)}`} className="text-sm font-medium hover:text-[var(--accent)]">{b.politician_name}</Link>
                  <div className="text-xs text-[var(--text-muted)]">{b.party} · {b.chamber}</div>
                </div>
                <div className="ml-auto text-sm font-semibold">{b.trade_count} trades</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
