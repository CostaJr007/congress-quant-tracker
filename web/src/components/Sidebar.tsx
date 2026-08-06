"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard, Radio, Users, BarChart3, Bitcoin, Trophy, Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

const mainNav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/trades", label: "Feed", icon: Radio },
  { href: "/politicians", label: "Politicians", icon: Users },
  { href: "/stocks", label: "Stocks", icon: BarChart3 },
  { href: "/crypto", label: "Crypto", icon: Bitcoin },
  { href: "/leaderboard", label: "Rankings", icon: Trophy },
  { href: "/signals", label: "Signals", icon: Zap },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden md:flex flex-col w-60 shrink-0 h-screen sticky top-0 border-r border-[var(--border-color)]"
      style={{ background: "linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%)" }}>
      {/* Logo — always clickable to go home */}
      <div className="px-5 pt-6 pb-5">
        <Link href="/" className="flex items-center gap-3 group cursor-pointer" title="Go to Dashboard">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform"
            style={{ background: "var(--gradient-accent)" }}>
            <span className="text-white font-black text-xs tracking-[0.15em]">CIQ</span>
          </div>
          <div>
            <span className="font-bold text-[var(--text-primary)] tracking-tight text-base group-hover:text-[var(--accent)] transition-colors">
              CapitolIQ
            </span>
            <p className="text-[10px] text-[var(--text-muted)] leading-none mt-0.5">Track every move</p>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
        {mainNav.map((item) => {
          const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link key={item.href} href={item.href} className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 group",
              active
                ? "bg-[var(--accent-soft)] text-[var(--accent)] font-medium"
                : "text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
            )}>
              <item.icon className={cn("w-4 h-4 shrink-0 transition-colors",
                active ? "text-[var(--accent)]" : "text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]"
              )} />
              {item.label}
              {item.label === "Signals" && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-[var(--warning)]" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-[var(--border-color)]">
        <div className="flex items-center justify-between text-[10px] text-[var(--text-subtle)]">
          <span>House & Senate</span>
          <span>2008–2026</span>
        </div>
      </div>
    </aside>
  );
}
