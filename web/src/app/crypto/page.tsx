"use client";

import { useEffect, useState } from "react";

const CRYPTO = ["BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "DOT", "LTC", "SUI", "AVAX", "LINK"];

export default function CryptoPage() {
  const [tickers, setTickers] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/tickers/hot?limit=100").then(r => r.json()).then(d =>
      setTickers((d || []).filter((t: any) => CRYPTO.includes(t.ticker?.toUpperCase())))
    );
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 animate-fade-up">
      <h1 className="text-2xl font-bold text-[var(--text-primary)] mb-1">Crypto</h1>
      <p className="text-sm text-[var(--text-muted)] mb-8">Congressional crypto trading</p>

      {tickers.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-5xl mb-4 opacity-20">₿</div>
          <p className="text-[var(--text-muted)]">No crypto trades detected yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tickers.map((t: any, i: number) => (
            <div key={i} className="flex items-center gap-6 px-5 py-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--border-hover)] transition-all">
              <span className="font-mono font-bold text-lg w-20">{t.ticker}</span>
              <span className="text-xs text-[var(--text-muted)] truncate">{t.asset_name || t.ticker}</span>
              <div className="ml-auto flex gap-8 text-sm">
                <span><span className="text-[var(--text-muted)]">Trades </span><span className="font-semibold">{t.trade_count || t.count}</span></span>
                <span><span className="text-[var(--text-muted)]">Volume </span><span>{t.total_volume || "—"}</span></span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
