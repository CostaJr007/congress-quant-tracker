import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string | number;
  delta?: number | null;
  suffix?: string;
  className?: string;
}

export default function KpiCard({ label, value, delta, suffix, className }: KpiCardProps) {
  const hasDelta = delta != null && !isNaN(delta);
  const positive = hasDelta && delta > 0;
  const negative = hasDelta && delta < 0;

  return (
    <div className={cn("rounded-2xl bg-card border border-border p-5", className)}>
      <div className="text-fg-muted text-xs font-medium uppercase tracking-wider mb-2">
        {label}
      </div>
      <div className="text-2xl font-bold text-fg flex items-baseline gap-1.5 flex-wrap">
        <span>{value}</span>
        {suffix && <span className="text-xs font-medium text-fg-subtle">{suffix}</span>}
      </div>
      {hasDelta ? (
        <div className={cn(
          "text-xs mt-1.5 font-medium inline-flex items-center gap-1 px-1.5 py-0.5 rounded",
          positive && "text-positive bg-positive/10",
          negative && "text-negative bg-negative/10",
          !positive && !negative && "text-fg-muted bg-surface-2",
        )}>
          <span>{positive ? "↑" : negative ? "↓" : "→"}</span>
          {Math.abs(delta).toFixed(1)}% {negative ? "vs prev month" : "vs prev month"}
        </div>
      ) : (
        <div className="text-xs mt-1.5 text-fg-subtle">no prior period</div>
      )}
    </div>
  );
}