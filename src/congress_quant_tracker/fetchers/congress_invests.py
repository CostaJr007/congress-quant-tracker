"""CongressInvests API integration — free, fast, MIT licensed."""

import hashlib
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx

from congress_quant_tracker.common import normalize_transaction_type

logger = logging.getLogger(__name__)

API_BASE = "https://congressinfor-production.up.railway.app"

# Members database (loaded lazily)
_members_db = None


def _normalize_party(party_raw: str) -> str:
    """Map full party names to D/R/I codes."""
    p = (party_raw or "").strip().lower()
    if p in ("d", "democrat", "democratic"):
        return "D"
    if p in ("r", "republican"):
        return "R"
    if p in ("i", "independent", "independent democrat", "libertarian"):
        return "I"
    if "democrat" in p:
        return "D"
    if "republican" in p:
        return "R"
    return "I"


def _normalize_chamber(term_type: str, fallback: str = "") -> str:
    t = (term_type or fallback or "").strip().lower()
    if t in ("rep", "house", "h"):
        return "house"
    if t in ("sen", "senate", "s"):
        return "senate"
    return fallback.lower() if fallback else "house"


def _load_members_db():
    """Load legislators YAML for party/state/district lookup."""
    global _members_db
    if _members_db is not None:
        return _members_db

    try:
        import yaml
        from pathlib import Path

        yaml_path = Path(__file__).parent.parent.parent.parent / "data" / "legislators-current.yaml"
        if not yaml_path.exists():
            # Try downloading
            import urllib.request
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            url = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml"
            urllib.request.urlretrieve(url, str(yaml_path))

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        _members_db = {}
        for member in data:
            name = member.get("name", {}) or {}
            first = (name.get("first") or "").strip()
            last = (name.get("last") or "").strip()
            official = (name.get("official_full") or "").strip()
            full_name = f"{first} {last}".strip()
            terms = member.get("terms") or []
            if not terms:
                continue
            last_term = terms[-1]
            info = {
                # party lives on the term, not bio
                "party": _normalize_party(last_term.get("party", "")),
                "state": last_term.get("state", "") or "",
                "district": last_term.get("district"),
                "chamber": _normalize_chamber(last_term.get("type", "")),
                "bioguide_id": (member.get("id") or {}).get("bioguide"),
            }
            for key in (full_name.lower(), official.lower()):
                if key:
                    _members_db[key] = info
            # Last-name fallback only when unique among current legislators
            if last:
                last_key = last.lower()
                if last_key not in _members_db:
                    _members_db[last_key] = info
                else:
                    # Ambiguous last name — remove so we don't assign wrong party
                    existing = _members_db.get(last_key)
                    if existing and existing.get("bioguide_id") != info.get("bioguide_id"):
                        _members_db.pop(last_key, None)
    except Exception as e:
        logger.warning(f"Failed to load members DB: {e}")
        _members_db = {}

    return _members_db


def _filing_id(chamber: str, tx_date: str, member: str, ticker: str) -> str:
    """Generate unique filing ID for dedup."""
    raw = f"{chamber}_{tx_date}_{member}_{ticker}"
    return hashlib.md5(raw.encode()).hexdigest()


def _parse_amount(amount_str: str) -> tuple[int, int, str]:
    """Parse amount ranges, including multi-line House disclosure strings."""
    cleaned = (amount_str or "").replace("\n", " ").replace("\r", " ")
    cleaned = " ".join(cleaned.split()).strip()
    amount_min, amount_max = 0, 0
    if "-" in cleaned:
        parts = cleaned.replace("$", "").replace(",", "").split("-")
        try:
            amount_min = int(parts[0].strip() or 0)
        except ValueError:
            amount_min = 0
        try:
            amount_max = int(parts[1].strip() or 0)
        except (ValueError, IndexError):
            amount_max = amount_min
    elif cleaned:
        try:
            amount_max = int(cleaned.replace("$", "").replace(",", "") or 0)
            amount_min = amount_max
        except ValueError:
            pass
    return amount_min, amount_max, cleaned


