"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { fetchLeaderboard, ApiError } from "@/lib/api";
import { formatCurrency, scoreColor, politicianHref, partyColor, cn } from "@/lib/utils";
import { ErrorState, EmptyState } from "@/components/states";
import PoliticianAvatar from "@/components/politician-avatar";

const METRICS = [
  { value: "score", label: "Suspicion Score" },
  { value: "volume", label: "Volume" },
  { value: "trades", label: "Trades" },
];

export default function LeaderboardPage() {
  const [data, setData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metric, setMetric] = useState("score");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchLeaderboard({ metric, limit: "25" }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Backend offline");
    } finally {
      setLoading(false);
    }
  }, [metric]);

  useEffect(() => { load(); }, [load]);

  const leaders = data.leaderboard || [];

  const valueFor = (p: any) => {
    if (metric === "volume") return { value: formatCurrency(p.total_volume), label: "volume" };
    if (metric === "trades") return { value: p.trades, label: "trades" };
    return { value: p.avg_score?.toFixed(1), label: "avg score" };
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-fg mb-1">Leaderboard</h1>
        <p className="text-fg-muted text-sm">Congress members ranked by trading activity</p>
      </div>

      <div className="flex gap-1.5 mb-6 bg-surface-2/50 border border-border rounded-xl p-1 w-fit">
        {METRICS.map((m) => (
          <button
            key={m.value}
            onClick={() => setMetric(m.value)}
            className={cn(
              "px-4 py-1.5 rounded-lg text-xs font-medium transition-colors",
              metric === m.value ? "bg-card text-fg shadow-sm" : "text-fg-muted hover:text-fg",
            )}
          >
            {m.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-card border border-border animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : leaders.length === 0 ? (
        <EmptyState title="No data yet" />
      ) : (
        <div className="space-y-2">
          {leaders.map((p: any) => {
            const v = valueFor(p);
            return (
              <Link
                key={p.name}
                href={politicianHref(p.name)}
                className="flex items-center gap-4 px-5 py-4 rounded-xl bg-card border border-border hover:border-accent/30 transition-colors group"
              >
                <div className={cn(
                  "w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold shrink-0",
                  p.rank === 1 ? "bg-amber-400/15 text-amber-400 border border-amber-400/30" :
                    p.rank === 2 ? "bg-slate-300/15 text-slate-300 border border-slate-300/30" :
                      p.rank === 3 ? "bg-orange-600/15 text-orange-600 border border-orange-600/30" :
                        "bg-surface-2 text-fg-muted border border-border",
                )}>
                  {p.rank}
                </div>

                <PoliticianAvatar
                  name={p.name}
                  party={p.party}
                  bioguideId={p.bioguide_id}
                  photoUrl={p.photo_url}
                  size="sm"
                />

                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-fg group-hover:text-accent transition-colors truncate">{p.name}</div>
                  <div className="text-xs text-fg-muted flex items-center gap-1.5">
                    <span className={cn("font-medium", partyColor(p.party))}>{p.party}</span>
                    <span>· {p.chamber}</span>
                    <span>· {p.trades} trades</span>
                    <span>· {formatCurrency(p.total_volume)} volume</span>
                  </div>
                </div>

                <div className="text-right">
                  <div className={cn("text-xl font-bold", metric === "score" && scoreColor(p.avg_score))}>{v.value}</div>
                  <div className="text-xs text-fg-muted">{v.label}</div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}