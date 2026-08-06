"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function StocksPage() {
  const [stocks, setStocks] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/tickers/hot?limit=50").then(r => r.json()).then(setStocks);
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 animate-fade-up">
      <h1 className="text-2xl font-bold text-[var(--text-primary)] mb-1">Stocks</h1>
      <p className="text-sm text-[var(--text-muted)] mb-8">{stocks.length} tickers tracked</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {stocks.map((s: any, i: number) => (
          <Link key={i} href={`/stocks/${s.ticker}`}
            className="glass-card p-5 hover:border-[var(--accent)]/20 transition-all group">
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono font-bold text-lg group-hover:text-[var(--accent)] transition-colors">{s.ticker}</span>
              {s.buy_pct !== undefined && (
                <span className="text-[10px] font-semibold text-[var(--positive)] bg-[var(--positive-soft)] px-2 py-0.5 rounded-md">
                  {(s.buy_pct * 100).toFixed(0)}% buy
                </span>
              )}
            </div>
            <div className="text-xs text-[var(--text-muted)] mb-4 truncate">{s.asset_name || s.name || s.ticker}</div>
            <div className="flex items-center justify-between text-xs pt-3 border-t border-[var(--border-color)]">
              <span className="text-[var(--text-muted)]">{s.trade_count || s.count} trades</span>
              <span className="text-[var(--text-subtle)]">{s.sector}</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
