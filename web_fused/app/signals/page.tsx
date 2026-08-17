"use client";

import { Suspense } from "react";
import { EmptyState, ErrorState, LoadingState, Pagination } from "@/components/States";
import { TradeTable } from "@/components/TradeTable";
import { qs } from "@/lib/format";
import { useApi, useFilters } from "@/lib/hooks";
import type { SignalsResponse } from "@/lib/types";

const LIMIT = 50;

export default function SignalsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading signals…" />}>
      <SignalsView />
    </Suspense>
  );
}

function SignalsView() {
  const { get, set, setMany } = useFilters();
  const tag = get("tag");
  const offset = Math.max(0, Number(get("offset", "0")) || 0);
  const path = `/api/signals${qs({ tag: tag || undefined, limit: LIMIT, offset })}`;
  const { data, loading, error, reload } = useApi<SignalsResponse>(path);

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-kicker">Alerts</div>
          <h1 className="page-title">Signals</h1>
          <p className="page-desc">Higher-score disclosures — noteworthy through high alert.</p>
        </div>
        {data && (
          <span className="chip">
            Total <strong>{data.total.toLocaleString()}</strong>
          </span>
        )}
      </header>

      <div className="filters">
        <select className="select" value={tag} onChange={(e) => set("tag", e.target.value)}>
          <option value="">All tags</option>
          <option value="noteworthy">Noteworthy</option>
          <option value="suspicious">Suspicious</option>
          <option value="high_alert">High alert</option>
        </select>
      </div>

      {loading && <LoadingState label="Loading signals…" />}
      {error && !loading && <ErrorState message={error} onRetry={reload} />}
      {!loading && !error && data && data.signals.length === 0 && (
        <EmptyState title="No signals" detail="Nothing above the score threshold." />
      )}
      {!loading && !error && data && data.signals.length > 0 && (
        <>
          <div className="card" style={{ padding: 0 }}>
            <TradeTable trades={data.signals} />
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
