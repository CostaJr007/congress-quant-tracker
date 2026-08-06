"use client";

import Link from "next/link";
import {
  cn, scoreBadge, tagStyle, tagLabel, formatDateShort, timeAgo, formatCurrency, partyColor,
} from "@/lib/utils";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import MiniSparkline from "@/components/mini-sparkline";
import PoliticianAvatar from "@/components/politician-avatar";

interface TradeRowProps {
  trade: Record<string, any>;
  showPolitician?: boolean;
}

function OwnerBadge({ owner }: { owner?: string }) {
  const map: Record<string, string> = { SP: "Spouse", JT: "Joint", DC: "Dependent" };
  if (!owner) return null;
  return (
    <span className="px-1.5 py-0.5 rounded bg-surface-2 text-[10px] text-fg-muted border border-border">
      {map[owner] || owner}
    </span>
  );
}

function AssetTypeBadge({ assetType }: { assetType?: string }) {
  if (assetType === "option_call")
    return <span className="px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 text-[10px] font-semibold border border-violet-500/20">CALL</span>;
  if (assetType === "option_put")
    return <span className="px-1.5 py-0.5 rounded bg-fuchsia-500/10 text-fuchsia-400 text-[10px] font-semibold border border-fuchsia-500/20">PUT</span>;
  if (assetType === "crypto")
    return <span className="px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 text-[10px] font-semibold border border-orange-500/20">CRYPTO</span>;
  if (assetType === "bond")
    return <span className="px-1.5 py-0.5 rounded bg-teal-500/10 text-teal-400 text-[10px] font-semibold border border-teal-500/20">BOND</span>;
  return null;
}

