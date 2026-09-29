"""Unified trade ingestion path — the single way any source enters the DB.

Every pipeline (House official PDFs, Senate eFD, CongressInvests fallback)
funnels through here so normalization, validation, dedup/merge, options
extraction and provenance tagging behave identically regardless of origin.

Guarantees:
  * rejects malformed rows early with an explicit reason
  * rejects demo/sample payloads (defense against seed-style contamination)
  * same-day/same-side duplicates are MERGED (widened ranges, backfilled
    fields), never silently dropped
  * a disclosed trade is never dropped for lack of a ticker: the symbol is
    resolved from the asset name when the DB knows the company, and otherwise
    stored under a stable pseudo-symbol so the trade stays visible
  * every stored Trade carries provenance in `notes` (source tag [+ boost])
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from congress_quant_tracker.common import (
    normalize_transaction_type,
    sanitize_ticker,
)
from congress_quant_tracker.database.models import (
    Company,
    OptionsTrade,
    Politician,
    Trade,
)
from congress_quant_tracker.enrichers.sectors import resolve_sector
from congress_quant_tracker.fetchers.congress_invests import (
    classify_asset,
    parse_date,
    parse_option_details,
    sanitize_trade_dates,
)

logger = logging.getLogger(__name__)

# Markers that identify generated/demo payloads, which no real filing contains:
# the seeder's "Sample trade for ..." text and the printed instruction row the
# House PTR form itself carries ("Example Mega Corp Common Stock"). OCR of that
# printed row reads cleanly, so it must be rejected by name.
_SAMPLE_MARKERS = ("sample trade", "sample_trade", "__seed__", "example mega corp", "exmpl")

_ASSET_TYPES = {"stock", "etf", "option_call", "option_put", "crypto", "bond", "other"}
_OWNER_CODES = {"SP", "DC", "JT", "C"}

# Trades whose asset has no market symbol (private companies, funds, bonds,
# real estate) are stored under "XX" + a stable suffix. The prefix keeps them
# out of market lookups: nothing here is a real exchange symbol.
UNLISTED_PREFIX = "XX"
UNLISTED_SUFFIX_CHARS = 4

# Words that describe a security rather than the issuer, stripped before a name
# is matched against the company directory.
_NAME_NOISE = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|lp|nv|sa|ag|"
    r"common|stock|shares?|cl|class|series|cmn|com|adr|ads|depositary|"
    r"the|and|of|new|fund|trust|etf|index|us|usa)\b",
    re.I,
)
# Everything from one of these words on describes the security, not the issuer.
_SECURITY_DESCRIPTORS = {
    "class", "cl", "series", "common", "cmn", "com", "stock", "stocks", "share",
    "shares", "depositary", "adr", "ads", "unit", "units", "warrant", "warrants",
    "right", "rights", "note", "notes", "bond", "bonds", "debenture", "debentures",
    "preferred", "pref", "pfd", "ordinary", "capital",
}
_LEGAL_TAIL = re.compile(
    r"\s*[\(\[][A-Z][A-Z0-9.\-]{0,5}[\)\]]\s*(?:\[[A-Z]{2,3}\])?\s*$"
)
_DESCRIPTION_TAIL = re.compile(r"\s*(?:\(|\[)?(?:CALL|PUT|F S:|S O:|D:|L:)\b.*$", re.I)


def looks_like_sample(raw: dict) -> bool:
    """Heuristic guard against seeded/demo records reaching production.

    Covers both the old seeder's payloads and the example row printed on the
    PTR form itself, which OCR reads as a clean, entirely fictitious trade.
    """
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


def clean_company_name(asset_name: str) -> str:
    """Issuer name from a PTR asset description.

    "Zoetis Inc. Class A Common Stock (ZTS)" -> "Zoetis Inc."
    """
    name = str(asset_name or "").strip()
    if not name:
        return ""
    name = _DESCRIPTION_TAIL.sub("", name)
    name = _LEGAL_TAIL.sub("", name)
    words = name.split()
    for index, word in enumerate(words[1:], start=1):
        if word.strip(".,").lower() in _SECURITY_DESCRIPTORS:
            words = words[:index]
            break
    name = re.sub(r"\s+", " ", " ".join(words)).strip(" -,\t")
    return name[:120]


def _name_tokens(name: str) -> list[str]:
    cleaned = _NAME_NOISE.sub(" ", clean_company_name(name).lower())
    return [t for t in re.split(r"[^a-z0-9]+", cleaned) if len(t) >= 3]


def synthetic_ticker(asset_name: str) -> str:
    """Stable pseudo-symbol for an asset with no market ticker.

    Derived from the name, so every disclosure of the same asset aggregates
    under one symbol instead of scattering.
    """
    digest = hashlib.sha1(
        " ".join(_name_tokens(asset_name) or [str(asset_name).lower()]).encode("utf-8")
    ).hexdigest()
    return UNLISTED_PREFIX + digest[:UNLISTED_SUFFIX_CHARS].upper()


def is_synthetic_ticker(ticker: str | None) -> bool:
    if not ticker:
        return False
    symbol = str(ticker).upper()
    return symbol.startswith(UNLISTED_PREFIX) and len(symbol) == 2 + UNLISTED_SUFFIX_CHARS


def resolve_ticker_from_name(asset_name: str, session: Session | None = None) -> str:
    """Symbol for an asset name, from the company directory. "" when unknown.

    Only unambiguous matches are accepted: a single company whose normalized
    name starts with the asset's normalized name, or contains all of its
    significant words. Filings often omit the ticker ("Zoetis Inc. Class A
    Common Stock"), and guessing one is worse than none.
    """
    if session is None:
        return ""
    tokens = _name_tokens(asset_name)
    if not tokens:
        return ""
    companies = session.query(Company.ticker, Company.name).all()
    matches: list[str] = []
    for ticker, company_name in companies:
        if not company_name or company_name.upper() == (ticker or "").upper():
            continue
        normalized = _NAME_NOISE.sub(" ", str(company_name).lower())
        words = {t for t in re.split(r"[^a-z0-9]+", normalized) if len(t) >= 3}
        if not words:
            continue
        if tokens[0] in words and all(t in words for t in tokens[:2]):
            matches.append(ticker)
    unique = sorted(set(matches))
    return unique[0] if len(unique) == 1 else ""


def _ensure_company_name(session: Session, ticker: str, asset_name: str) -> None:
    """Record the issuer name behind a ticker so name search works."""
    name = clean_company_name(asset_name)
    if not ticker or not name or name.upper() == ticker:
        return
    company = session.query(Company).filter(Company.ticker == ticker).first()
    if company:
        if not company.name or company.name.upper() == ticker.upper():
            company.name = name
        return
    session.add(Company(ticker=ticker, name=name))


def normalize_record(
    raw: dict, *, session: Session | None = None
) -> tuple[dict | None, str | None]:
    """Map any source shape to the canonical record.

    Accepts field aliases: member|politician|politician_name,
    amount_min/value_min, amount_max/value_max, link/pdf_url/url.

    `session` (optional) lets an asset without a ticker be resolved against the
    company directory. Without it — or when no company matches — the row is
    stored under a stable pseudo-symbol rather than dropped, because the
    disclosure itself is real data.

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

    asset_name = str(raw.get("asset_name") or raw.get("asset") or "").strip()[:255]
    ticker = sanitize_ticker(raw.get("ticker"))
    unlisted = False
    if not ticker:
        ticker = resolve_ticker_from_name(asset_name, session)
    if not ticker:
        if not asset_name:
            return None, "missing_or_bad_ticker"
        ticker = synthetic_ticker(asset_name)
        unlisted = True

    tx_type = normalize_transaction_type(
        raw.get("transaction_type") or raw.get("trade_type")
    )

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
    if trade_date > date.today() + timedelta(days=14):
        # OCR-fabricated year ("2608") or an option expiration in the date
        # slot: never store a trade from the future.
        return None, "bad_date"
    if filing_date and filing_date < trade_date:
        filing_date = None  # never trust a filing earlier than the trade
    if filing_date and filing_date > date.today() + timedelta(days=14):
        filing_date = None  # future filing stamp is a parse error, not data

    # 0 means "amount unknown" (no text amount, no checked column): store NULL
    # so $0 never pollutes volume sums, sorting or the UI.
    value_min = _to_int(raw.get("value_min", raw.get("amount_min"))) or None
    value_max = _to_int(raw.get("value_max", raw.get("amount_max"))) or None
    if value_min and value_max and value_min > value_max:
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
        "unlisted": unlisted,
        "company_name": clean_company_name(asset_name),
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
    if rec.get("unlisted"):
        tag = f"{tag};unlisted"
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

    _ensure_company_name(session, rec["ticker"], rec["asset_name"])

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
    "UNLISTED_PREFIX",
    "backfill_sector",
    "clean_company_name",
    "is_synthetic_ticker",
    "looks_like_sample",
    "merge_into_existing",
    "normalize_record",
    "resolve_ticker_from_name",
    "store_trade",
    "synthetic_ticker",
]
