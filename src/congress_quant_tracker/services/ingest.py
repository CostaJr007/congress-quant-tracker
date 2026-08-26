"""Unified trade ingestion path — the single way any source enters the DB.

Every pipeline (House official PDFs, Senate eFD, CongressInvests fallback)
funnels through here so normalization, validation, dedup/merge, options
extraction and provenance tagging behave identically regardless of origin.

Guarantees:
  * rejects malformed rows early with an explicit reason
  * rejects demo/sample payloads (defense against seed-style contamination)
  * same-day/same-side duplicates are MERGED (widened ranges, backfilled
    fields), never silently dropped
  * every stored Trade carries provenance in `notes` (source tag [+ boost])
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from congress_quant_tracker.common import (
    normalize_transaction_type,
    sanitize_ticker,
)
from congress_quant_tracker.database.models import OptionsTrade, Politician, Trade
from congress_quant_tracker.enrichers.sectors import resolve_sector
from congress_quant_tracker.fetchers.congress_invests import (
    classify_asset,
    parse_date,
    parse_option_details,
    sanitize_trade_dates,
)

logger = logging.getLogger(__name__)

# Markers that identify generated/demo payloads. Real filings never contain them.
_SAMPLE_MARKERS = ("sample trade", "sample_trade", "__seed__")

_ASSET_TYPES = {"stock", "etf", "option_call", "option_put", "crypto", "bond", "other"}
_OWNER_CODES = {"SP", "DC", "JT", "C"}


def looks_like_sample(raw: dict) -> bool:
    """Heuristic guard against seeded/demo records reaching production."""
    blob = " ".join(
        str(raw.get(k) or "")
        for k in (
            "member",
            "name",
            "politician",
            "politician_name",
            "asset_name",
            "asset",
            "notes",
            "report_type",
        )
    ).lower()
    return any(marker in blob for marker in _SAMPLE_MARKERS)


def _to_int(v: Any) -> int:
    try:
        n = int(float(str(v or 0).replace(",", "").strip()))
        return max(0, n)
    except (ValueError, TypeError):
        return 0


def _as_date(v: Any) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return parse_date(str(v or ""))


def _clean_owner(owner: Any) -> str:
    o = str(owner or "").strip().upper()
    return o[:10] if o else ""


def normalize_record(raw: dict) -> tuple[dict | None, str | None]:
    """Map any source shape to the canonical record.

    Accepts field aliases: member|politician|politician_name,
    amount_min/value_min, amount_max/value_max, link/pdf_url/url.

    Returns (record, None) on success or (None, reject_reason).
    """
    if looks_like_sample(raw):
        return None, "sample_data_rejected"

    name = (
        raw.get("member")
        or raw.get("politician")
        or raw.get("politician_name")
        or raw.get("name")
        or ""
    )
    name = str(name).strip()
    if not name:
        return None, "missing_politician"

    ticker = sanitize_ticker(raw.get("ticker"))
    if not ticker:
        return None, "missing_or_bad_ticker"

    tx_type = normalize_transaction_type(
        raw.get("transaction_type") or raw.get("trade_type")
    )

    asset_name = str(raw.get("asset_name") or raw.get("asset") or "").strip()[:255]
    asset_type = str(
        raw.get("asset_type") or classify_asset(asset_name, ticker) or "stock"
    ).strip().lower()
    if asset_type not in _ASSET_TYPES:
        asset_type = classify_asset(asset_name, ticker) or "stock"

    trade_date = _as_date(raw.get("trade_date") or raw.get("tx_date"))
    filing_date = _as_date(raw.get("filing_date") or raw.get("disclosed"))
    trade_date, filing_date, _corrected = sanitize_trade_dates(
        trade_date, filing_date, asset_name
    )
    if not trade_date:
        return None, "missing_or_invalid_trade_date"
    if filing_date and filing_date < trade_date:
        filing_date = None  # never trust a filing earlier than the trade

    value_min = _to_int(raw.get("value_min", raw.get("amount_min")))
    value_max = _to_int(raw.get("value_max", raw.get("amount_max")))
    if value_max and value_min > value_max:
        value_min, value_max = value_max, value_min
    value_range = str(
        raw.get("value_range") or raw.get("amount_range") or ""
    ).strip()[:50]

    pdf_url = str(raw.get("pdf_url") or raw.get("link") or raw.get("url") or "").strip()
    owner = _clean_owner(raw.get("owner"))

    boost = _to_int(raw.get("news_score_boost"))
    source = str(raw.get("source") or "unknown").strip()[:40]

    record = {
        "politician_name": name,
        "ticker": ticker,
        "asset_name": asset_name or ticker,
        "asset_type": asset_type,
        "transaction_type": tx_type,
        "trade_date": trade_date,
        "filing_date": filing_date,
        "value_min": value_min,
        "value_max": value_max,
        "value_range": value_range,
        "pdf_url": pdf_url[:1000],
        "owner": owner,
        "sector": str(raw.get("sector") or "").strip()[:100],
        "boost": boost,
        "source": source,
    }
    return record, None


def merge_into_existing(existing: Trade, rec: dict) -> bool:
    """Backfill/widen a duplicate row instead of dropping information.

    Returns True when anything changed. A duplicate is defined by uq_trade:
    (politician, ticker, trade_date, side) — PTR disclosures only give value
    RANGES, so two such rows are indistinguishable from one another and merging
    is strictly safer than keeping only the first version seen.
    """
    changed = False

    if not existing.filing_date and rec["filing_date"]:
        existing.filing_date = rec["filing_date"]
        changed = True
    if not existing.pdf_url and rec["pdf_url"]:
        existing.pdf_url = rec["pdf_url"]
        changed = True
    for field in ("owner", "sector"):
        incoming = rec.get(field)
        if incoming and not getattr(existing, field, None):
            setattr(existing, field, incoming)
            changed = True
    incoming_name = rec.get("asset_name")
    if incoming_name and incoming_name != rec["ticker"] and not existing.asset_name:
        existing.asset_name = incoming_name
        changed = True

    if rec["value_min"] and (existing.value_min is None or rec["value_min"] < existing.value_min):
        existing.value_min = rec["value_min"]
        changed = True
    if rec["value_max"] and (existing.value_max is None or rec["value_max"] > existing.value_max):
        existing.value_max = rec["value_max"]
        changed = True
    if changed and rec["value_range"] and not existing.value_range:
        existing.value_range = rec["value_range"]
    return changed


def _provenance_notes(rec: dict) -> str:
    tag = rec["source"] or "unknown"
    if rec["boost"]:
        return f"{tag};tavily_boost={rec['boost']}"
    return tag


def store_trade(
    session: Session,
    rec: dict,
    pol: Politician,
    stats: dict | None = None,
) -> str:
    """Insert or merge one canonical record for an already-resolved politician.

    Returns "added" | "merged" | "deduped".
    """
    existing = (
        session.query(Trade)
        .filter(
            Trade.politician_id == pol.id,
            Trade.ticker == rec["ticker"],
            Trade.trade_date == rec["trade_date"],
            Trade.transaction_type == rec["transaction_type"],
        )
        .first()
    )
    if existing:
        status = "merged" if merge_into_existing(existing, rec) else "deduped"
        if stats is not None:
            stats[status] = stats.get(status, 0) + 1
        return status

    row = Trade(
        politician_id=pol.id,
        ticker=rec["ticker"],
        asset_name=rec["asset_name"],
        asset_type=rec["asset_type"],
        transaction_type=rec["transaction_type"],
        trade_date=rec["trade_date"],
        filing_date=rec["filing_date"],
        value_min=rec["value_min"],
        value_max=rec["value_max"],
        value_range=rec["value_range"],
        pdf_url=rec["pdf_url"],
        owner=rec["owner"],
        sector=rec["sector"],
        score=0,  # tag=None marks the row as unscored until the scorer runs
        tag=None,
        reason=None,
        notes=_provenance_notes(rec),
    )
    session.add(row)
    session.flush()

    if str(rec["asset_type"]).startswith("option"):
        opt = parse_option_details(rec["asset_name"], rec["asset_type"])
        if opt:
            session.add(
                OptionsTrade(
                    trade_id=row.id,
                    option_type=opt.get("option_type")
                    or ("put" if rec["asset_type"] == "option_put" else "call"),
                    strike=opt.get("strike"),
                    expiration_date=opt.get("expiration_date"),
                    underlying_asset=rec["ticker"],
                    premium_min=rec["value_min"],
                    premium_max=rec["value_max"],
                    premium_range=rec["value_range"],
                )
            )

    if stats is not None:
        stats["added"] = stats.get("added", 0) + 1
    return "added"


def backfill_sector(session: Session, trade: Trade) -> None:
    """Best-effort static-map sector fill for legacy rows without one."""
    if trade.sector or not trade.ticker:
        return
    label = resolve_sector(trade.ticker, None, None)
    if label:
        trade.sector = label


__all__ = [
    "backfill_sector",
    "looks_like_sample",
    "merge_into_existing",
    "normalize_record",
    "store_trade",
]
