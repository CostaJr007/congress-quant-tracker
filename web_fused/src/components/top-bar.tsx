"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import SearchBar from "@/components/search-bar";
import {
  LayoutDashboard, Users, ArrowLeftRight, TrendingUp,
  Bitcoin, Trophy, AlertTriangle, Menu, X,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/politicians", label: "Politicians", icon: Users },
  { href: "/trades", label: "Trades", icon: ArrowLeftRight },
  { href: "/stocks", label: "Stocks", icon: TrendingUp },
  { href: "/crypto", label: "Crypto", icon: Bitcoin },
  { href: "/signals", label: "Signals", icon: AlertTriangle },
  { href: "/leaderboard", label: "Leaderboard", icon: Trophy },
];

export default function TopBar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname.startsWith(href);

  return (
    <header className="h-14 shrink-0 border-b border-border bg-card/60 backdrop-blur flex items-center gap-4 px-4 sm:px-6">
      {/* Mobile menu button */}
      <button
        onClick={() => setMobileOpen((v) => !v)}
        className="md:hidden text-fg-muted hover:text-fg p-1 -ml-1"
        aria-label="Toggle menu"
      >
        {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      <SearchBar />

      <div className="ml-auto hidden sm:flex items-center gap-2 text-xs text-fg-subtle">
        <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-positive/10 text-positive border border-positive/20">
          <span className="w-1.5 h-1.5 rounded-full bg-positive animate-pulse" />
          Live
        </span>
        <span className="hidden lg:inline text-fg-subtle">House · Senate · PTR filings</span>
      </div>

      {/* Mobile nav */}
      {mobileOpen && (
        <nav className="absolute md:hidden top-14 left-0 right-0 z-50 bg-card border-b border-border p-3 space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
                isActive(item.href, item.exact)
                  ? "bg-accent/10 text-accent font-semibold border border-accent/20"
                  : "text-fg-muted hover:text-fg hover:bg-surface-2/60 border border-transparent",
              )}
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}