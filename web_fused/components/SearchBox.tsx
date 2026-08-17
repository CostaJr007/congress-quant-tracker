"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useDebounced } from "@/lib/hooks";
import { formatNumber, politicianHref, tickerHref } from "@/lib/format";
import type { SearchResponse } from "@/lib/types";
import { Avatar } from "./Avatar";
import { PartyPill } from "./PartyPill";

export function SearchBox() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const debounced = useDebounced(q.trim(), 260);

  useEffect(() => {
    if (debounced.length < 1) {
      setData(null);
      return;
    }
    let alive = true;
    setBusy(true);
    api
      .search(debounced)
      .then((res) => {
        if (alive) setData(res);
      })
      .catch(() => {
        if (alive) setData(null);
      })
      .finally(() => {
        if (alive) setBusy(false);
      });
    return () => {
      alive = false;
    };
  }, [debounced]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const pols = data?.politicians || [];
  const ticks = data?.tickers || [];
  const empty = Boolean(debounced) && !busy && pols.length === 0 && ticks.length === 0;
  const show = open && q.trim().length > 0;

  return (
    <div className="search-wrap" ref={wrap}>
      <svg className="search-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="11" cy="11" r="7" />
        <path d="M20 20l-3.5-3.5" />
      </svg>
      <input
        className="search-input"
        placeholder="Search members, tickers"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
          if (e.key === "Enter" && q.trim()) {
            setOpen(false);
            router.push(`/trades?q=${encodeURIComponent(q.trim())}`);
          }
        }}
      />
      {show && (
        <div className="search-pop">
          {busy && <div className="search-empty">Searching…</div>}
          {empty && <div className="search-empty">No matches for “{debounced}”</div>}
          {pols.length > 0 && (
            <div className="search-sec">
              <div className="search-label">Politicians</div>
              {pols.map((p) => (
                <button
                  key={p.name}
                  className="search-row"
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    setQ("");
                    router.push(politicianHref(p.name));
                  }}
                >
                  <Avatar src={p.photo_url} name={p.name} party={p.party} size="sm" />
                  <span className="ellipsis">{p.name}</span>
                  <PartyPill party={p.party} />
                  <span className="meta">{formatNumber(p.trades)}</span>
                </button>
              ))}
            </div>
          )}
          {ticks.length > 0 && (
            <div className="search-sec">
              <div className="search-label">Tickers</div>
              {ticks.map((t) => (
                <button
                  key={t.ticker}
                  className="search-row"
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    setQ("");
                    router.push(tickerHref(t.ticker));
                  }}
                >
                  <span className="ticker">{t.ticker}</span>
                  <span className="meta">{formatNumber(t.trades)} trades</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
