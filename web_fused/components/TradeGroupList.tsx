"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { Trade } from "@/lib/types";
import { formatMoney, formatNumber, politicianHref } from "@/lib/format";
import { Avatar } from "./Avatar";
import { PartyPill } from "./PartyPill";
import { TradeTable } from "./TradeTable";

interface Group {
  name: string;
  trades: Trade[];
  sample: Trade;
}

function groupTrades(trades: Trade[]): Group[] {
  const order: string[] = [];
  const map = new Map<string, Trade[]>();
  for (const t of trades) {
    const key = t.representative || "Unknown";
    if (!map.has(key)) {
      order.push(key);
      map.set(key, []);
    }
    map.get(key)!.push(t);
  }
  return order.map((name) => ({
    name,
    trades: map.get(name)!,
    sample: map.get(name)![0],
  }));
}

export function TradeGroupList({ trades }: { trades: Trade[] }) {
  const groups = useMemo(() => groupTrades(trades), [trades]);
  const shouldGroup = groups.some((g) => g.trades.length >= 2);

  if (!shouldGroup) {
    return (
      <div className="card" style={{ padding: 0 }}>
        <TradeTable trades={trades} />
      </div>
    );
  }

  return (
    <div>
      {groups.map((g) =>
        g.trades.length === 1 ? (
          <div className="card" key={g.name + g.trades[0].id} style={{ padding: 0, marginBottom: 8 }}>
            <TradeTable trades={g.trades} />
          </div>
        ) : (
          <MemberGroup key={g.name} group={g} />
        ),
      )}
    </div>
  );
}

function MemberGroup({ group }: { group: Group }) {
  const heavy = group.trades.length >= 4;
  const [open, setOpen] = useState(!heavy);
  const volume = group.trades.reduce((s, t) => s + (t.amount_max || t.amount_min || 0), 0);
  const alerts = group.trades.filter((t) => t.tag === "high_alert" || t.tag === "suspicious").length;
  const sample = group.sample;

  return (
    <div className={`group ${heavy ? "heavy" : ""}`}>
      <button className="group-head" type="button" onClick={() => setOpen((v) => !v)}>
        <span className="chev">{open ? "▾" : "▸"}</span>
        <Avatar src={sample.photo_url} name={group.name} party={sample.party} />
        <div className="grow ellipsis">
          {group.name !== "Unknown" ? (
            <Link className="name" href={politicianHref(group.name)} onClick={(e) => e.stopPropagation()}>
              {group.name}
            </Link>
          ) : (
            <span className="name">Unknown</span>
          )}
          <div className="sub">
            <PartyPill party={sample.party} /> {sample.chamber || ""} {sample.state_district || ""}
          </div>
        </div>
        <div className="right hide-sm">
          <div className="num">{formatNumber(group.trades.length)} trades</div>
          <div className="sub">{formatMoney(volume)}</div>
        </div>
        {alerts > 0 && (
          <span className="tag suspicious">
            {alerts} flagged
          </span>
        )}
      </button>
      {open && (
        <div className="group-body">
          <TradeTable trades={group.trades} showMember={false} />
        </div>
      )}
    </div>
  );
}
