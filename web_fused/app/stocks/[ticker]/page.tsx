"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ActivityChart } from "@/components/ActivityChart";
import { PartyPill } from "@/components/PartyPill";
import { StatCard } from "@/components/StatCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { TradeTable } from "@/components/TradeTable";
import { formatMoney, formatNumber, formatScore, politicianHref } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { MonthActivity, StockDetail } from "@/lib/types";

export default function StockDetailPage() {
  const params = useParams();
  const ticker = String(params.ticker || "").toUpperCase();
  const { data, loading, error, reload } = useApi<StockDetail>(
    ticker ? `/api/stocks/${encodeURIComponent(ticker)}` : null,
  );

  if (loading) return <LoadingState label="Loading ticker…" />;
  if (error || !data) return <ErrorState message={error} onRetry={reload} />;

  const trend: MonthActivity[] = (data.volume_trend || []).map((m) => ({
    month: m.month,
    count: m.count,
    buys: m.buys,
    sells: m.sells,
    volume: m.volume,
  }));

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-kicker">Ticker</div>
          <h1 className="page-title">
            <span className="accent">{data.ticker}</span>
          </h1>
          <p className="page-desc">
            {data.name}
            {data.sector ? ` · ${data.sector}` : ""}
            {data.industry ? ` · ${data.industry}` : ""}
          </p>
        </div>
      </header>

      <div className="grid stats" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
        <StatCard label="Trades" value={formatNumber(data.total_trades ?? data.trades)} />
        <StatCard label="Volume" value={formatMoney(data.total_volume)} accent />
        <StatCard label="Members" value={formatNumber(data.unique_politicians)} />
        <StatCard
          label="Avg score"
          value={formatScore(data.avg_score)}
          sub={`${data.buy_count} buy / ${data.sell_count} sell`}
        />
      </div>

      <div className="grid two-col section">
        <div className="card">
          <div className="section-head">
            <h2 className="section-title">Volume trend</h2>
          </div>
          {trend.length ? <ActivityChart months={trend} /> : <EmptyState title="No monthly trend" />}
        </div>
        <div className="card">
          <div className="section-head">
            <h2 className="section-title">Holders</h2>
          </div>
          {(data.politicians || []).length === 0 && <EmptyState title="No holders" />}
          {(data.politicians || []).map((p) => (
            <Link key={p.name} href={politicianHref(p.name)} className="list-row">
              <div className="grow ellipsis">
                <div className="name">{p.name}</div>
                <div className="sub">
                  <PartyPill party={p.party} />
                </div>
              </div>
              <div className="right">
                <div className="num">{formatNumber(p.trades)}</div>
                <div className="sub">{formatMoney(p.volume)}</div>
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
            <TradeTable trades={data.recent_trades} />
          </div>
        ) : (
          <EmptyState title="No trades on file" />
        )}
      </section>
    </>
  );
}
