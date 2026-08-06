"use client";

import { useState } from "react";
import { getInitials, cn, bioguidePhotoUrl } from "@/lib/utils";

interface PoliticianAvatarProps {
  name: string;
  bioguideId?: string;
  party?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizes = { sm: "w-8 h-8 text-xs", md: "w-10 h-10 text-sm", lg: "w-12 h-12 text-base" };

export default function PoliticianAvatar({ name, bioguideId, party, size = "md", className }: PoliticianAvatarProps) {
  const [imgError, setImgError] = useState(false);
  const initials = getInitials(name);
  const photoUrl = bioguideId ? bioguidePhotoUrl(bioguideId) : null;

  return (
    <div className={cn("rounded-full overflow-hidden shrink-0", sizes[size], className,
      !photoUrl || imgError ? cn("flex items-center justify-center font-semibold",
        party === "D" ? "bg-blue-500/15 text-blue-400" : party === "R" ? "bg-red-500/15 text-red-400" : "bg-[var(--surface-2)] text-[var(--fg-muted)]"
      ) : ""
    )}>
      {photoUrl && !imgError ? (
        <img
          src={photoUrl}
          alt={name}
          className="w-full h-full object-cover"
          onError={() => setImgError(true)}
          loading="lazy"
        />
      ) : (
        <span>{initials}</span>
      )}
    </div>
  );
}
