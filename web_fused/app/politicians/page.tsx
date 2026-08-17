"use client";

import Link from "next/link";
import { Suspense } from "react";
import { Avatar } from "@/components/Avatar";
import { PartyPill } from "@/components/PartyPill";
import { EmptyState, ErrorState, LoadingState, Pagination } from "@/components/States";
import { formatMoney, formatNumber, formatScore, politicianHref, qs } from "@/lib/format";
import { useApi, useFilters } from "@/lib/hooks";
import type { PoliticiansResponse } from "@/lib/types";

const LIMIT = 24;

export default function PoliticiansPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading members…" />}>
      <PoliticiansView />
    </Suspense>
  );
}

function PoliticiansView() {
  const { get, set, setMany } = useFilters();
  const q = get("q");
  const party = get("party");
  const chamber = get("chamber");
  const sortBy = get("sort_by", "trades");
  const offset = Math.max(0, Number(get("offset", "0")) || 0);

  const path = `/api/politicians${qs({
    q,
    party,
    chamber,
    sort_by: sortBy,
    limit: LIMIT,
    offset,
  })}`;
  const { data, loading, error, reload } = useApi<PoliticiansResponse>(path);

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-kicker">Members</div>
          <h1 className="page-title">Politicians</h1>
          <p className="page-desc">House and Senate filers with volume, score, and mix.</p>
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
          placeholder="Search name"
          defaultValue={q}
          key={`q-${q}`}
          onKeyDown={(e) => {
            if (e.key === "Enter") set("q", (e.target as HTMLInputElement).value);
          }}
          onBlur={(e) => set("q", e.target.value)}
        />
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
        <select className="select" value={sortBy} onChange={(e) => set("sort_by", e.target.value)}>
          <option value="trades">Most trades</option>
          <option value="volume">Volume</option>
          <option value="score">Avg score</option>
        </select>
      </div>

      {loading && <LoadingState label="Loading members…" />}
      {error && !loading && <ErrorState message={error} onRetry={reload} />}
      {!loading && !error && data && data.politicians.length === 0 && (
        <EmptyState title="No politicians match" />
      )}
      {!loading && !error && data && data.politicians.length > 0 && (
        <>
          <div className="grid cards">
            {data.politicians.map((p) => (
              <Link key={p.name} href={politicianHref(p.name)} className="pcard">
                <div className="pcard-top">
                  <Avatar src={p.photo_url} name={p.name} party={p.party} />
                  <div className="grow ellipsis">
                    <div className="name">{p.name}</div>
                    <div className="sub">
                      <PartyPill party={p.party} /> {p.chamber || ""} {p.state_district || ""}
                    </div>
                  </div>
                </div>
                <div className="pcard-stats">
                  <div className="mini-stat">
                    <div className="k">Trades</div>
                    <div className="v">{formatNumber(p.trades)}</div>
                  </div>
                  <div className="mini-stat">
                    <div className="k">Volume</div>
                    <div className="v">{formatMoney(p.total_volume)}</div>
                  </div>
                  <div className="mini-stat">
                    <div className="k">Score</div>
                    <div className="v">{formatScore(p.avg_score)}</div>
                  </div>
                  <div className="mini-stat">
                    <div className="k">Buy / sell</div>
                    <div className="v">
                      <span className="buy">{p.buys}</span>
                      <span className="faint"> / </span>
                      <span className="sell">{p.sells}</span>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
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
