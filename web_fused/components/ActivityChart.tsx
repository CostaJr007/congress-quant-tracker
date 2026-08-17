import { formatMonth, formatMoney, formatNumber } from "@/lib/format";
import type { MonthActivity } from "@/lib/types";

export function ActivityChart({ months }: { months: MonthActivity[] }) {
  const max = Math.max(1, ...months.map((m) => m.count));
  return (
    <div>
      <div className="bars" role="img" aria-label="Monthly trade activity">
        {months.map((m) => {
          const h = Math.max(2, Math.round((m.count / max) * 100));
          const buyH = m.count ? Math.round((m.buys / m.count) * h) : 0;
          const sellH = Math.max(0, h - buyH);
          return (
            <div
              className="bar-col"
              key={m.month}
              title={`${formatMonth(m.month)} · ${formatNumber(m.count)} trades · ${formatMoney(m.volume)}`}
            >
              <div className="bar-stack">
                <div className="bar-buy" style={{ height: `${buyH}%` }} />
                <div className="bar-sell" style={{ height: `${sellH}%` }} />
              </div>
              <div className="bar-lbl">{m.month.slice(5)}</div>
            </div>
          );
        })}
      </div>
      <div className="legend">
        <span>
          <i className="swatch" style={{ background: "#16a34a" }} /> Buys
        </span>
        <span>
          <i className="swatch" style={{ background: "#b91c1c" }} /> Sells
        </span>
      </div>
    </div>
  );
}

export function PartySplit({ split }: { split: Record<string, number> }) {
  const entries = Object.entries(split).filter(([, n]) => n > 0);
  const total = entries.reduce((s, [, n]) => s + n, 0) || 1;
  return (
    <div>
      <div className="hbar" aria-label="Party split">
        {entries.map(([party, n]) => {
          const key = party.toUpperCase().startsWith("D")
            ? "d"
            : party.toUpperCase().startsWith("R")
              ? "r"
              : "i";
          return (
            <div
              key={party}
              className={`hseg ${key}`}
              style={{ width: `${(n / total) * 100}%` }}
              title={`${party}: ${n}`}
            />
          );
        })}
      </div>
      <div className="legend">
        {entries.map(([party, n]) => (
          <span key={party}>
            {party} · {Math.round((n / total) * 100)}%
          </span>
        ))}
      </div>
    </div>
  );
}
