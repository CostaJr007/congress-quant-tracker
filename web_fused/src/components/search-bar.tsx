"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, Users, TrendingUp, X } from "lucide-react";
import { fetchSearch } from "@/lib/api";
import { politicianHref, partyColor } from "@/lib/utils";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<{ politicians: any[]; tickers: any[] }>({
    politicians: [],
    tickers: [],
  });
  const boxRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (!query.trim()) {
      setResults({ politicians: [], tickers: [] });
      setOpen(false);
      return;
    }
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      fetchSearch(query.trim(), ctrl.signal)
        .then((r) => {
          setResults(r);
          setOpen(true);
        })
        .catch(() => {})
        .finally(() => setLoading(false));
    }, 250);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [query]);

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, []);

  function go(href: string) {
    setOpen(false);
    setQuery("");
    router.push(href);
  }

  const total = results.politicians.length + results.tickers.length;

  return (
    <div ref={boxRef} className="relative w-full max-w-md">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fg-subtle" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => query.trim() && setOpen(true)}
          placeholder="Search politicians or tickers…"
          className="w-full bg-surface-2/70 border border-border rounded-lg pl-9 pr-8 py-2 text-sm text-fg placeholder:text-fg-subtle focus:outline-none focus:border-accent/50 focus:bg-surface-2 transition-colors"
        />
        {query && (
          <button
            onClick={() => setQuery("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-fg-subtle hover:text-fg"
            aria-label="Clear search"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {open && (
        <div className="absolute z-50 mt-2 w-full rounded-xl bg-card border border-border shadow-xl shadow-black/40 overflow-hidden">
          {loading && (
            <div className="p-4 text-sm text-fg-muted flex items-center gap-2">
              <span className="w-3 h-3 rounded-full border-2 border-fg-subtle border-t-accent animate-spin" />
              Searching…
            </div>
          )}

          {!loading && total === 0 && (
            <div className="p-4 text-sm text-fg-muted">
              No results for &ldquo;{query}&rdquo;
            </div>
          )}

          {!loading && results.politicians.length > 0 && (
            <div>
              <div className="px-3 pt-3 pb-1 text-[10px] uppercase tracking-wider text-fg-subtle flex items-center gap-1.5">
                <Users className="w-3 h-3" /> Politicians
              </div>
              {results.politicians.map((p) => (
                <button
                  key={p.name}
                  onClick={() => go(politicianHref(p.name))}
                  className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-surface-2 transition-colors"
                >
                  <span className="text-xs text-fg-muted">#{p.trades} trades</span>
                  <span className="text-sm text-fg">{p.name}</span>
                  <span className={`text-xs ml-auto ${partyColor(p.party)}`}>{p.party}</span>
                </button>
              ))}
            </div>
          )}

          {!loading && results.tickers.length > 0 && (
            <div className="border-t border-border">
              <div className="px-3 pt-3 pb-1 text-[10px] uppercase tracking-wider text-fg-subtle flex items-center gap-1.5">
                <TrendingUp className="w-3 h-3" /> Assets
              </div>
              {results.tickers.map((t) => (
                <button
                  key={t.ticker}
                  onClick={() => go(`/stocks/${t.ticker}`)}
                  className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-surface-2 transition-colors"
                >
                  <span className="text-sm font-mono text-accent">{t.ticker}</span>
                  <span className="text-xs text-fg-muted truncate">{t.name}</span>
                  <span className="text-xs text-fg-muted ml-auto">#{t.trades}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}