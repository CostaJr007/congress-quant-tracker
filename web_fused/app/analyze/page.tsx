"use client";

import { ErrorState, LoadingState } from "@/components/States";
import { formatMoney, formatNumber } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { AnalyzeOverview } from "@/lib/types";

const SECTIONS: { key: keyof AnalyzeOverview; title: string; hint: string }[] = [
  { key: "party", title: "Party", hint: "Exposure and mix by party" },
  { key: "sector", title: "Sector", hint: "Where volume concentrates" },
  { key: "options", title: "Options", hint: "Calls, puts, unusual structures" },
  { key: "suspicious", title: "Suspicious", hint: "Flagged clusters" },
];

export default function AnalyzePage() {
  const { data, loading, error, status, reload } = useApi<AnalyzeOverview>("/api/analyze/overview");
  const missing = status === 404;

  return (
    <>
      <header className="page-head">
        <div>
          <div className="page-kicker">Desk</div>
          <h1 className="page-title">Analyze</h1>
          <p className="page-desc">Party, sector, options, and suspicious clusters from the API overview.</p>
        </div>
      </header>

      {loading && <LoadingState label="Loading analysis…" />}

      {!loading && missing && (
        <div className="note">
          <strong>Overview not available.</strong>{" "}
          <code className="mono">GET /api/analyze/overview</code> returned 404. This API build
          does not expose the analyze endpoint yet — the rest of CongressInvests still works.
        </div>
      )}

      {!loading && error && !missing && <ErrorState message={error} onRetry={reload} />}

      {!loading && data && !missing && (
        <div className="grid" style={{ gap: 16 }}>
          {SECTIONS.map((sec) => {
            const payload = data[sec.key];
            if (payload == null) return null;
            return (
              <section className="card" key={String(sec.key)}>
                <div className="section-head">
                  <div>
                    <h2 className="section-title">{sec.title}</h2>
                    <div className="sub">{sec.hint}</div>
                  </div>
                </div>
                <AnalyzeBlock value={payload} />
              </section>
            );
          })}
          {SECTIONS.every((s) => data[s.key] == null) && (
            <div className="note">Overview responded, but party / sector / options / suspicious were empty.</div>
          )}
        </div>
      )}
    </>
  );
}

function AnalyzeBlock({ value }: { value: unknown }) {
  if (value == null) return null;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <div className="num">{String(value)}</div>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <div className="dim">No rows</div>;
    if (value.every((v) => v && typeof v === "object" && !Array.isArray(v))) {
      return <ObjectTable rows={value as Record<string, unknown>[]} />;
    }
    return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>;
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.every(([, v]) => typeof v === "number")) {
      const max = Math.max(1, ...entries.map(([, v]) => Number(v)));
      return (
        <div>
          {entries.map(([k, v]) => (
            <div className="list-row" key={k}>
              <div className="grow">
                <div className="name">{k}</div>
                <div className="score-bar" style={{ width: "100%", marginTop: 6 }}>
                  <i style={{ width: `${(Number(v) / max) * 100}%` }} />
                </div>
              </div>
              <div className="num">{pretty(v)}</div>
            </div>
          ))}
        </div>
      );
    }
    return <ObjectTable rows={[value as Record<string, unknown>]} />;
  }
  return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>;
}

function ObjectTable({ rows }: { rows: Record<string, unknown>[] }) {
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(r)))).slice(0, 8);
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c}>{c.replace(/_/g, " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 40).map((row, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c}>{pretty(row[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function pretty(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") {
    if (Math.abs(v) >= 1000) return formatMoney(v).startsWith("$") && v > 10000 ? formatMoney(v) : formatNumber(v);
    return formatNumber(v);
  }
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
