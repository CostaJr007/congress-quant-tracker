"""Parse House Periodic Transaction Report PDFs.

Strategy:
  1. pdfplumber text extraction
  2. Deterministic regex (fast, free, good on standard PTR layout)
  3. Optional Groq LLM cleanup / fill gaps when GROQ_API_KEY is set
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional

import httpx
import pdfplumber

from congress_quant_tracker.common import normalize_transaction_type
from congress_quant_tracker.config import settings

logger = logging.getLogger(__name__)

# Owner codes on House PTRs
OWNER_CODES = {"SP", "DC", "JT", "C", "Self", "self"}


def _parse_date(s: str) -> Optional[date]:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(amount: str) -> tuple[int, int, str]:
    cleaned = re.sub(r"\s+", " ", (amount or "").replace("\n", " ")).strip()
    nums = re.findall(r"\$?\s*([\d,]+)", cleaned)
    vals = []
    for n in nums:
        try:
            vals.append(int(n.replace(",", "")))
        except ValueError:
            pass
    if len(vals) >= 2:
        return vals[0], vals[1], cleaned
    if len(vals) == 1:
        return vals[0], vals[0], cleaned
    return 0, 0, cleaned


def extract_text(pdf_path: Path) -> str:
    parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[: settings.MAX_PDF_PAGES]:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t)
    return "\n".join(parts)


def extract_member_name(text: str, fallback: str = "") -> str:
    m = re.search(r"Name:\s*(?:Hon\.\s*)?(.+)", text)
    if m:
        return m.group(1).strip()
    return fallback


def _normalize_tx(tx_raw: str) -> str:
    return normalize_transaction_type(tx_raw)


def parse_trades_regex(text: str, filing_meta: Optional[dict] = None) -> list[dict]:
    """Parse trades from House PTR plain text (handles multi-line layouts)."""
    trades: list[dict] = []
    filing_meta = filing_meta or {}
    text = text.replace("\x00", "")

    # Collapse to single-spaced lines, then one big blob for cross-line matches
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    blob = " ".join(lines)
    blob = re.sub(r"\s+", " ", blob)

    # Core: owner? asset... (TICKER) ... TYPE date date $amount
    # Also: owner? asset... TYPE date date $amount ... (TICKER)
    patterns = [
        # ticker before type (common)
        re.compile(
            r"(?P<owner>\b(?:SP|DC|JT)\b)\s+"
            r"(?P<asset>.{3,100}?)"
            r"\((?P<ticker>[A-Z]{1,6}(?:\.[A-Z])?)\)\s*"
            r"(?:\[(?P<code>[A-Z]{1,4})\])?\s*"
            r"(?P<tx>S\s*\(\s*partial\s*\)|S\s*\(\s*full\s*\)|Purchase|Sale|[PSE])\s+"
            r"(?P<txd>\d{1,2}/\d{1,2}/\d{4})\s+"
            r"(?P<nd>\d{1,2}/\d{1,2}/\d{4})\s+"
            r"(?P<amt>\$[\d,]+(?:\s*-\s*\$?[\d,]*)?)",
            re.I,
        ),
        # type/dates before ticker on following "Stock (XXX)" chunk
        re.compile(
            r"(?P<owner>\b(?:SP|DC|JT)\b)\s+"
            r"(?P<asset>.{3,80}?)\s+"
            r"(?P<tx>S\s*\(\s*partial\s*\)|S\s*\(\s*full\s*\)|[PSE])\s+"
            r"(?P<txd>\d{1,2}/\d{1,2}/\d{4})\s+"
            r"(?P<nd>\d{1,2}/\d{1,2}/\d{4})\s+"
            r"(?P<amt>\$[\d,]+(?:\s*-\s*\$?[\d,]*)?)\s*"
            r"(?P<asset2>.{0,40}?)"
            r"\((?P<ticker>[A-Z]{1,6}(?:\.[A-Z])?)\)",
            re.I,
        ),
        # no owner code
        re.compile(
            r"(?P<asset>(?:[A-Z][A-Za-z0-9&.,' \-]{2,80}))"
            r"\((?P<ticker>[A-Z]{1,6}(?:\.[A-Z])?)\)\s*"
            r"(?:\[(?P<code>[A-Z]{1,4})\])?\s*"
            r"(?P<tx>S\s*\(\s*partial\s*\)|S\s*\(\s*full\s*\)|[PSE])\s+"
            r"(?P<txd>\d{1,2}/\d{1,2}/\d{4})\s+"
            r"(?P<nd>\d{1,2}/\d{1,2}/\d{4})\s+"
            r"(?P<amt>\$[\d,]+(?:\s*-\s*\$?[\d,]*)?)",
            re.I,
        ),
    ]

    seen: set[tuple] = set()
    for pattern in patterns:
        for m in pattern.finditer(blob):
            gd = m.groupdict()
            ticker = (gd.get("ticker") or "").upper()
            if not ticker or ticker in ("ST", "PT", "ID", "PTR", "FILING"):
                continue
            tx_type = _normalize_tx(gd.get("tx") or "P")
            trade_date = _parse_date(gd.get("txd") or "")
            filing_date = _parse_date(gd.get("nd") or "") or filing_meta.get("filing_date")
            amin, amax, arange = _parse_amount(gd.get("amt") or "")
            # amount may continue on next chunk ($15,001 - / $50,000)
            if amax and amax == amin:
                # look ahead for upper bound near match end
                tail = blob[m.end() : m.end() + 30]
                m2 = re.match(r"\s*\$?([\d,]+)", tail)
                if m2:
                    try:
                        amax = int(m2.group(1).replace(",", ""))
                        arange = f"${amin:,} - ${amax:,}"
                    except ValueError:
                        pass

            asset = re.sub(r"\s+", " ", (gd.get("asset") or "")).strip(" -,\t")
            asset2 = re.sub(r"\s+", " ", (gd.get("asset2") or "")).strip()
            if asset2 and asset2.lower() not in asset.lower():
                asset = f"{asset} {asset2}".strip()
            # strip leading owner if duplicated into asset
            asset = re.sub(r"^(?:SP|DC|JT)\s+", "", asset).strip()
            owner = (gd.get("owner") or "").upper() or None

            key = (ticker, str(trade_date), tx_type, amax or amin, owner)
            if key in seen or not trade_date:
                continue
            seen.add(key)

            trades.append({
                "ticker": ticker,
                "asset_name": f"{asset} ({ticker})".strip() if asset else ticker,
                "asset_type": "stock",
                "transaction_type": tx_type,
                "trade_date": trade_date.isoformat(),
                "filing_date": filing_date.isoformat() if isinstance(filing_date, date) else (
                    str(filing_date) if filing_date else None
                ),
                "value_min": amin,
                "value_max": amax or amin,
                "value_range": arange,
                "owner": owner,
                "source": "house_ptr_regex",
            })

    return trades


def _coerce_groq_trade(t: dict) -> Optional[dict]:
    """Strictly validate/coerce one LLM-extracted trade.

    LLM output is never trusted: every field is re-parsed, bounded and typed
    before it can reach the database. Returns None for unusable rows.
    """
    ticker = str(t.get("ticker") or "").upper().strip()
    if not re.fullmatch(r"[A-Z]{1,6}(?:\.[A-Z])?", ticker):
        return None

    def _int(v) -> int:
        try:
            n = int(float(str(v).replace(",", "").strip()))
            return n if n >= 0 else 0
        except (ValueError, TypeError):
            return 0

    value_min = _int(t.get("value_min"))
    value_max = _int(t.get("value_max"))
    if value_max and value_min > value_max:
        value_min, value_max = value_max, value_min

    trade_date = _parse_date(str(t.get("trade_date") or ""))
    if not trade_date:
        return None
    filing_date = _parse_date(str(t.get("filing_date") or ""))

    asset_type = str(t.get("asset_type") or "stock").lower()
    if asset_type not in (
        "stock",
        "etf",
        "option_call",
        "option_put",
        "crypto",
        "bond",
    ):
        asset_type = "stock"

    owner = str(t.get("owner") or "").strip().upper()[:10] or ""

    return {
        "ticker": ticker,
        "asset_name": re.sub(r"\s+", " ", str(t.get("asset_name") or ticker)).strip()[:255],
        "asset_type": asset_type,
        "transaction_type": _normalize_tx(t.get("transaction_type") or "buy"),
        "trade_date": trade_date.isoformat(),
        "filing_date": filing_date.isoformat() if filing_date else None,
        "value_min": value_min,
        "value_max": value_max,
        "value_range": re.sub(r"\s+", " ", str(t.get("value_range") or "")).strip()[:50],
        "owner": owner if owner in OWNER_CODES else "",
        "source": "house_ptr_groq",
    }


def parse_with_groq(text: str, filing_meta: Optional[dict] = None) -> list[dict]:
    """Use Groq (OpenAI-compatible) to extract trades as JSON."""
    api_key = (settings.GROQ_API_KEY or "").strip()
    if len(api_key) < 20 or api_key in ("your_key", "xxx", "changeme"):
        return []

    filing_meta = filing_meta or {}
    model = settings.GROQ_MODEL
    system = (
        "You extract congressional Periodic Transaction Report trades. "
        "Return ONLY valid JSON: {\"trades\":[...]}. Never invent tickers or amounts. "
        "transaction_type must be buy|sell|exchange. Dates ISO YYYY-MM-DD. "
        "amount ranges like $1,001 - $15,000 become value_min/value_max integers."
    )
    user = f"""Extract every stock/option trade from this House PTR text.

