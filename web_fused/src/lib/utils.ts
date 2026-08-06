import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, formatDistanceToNowStrict, parseISO } from "date-fns";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ─── Números ─────────────────────────────────────────

export function formatCurrency(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toFixed(0)}`;
}

export function formatVolume(volume: number): string {
  if (!volume) return "$0";
  return formatCurrency(volume);
}

export function formatNumber(value: number): string {
  if (value == null || isNaN(value)) return "—";
  return value.toLocaleString("en-US");
}

export function formatPercent(value: number): string {
  if (value == null || isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

// ─── Datas ───────────────────────────────────────────

export function formatDate(iso: string): string {
  if (!iso) return "—";
  try {
    return format(parseISO(iso), "MMM d, yyyy");
  } catch {
    return iso;
  }
}

export function formatDateShort(iso: string): string {
  if (!iso) return "—";
  try {
    return format(parseISO(iso), "MMM d");
  } catch {
    return iso;
  }
}

export function timeAgo(iso: string): string {
  if (!iso) return "—";
  try {
    return formatDistanceToNowStrict(parseISO(iso), { addSuffix: true });
  } catch {
    return iso;
  }
}

// ─── Ticker helper ───────────────────────────────────

export function politicianHref(name: string): string {
  const slug = (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  return `/politicians/${slug}`;
}

export function initials(name: string): string {
  if (!name) return "?";
  const parts = name.replace(/,/g, "").split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0][0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] || "" : "";
  return `${first}${last}`.toUpperCase();
}

// ─── Cores de score/tag ─────────────────────────────

export function scoreColor(score: number): string {
  if (score >= 76) return "text-red-500";
  if (score >= 51) return "text-orange-500";
  if (score >= 26) return "text-blue-500";
  return "text-fg-muted";
}

export function scoreBadge(score: number): string {
  if (score >= 76) return "bg-red-500/15 text-red-500 border-red-500/30";
  if (score >= 51) return "bg-orange-500/15 text-orange-500 border-orange-500/30";
  if (score >= 26) return "bg-blue-500/15 text-blue-500 border-blue-500/30";
  return "bg-surface-2 text-fg-muted border-border";
}

export function tagStyle(tag: string): string {
  switch (tag) {
    case "high_alert":
      return "bg-red-500/15 text-red-500 border-red-500/30";
    case "suspicious":
      return "bg-orange-500/15 text-orange-500 border-orange-500/30";
    case "noteworthy":
      return "bg-blue-500/15 text-blue-500 border-blue-500/30";
    default:
      return "bg-surface-2 text-fg-muted border-border";
  }
}

export function tagLabel(tag: string): string {
  const map: Record<string, string> = {
    high_alert: "High Alert",
    suspicious: "Suspicious",
    noteworthy: "Noteworthy",
    routine: "Routine",
  };
  return map[tag] || tag;
}

export function partyColor(party: string): string {
  if (party === "D") return "text-blue-400";
  if (party === "R") return "text-red-400";
  return "text-fg-muted";
}

export function partyBadge(party: string): string {
  if (party === "D") return "bg-blue-500/15 text-blue-400 border-blue-500/30";
  if (party === "R") return "bg-red-500/15 text-red-400 border-red-500/30";
  return "bg-surface-2 text-fg-muted border-border";
}