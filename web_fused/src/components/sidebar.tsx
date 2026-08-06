"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard, Users, ArrowLeftRight, TrendingUp,
  Bitcoin, Trophy, AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchMeta } from "@/lib/api";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/politicians", label: "Politicians", icon: Users },
  { href: "/trades", label: "Trades", icon: ArrowLeftRight },
  { href: "/stocks", label: "Stocks", icon: TrendingUp },
  { href: "/crypto", label: "Crypto", icon: Bitcoin },
  { href: "/signals", label: "Signals", icon: AlertTriangle },
  { href: "/leaderboard", label: "Leaderboard", icon: Trophy },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [meta, setMeta] = useState<{
    total_trades?: number;
    data_age_days?: number | null;
    last_update?: { status?: string } | null;
  } | null>(null);
  const [online, setOnline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function ping() {
      try {
        const m = await fetchMeta();
        if (!cancelled) {
          setMeta(m as any);
          setOnline(true);
        }
      } catch {
        if (!cancelled) setOnline(false);
      }
    }
    ping();
    const id = setInterval(ping, 60_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <aside className="w-56 h-screen bg-card border-r border-border flex flex-col shrink-0 hidden md:flex">
      <div className="p-4 border-b border-border">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shadow-lg shadow-accent/20">
            <span className="text-background font-bold text-sm">CI</span>
          </div>
          <div className="min-w-0">
            <div className="font-semibold text-fg text-base leading-tight">CongressInvests</div>
            <div className="text-[10px] text-fg-subtle truncate">Trading intelligence</div>
          </div>
        </Link>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const active = item.exact
            ? pathname === item.href
            : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                active
                  ? "bg-accent/10 text-accent font-semibold border border-accent/20"
                  : "text-fg-muted hover:text-fg hover:bg-surface-2/60 border border-transparent",
              )}
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-border text-xs text-fg-subtle space-y-1.5">
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "w-1.5 h-1.5 rounded-full",
              online ? "bg-positive" : "bg-negative",
            )}
          />
          {online ? "API online" : "API offline"}
        </div>
        {online && meta?.total_trades != null && (
          <div>{meta.total_trades.toLocaleString()} trades loaded</div>
        )}
        {online && meta?.data_age_days != null && (
          <div>Data age: {meta.data_age_days}d</div>
        )}
        <div className="text-[10px] text-fg-subtle/80 pt-1">House & Senate disclosures</div>
      </div>
    </aside>
  );
}
