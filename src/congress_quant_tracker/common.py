"""Shared normalization helpers for the ingestion pipeline.

Cross-cutting helpers used by fetchers, parsers and services so every
source produces the same canonical values (transaction type, ticker,
politician identity, scoring, politician stats).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy import func

logger = logging.getLogger(__name__)

# Values that are not real tickers (headers, separators, OCR noise)
BAD_TICKERS = {"--", "N/A", "NONE", "UNKNOWN", "NA", "XXX", "ST", "PT", "ID", "PTR", "FILING"}


def normalize_transaction_type(tx) -> str:
    """Map free-text transaction labels to buy|sell|exchange (safe default: buy)."""
    if not tx:
        return "buy"
    t = re.sub(r"\s+", " ", str(tx)).strip().lower()
    if t in ("p", "buy", "purchase") or t.startswith("purchase") or t.startswith("buy"):
        return "buy"
    if t in ("e", "exchange") or t.startswith("exchange"):
        return "exchange"
    if (
        t in ("s", "sell", "sale", "sale_full", "sale_partial")
        or "sale" in t
        or "sell" in t
        or t.startswith("s")
        or "partial" in t
        or "full" in t
    ):
        return "sell"
    return "buy"


def sanitize_ticker(ticker) -> Optional[str]:
    """Uppercase/strip a ticker; return None for junk/empty values."""
    t = str(ticker or "").strip().upper()
    if not t or t in BAD_TICKERS or len(t) > 6:
        return None
    return t


def find_politician(session, name: str, chamber: Optional[str] = None):
    """Locate a politician row.

    Exact normalized name first (optionally restricted to a chamber),
    then a suffix-stripped variant, then the legacy substring fallback.
    """
    from congress_quant_tracker.database.models import Politician

    key = " ".join((name or "").lower().split())
    if not key:
        return None

    def _query(term: str):
        q = session.query(Politician).filter(func.lower(Politician.name) == term)
        if chamber:
            q = q.filter(Politician.chamber == chamber)
        return q.first()

    pol = _query(key)
    if pol:
        return pol

    cleaned = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", key).strip()
    if cleaned and cleaned != key:
        pol = _query(cleaned)
        if pol:
            return pol

    # Legacy substring fallback (also chamber-scoped so a senator's trade is
    # never attached to a same-name House member)
    q = session.query(Politician).filter(Politician.name.ilike(f"%{name}%"))
    if chamber:
        q = q.filter(Politician.chamber == chamber)
    return q.first()


def score_trades(session, trades: list, stats: dict, apply_tavily_boost: bool = False) -> None:
    """Score Trade rows in place and persist score/tag/reason.

    apply_tavily_boost: add the per-trade Tavily news boost stored in
    Trade.notes (used by the House pipeline).
    """
    if not trades:
        return
    from congress_quant_tracker.database.models import Company, Politician
    from congress_quant_tracker.enrichers.sectors import resolve_sector, scorer_sector
    from congress_quant_tracker.scoring.scorer import TradeScorer

    pols = {p.id: p for p in session.query(Politician).all()}
    companies = {c.ticker: c for c in session.query(Company).all()}

    trade_dicts = []
    for t in trades:
        pol = pols.get(t.politician_id)
        trade_dicts.append({
            "id": t.id,
            "politician_id": t.politician_id,
            "politician_name": pol.name if pol else "",
            "ticker": t.ticker,
            "trade_date": str(t.trade_date) if t.trade_date else None,
            "filing_date": str(t.filing_date) if t.filing_date else None,
            "transaction_type": t.transaction_type,
            "value_max": t.value_max or 0,
            "asset_type": t.asset_type or "stock",
            "owner": t.owner or "",
        })

    committee_map = {
        pid: [c.strip() for c in (p.committees or "").split(",") if c.strip()]
        for pid, p in pols.items()
        if p.committees
    }

    sector_map: dict[str, str] = {}
    for t in trades:
        company = companies.get((t.ticker or "").upper())
        label = resolve_sector(t.ticker, t.sector, company.sector if company else None)
        if label and t.ticker:
            sector_map[t.ticker] = scorer_sector(label)

    scored = TradeScorer().score_batch(trade_dicts, committee_map, sector_map)
    by_id = {s["id"]: s for s in scored}

    for t in trades:
        s = by_id.get(t.id)
        if not s:
            continue
        score = int(s.get("score") or 0)
        if apply_tavily_boost and t.notes and "tavily_boost=" in t.notes:
            try:
                boost = int(t.notes.split("tavily_boost=")[1].split(";")[0])
                score = min(100, score + boost)
            except (ValueError, IndexError):
                logger.warning("Malformed tavily_boost in trade %s notes: %r", t.id, t.notes)
        t.score = score
        t.tag = s.get("tag", "routine")
        t.reason = s.get("reason", "")
        stats["trades_scored"] = stats.get("trades_scored", 0) + 1

    session.commit()


def refresh_politician_stats(session, chamber: Optional[str] = None) -> None:
    """Recalculate total_trades / avg_score for politicians (optionally one chamber).

    Aggregated in SQL instead of one query per politician.
    """
    from congress_quant_tracker.database.models import Politician, Trade

    q = session.query(Politician)
    if chamber:
        q = q.filter(Politician.chamber == chamber)
    pols = q.all()
    if not pols:
        return

    totals = dict(
        session.query(Trade.politician_id, func.count(Trade.id))
        .group_by(Trade.politician_id)
        .all()
    )
    avgs = dict(
        session.query(Trade.politician_id, func.avg(Trade.score))
        .filter(Trade.score > 0)
        .group_by(Trade.politician_id)
        .all()
    )
    for pol in pols:
        pol.total_trades = totals.get(pol.id, 0)
        pol.avg_score = avgs.get(pol.id) or 0.0
    session.commit()
