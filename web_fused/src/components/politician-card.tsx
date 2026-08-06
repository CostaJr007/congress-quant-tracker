import Link from "next/link";
import { cn, partyColor } from "@/lib/utils";

interface PoliticianCardProps {
  politician: Record<string, any>;
}

export default function PoliticianCard({ politician }: PoliticianCardProps) {
  return (
    <Link
      href={`/politicians/${encodeURIComponent(politician.name?.toLowerCase().replace(/\s+/g, "-") || "")}`}
      className="group relative flex flex-col rounded-2xl bg-card border border-border p-5 hover:border-border/50 transition-all"
    >
      <div className="flex items-center gap-2 mb-3">
        <span className={cn("text-sm font-bold", partyColor(politician.party))}>
          {politician.party}
        </span>
        <span className="text-xs text-fg-muted">·</span>
        <span className="text-xs text-fg-muted">{politician.state_district?.slice(0, 2) || ""}</span>
        <span className="text-xs text-fg-muted">·</span>
        <span className="text-xs text-fg-muted">{politician.chamber}</span>
      </div>

      <h3 className="text-fg font-semibold text-sm leading-snug mb-4 truncate">
        {politician.name}
      </h3>

      <div className="grid grid-cols-2 gap-3 mt-auto">
        <div>
          <div className="text-xs text-fg-muted mb-0.5">Avg Score</div>
          <div className="text-lg font-bold text-fg">{politician.avg_score}</div>
        </div>
        <div>
          <div className="text-xs text-fg-muted mb-0.5">Trades</div>
          <div className="text-lg font-bold text-fg">{politician.trades}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mt-2">
        <div>
          <div className="text-xs text-fg-muted mb-0.5">Volume</div>
          <div className="text-sm text-fg-muted">${(politician.total_volume / 1_000_000).toFixed(1)}M</div>
        </div>
        <div>
          <div className="text-xs text-fg-muted mb-0.5">Assets</div>
          <div className="text-sm text-fg-muted">{politician.unique_assets}</div>
        </div>
      </div>
    </Link>
  );
}
