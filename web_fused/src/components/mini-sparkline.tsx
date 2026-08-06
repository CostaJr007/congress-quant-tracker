"use client";

/** Tiny SVG sparkline for price series (no recharts overhead). */
export default function MiniSparkline({
  points,
  positive,
  width = 72,
  height = 28,
}: {
  points: { close: number }[];
  positive?: boolean;
  width?: number;
  height?: number;
}) {
  if (!points?.length || points.length < 2) {
    return (
      <div
        className="rounded bg-surface-2/40 border border-border"
        style={{ width, height }}
      />
    );
  }

  const vals = points.map((p) => p.close).filter((v) => typeof v === "number" && !isNaN(v));
  if (vals.length < 2) {
    return <div className="rounded bg-surface-2/40 border border-border" style={{ width, height }} />;
  }

  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const pad = 2;
  const coords = vals.map((v, i) => {
    const x = pad + (i / (vals.length - 1)) * (width - pad * 2);
    const y = pad + (1 - (v - min) / span) * (height - pad * 2);
    return `${x},${y}`;
  });
  const stroke = positive === false ? "#fb2c36" : positive === true ? "#00bb7f" : "#f59e0b";

  return (
    <svg width={width} height={height} className="overflow-visible shrink-0">
      <polyline
        fill="none"
        stroke={stroke}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={coords.join(" ")}
      />
    </svg>
  );
}
