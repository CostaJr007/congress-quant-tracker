import { formatDelta } from "@/lib/format";

export function StatCard({
  label,
  value,
  sub,
  delta,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  delta?: number | null;
  accent?: boolean;
}) {
  const d = formatDelta(delta ?? null);
  return (
    <div className="card stat-card">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${accent ? "accent" : ""}`}>{value}</div>
      {(sub || d) && (
        <div className="stat-sub">
          {d && (
            <span className={Number(delta) >= 0 ? "delta-up" : "delta-dn"}>{d} mo/mo</span>
          )}
          {d && sub ? " · " : null}
          {sub}
        </div>
      )}
    </div>
  );
}