function MarketBlock({ trade }: { trade: Record<string, any> }) {
  const m = trade.market;
  const pct = m?.change_pct ?? trade.price_change_pct;
  const priceNow = m?.price_now ?? trade.current_price;
  const priceThen = m?.price_at_trade;
  const shares = m?.shares?.shares_est ?? trade.shares_est;
  const pnl = m?.pnl_mid_est ?? trade.pnl_mid_est;
  const chart = m?.chart || [];

  const up = pct != null && pct > 0;
  const down = pct != null && pct < 0;

  if (pct == null && !priceNow) {
    return (
      <div className="hidden sm:flex flex-col items-end shrink-0 min-w-[4.5rem] text-[10px] text-fg-subtle">
        <span className="font-mono text-fg-muted">—</span>
        <span>no quote</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 shrink-0">
      <div className="hidden md:block">
        <MiniSparkline points={chart} positive={up ? true : down ? false : undefined} />
      </div>
      <div className="text-right min-w-[4.5rem]">
        <div
          className={cn(
            "text-sm font-semibold font-mono",
            up && "text-positive",
            down && "text-negative",
            !up && !down && "text-fg-muted",
          )}
          title={
            priceThen != null && priceNow != null
              ? `At trade: $${Number(priceThen).toFixed(2)} → Now: $${Number(priceNow).toFixed(2)}`
              : undefined
          }
        >
          {pct != null ? `${pct > 0 ? "+" : ""}${Number(pct).toFixed(1)}%` : "—"}
        </div>
        <div className="text-[10px] text-fg-subtle whitespace-nowrap">
          {priceNow != null ? `$${Number(priceNow).toFixed(2)}` : "—"}
          {shares != null ? ` · ~${Number(shares).toLocaleString(undefined, { maximumFractionDigits: 0 })} sh` : ""}
        </div>
        {pnl != null && (
          <div
            className={cn(
              "text-[10px] font-medium",
              pnl > 0 ? "text-positive" : pnl < 0 ? "text-negative" : "text-fg-subtle",
            )}
            title="Estimated P&L on range midpoint (not actual)"
          >
            est {pnl >= 0 ? "+" : ""}{formatCurrency(pnl)}
          </div>
        )}
      </div>
    </div>
  );
}

export default function TradeRow({ trade, showPolitician = true }: TradeRowProps) {
  const isBuy = trade.transaction_type?.includes("Purchase");
  const action = isBuy ? "BUY" : "SELL";
  const score = trade.score || 0;
  const amount = trade.amount_max
    ? formatCurrency(trade.amount_max)
    : trade.amount?.split(" - ")[1] || trade.amount || "—";
  const delay = (() => {
    if (trade.transaction_date && trade.notification_date) {
      const a = new Date(trade.transaction_date).getTime();
      const b = new Date(trade.notification_date).getTime();
      if (!isNaN(a) && !isNaN(b)) return Math.round((b - a) / 86400000);
    }
    return null;
  })();
  const delayed = delay != null && delay >= 45;

  return (
    <div className={cn(
      "flex items-center gap-3 px-4 py-3 rounded-xl border transition-colors hover:bg-surface-2/40",
      score >= 76 ? "border-red-500/20" : score >= 51 ? "border-orange-500/20" : score >= 26 ? "border-blue-500/20" : "border-border",
    )}>
      <div className={cn(
        "w-14 shrink-0 flex flex-col items-center gap-0.5 px-2 py-1 rounded-lg text-[10px] font-bold uppercase",
        isBuy ? "bg-positive/10 text-positive" : "bg-negative/10 text-negative",
      )}>
        {isBuy ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
        {action}
      </div>

      <div className="flex-1 min-w-0">
        {showPolitician && (
          <div className="flex items-center gap-2 min-w-0">
            <PoliticianAvatar
              name={trade.representative}
              party={trade.party}
              bioguideId={trade.bioguide_id || trade.bioguideId}
              photoUrl={trade.photo_url || trade.photoUrl}
              size="sm"
              rounded="full"
              className="shrink-0"
            />
            <Link
              href={`/politicians/${encodeURIComponent((trade.representative || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""))}`}
              className="text-sm font-medium text-fg hover:text-accent truncate"
            >
              {trade.representative}
            </Link>
            {trade.party && <span className={cn("text-[10px] font-semibold", partyColor(trade.party))}>{trade.party}</span>}
            <OwnerBadge owner={trade.owner} />
          </div>
        )}

        <div className="flex items-center gap-2 mt-0.5 min-w-0">
          {trade.ticker ? (
            <Link href={`/stocks/${trade.ticker}`} className="text-xs font-mono font-semibold text-accent hover:underline shrink-0">
              {trade.ticker}
            </Link>
          ) : <span className="text-xs font-mono font-semibold text-fg-subtle shrink-0">—</span>}
          <AssetTypeBadge assetType={trade.asset_type} />
          <span className="text-xs text-fg-muted truncate">{trade.asset}</span>
          {trade.sector && <span className="text-[10px] text-fg-subtle hidden md:inline shrink-0">{trade.sector}</span>}
        </div>
        {trade.reason && ["high_alert", "suspicious"].includes(trade.tag) && (
          <div className="text-[11px] text-fg-subtle mt-1 truncate max-w-md" title={trade.reason}>
            {trade.reason}
          </div>
        )}
      </div>

      <div className="hidden md:block text-right shrink-0">
        <div className="text-sm font-semibold text-fg whitespace-nowrap">{amount}</div>
        <div className="text-[11px] text-fg-subtle">est. value</div>
      </div>

      {/* Performance since trade */}
      <MarketBlock trade={trade} />

      {/* Trade date */}
      <div className="hidden lg:block text-right shrink-0 w-20">
        <div
          className="text-xs text-fg-muted whitespace-nowrap"
          title={`Trade date: ${trade.transaction_date || "—"}`}
        >
          {formatDateShort(trade.transaction_date)}
        </div>
        <div className="text-[10px] text-fg-subtle">traded</div>
      </div>

      {/* Disclosure date */}
      <div className="hidden md:block text-right shrink-0 w-20">
        <div
          className="text-xs text-fg whitespace-nowrap"
          title={`Disclosed: ${trade.notification_date || "—"}`}
        >
          {formatDateShort(trade.notification_date) || "—"}
        </div>
        <div
          className={cn("text-[10px] text-fg-subtle", delayed && "text-orange-400")}
          title={delay != null ? `${delay} days from trade to filing` : ""}
        >
          {delay != null ? (delayed ? `filed · ${delay}d late` : `filed · ${delay}d`) : "filed"}
        </div>
      </div>

      {trade.tag && trade.tag !== "routine" ? (
        <span className={cn("shrink-0 px-2 py-0.5 rounded text-[10px] font-semibold border", tagStyle(trade.tag))}>
          {tagLabel(trade.tag)}
        </span>
      ) : (
        <span
          className="shrink-0 w-14 text-right text-[11px] text-fg-subtle"
          title={trade.notification_date || trade.transaction_date}
        >
          {timeAgo(trade.notification_date || trade.transaction_date)}
        </span>
      )}

      {score > 0 && (
        <div className={cn("shrink-0 w-11 text-right px-1.5 py-0.5 rounded-md border text-sm font-bold", scoreBadge(score))}>
          {score}
        </div>
      )}
    </div>
  );
}
