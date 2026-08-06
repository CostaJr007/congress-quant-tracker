"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { fetchPoliticians, fetchMeta, ApiError } from "@/lib/api";
import {
  politicianHref, formatCurrency, partyColor, scoreColor, cn,
} from "@/lib/utils";
import { EmptyState, ErrorState } from "@/components/states";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import PoliticianAvatar from "@/components/politician-avatar";

const PARTIES = [
  { value: "", label: "All", color: "" },
  { value: "D", label: "Democrat", color: "text-blue-400" },
  { value: "R", label: "Republican", color: "text-red-400" },
  { value: "I", label: "Independent", color: "text-fg-muted" },
];

export default function PoliticiansPage() {
  const [data, setData] = useState<Record<string, any>>({});
  const [meta, setMeta] = useState<{ states: string[] }>({ states: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const debouncedQ = useDebouncedValue(q, 300);
  const [party, setParty] = useState("");
  const [chamber, setChamber] = useState("");
  const [state, setState] = useState("");
  const [sortBy, setSortBy] = useState("trades");
  const [offset, setOffset] = useState(0);
  const LIMIT = 24;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {
        limit: String(LIMIT), offset: String(offset), sort_by: sortBy,
      };
      if (debouncedQ) params.q = debouncedQ;
      if (party) params.party = party;
      if (chamber) params.chamber = chamber;
      if (state) params.state = state;
      setData(await fetchPoliticians(params));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Backend offline");
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, party, chamber, state, sortBy, offset]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setOffset(0); }, [debouncedQ, party, chamber, state, sortBy]);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchMeta(ctrl.signal).then(setMeta).catch(() => {});
    return () => ctrl.abort();
  }, []);

  const hasFilters = Boolean(debouncedQ || party || chamber || state);
  const total = data.total ?? 0;
  const politicians = data.politicians || [];

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-fg mb-1">Politicians</h1>
          <p className="text-fg-muted text-sm">{total.toLocaleString()} members tracked</p>
        </div>

        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by name…"
          className="bg-surface-2/70 border border-border rounded-lg px-3 py-2 text-sm text-fg placeholder:text-fg-subtle focus:outline-none focus:border-accent/50 w-56"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        <div className="flex gap-1.5 mr-2">
          {PARTIES.map((p) => (
            <button
              key={p.value}
              onClick={() => setParty(p.value)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors border",
                party === p.value
                  ? "bg-surface-2 text-fg border-border"
                  : "bg-transparent text-fg-muted hover:text-fg border-transparent",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>

        <select
          value={chamber}
          onChange={(e) => setChamber(e.target.value)}
          className="bg-surface-2/70 border border-border rounded-lg px-3 py-1.5 text-xs text-fg focus:outline-none focus:border-accent/50"
        >
          <option value="">All Chambers</option>
          <option value="House">House</option>
          <option value="Senate">Senate</option>
        </select>

        <select
          value={state}
          onChange={(e) => setState(e.target.value)}
          className="bg-surface-2/70 border border-border rounded-lg px-3 py-1.5 text-xs text-fg focus:outline-none focus:border-accent/50"
        >
          <option value="">All States</option>
          {meta.states.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        <div className="ml-auto flex items-center gap-1.5 text-xs">
          <span className="text-fg-subtle">Sort</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-surface-2/70 border border-border rounded-lg px-3 py-1.5 text-xs text-fg focus:outline-none focus:border-accent/50"
          >
            <option value="trades">Most trades</option>
            <option value="volume">Most volume</option>
            <option value="score">Highest score</option>
          </select>
        </div>

        {hasFilters && (
          <button
            onClick={() => { setQ(""); setParty(""); setChamber(""); setState(""); }}
            className="px-3 py-1.5 rounded-lg text-xs text-fg-subtle hover:text-fg"
          >
            Clear
          </button>
        )}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {[...Array(12)].map((_, i) => (
            <div key={i} className="h-48 rounded-2xl bg-card border border-border animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : politicians.length === 0 ? (
        <EmptyState title="No politicians match your filters" />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {politicians.map((p: any) => <PoliticianCard key={p.name} p={p} />)}
          </div>

          {total > LIMIT && (
            <div className="flex items-center justify-center gap-4 mt-8">
              <button
                onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
                disabled={offset === 0}
                className="px-4 py-2 rounded-lg bg-surface-2 border border-border text-xs font-medium text-fg hover:bg-surface-2/60 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                ← Previous
              </button>
              <span className="text-xs text-fg-subtle">
                {offset + 1}–{Math.min(offset + LIMIT, total)} of {total}
              </span>
              <button
                onClick={() => setOffset((o) => o + LIMIT)}
                disabled={offset + LIMIT >= total}
                className="px-4 py-2 rounded-lg bg-surface-2 border border-border text-xs font-medium text-fg hover:bg-surface-2/60 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function PoliticianCard({ p }: { p: any }) {
  return (
    <Link
      href={politicianHref(p.name)}
      className="group relative flex flex-col rounded-2xl bg-card border border-border p-5 hover:border-accent/30 hover:-translate-y-0.5 transition-all duration-150"
    >
      <div className="flex items-start gap-3 mb-4">
        <PoliticianAvatar
          name={p.name}
          party={p.party}
          bioguideId={p.bioguide_id}
          photoUrl={p.photo_url}
          size="md"
        />
        <div className="min-w-0">
          <h3 className="text-fg font-semibold text-sm leading-snug truncate group-hover:text-accent transition-colors">
            {p.name}
          </h3>
          <div className="flex items-center gap-1.5 mt-0.5 text-xs text-fg-muted">
            <span className={cn("text-[10px] font-bold", partyColor(p.party))}>{p.party || "·"}</span>
            <span>·</span>
            <span>{p.state_district || ""}</span>
            <span>·</span>
            <span>{p.chamber}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mt-auto">
        <MiniStat label="Trades" value={p.trades} />
        <MiniStat label="Avg Score" value={p.avg_score?.toFixed(1)} valueClass={scoreColor(p.avg_score)} />
        <MiniStat label="Volume" value={formatCurrency(p.total_volume)} muted />
        <MiniStat label="Buys / Sells" value={`${p.buys ?? "—"} / ${p.sells ?? "—"}`} muted />
      </div>
    </Link>
  );
}

function MiniStat({ label, value, muted, valueClass }: {
  label: string; value: string | number; muted?: boolean; valueClass?: string;
}) {
  return (
    <div>
      <div className="text-xs text-fg-muted mb-0.5">{label}</div>
      <div className={cn("text-lg font-bold text-fg", valueClass, muted && "text-fg-muted text-sm font-semibold")}>
        {value}
      </div>
    </div>
  );
}