"use client";

import Link from "next/link";
import { Suspense } from "react";
import { EmptyState, ErrorState, LoadingState, Pagination } from "@/components/States";
import { formatMoney, formatNumber, formatScore, qs, tickerHref } from "@/lib/format";
import { useApi, useFilters } from "@/lib/hooks";
import type { StocksResponse } from "@/lib/types";

const LIMIT = 40;

export default function StocksPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading stocks…" />}>
      <StocksView />
    </Suspense>
  );
}

function StocksView() {
  const { get, set, setMany } = useFilters();
  const q = get("q");
  const sortBy = get("sort_by", "trades");
  const offset = Math.max(0, Number(get("offset", "0")) || 0);
  const path = `/api/stocks${qs({ q, sort_by: sortBy, limit: LIMIT, offset })}`;
  const { data, loading, error, reload } = useApi<StocksResponse>(path);

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-kicker">Universe</div>
          <h1 className="page-title">Stocks</h1>
          <p className="page-desc">Tickers appearing in congressional disclosures.</p>
        </div>
        {data && (
          <span className="chip">
            Total <strong>{data.total.toLocaleString()}</strong>
          </span>
        )}
      </header>

      <div className="filters">
        <input
          className="field q"
          placeholder="Search ticker or name"
          defaultValue={q}
          key={`q-${q}`}
          onKeyDown={(e) => {
            if (e.key === "Enter") set("q", (e.target as HTMLInputElement).value);
          }}
          onBlur={(e) => set("q", e.target.value)}
        />
        <select className="select" value={sortBy} onChange={(e) => set("sort_by", e.target.value)}>
          <option value="trades">Most trades</option>
          <option value="volume">Volume</option>
          <option value="politicians">Politicians</option>
          <option value="score">Avg score</option>
        </select>
      </div>

      {loading && <LoadingState label="Loading stocks…" />}
      {error && !loading && <ErrorState message={error} onRetry={reload} />}
      {!loading && !error && data && data.stocks.length === 0 && <EmptyState title="No stocks match" />}
      {!loading && !error && data && data.stocks.length > 0 && (
        <>
          <div className="card" style={{ padding: 0 }}>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Name</th>
                    <th className="hide-sm">Sector</th>
                    <th className="num">Trades</th>
                    <th className="num">Volume</th>
                    <th className="num hide-sm">Members</th>
                    <th className="num">Score</th>
                    <th className="num hide-sm">B / S</th>
                  </tr>
                </thead>
                <tbody>
                  {data.stocks.map((s) => (
                    <tr key={s.ticker}>
                      <td>
                        <Link className="ticker" href={tickerHref(s.ticker)}>
                          {s.ticker}
                        </Link>
                      </td>
                      <td className="ellipsis">{s.name}</td>
                      <td className="hide-sm dim">{s.sector || "—"}</td>
                      <td className="num">{formatNumber(s.trades)}</td>
                      <td className="num">{formatMoney(s.total_volume)}</td>
                      <td className="num hide-sm">{formatNumber(s.unique_politicians)}</td>
                      <td className="num">{formatScore(s.avg_score)}</td>
                      <td className="num hide-sm">
                        <span className="buy">{s.buys}</span>
                        <span className="faint"> / </span>
                        <span className="sell">{s.sells}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <Pagination
            total={data.total}
            limit={LIMIT}
            offset={offset}
            onPage={(next) => setMany({ offset: next || undefined }, false)}
          />
        </>
      )}
    </>
  );
}
