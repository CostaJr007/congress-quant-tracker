import { partyKey } from "@/lib/format";

export function PartyPill({ party }: { party?: string | null }) {
  const key = partyKey(party);
  const letter = (party || "I").toString().trim().charAt(0).toUpperCase() || "I";
  return (
    <span className={`party ${key}`} title={party || "Independent"}>
      {letter}
    </span>
  );
}
