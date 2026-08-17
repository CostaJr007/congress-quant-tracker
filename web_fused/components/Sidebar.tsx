"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SearchBox } from "./SearchBox";

const NAV = [
  { href: "/", label: "Dashboard", icon: IconGrid },
  { href: "/trades", label: "Trades", icon: IconSwap },
  { href: "/politicians", label: "Politicians", icon: IconUser },
  { href: "/stocks", label: "Stocks", icon: IconChart },
  { href: "/signals", label: "Signals", icon: IconAlert },
  { href: "/leaderboard", label: "Leaderboard", icon: IconRank },
  { href: "/analyze", label: "Analyze", icon: IconPulse },
];

function active(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <Link href="/" className="sidebar-brand" onClick={onClose}>
        <span className="brand-mark">CI</span>
        <span className="brand-text">
          <span className="brand-name">CongressInvests</span>
          <span className="brand-sub">Trading intelligence</span>
        </span>
      </Link>
      <SearchBox />
      <nav className="nav">
        {NAV.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item ${active(pathname, item.href) ? "active" : ""}`}
              onClick={onClose}
            >
              <Icon />
              {item.label}
            </Link>
          );
        })}
        <a
          className="nav-item ext"
          href="http://localhost:8000/terminal/"
          target="_blank"
          rel="noreferrer"
        >
          <IconTerm />
          CI Terminal
          <span className="ext-hint">↗</span>
        </a>
      </nav>
      <div className="sidebar-foot">
        Public House &amp; Senate disclosures.
        <br />
        Not investment advice.
      </div>
    </aside>
  );
}

function IconGrid() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}
function IconSwap() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M7 7h11l-3-3M17 17H6l3 3" />
    </svg>
  );
}
function IconUser() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5 19c1.4-3 4-4.5 7-4.5S17.6 16 19 19" />
    </svg>
  );
}
function IconChart() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 19V5M4 19h16" />
      <path d="M8 15l4-5 3 3 5-7" />
    </svg>
  );
}
function IconAlert() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M12 4l9 16H3L12 4z" />
      <path d="M12 10v4M12 16.5v.5" />
    </svg>
  );
}
function IconRank() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M7 20V10h4v10H7zM13 20V6h4v14h-4zM4 20h16" />
    </svg>
  );
}
function IconPulse() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 12h4l2-6 4 12 2-6h6" />
    </svg>
  );
}
function IconTerm() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M7 10l3 2-3 2M13 14h4" />
    </svg>
  );
}
