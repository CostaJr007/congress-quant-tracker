import { tagKey, tagLabel } from "@/lib/format";

export function TagBadge({ tag }: { tag?: string | null }) {
  const key = tagKey(tag);
  return <span className={`tag ${key}`}>{tagLabel(tag)}</span>;
}
