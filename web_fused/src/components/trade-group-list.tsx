"use client";

import { useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, FileText } from "lucide-react";
import TradeRow from "@/components/trade-row";
import PoliticianAvatar from "@/components/politician-avatar";
import {
  cn, formatCurrency, formatDateShort, partyColor, politicianHref, timeAgo,
} from "@/lib/utils";

export type TradeLike = Record<string, any>;

export type TradeGroup = {
  key: string;
  representative: string;
  party?: string;
  bioguide_id?: string;
  photo_url?: string;
  filing_date?: string;
  trades: TradeLike[];
  buys: number;
  sells: number;
  volume: number;
  tickers: string[];
};

/** Group by politician + filing (notification) date. */
export function groupTrades(
  trades: TradeLike[],
  minGroupSize = 3,
): { groups: TradeGroup[]; singles: TradeLike[] } {
  const map = new Map<string, TradeLike[]>();
  for (const t of trades) {
    const name = t.representative || t.name || "Unknown";
    const filed = t.notification_date || t.filing_date || "unknown";
    const key = `${name}||${filed}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(t);
  }

  const groups: TradeGroup[] = [];
  const singles: TradeLike[] = [];

  // Preserve first-seen order (already sorted by API)
  const order: string[] = [];
  for (const t of trades) {
    const name = t.representative || t.name || "Unknown";
    const filed = t.notification_date || t.filing_date || "unknown";
    const key = `${name}||${filed}`;
    if (!order.includes(key)) order.push(key);
  }

  for (const key of order) {
    const list = map.get(key) || [];
    if (list.length < minGroupSize) {
      singles.push(...list);
      continue;
    }
    const head = list[0];
    const tickers = Array.from(
      new Set(list.map((t) => t.ticker).filter(Boolean)),
    ) as string[];
    groups.push({
      key,
      representative: head.representative || head.name || "Unknown",
      party: head.party,
      bioguide_id: head.bioguide_id,
      photo_url: head.photo_url,
      filing_date: head.notification_date || head.filing_date,
      trades: list,
      buys: list.filter((t) => String(t.transaction_type || "").includes("Purchase") || t.transaction_type === "buy").length,
      sells: list.filter((t) => String(t.transaction_type || "").includes("Sale") || t.transaction_type === "sell").length,
      volume: list.reduce((s, t) => s + (t.amount_max || t.value_max || 0), 0),
      tickers,
    });
  }

  return { groups, singles };
}

/** Merge groups + singles back into chronological display order. */
function interleave(trades: TradeLike[], groups: TradeGroup[], singles: TradeLike[]) {
  const groupByKey = new Map(groups.map((g) => [g.key, g]));
  const singleIds = new Set(singles.map((t) => t.id ?? `${t.ticker}-${t.transaction_date}`));
  const seenGroups = new Set<string>();
  const items: Array<{ type: "group"; group: TradeGroup } | { type: "trade"; trade: TradeLike }> = [];

  for (const t of trades) {
    const name = t.representative || t.name || "Unknown";
    const filed = t.notification_date || t.filing_date || "unknown";
    const key = `${name}||${filed}`;
    if (groupByKey.has(key)) {
      if (!seenGroups.has(key)) {
        seenGroups.add(key);
        items.push({ type: "group", group: groupByKey.get(key)! });
      }
    } else {
      const id = t.id ?? `${t.ticker}-${t.transaction_date}`;
      if (singleIds.has(id) || singles.includes(t)) {
        items.push({ type: "trade", trade: t });
      }
    }
  }
  return items;
}

function GroupCard({
  group,
  defaultOpen = false,
}: {
  group: TradeGroup;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const tickerPreview = group.tickers.slice(0, 6).join(", ");
  const more = group.tickers.length > 6 ? ` +${group.tickers.length - 6}` : "";

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-2/40 transition-colors text-left"
      >
        <span className="text-fg-subtle shrink-0">
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </span>

        <PoliticianAvatar
          name={group.representative}
          party={group.party}
          bioguideId={group.bioguide_id}
          photoUrl={group.photo_url}
          size="sm"
          rounded="full"
        />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 min-w-0">
            <Link
              href={politicianHref(group.representative)}
              onClick={(e) => e.stopPropagation()}
              className="text-sm font-semibold text-fg hover:text-accent truncate"
            >
              {group.representative}
            </Link>
            {group.party && (
              <span className={cn("text-[10px] font-bold", partyColor(group.party))}>
                {group.party}
              </span>
            )}
            <span className="px-2 py-0.5 rounded-full bg-accent/10 text-accent text-[10px] font-semibold border border-accent/20 shrink-0">
              {group.trades.length} trades
            </span>
          </div>
          <div className="text-[11px] text-fg-subtle mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="inline-flex items-center gap-1">
              <FileText className="w-3 h-3" />
              filed {formatDateShort(group.filing_date || "")}
              {group.filing_date && (
                <span className="text-fg-subtle/80">· {timeAgo(group.filing_date)}</span>
              )}
            </span>
            <span>
              <span className="text-positive">{group.buys} buy</span>
              {" · "}
              <span className="text-negative">{group.sells} sell</span>
            </span>
            <span className="font-mono">{formatCurrency(group.volume)} vol</span>
          </div>
          <div className="text-[11px] text-fg-muted mt-0.5 truncate font-mono">
            {tickerPreview}{more}
          </div>
        </div>

        <div className="text-[11px] text-fg-subtle shrink-0 hidden sm:block">
          {open ? "Hide" : "Expand"}
        </div>
      </button>

      {open && (
        <div className="border-t border-border px-2 py-2 space-y-1.5 bg-background/40">
          {group.trades.map((t, i) => (
            <TradeRow
              key={t.id ?? `${t.ticker}-${t.transaction_date}-${i}`}
              trade={t}
              showPolitician={false}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Renders trades with automatic grouping when many share the same
 * politician + filing date (minGroupSize, default 3).
 */
export default function TradeGroupList({
  trades,
  minGroupSize = 3,
  empty,
}: {
  trades: TradeLike[];
  minGroupSize?: number;
  empty?: ReactNode;
}) {
  const { groups, singles } = useMemo(
    () => groupTrades(trades, minGroupSize),
    [trades, minGroupSize],
  );
  const items = useMemo(
    () => interleave(trades, groups, singles),
    [trades, groups, singles],
  );

  if (!trades.length) return <>{empty ?? null}</>;

  return (
    <div className="space-y-2">
      {items.map((item) =>
        item.type === "group" ? (
          <GroupCard key={item.group.key} group={item.group} />
        ) : (
          <TradeRow
            key={item.trade.id ?? `${item.trade.ticker}-${item.trade.transaction_date}`}
            trade={item.trade}
          />
        ),
      )}
    </div>
  );
}
