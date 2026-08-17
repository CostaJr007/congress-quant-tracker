"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <div className="shell">
      <div className={`scrim ${open ? "show" : ""}`} onClick={() => setOpen(false)} />
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="main">
        <header className="topbar">
          <button className="icon-btn" type="button" aria-label="Open menu" onClick={() => setOpen(true)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
          <span className="brand-mark" style={{ width: 28, height: 28, fontSize: 11 }}>
            CI
          </span>
          <strong>CongressInvests</strong>
        </header>
        <div className="page">{children}</div>
      </div>
    </div>
  );
}
