export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state">
      <div className="skel" style={{ width: 180, margin: "0 auto 10px" }} />
      <div className="skel" style={{ width: 260, margin: "0 auto 8px", height: 10 }} />
      <div className="skel" style={{ width: 220, margin: "0 auto", height: 10 }} />
      <p style={{ marginTop: 12 }}>{label}</p>
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="state">
      <h3>{title}</h3>
      {detail && <p>{detail}</p>}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div className="state">
      <h3>Couldn’t load data</h3>
      <p>{message || "The API did not respond. Is it running on :8000?"}</p>
      {onRetry && (
        <div style={{ marginTop: 12 }}>
          <button className="btn" onClick={onRetry} type="button">
            Retry
          </button>
        </div>
      )}
    </div>
  );
}

export function Pagination({
  total,
  limit,
  offset,
  onPage,
}: {
  total: number;
  limit: number;
  offset: number;
  onPage: (offset: number) => void;
}) {
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);
  const prev = Math.max(0, offset - limit);
  const next = offset + limit;
  return (
    <div className="pager">
      <span className="num">
        {from.toLocaleString()}–{to.toLocaleString()} of {total.toLocaleString()}
      </span>
      <div className="pager-btns">
        <button className="btn" type="button" disabled={offset <= 0} onClick={() => onPage(prev)}>
          Prev
        </button>
        <button className="btn" type="button" disabled={next >= total} onClick={() => onPage(next)}>
          Next
        </button>
      </div>
    </div>
  );
}
