"""Read House PTR pages — native text or OCR — into normalized trade rows.

The House PTR form has two layouts and both must be read:

**Born-digital** (Clerk-generated PDF, has a text layer)::

    DC Applied Materials, Inc. - Common P 06/18/2026 06/30/2026 $1,001 - $15,000
    Stock (AMAT) [ST]

**Scanned / hand-filled** (image-only)::

    DC AMRIZE LTD CMN X 08/07/26 09/01/26 X

Scanned forms never spell out the side or the amount; both are checked boxes in
a printed table. `ptr_form` recovers them from the page image and hands them to
`parse_row` as overrides (`side=`, `value_*`), so this module stays text-only.

Everything is anchored on the row's two dates (transaction + notification), so a
row is read even when the ticker, the amount, or the whole asset name wraps onto
the next line — and rows for assets with no ticker at all (private companies,
funds, bonds) are no longer skipped.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

from congress_quant_tracker.common import (
    PTR_ASSET_CODES,
    normalize_transaction_type,
    sanitize_ticker,
)
from congress_quant_tracker.parsers.pdf_text import repair_ocr_token

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Regexes
# --------------------------------------------------------------------------

DATE = r"\d{1,2}/\d{1,2}/\d{2,4}"
ROW_ANCHOR = re.compile(rf"(?P<d1>{DATE})\s+(?P<d2>{DATE})")
DATE_FIND = re.compile(DATE)
TICKER_IN_PARENS = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,5})\)")
ASSET_CODE = re.compile(r"\[([A-Z]{2,3})\]")
MONEY_VALUE = re.compile(r"\$\s*([\d,]{1,15})")
TYPE_TOKEN = re.compile(r"^(P|S|E|PURCHASE|SALE|EXCHANGE)(?:\s*\((\w+)\))?$", re.I)
OWNER_TOKEN = re.compile(r"^(SP|DC|JT|C)$", re.I)
DESCRIPTION = re.compile(r"\bD:\s*(.+?)(?=\s+(?:F S:|S O:|L:|D:|Cap\.|Gains)\b|$)")
CALL = re.compile(r"\bcalls?\b", re.I)
PUT = re.compile(r"\bputs?\b", re.I)

# Parenthesized words that are account noise, never tickers
NOT_TICKERS = {
    "IRA", "ROTH", "SEP", "LLC", "LP", "INC", "CO", "TRUST", "FUND", "ESOP",
    "UST", "CD", "MM", "MMF", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
}
STOP_MARKERS = ("CERTIFY", "Digitally Signed", "Filing ID", "P T R")
MAX_CONTINUATION_LINES = 8
MAX_ROW_CHARS = 600
MIN_PLAUSIBLE_AMOUNT = 1_000  # STOCK Act floor is $1,001


def parse_ptr_date(raw: str | None) -> date | None:
    """Parse PTR dates, including the scanned form's 2-digit years.

    OCR routinely fabricates years ("26"+"08" -> 2608), so anything outside
    2000..next-year is rejected instead of stored.
    """
    if not raw:
        return None
    token = repair_ocr_token(str(raw).strip())
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y"):
        try:
            parsed = datetime.strptime(token, fmt).date()
        except ValueError:
            continue
        # 2-digit years on current filings always mean 20xx
        if fmt.endswith("%y") and parsed.year < 1990:
            continue
        if parsed.year < 2000 or parsed.year > date.today().year + 1:
            return None
        return parsed
    return None


# --------------------------------------------------------------------------
# Row segmentation
# --------------------------------------------------------------------------


def logical_rows(text: str) -> list[str]:
    """Group lines into one string per transaction row.

    A row starts on the line carrying the two dates and absorbs the following
    lines that do not start a row of their own — that is where a wrapped asset
    name, the ticker, or the second half of a split amount lives.
    """
    rows: list[str] = []
    current: list[str] = []
    for raw_line in (text or "").splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line:
            continue
        if any(marker in line for marker in STOP_MARKERS):
            if current:
                rows.append(" ".join(current))
                current = []
            continue
        if ROW_ANCHOR.search(line):
            if current:
                rows.append(" ".join(current))
            current = [line]
        elif current:
            if len(current) >= MAX_CONTINUATION_LINES or len(" ".join(current)) > MAX_ROW_CHARS:
                rows.append(" ".join(current))
                current = []
            else:
                current.append(line)
    if current:
        rows.append(" ".join(current))
    return [r for r in rows if ROW_ANCHOR.search(r)]


# --------------------------------------------------------------------------
# Row parsing
# --------------------------------------------------------------------------


def _split_type(head_tokens: list[str]) -> tuple[str | None, int | None, list[str]]:
    """Find the transaction-type token at the end of the row head."""
    for index in range(len(head_tokens) - 1, -1, -1):
        token = head_tokens[index].strip(".,;")
        match = TYPE_TOKEN.match(token)
        if match:
            return match.group(0), index, head_tokens[:index] + head_tokens[index + 1 :]
    return None, None, head_tokens


def _clean_asset_name(tokens: list[str]) -> str:
    # Check marks and the owner code land inside the asset-name cell on scans.
    cleaned = [t for t in tokens if t.upper() not in ("X", "×")]
    while cleaned and (len(cleaned[-1]) == 1 or OWNER_TOKEN.match(cleaned[-1])):
        cleaned.pop()
    name = " ".join(cleaned)
    name = re.sub(
        r"\b(MM/DD/YY|MM/DD/YYYY|Type|Date|Notification|Amount|Transaction)\b.*$", "", name
    )
    name = re.sub(r"^[^A-Za-z0-9]+", "", name)
    name = re.sub(r"\s+", " ", name).strip(" -,\t")
    return name[:180]


def _extract_ticker(text: str, preferred: str = "") -> str:
    """Ticker from "(XYZ)" — prefer a symbol followed by an asset-type code."""
    coded = re.search(r"\(([A-Z][A-Z0-9.\-]{0,5})\)\s*\[[A-Z]{2,3}\]", text)
    candidates = []
    if coded:
        candidates.append(coded.group(1))
    if preferred:
        ticker = sanitize_ticker(preferred)
        if ticker:
            candidates.append(ticker)
    candidates.extend(TICKER_IN_PARENS.findall(text))
    for candidate in candidates:
        if candidate.upper() in NOT_TICKERS:
            continue
        ticker = sanitize_ticker(candidate)
        if ticker:
            return ticker
    return ""


def _amounts_from_row(row_text: str) -> tuple[int, int, str]:
    """Dollar amounts, ignoring price/description text after the 'D:' block."""
    body = row_text
    marker = re.search(r"\bD:", body)
    if marker:
        body = body[: marker.start()]
    numbers = []
    for raw in MONEY_VALUE.findall(body):
        try:
            value = int(raw.replace(",", ""))
        except ValueError:
            continue
        if value >= MIN_PLAUSIBLE_AMOUNT:
            numbers.append(value)
    if len(numbers) >= 2:
        low, high = numbers[0], numbers[1]
        if low > high:
            low, high = high, low
        return low, high, f"${low:,} - ${high:,}"
    if len(numbers) == 1:
        return numbers[0], numbers[0], f"${numbers[0]:,}"
    return 0, 0, ""


def _option_type(code: str, description: str) -> str:
    if PUT.search(description):
        return "option_put"
    if CALL.search(description):
        return "option_call"
    # A bare [OP] code with no call/put wording is not proof of an option
    # (OCR often mangles [ST] and common-stock rows carry no keywords):
    # leave it unresolved so the name-based classifier decides.
    return ""


def parse_row(
    row_text: str,
    *,
    side: str | None = None,
    value_min: int = 0,
    value_max: int = 0,
    value_range: str = "",
    amount_column: str = "",
) -> dict | None:
    """Parse one transaction row. Returns None when it cannot be a trade.

    `side`/`value_*` come from the printed grid (see `ptr_form`) and override
    what the text says — on scanned forms the text says nothing at all.
    """
    anchor = ROW_ANCHOR.search(row_text)
    if not anchor:
        return None
    trade_date = parse_ptr_date(anchor.group("d1"))
    filing_date = parse_ptr_date(anchor.group("d2"))
    if not trade_date:
        return None

    head = row_text[: anchor.start()]
    middle = row_text[anchor.end() :]

    type_raw, type_index, head_without_type = _split_type(head.split())
    transaction_type = normalize_transaction_type(side or type_raw or "P")

    owner = ""
    tokens = [t.strip(".,;") for t in head_without_type]
    for i, token in enumerate(tokens[:3]):
        if OWNER_TOKEN.match(token):
            owner = token.upper()
            tokens = tokens[:i] + tokens[i + 1 :]
            break

    asset_name = _clean_asset_name(tokens)

    # Wrapped name fragment: the piece right after the amount/code metadata on
    # the continuation line ("... $1,001 - $15,000" / "Stock (AMAT) [ST]").
    trailer = re.sub(r"\([A-Z][A-Z0-9.\-]{0,5}\)", " ", middle)
    trailer = ASSET_CODE.sub(" ", trailer)
    trailer = re.sub(r"\$\s*[\d,]+(?:\s*-\s*\$?\s*[\d,]+)?", " ", trailer)
    trailer = re.sub(r"\b(F S:|S O:|L:|Cap\.|Gains|New|Partnership)\b.*$", " ", trailer)
    trailer_words = [
        w for w in trailer.split() if re.fullmatch(r"[A-Za-z][A-Za-z&.'\-]{0,15}", w)
    ]
    if 0 < len(trailer_words) <= 3 and asset_name:
        asset_name = _clean_asset_name(asset_name.split() + trailer_words)

    ticker = _extract_ticker(f"{head} {middle}")
    code_match = ASSET_CODE.search(middle) or ASSET_CODE.search(head)
    code = code_match.group(1) if code_match else ""

    descriptions = [d.strip() for d in DESCRIPTION.findall(middle)]
    description = " ".join(d for d in descriptions if d)

    text_min, text_max, text_range = _amounts_from_row(row_text)
    if text_min:
        value_min, value_max, value_range = text_min, text_max, text_range
    amount_column = amount_column if value_min else ""

    asset_type = PTR_ASSET_CODES.get(code, "")
    if asset_type == "option":
        asset_type = _option_type(code, description or asset_name)
    if not asset_type:
        from congress_quant_tracker.fetchers.congress_invests import classify_asset

        asset_type = classify_asset(asset_name, ticker)

    # Keep the filing's own asset-type code in the name: the UI can show it and
    # a later reclassification reads it instead of guessing from the wording.
    if code:
        asset_name = f"{asset_name} [{code}]".strip()

    # Option rows need the description text for strike/expiry extraction.
    if asset_type.startswith("option") and description:
        keyword = "put" if asset_type == "option_put" else "call"
        if keyword in description.lower():
            asset_name = f"{asset_name} {description}".strip()

    return {
        "ticker": ticker,
        "asset_name": asset_name or ticker,
        "asset_type": asset_type,
        "asset_code": code,
        "transaction_type": transaction_type,
        "trade_date": trade_date.isoformat(),
        "filing_date": filing_date.isoformat() if filing_date else None,
        "value_min": value_min,
        "value_max": value_max,
        "value_range": value_range,
        "owner": owner,
        "description": description,
        "amount_column": amount_column,
        "source": "house_ptr_rows",
    }


def parse_rows(text: str) -> list[dict]:
    """Parse every transaction row of a PTR page text."""
    trades: list[dict] = []
    seen: set[tuple] = set()
    for row_text in logical_rows(text):
        parsed = parse_row(row_text)
        if not parsed:
            continue
        key = (
            parsed["ticker"] or parsed["asset_name"].upper(),
            parsed["trade_date"],
            parsed["transaction_type"],
            parsed["value_max"],
        )
        if key in seen:
            continue
        seen.add(key)
        trades.append(parsed)
    return trades


def dedupe_key(trade: dict) -> tuple:
    """Identity used to merge row-parsed and regex-parsed views of one trade."""
    return (
        (trade.get("ticker") or "").upper() or (trade.get("asset_name") or "").upper()[:40],
        str(trade.get("trade_date") or ""),
        trade.get("transaction_type") or "",
    )


__all__ = [
    "PTR_ASSET_CODES",
    "dedupe_key",
    "logical_rows",
    "parse_ptr_date",
    "parse_row",
    "parse_rows",
]
