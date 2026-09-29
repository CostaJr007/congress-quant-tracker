import Link from "next/link";
import type { Trade } from "@/lib/types";
import {
  assetTypeLabel,
  formatDate,
  formatRange,
  formatScore,
  isBuy,
  isExchange,
  politicianHref,
  sideLabel,
  tickerHref,
} from "@/lib/format";
import { Avatar } from "./Avatar";
import { PartyPill } from "./PartyPill";
import { TagBadge } from "./TagBadge";

function lagLabel(t: Trade): string | null {
  if (t.lag_days == null) return null;
  if (t.lag_days <= 45) return null;
  return `filed +${t.lag_days}d late`;
}

export function TradeTable({
  trades,
  showMember = true,
}: {
  trades: Trade[];
  showMember?: boolean;
}) {
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            {showMember && <th>Member</th>}
            <th>Ticker</th>
            <th>Side</th>
            <th>Amount</th>
            <th className="hide-sm">Traded</th>
            <th className="hide-sm">Filed</th>
            <th>Score</th>
            <th>Tag</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <TradeRow key={t.id} trade={t} showMember={showMember} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TradeRow({
  trade: t,
  showMember = true,
}: {
  trade: Trade;
  showMember?: boolean;
}) {
  const buy = isBuy(t.transaction_type);
  return (
    <tr>
      {showMember && (
        <td>
          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 180 }}>
            <Avatar src={t.photo_url} name={t.representative} party={t.party} size="sm" />
            <div className="grow ellipsis">
              {t.representative ? (
                <Link className="name" href={politicianHref(t.representative)}>
                  {t.representative}
                </Link>
              ) : (
                <span className="name">Unknown</span>
              )}
              <div className="sub">
                <PartyPill party={t.party} /> {t.chamber || ""} {t.state_district || ""}
              </div>
            </div>
          </div>
        </td>
      )}
      <td>
        {t.ticker ? (
          <Link className="ticker" href={tickerHref(t.ticker)}>
            {t.ticker}
          </Link>
        ) : (
          <span className="dim">—</span>
        )}
        {t.asset && t.asset !== t.ticker && (
          <div className="sub ellipsis" style={{ maxWidth: 180 }} title={t.asset}>
            {t.asset}
          </div>
        )}
        {(assetTypeLabel(t.asset_type) || t.owner) && (
          <div className="sub ellipsis" style={{ maxWidth: 180 }}>
            {[assetTypeLabel(t.asset_type), t.owner].filter(Boolean).join(" · ")}
          </div>
        )}
        {(t.strike != null || t.expiration_date) && (
          <div className="sub ellipsis" style={{ maxWidth: 180 }}>
            {t.strike != null ? `$${t.strike}` : "strike ?"}
            {t.expiration_date ? ` exp ${t.expiration_date}` : ""}
          </div>
        )}
      </td>
      <td>
        <span className={`side ${isExchange(t.transaction_type) ? "exch" : buy ? "buy" : "sell"}`}>{sideLabel(t.transaction_type)}</span>
      </td>
      <td className="num">{formatRange(t.amount_min, t.amount_max, t.amount)}</td>
      <td className="hide-sm num">{formatDate(t.transaction_date)}</td>
      <td className="hide-sm num" title={lagLabel(t) || undefined}>
        {formatDate(t.notification_date)}
        {lagLabel(t) && <div className="sub" style={{ color: "var(--warn, #b45309)" }}>{lagLabel(t)}</div>}
      </td>
      <td className="num">
        <span className="score-bar" title={t.reason || undefined}>
          <i style={{ width: `${Math.min(100, Math.max(0, t.score || 0))}%` }} />
        </span>
        {formatScore(t.score)}
      </td>
      <td>
        <TagBadge tag={t.tag} />
      </td>
    </tr>
  );
}
