"use client";

import { useMemo, useState } from "react";
import { cn, initials, partyColor } from "@/lib/utils";

type Size = "xs" | "sm" | "md" | "lg" | "xl";

const SIZE: Record<Size, string> = {
  xs: "w-7 h-7 text-[10px]",
  sm: "w-9 h-9 text-xs",
  md: "w-10 h-10 text-sm",
  lg: "w-14 h-14 text-lg",
  xl: "w-20 h-20 text-xl",
};

function cdnUrl(bioguideId?: string | null) {
  if (!bioguideId) return null;
  // GitHub raw is more reliable than theunitedstates.io (SSL often fails)
  return `https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/225x275/${bioguideId}.jpg`;
}

function cdnUrlAlt(bioguideId?: string | null) {
  if (!bioguideId) return null;
  return `https://cdn.jsdelivr.net/gh/unitedstates/images@gh-pages/congress/225x275/${bioguideId}.jpg`;
}

function InitialsBubble({
  name, party, size, roundClass, className,
}: {
  name?: string; party?: string; size: Size; roundClass: string; className?: string;
}) {
  return (
    <div
      className={cn(
        SIZE[size],
        roundClass,
        "flex items-center justify-center font-bold shrink-0 border border-border bg-surface-2",
        partyColor(party || ""),
        className,
      )}
      title={name}
    >
      {initials(name || "?")}
    </div>
  );
}

export default function PoliticianAvatar({
  name,
  party,
  bioguideId,
  photoUrl,
  size = "md",
  className,
  rounded = "xl",
}: {
  name?: string;
  party?: string;
  bioguideId?: string | null;
  photoUrl?: string | null;
  size?: Size;
  className?: string;
  rounded?: "full" | "xl" | "2xl";
}) {
  const candidates = useMemo(() => {
    const list: string[] = [];
    // Prefer local static files first (we download bioguide JPGs into /public/politicians)
    const localFromBio = bioguideId ? `/politicians/${bioguideId}.jpg` : null;
    if (localFromBio) list.push(localFromBio);
    if (photoUrl && photoUrl !== localFromBio) list.push(photoUrl);
    const cdn = cdnUrl(bioguideId);
    if (cdn) list.push(cdn);
    const alt = cdnUrlAlt(bioguideId);
    if (alt) list.push(alt);
    // de-dupe
    return Array.from(new Set(list));
  }, [photoUrl, bioguideId]);

  const [idx, setIdx] = useState(0);
  const [failed, setFailed] = useState(false);
  // reset when identity changes (important for list re-use)
  const key = `${bioguideId || ""}|${photoUrl || ""}|${name || ""}`;
  const [prevKey, setPrevKey] = useState(key);
  if (key !== prevKey) {
    setPrevKey(key);
    setIdx(0);
    setFailed(false);
  }
  const src = !failed ? candidates[idx] : null;
  const roundClass =
    rounded === "full" ? "rounded-full" : rounded === "2xl" ? "rounded-2xl" : "rounded-xl";

  if (!src) {
    return (
      <InitialsBubble
        name={name}
        party={party}
        size={size}
        roundClass={roundClass}
        className={className}
      />
    );
  }

  return (
    <div
      className={cn(
        SIZE[size],
        roundClass,
        "relative shrink-0 overflow-hidden border border-border bg-surface-2 ring-1 ring-white/5",
        className,
      )}
      title={name}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={name || "Politician"}
        className="w-full h-full object-cover object-top"
        loading="lazy"
        onError={() => {
          if (idx + 1 < candidates.length) setIdx((i) => i + 1);
          else setFailed(true);
        }}
      />
    </div>
  );
}