def _extract_dates_from_text(text: str) -> list[date]:
    """Pull MM/DD/YYYY (and variants) dates from disclosure asset strings."""
    if not text:
        return []
    found: list[date] = []
    patterns = (
        (r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", "%m/%d/%Y"),
        (r"\b(\d{4})-(\d{2})-(\d{2})\b", "%Y-%m-%d"),
        (r"\b(\d{1,2})/(\d{1,2})/(\d{2})\b", "%m/%d/%y"),
    )
    for pat, fmt in patterns:
        for m in re.finditer(pat, text):
            raw = m.group(0)
            try:
                if fmt == "%m/%d/%Y":
                    d = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
                elif fmt == "%Y-%m-%d":
                    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                else:
                    d = datetime.strptime(raw, fmt).date()
                if d not in found:
                    found.append(d)
            except (ValueError, TypeError):
                continue
    return found


def sanitize_trade_dates(
    trade_date: Optional[date],
    filing_date: Optional[date],
    asset_name: str = "",
    *,
    today: Optional[date] = None,
) -> tuple[Optional[date], Optional[date], bool]:
    """
    Fix common upstream date bugs.

    CongressInvests (and House PDF scrapers) sometimes put option expiration
    or scrambled asset-string dates into tx_date. Example:
      asset: "... P 12/26/2026 01/21/2026 ..."
      tx_date: 2026-12-26  (expiration — wrong)
      disclosed: 2026-02-09
    Real trade is usually on/before filing and often appears in the asset text.

    Returns (trade_date, filing_date, was_corrected).
    """
    today = today or date.today()
    corrected = False
    if not trade_date and not filing_date:
        return trade_date, filing_date, False

    def is_bad_trade(td: Optional[date], fd: Optional[date]) -> bool:
        if not td:
            return False
        # Far-future transaction (likely option expiration)
        if td > today + timedelta(days=14):
            return True
        # Trade after disclosure is almost always a parse error
        if fd and td > fd:
            return True
        # Trade more than ~2 years before filing is suspicious for PTR
        if fd and (fd - td).days > 730:
            return True
        return False

    if is_bad_trade(trade_date, filing_date):
        candidates = _extract_dates_from_text(asset_name)
        # Prefer dates on or before filing (and not absurdly old)
        pool: list[date] = []
        for d in candidates:
            if filing_date and d > filing_date:
                continue  # skip expirations / future markers
            if filing_date and (filing_date - d).days > 730:
                continue
            if d > today + timedelta(days=14):
                continue
            pool.append(d)
        if pool and filing_date:
            # Closest to filing from below = most likely true trade date
            pool.sort(key=lambda d: (filing_date - d).days)
            trade_date = pool[0]
            corrected = True
        elif pool:
            # No filing: pick latest non-future candidate
            pool = [d for d in pool if d <= today]
            if pool:
                trade_date = max(pool)
                corrected = True
        elif filing_date:
            # Last resort: use filing date (better than future expiration)
            trade_date = filing_date
            corrected = True

    return trade_date, filing_date, corrected


def normalize_trade(raw: dict) -> dict:
    """Normalize a CongressInvests trade to our schema."""
    member = raw.get("member", "")
    tx_type = normalize_transaction_type(raw.get("trade_type"))

    amount_min, amount_max, amount_str = _parse_amount(raw.get("amount", ""))
    asset_name = raw.get("asset", "") or ""
    trade_date = parse_date(raw.get("tx_date", ""))
    filing_date = parse_date(raw.get("disclosed", ""))
    trade_date, filing_date, _ = sanitize_trade_dates(
        trade_date, filing_date, asset_name
    )

    return {
        "member": member,
        "chamber": _normalize_chamber("", raw.get("chamber", "")),
        "ticker": (raw.get("ticker") or "").upper(),
        "asset_name": asset_name,
        "transaction_type": tx_type,
        # ISO strings for storage pipeline
        "trade_date": trade_date.isoformat() if trade_date else (raw.get("tx_date") or ""),
        "filing_date": filing_date.isoformat() if filing_date else (raw.get("disclosed") or ""),
        "amount_min": amount_min,
        "amount_max": amount_max,
        "amount_range": amount_str,
        "pdf_url": raw.get("link", ""),
        "owner": raw.get("owner", ""),
    }


def classify_asset(asset_name: str, ticker: str = "") -> str:
    """Classify asset type from name and ticker."""
    name_lower = (asset_name or "").lower()
    ticker_u = (ticker or "").upper()

    # Options first (call/put wording is common in House PDFs)
    is_option = any(kw in name_lower for kw in ("option", " call", " put", "[op]", "strike"))
    if is_option or re.search(r"\b(call|put)s?\b", name_lower):
        if re.search(r"\bputs?\b", name_lower) or " put" in name_lower:
            return "option_put"
        return "option_call"

    crypto_tickers = {
        "BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "AVAX", "DOT", "MATIC",
        "LINK", "LTC", "BCH", "UNI", "ATOM", "SHIB", "COIN",
    }
    if ticker_u in crypto_tickers or any(
        kw in name_lower
        for kw in ("crypto", "bitcoin", "ethereum", "coinbase", "blockchain", "digital currency")
    ):
        return "crypto"

    if any(kw in name_lower for kw in ("etf", "fund", "trust", "index")):
        return "etf"
    if any(kw in name_lower for kw in ("bond", "treasury", "note", "municipal", "t-bill")):
        return "bond"
    return "stock"


def parse_option_details(asset_name: str, asset_type: str) -> Optional[dict]:
    """Best-effort extraction of strike / expiration from disclosure text."""
    if not asset_type or not asset_type.startswith("option"):
        return None
    text = asset_name or ""
    option_type = "put" if asset_type == "option_put" else "call"

    strike = None
    m_strike = re.search(r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:strike)?", text, re.I)
    if not m_strike:
        m_strike = re.search(r"strike\s*(?:price)?\s*[:#]?\s*\$?\s*([\d,]+(?:\.\d+)?)", text, re.I)
    if m_strike:
        try:
            strike = float(m_strike.group(1).replace(",", ""))
        except ValueError:
            strike = None

    expiration = None
    for fmt, pat in (
        ("%m/%d/%Y", r"\b(\d{1,2}/\d{1,2}/\d{4})\b"),
        ("%Y-%m-%d", r"\b(\d{4}-\d{2}-\d{2})\b"),
        ("%m/%d/%y", r"\b(\d{1,2}/\d{1,2}/\d{2})\b"),
    ):
        m = re.search(pat, text)
        if m:
            try:
                expiration = datetime.strptime(m.group(1), fmt).date()
                break
            except ValueError:
                continue

    return {
        "option_type": option_type,
        "strike": strike,
        "expiration_date": expiration,
        "underlying_asset": None,
    }


async def fetch_trades(chamber: str = "house", limit: int = 200, offset: int = 0) -> list[dict]:
    """Fetch trades from CongressInvests API (with 429 backoff)."""
    import asyncio

    params = {"limit": limit, "offset": offset}
    if chamber:
        params["chamber"] = chamber

    url = f"{API_BASE}/trades?{urlencode(params)}"
    last_err: Exception | None = None
    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                resp = await client.get(url)
                if resp.status_code == 429:
                    wait = 3 * (attempt + 1)
                    logger.warning("CongressInvests 429, sleep %ss", wait)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
            trades = data.get("trades", []) if isinstance(data, dict) else data
            return [normalize_trade(t) for t in trades]
        except Exception as e:
            last_err = e
            await asyncio.sleep(2 * (attempt + 1))
    if last_err:
        raise last_err
    return []


async def fetch_all_trades(max_pages: int = 50) -> list[dict]:
    """Fetch all available trades from CongressInvests."""
    all_trades = []
    members_db = _load_members_db()

    for chamber in ["house", "senate"]:
        offset = 0
        for _ in range(max_pages):
            # Per-page retry: a transient failure must not truncate history
            trades = None
            for attempt in range(3):
                try:
                    trades = await fetch_trades(chamber=chamber, limit=200, offset=offset)
                    break
                except Exception as e:
                    logger.warning(
                        "CongressInvests fetch error %s @offset %s (attempt %s/3): %s",
                        chamber, offset, attempt + 1, e,
                    )
                    if attempt < 2:
                        await asyncio.sleep(3 * (attempt + 1))
            if not trades:
                break

            for t in trades:
                # Enrich with member DB (try full name, then last name)
                member_key = (t["member"] or "").lower().strip()
                member_info = members_db.get(member_key, {})
                if not member_info and " " in member_key:
                    # "Nancy Pelosi" -> try last token; also strip suffixes
                    last = member_key.split()[-1]
                    member_info = members_db.get(last, {})
                t["party"] = member_info.get("party") or "I"
                t["state"] = member_info.get("state", "") or ""
                t["district"] = member_info.get("district")
                if member_info.get("chamber"):
                    t["chamber"] = member_info["chamber"]
                if member_info.get("bioguide_id"):
                    t["bioguide_id"] = member_info["bioguide_id"]
                t["asset_type"] = classify_asset(t["asset_name"], t.get("ticker", ""))
                t["option_details"] = parse_option_details(t["asset_name"], t["asset_type"])
                t["filing_id"] = _filing_id(chamber, t["trade_date"], t["member"], t["ticker"])

            all_trades.extend(trades)
            offset += 200

            if len(trades) < 200:
                break

    return all_trades


def parse_date(date_str: str) -> Optional[date]:
    """Parse various date formats."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except (ValueError, TypeError):
            continue
    return None
