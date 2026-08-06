import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }

export function partyColor(p: string) { return p === "D" ? "text-blue-400" : p === "R" ? "text-red-400" : "text-[var(--fg-muted)]"; }
export function partyBg(p: string) { return p === "D" ? "bg-blue-500/10" : p === "R" ? "bg-red-500/10" : "bg-[var(--surface-2)]"; }
export function txColor(t: string) { return t?.toLowerCase().includes("buy") ? "bg-[var(--positive-bg)] text-[var(--positive)]" : "bg-[var(--negative-bg)] text-[var(--negative)]"; }
export function fmtPct(v: number) { return (v ?? 0).toFixed(1) + "%"; }

export function fmtDollar(v: number): string {
  if (!v) return "$0";
  if (v >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6) return "$" + (v / 1e6).toFixed(1) + "M";
  if (v >= 1e3) return "$" + (v / 1e3).toFixed(0) + "K";
  return "$" + v.toLocaleString();
}

export function getInitials(name: string): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.substring(0, 2).toUpperCase();
}

export function bioguidePhotoUrl(bioguideId: string): string {
  if (!bioguideId) return "";
  return `/politicians/${bioguideId}.jpg`;
}
