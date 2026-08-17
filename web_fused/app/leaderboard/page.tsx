"use client";

import Link from "next/link";
import { Suspense } from "react";
import { Avatar } from "@/components/Avatar";
import { PartyPill } from "@/components/PartyPill";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { formatMoney, formatNumber, formatScore, politicianHref, qs } from "@/lib/format";
import { useApi, useFilters } from "@/lib/hooks";
import type { LeaderboardResponse } from "@/lib/types";

export default function LeaderboardPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading leaderboard…" />}>
      <LeaderboardView />
    </Suspense>
  );
}

function LeaderboardView() {
  const { get, set } = useFilters();
  const metric = get("metric", "score");
  const path = `/api/leaderboard${qs({ metric, limit: 50 })}`;
  const { data, loading, error, reload } = useApi<LeaderboardResponse>(path);

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-kicker">Ranks</div>
          <h1 className="page-title">Leaderboard</h1>
          <p className="page-desc">Members ranked by score, volume, or trade count (min. 3 trades).</p>
        </div>
        <div className="tabs">
          {(["score", "volume", "trades"] as const).map((m) => (
            <button
              key={m}
              type="button"
              className={`tab ${metric === m ? "on" : ""}`}
              onClick={() => set("metric", m)}
            >
              {m === "score" ? "Score" : m === "volume" ? "Volume" : "Trades"}
            </button>
          ))}
        </div>
      </header>

      {loading && <LoadingState label="Loading leaderboard…" />}
      {error && !loading && <ErrorState message={error} onRetry={reload} />}
      {!loading && !error && data && data.leaderboard.length === 0 && (
        <EmptyState title="No rankings yet" />
      )}
      {!loading && !error && data && data.leaderboard.length > 0 && (
        <div className="card" style={{ padding: "6px 10px" }}>
          {data.leaderboard.map((row) => {
            const rankCls =
              row.rank === 1 ? "gold" : row.rank === 2 ? "silver" : row.rank === 3 ? "bronze" : "";
            return (
              <Link key={row.name} href={politicianHref(row.name)} className="list-row">
                <span className={`rank ${rankCls}`}>{row.rank}</span>
                <Avatar src={row.photo_url} name={row.name} party={row.party} />
                <div className="grow ellipsis">
                  <div className="name">{row.name}</div>
                  <div className="sub">
                    <PartyPill party={row.party} /> {row.chamber || ""} {row.state_district || ""}
                  </div>
                </div>
                <div className="right hide-sm">
                  <div className="num">{formatNumber(row.trades)} trades</div>
                  <div className="sub">{formatMoney(row.total_volume)}</div>
                </div>
                <div className="right" style={{ minWidth: 64 }}>
                  <div className="num accent">{formatScore(row.avg_score)}</div>
                  <div className="sub">score</div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </>
  );
}
