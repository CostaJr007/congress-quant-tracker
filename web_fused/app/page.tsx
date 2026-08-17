"use client";

import Link from "next/link";
import { ActivityChart, PartySplit } from "@/components/ActivityChart";
import { Avatar } from "@/components/Avatar";
import { PartyPill } from "@/components/PartyPill";
import { StatCard } from "@/components/StatCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { TagBadge } from "@/components/TagBadge";
import { TradeTable } from "@/components/TradeTable";
import { formatDate, formatMoney, formatNumber, formatScore, politicianHref, tickerHref } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Dashboard } from "@/lib/types";

export default function DashboardPage() {
  const { data, loading, error, reload } = useApi<Dashboard>("/api/dashboard");

  if (loading) return <LoadingState label="Loading dashboard…" />;
  if (error || !data) return <ErrorState message={error} onRetry={reload} />;

  const dist = data.signal_distribution || {};
  const range = data.data_range || { min_date: null, max_date: null };

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-kicker">CongressInvests</div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-desc">House and Senate disclosures, scored and tagged.</p>
        </div>
        <div className="page-meta">
          {data.data_age_days != null && (
            <span className="chip">
              Age <strong>{data.data_age_days}d</strong>
            </span>
          )}
          {range.min_date && (
            <span className="chip">
              Range{" "}
              <strong>
                {formatDate(range.min_date)} – {formatDate(range.max_date)}
              </strong>
            </span>
          )}
          {data.last_update?.completed_at && (
            <span className="chip">
              Updated <strong>{formatDate(data.last_update.completed_at)}</strong>
            </span>
          )}
        </div>
      </header>

      <div className="grid stats">
        <StatCard
          label="Trades"
          value={formatNumber(data.total_trades)}
          delta={data.deltas?.trades}
        />
        <StatCard
          label="Volume"
          value={formatMoney(data.total_volume)}
          delta={data.deltas?.volume}
          accent
        />
        <StatCard label="Members" value={formatNumber(data.unique_politicians)} />
        <StatCard label="Assets" value={formatNumber(data.unique_assets)} />
        <StatCard label="Avg score" value={formatScore(data.avg_score)} />
        <StatCard
          label="High alerts"
          value={formatNumber(data.high_alert_count)}
          sub={`${formatNumber(data.suspicious_count)} suspicious`}
        />
      </div>

      <div className="grid two-col section">
        <div className="card">
          <div className="section-head">
            <h2 className="section-title">Activity · 12 months</h2>
          </div>
          {data.activity_by_month?.length ? (
            <ActivityChart months={data.activity_by_month} />
          ) : (
            <EmptyState title="No monthly activity" />
          )}
        </div>
        <div className="card">
          <div className="section-head">
            <h2 className="section-title">Mix</h2>
          </div>
          <div className="kv">
            <div className="kv-row">
              <span>Buys</span>
              <strong className="buy num">{formatNumber(data.buy_count)}</strong>
            </div>
            <div className="kv-row">
              <span>Sells</span>
              <strong className="sell num">{formatNumber(data.sell_count)}</strong>
            </div>
          </div>
          <div style={{ margin: "16px 0 10px" }} className="stat-label">
            Party
          </div>
          <PartySplit split={data.party_split || {}} />
          <div style={{ margin: "16px 0 10px" }} className="stat-label">
            Signals
          </div>
          <div className="pills">
            <span className="pill">
              <TagBadge tag="noteworthy" /> {formatNumber(dist.noteworthy ?? data.noteworthy_count)}
            </span>
            <span className="pill">
              <TagBadge tag="suspicious" /> {formatNumber(dist.suspicious ?? data.suspicious_count)}
            </span>
            <span className="pill">
              <TagBadge tag="high_alert" /> {formatNumber(dist.high_alert ?? data.high_alert_count)}
            </span>
            <span className="pill">
              <TagBadge tag="routine" /> {formatNumber(dist.routine)}
            </span>
          </div>
        </div>
      </div>

      <div className="grid two-col section">
        <div className="card">
          <div className="section-head">
            <h2 className="section-title">Top politicians</h2>
            <Link className="section-link" href="/politicians">
              All
            </Link>
          </div>
          {(data.top_politicians || []).map((p) => (
            <Link key={p.name} href={politicianHref(p.name)} className="list-row">
              <Avatar src={p.photo_url} name={p.name} party={p.party} />
              <div className="grow ellipsis">
                <div className="name">{p.name}</div>
                <div className="sub">
                  <PartyPill party={p.party} /> {p.chamber || ""}
                </div>
              </div>
              <div className="right">
                <div className="num">{formatNumber(p.trades)}</div>
                <div className="sub">{formatMoney(p.total_volume)}</div>
              </div>
            </Link>
          ))}
        </div>
        <div className="card">
          <div className="section-head">
            <h2 className="section-title">Top tickers</h2>
            <Link className="section-link" href="/stocks">
              All
            </Link>
          </div>
          {(data.top_tickers || []).map((t) => (
            <Link key={t.ticker} href={tickerHref(t.ticker)} className="list-row">
              <div className="grow ellipsis">
                <div className="ticker">{t.ticker}</div>
                <div className="sub ellipsis">{t.name}</div>
              </div>
              <div className="right">
                <div className="num">{formatNumber(t.trades)}</div>
                <div className="sub">{formatMoney(t.total_volume)}</div>
              </div>
            </Link>
          ))}
        </div>
      </div>

      <section className="section">
        <div className="section-head">
          <h2 className="section-title">Recent trades</h2>
          <Link className="section-link" href="/trades">
            All trades
          </Link>
        </div>
        {data.recent_trades?.length ? (
          <div className="card" style={{ padding: 0 }}>
            <TradeTable trades={data.recent_trades} />
          </div>
        ) : (
          <EmptyState title="No recent trades" />
        )}
      </section>
    </>
  );
}
