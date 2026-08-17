"use client";

import { Suspense } from "react";
import { EmptyState, ErrorState, LoadingState, Pagination } from "@/components/States";
import { TradeGroupList } from "@/components/TradeGroupList";
import { qs } from "@/lib/format";
import { useApi, useFilters } from "@/lib/hooks";
import type { TradeMonthsResponse, TradesResponse } from "@/lib/types";

const LIMIT = 40;

export default function TradesPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading trades…" />}>
      <TradesView />
    </Suspense>
  );
}

function TradesView() {
  const { get, set, setMany } = useFilters();
  const q = get("q");
  const tag = get("tag");
  const party = get("party");
  const chamber = get("chamber");
  const month = get("month");
  const tradeType = get("trade_type");
  const sortBy = get("sort_by", "date");
  const offset = Math.max(0, Number(get("offset", "0")) || 0);

  const path = `/api/trades${qs({
    q,
    tag,
    party,
    chamber,
    month,
    trade_type: tradeType,
    sort_by: sortBy,
    limit: LIMIT,
    offset,
  })}`;

  const { data, loading, error, reload } = useApi<TradesResponse>(path);
  const months = useApi<TradeMonthsResponse>("/api/trades/months");

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-kicker">Tape</div>
          <h1 className="page-title">Trades</h1>
          <p className="page-desc">Filter disclosures by member, party, tag, and month.</p>
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
          placeholder="Search ticker, asset, member"
          defaultValue={q}
          key={`q-${q}`}
          onKeyDown={(e) => {
            if (e.key === "Enter") set("q", (e.target as HTMLInputElement).value);
          }}
          onBlur={(e) => set("q", e.target.value)}
        />
        <select className="select" value={tag} onChange={(e) => set("tag", e.target.value)}>
          <option value="">All tags</option>
          <option value="routine">Routine</option>
          <option value="noteworthy">Noteworthy</option>
          <option value="suspicious">Suspicious</option>
          <option value="high_alert">High alert</option>
        </select>
        <select className="select" value={party} onChange={(e) => set("party", e.target.value)}>
          <option value="">All parties</option>
          <option value="D">Democrat</option>
          <option value="R">Republican</option>
          <option value="I">Independent</option>
        </select>
        <select className="select" value={chamber} onChange={(e) => set("chamber", e.target.value)}>
          <option value="">All chambers</option>
          <option value="house">House</option>
          <option value="senate">Senate</option>
        </select>
        <select className="select" value={tradeType} onChange={(e) => set("trade_type", e.target.value)}>
          <option value="">Buy + sell</option>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
        <select className="select" value={sortBy} onChange={(e) => set("sort_by", e.target.value)}>
          <option value="date">Newest filed</option>
          <option value="trade_date">Trade date</option>
          <option value="score">Score</option>
          <option value="volume">Volume</option>
        </select>
      </div>

      {months.data?.months && months.data.months.length > 0 && (
        <div className="months">
          <button
            type="button"
            className={`mchip ${!month ? "on" : ""}`}
            onClick={() => set("month", "")}
          >
            All months
          </button>
          {months.data.months.map((m) => (
            <button
              key={m.month}
              type="button"
              className={`mchip ${month === m.month ? "on" : ""}`}
              onClick={() => set("month", month === m.month ? "" : m.month)}
            >
              {m.label} · {m.count}
            </button>
          ))}
        </div>
      )}

      {loading && <LoadingState label="Loading trades…" />}
      {error && !loading && <ErrorState message={error} onRetry={reload} />}
      {!loading && !error && data && data.trades.length === 0 && (
        <EmptyState title="No trades match" detail="Try clearing a filter." />
      )}
      {!loading && !error && data && data.trades.length > 0 && (
        <>
          <TradeGroupList trades={data.trades} />
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
