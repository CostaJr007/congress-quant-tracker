"""Parse House Periodic Transaction Report PDFs.

Strategy:
  1. Page-level text extraction with OCR fallback for scanned filings
     (see `pdf_text`): pdfplumber -> pypdf -> pypdfium2 -> OCR
  2. Row parsing anchored on the transaction/notification dates, which reads
     wrapped names, split amounts, ticker-after-amount and ticker-less rows
  3. Deterministic regex (fast, good on the standard one-line PTR layout)
  4. Optional Groq LLM cleanup / fill gaps when GROQ_API_KEY is set

Scanned/hand-filled PTRs carry no dollar amounts at all: the amount is a checked
box in one of ten lettered columns. Those are recovered from the OCR geometry by
`ptr_rows.checked_amounts`.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

from congress_quant_tracker.common import normalize_transaction_type
from congress_quant_tracker.config import settings
from congress_quant_tracker.parsers.pdf_text import (
    DocumentText,
    extract_document,
)
from congress_quant_tracker.parsers.pdf_text import (
    extract_text as _extract_document_text,
)
from congress_quant_tracker.parsers.ptr_form import read_page
from congress_quant_tracker.parsers.ptr_rows import (
    dedupe_key,
    parse_row,
    parse_rows,
)

logger = logging.getLogger(__name__)

# Owner codes on House PTRs
OWNER_CODES = {"SP", "DC", "JT", "C", "Self", "self"}


def _parse_date(s: str) -> date | None:
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


def extract_text(pdf_path: Path, **kwargs) -> str:
    """Whole-document text (text layer, OCR'ing image-only pages when needed)."""
    return _extract_document_text(pdf_path, **kwargs)


_NAME_STOPWORDS = {
    "page", "status", "state", "district", "member", "office", "telephone",
    "name", "report", "periodic", "transaction", "filing", "id", "ptr",
}
_NAME_TITLES = {"hon", "mr", "mrs", "ms", "dr", "sen", "rep", "representative", "senator"}


def _clean_member_name(candidate: str) -> str:
    """Keep the person's words, drop the form-field noise OCR drags along."""
    words: list[str] = []
    for token in re.split(r"\s+", (candidate or "").strip()):
        bare = token.strip(".,;:").lower()
        if bare in _NAME_TITLES:
            continue
        glued_noise = any(
            noise in bare for noise in ("office", "telephone", "district", "periodic")
        )
        if (
            bare in _NAME_STOPWORDS
            or glued_noise
            or not re.fullmatch(r"[A-Za-z][A-Za-z'\-]{0,20}", token.strip(".,"))
        ):
            break
        words.append(token.strip(".,").title())
        if len(words) == 3:
            break
    return " ".join(words)


def _is_plausible_name(name: str) -> bool:
    words = name.split()
    return len(words) >= 2 and all(len(word) >= 2 for word in words)


def extract_member_name(text: str, fallback: str = "") -> str:
    """Member name from the filing text; empty when the text does not show one.

    Candidates from both layouts are considered in order of appearance, because
    the name label ("Name Rohit Khanna") sits above the signature block OCR
    renders as "NAME: R br KOhanza Pare".
    """
    patterns = (
        r"Name:\s*(.+)",
        # Scanned filings: "NAME Rohit Khanna" / "NAME. R hht Kha na"
        r"\bNAME[:.\s]+([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){1,3})",
    )
    candidates: list[tuple[int, str]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            candidates.append((match.start(), match.group(1)))
    for _position, raw in sorted(candidates, key=lambda item: item[0]):
        cleaned = _clean_member_name(raw)
        if _is_plausible_name(cleaned):
            return cleaned
    return fallback


def _normalize_tx(tx_raw: str) -> str:
    return normalize_transaction_type(tx_raw)


def parse_trades_regex(text: str, filing_meta: dict | None = None) -> list[dict]:
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


def _coerce_groq_trade(t: dict) -> dict | None:
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


def parse_with_groq(text: str, filing_meta: dict | None = None) -> list[dict]:
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


def merge_parsed_trades(primary: list[dict], secondary: list[dict]) -> list[dict]:
    """Merge two views of the same filing, keeping the richest version of a row.

    Rows are matched on (ticker-or-asset, trade_date, side) because PTR values
    are ranges: two views of one trade differ in wording, not in identity.
    Dollar values found in the text always win over a checked-column band.
    """
    by_key: dict[tuple, dict] = {}
    for trade in primary:
        by_key.setdefault(dedupe_key(trade), dict(trade))
    for trade in secondary:
        key = dedupe_key(trade)
        base = by_key.get(key)
        if base is None:
            by_key[key] = dict(trade)
            continue
        for field in ("asset_name", "owner", "value_range", "asset_type", "description"):
            if not base.get(field) and trade.get(field):
                base[field] = trade[field]
        if not base.get("ticker") and trade.get("ticker"):
            base["ticker"] = trade["ticker"]
        base["value_min"] = min(
            v for v in (base.get("value_min"), trade.get("value_min")) if v
        ) if any((base.get("value_min"), trade.get("value_min"))) else 0
        base["value_max"] = max(base.get("value_max") or 0, trade.get("value_max") or 0)
    return list(by_key.values())


def _parse_method(rows: list[dict], regex: list[dict], doc: DocumentText) -> str:
    parts: list[str] = []
    if rows:
        parts.append("rows" if not doc.ocr_pages else "rows+ocr")
    if regex:
        parts.append("regex" if not parts else "regex")
    if not parts:
        return "empty" if not doc.text.strip() else "unparsed"
    return "+".join(dict.fromkeys(parts))


def parse_house_ptr(pdf_path: Path, filing_meta: dict | None = None) -> dict[str, Any]:
    """Full parse of one House PTR PDF (text layer or scanned image)."""
    filing_meta = filing_meta or {}
    doc = extract_document(pdf_path)
    text = doc.text

    base_result = {
        "politician": {"name": filing_meta.get("name"), "chamber": "house"},
        "trades": [],
        "text_len": len(text),
        "extraction": doc.diagnostics(),
        "doc_id": filing_meta.get("doc_id") or Path(pdf_path).stem,
        "pdf_url": filing_meta.get("pdf_url"),
        "source_pdf": str(pdf_path),
    }
    if not text.strip():
        return {**base_result, "method": "empty"}

    # The Clerk's index carries the member's canonical name; OCR of a scanned
    # page does not ("Rohrt Khanna OFFICETELEPHONE").
    name = (filing_meta.get("name") or "").strip() or extract_member_name(text)

    row_trades: list[dict] = []
    row_stats = {
        "rows_read": 0,
        "rows_without_side": 0,
        "rows_without_dates": 0,
        "form_pages": 0,
        "forms_with_type_columns": 0,
    }
    for page in doc.pages:
        if not page.text.strip():
            continue
        if page.method == "ocr":
            form_rows, geometry = read_page(pdf_path, page)
            if form_rows:
                row_stats["form_pages"] += 1
                if geometry is not None and geometry.usable_types:
                    row_stats["forms_with_type_columns"] += 1
                    for row in form_rows:
                        # The side is a checked box here; an unmarked row is
                        # reported as unread rather than assumed to be a buy.
                        if not row.side:
                            row_stats["rows_without_side"] += 1
                            continue
                        parsed = parse_row(
                            row.text,
                            side=row.side,
                            value_min=row.value_min,
                            value_max=row.value_max,
                            value_range=row.value_range,
                            amount_column=row.amount_letter or "",
                        )
                        if parsed:
                            row_trades.append(parsed)
                            row_stats["rows_read"] += 1
                        else:
                            row_stats["rows_without_dates"] += 1
                    continue
        page_trades = parse_rows(page.text)
        row_trades.extend(page_trades)
        row_stats["rows_read"] += len(page_trades)

    regex_trades = parse_trades_regex(text, filing_meta)
    trades = merge_parsed_trades(row_trades, regex_trades)
    method = _parse_method(row_trades, regex_trades, doc)

    # Groq when enabled and (few hits so far OR always if FORCE)
    groq_key = (settings.GROQ_API_KEY or "").strip()
    use_groq = len(groq_key) >= 20 and (settings.LLM_ENABLED or len(trades) < 2)
    if use_groq:
        groq_trades = parse_with_groq(text, {**filing_meta, "name": name})
        if groq_trades:
            trades = merge_parsed_trades(trades, groq_trades)
            method = f"{method}+groq"

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
        "extraction": doc.diagnostics(),
        "row_stats": row_stats,
        "doc_id": filing_meta.get("doc_id") or Path(pdf_path).stem,
        "pdf_url": filing_meta.get("pdf_url"),
        "source_pdf": str(pdf_path),
    }
