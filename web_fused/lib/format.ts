export function formatMoney(n?: number | null): string {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const value = Number(n);
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${sign}$${trimNum(abs / 1_000_000_000)}B`;
  if (abs >= 1_000_000) return `${sign}$${trimNum(abs / 1_000_000)}M`;
  if (abs >= 1_000) return `${sign}$${trimNum(abs / 1_000)}K`;
  if (abs === 0) return "$0";
  return `${sign}$${abs.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function trimNum(n: number): string {
  const rounded = n >= 10 ? n.toFixed(1) : n.toFixed(1);
  return rounded.replace(/\.0$/, "");
}

export function formatRange(
  min?: number | null,
  max?: number | null,
  amount?: string | null,
): string {
  if (amount && amount.trim()) return amount;
  if (min != null && max != null && min !== max) {
    return `${formatMoney(min)}–${formatMoney(max)}`;
  }
  if (max != null) return formatMoney(max);
  if (min != null) return formatMoney(min);
  return "—";
}

export function formatNumber(n?: number | null): string {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString("en-US");
}

export function formatScore(n?: number | null): string {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return Number(n).toFixed(1).replace(/\.0$/, "");
}

export function formatDate(s?: string | null): string {
  if (!s) return "—";
  const raw = s.length <= 10 ? `${s}T00:00:00` : s;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatMonth(s?: string | null): string {
  if (!s) return "—";
  const [y, m] = s.split("-");
  if (!y || !m) return s;
  const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const mi = Number(m) - 1;
  return names[mi] ? `${names[mi]} ${y}` : s;
}

export function formatDelta(n?: number | null): string | null {
  if (n == null || Number.isNaN(Number(n))) return null;
  const v = Number(n);
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}%`;
}

export function isBuy(type?: string | null): boolean {
  const t = (type || "").toLowerCase();
  return t === "buy" || t === "purchase";
}

export function sideLabel(type?: string | null): string {
  if (!type) return "—";
  return isBuy(type) ? "Buy" : "Sell";
}

export function politicianHref(name: string): string {
  return `/politicians/${encodeURIComponent(name.trim().replace(/\s+/g, "-"))}`;
}

export function politicianNameFromSlug(slug: string): string {
  return decodeURIComponent(slug).replace(/-/g, " ").trim();
}

export function tickerHref(ticker: string): string {
  return `/stocks/${encodeURIComponent(ticker.toUpperCase())}`;
}

export function photoSrc(url?: string | null): string | null {
  if (!url) return null;
  return url;
}

export function partyKey(party?: string | null): "d" | "r" | "i" {
  const p = (party || "").toUpperCase();
  if (p.startsWith("D")) return "d";
  if (p.startsWith("R")) return "r";
  return "i";
}

export function tagKey(tag?: string | null): "routine" | "noteworthy" | "suspicious" | "high_alert" {
  const t = (tag || "routine").toLowerCase().replace(/\s+/g, "_");
  if (t === "high_alert" || t === "high-alert") return "high_alert";
  if (t === "suspicious") return "suspicious";
  if (t === "noteworthy") return "noteworthy";
  return "routine";
}

export function tagLabel(tag?: string | null): string {
  const k = tagKey(tag);
  if (k === "high_alert") return "High alert";
  return k.charAt(0).toUpperCase() + k.slice(1);
}

export function qs(params: Record<string, string | number | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export function initial(name?: string | null): string {
  const ch = (name || "?").trim().charAt(0);
  return ch ? ch.toUpperCase() : "?";
}