Member hint: {filing_meta.get('name', '')}
Filing date hint: {filing_meta.get('filing_date', '')}

Each trade object fields:
ticker, asset_name, asset_type (stock|etf|option_call|option_put|crypto|bond),
transaction_type (buy|sell|exchange), trade_date, filing_date,
value_min, value_max, value_range, owner (SP|DC|JT|null)

TEXT:
{text[:25000]}
"""

    import time

    last_err = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=90) as client:
                r = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
                if r.status_code == 429:
                    # rate limit — back off
                    wait = 2 ** attempt + 1
                    logger.warning("Groq 429, sleep %ss", wait)
                    time.sleep(wait)
                    last_err = "429"
                    continue
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                data = json.loads(content)
                trades = data.get("trades") if isinstance(data, dict) else data
                if not isinstance(trades, list):
                    return []
                out = []
                for t in trades:
                    if not isinstance(t, dict):
                        continue
                    coerced = _coerce_groq_trade(t)
                    if coerced:
                        out.append(coerced)
                dropped = len(trades) - len(out)
                if dropped:
                    logger.warning("Groq: dropped %d invalid trade row(s)", dropped)
                return out
        except Exception as e:
            last_err = e
            logger.warning("Groq parse failed: %s", e)
            time.sleep(1)
    if last_err:
        logger.warning("Groq gave up: %s", last_err)
    return []


def merge_trades(primary: list[dict], secondary: list[dict]) -> list[dict]:
    """Merge secondary into primary by (ticker, trade_date, type), prefer filled fields."""
    def key(t: dict) -> tuple:
        return (
            (t.get("ticker") or "").upper(),
            str(t.get("trade_date") or ""),
            t.get("transaction_type") or "",
            t.get("value_max") or 0,
        )

    by_key: dict[tuple, dict] = {}
    for t in primary:
        by_key[key(t)] = t
    for t in secondary:
        k = key(t)
        if k not in by_key:
            by_key[k] = t
        else:
            base = by_key[k]
            for field in ("asset_name", "owner", "value_range", "asset_type"):
                if not base.get(field) and t.get(field):
                    base[field] = t[field]
    return list(by_key.values())


def parse_house_ptr(pdf_path: Path, filing_meta: Optional[dict] = None) -> dict[str, Any]:
    """Full parse of one House PTR PDF."""
    filing_meta = filing_meta or {}
    text = extract_text(pdf_path)
    if not text.strip():
        return {
            "politician": {"name": filing_meta.get("name"), "chamber": "house"},
            "trades": [],
            "text_len": 0,
            "method": "empty",
        }

    name = extract_member_name(text, filing_meta.get("name", ""))
    regex_trades = parse_trades_regex(text, filing_meta)
    method = "regex"
    trades = regex_trades

    # Groq when enabled and (few regex hits OR always if FORCE)
    groq_key = (settings.GROQ_API_KEY or "").strip()
    use_groq = len(groq_key) >= 20 and (
        settings.LLM_ENABLED or len(regex_trades) < 2
    )
    if use_groq:
        groq_trades = parse_with_groq(text, {**filing_meta, "name": name})
        if groq_trades:
            trades = merge_trades(regex_trades, groq_trades) if regex_trades else groq_trades
            method = "regex+groq" if regex_trades else "groq"

    return {
        "politician": {
            "name": name,
            "chamber": "house",
            "state": filing_meta.get("state"),
            "district": filing_meta.get("district"),
        },
        "trades": trades,
        "text_len": len(text),
        "method": method,
        "doc_id": filing_meta.get("doc_id") or pdf_path.stem,
        "pdf_url": filing_meta.get("pdf_url"),
        "source_pdf": str(pdf_path),
    }
