"use client";

import { useState } from "react";
import { initial, partyKey, photoSrc } from "@/lib/format";

export function Avatar({
  src,
  name,
  party,
  size = "md",
}: {
  src?: string | null;
  name?: string | null;
  party?: string | null;
  size?: "sm" | "md" | "lg";
}) {
  const [failed, setFailed] = useState(false);
  const photo = !failed ? photoSrc(src) : null;
  const cls = `avatar ${partyKey(party)} ${size === "lg" ? "lg" : size === "sm" ? "sm" : ""} ${photo ? "has-photo" : ""}`;
  return (
    <span className={cls} aria-hidden>
      {photo ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={photo} alt="" onError={() => setFailed(true)} />
      ) : (
        initial(name)
      )}
    </span>
  );
}
