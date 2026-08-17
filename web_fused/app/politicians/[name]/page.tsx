"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ActivityChart } from "@/components/ActivityChart";
import { Avatar } from "@/components/Avatar";
import { PartyPill } from "@/components/PartyPill";
import { StatCard } from "@/components/StatCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { TagBadge } from "@/components/TagBadge";
import { TradeTable } from "@/components/TradeTable";
import {
  formatMoney,
  formatNumber,
  formatScore,
  politicianNameFromSlug,
  tickerHref,
} from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { MonthActivity, PoliticianDetail } from "@/lib/types";

export default function PoliticianDetailPage() {
  const params = useParams();
  const slug = String(params.name || "");
  const name = politicianNameFromSlug(slug);
  const { data, loading, error, reload } = useApi<PoliticianDetail>(
    name ? `/api/politicians/${encodeURIComponent(name)}` : null,
  );

  if (loading) return <LoadingState label="Loading member…" />;
  if (error || !data) return <ErrorState message={error} onRetry={reload} />;

  const trend: MonthActivity[] = (data.score_trend || []).map((m) => ({
    month: m.month,
    count: m.count ?? (m.buys || 0) + (m.sells || 0),
    buys: m.buys || 0,
    sells: m.sells || 0,
    volume: 0,
  }));

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-kicker">Member</div>
          <h1 className="page-title">{data.name}</h1>
        </div>
      </header>

      <div className="card hero">
        <Avatar src={data.photo_url} name={data.name} party={data.party} size="lg" />
        <div className="grow">
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <PartyPill party={data.party} />
            <span className="dim">
              {data.chamber || ""} {data.state_district || ""}
            </span>
          </div>
          {data.committees?.length > 0 && (
            <div className="pills" style={{ marginTop: 10 }}>
              {data.committees.map((c) => (
                <span className="pill" key={c}>
                  {c}
                </span>
              ))}
            </div>
          )}
          <div className="pills" style={{ marginTop: 10 }}>
            <span className="pill">
              <TagBadge tag="high_alert" /> {data.high_alert}
            </span>
            <span className="pill">
              <TagBadge tag="suspicious" /> {data.suspicious}
            </span>
            <span className="pill">
              <TagBadge tag="noteworthy" /> {data.noteworthy}
            </span>
          </div>
        </div>
      </div>

      <div className="grid stats section" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
        <StatCard label="Trades" value={formatNumber(data.total_trades ?? data.trades)} />
        <StatCard label="Volume" value={formatMoney(data.total_volume)} accent />
        <StatCard label="Avg score" value={formatScore(data.avg_score)} />
        <StatCard
          label="Buy / sell"
          value={`${data.buys ?? data.buy_count}/${data.sells ?? data.sell_count}`}
          sub={`${formatNumber(data.unique_assets)} assets`}
        />
      </div>

      <div className="grid two-col section">
        <div className="card">
          <div className="section-head">
            <h2 className="section-title">Activity</h2>
          </div>
          {trend.length ? <ActivityChart months={trend} /> : <EmptyState title="No monthly trend" />}
        </div>
        <div className="card">
          <div className="section-head">
            <h2 className="section-title">Top assets</h2>
          </div>
          {(data.top_assets || []).length === 0 && <EmptyState title="No assets" />}
          {(data.top_assets || []).map((a) => (
            <Link key={a.ticker} href={tickerHref(a.ticker)} className="list-row">
              <div className="grow ellipsis">
                <div className="ticker">{a.ticker}</div>
                <div className="sub ellipsis">{a.name}</div>
              </div>
              <div className="right">
                <div className="num">{formatNumber(a.trades)}</div>
                <div className="sub">{formatMoney(a.volume)}</div>
              </div>
            </Link>
          ))}
        </div>
      </div>

      <section className="section">
        <div className="section-head">
          <h2 className="section-title">Trades</h2>
        </div>
        {data.recent_trades?.length ? (
          <div className="card" style={{ padding: 0 }}>
            <TradeTable trades={data.recent_trades} showMember={false} />
          </div>
        ) : (
          <EmptyState title="No trades on file" />
        )}
      </section>
    </>
  );
}
