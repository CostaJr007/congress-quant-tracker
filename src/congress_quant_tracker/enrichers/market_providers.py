"""Market data providers with Yahoo-first + fallbacks (no API key).

Chain (auto):
  1. yfinance (Yahoo) — primary, bulk + cache friendly
  2. Yahoo Chart API v8 direct (https) — different code path, works when
     the yfinance lib is throttled but Yahoo HTTP still answers
  3. Stooq CSV (https://stooq.com) — free, no key, good for US equities

All providers return the same bar shape:
  [{date: YYYY-MM-DD, open, high, low, close, volume}]

Fail soft: never raise on network issues, return [] and let callers
decide (disk cache / DEMO / EMPTY).
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import requests  # already a project dependency
except ImportError:  # pragma: no cover
    requests = None

_YAHOO_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) congress-quant-tracker/2.1"

# Yahoo -> Stooq symbol map (indices / futures / foreign listings).
# Default: lowercase + .us suffix for US equities (e.g. NVDA -> nvda.us).
_STOOQ_OVERRIDES: dict[str, str] = {
    "^GSPC": "^spx",
    "^IXIC": "^ndq",
    "^DJI": "^dji",
    "^RUT": "^rut",
    "^VIX": "^vix",
    "^STOXX50E": "^sx5e",
    "^FTSE": "^ftse",
    "^N225": "^nkx",
    "^HSI": "^hsi",
    "000001.SS": "^shc",
    "GC=F": "xauusd",
    "SI=F": "xagusd",
    "PL=F": "xptusd",
    "PA=F": "xpdusd",
    "CL=F": "cl.f",
    "BZ=F": "bz.f",
    "DX-Y.NYB": "dx.f",
    "DX=F": "dx.f",
    "EURUSD=X": "eurusd",
    "GBPUSD=X": "gbpusd",
    "JPY=X": "usdjpy",
}


def to_stooq_symbol(yahoo_ticker: str) -> str:
    """Map a Yahoo ticker to its Stooq equivalent."""
    t = (yahoo_ticker or "").strip()
    if not t:
        return ""
    upper = t.upper()
    if upper in _STOOQ_OVERRIDES:
        return _STOOQ_OVERRIDES[upper]
    # strip Yahoo exchange suffixes Stooq doesn't use (.SA -> .br etc. kept simple)
    # US equities: nvda.us ; already-suffixed (.L, .T, .SS) lowercased as-is
    if "." in t or "^" in t or "=" in t:
        return t.lower()
    return f"{t.lower()}.us"


def fetch_stooq_history(
    ticker: str,
    start: date,
    end: date,
    timeout: int = 15,
) -> list[dict]:
    """Daily bars from Stooq CSV. Returns [] on any failure."""
    if requests is None:
        return []
    sym = to_stooq_symbol(ticker)
    if not sym:
        return []
    url = "https://stooq.com/q/d/l/"
    params = {
        "s": sym,
        "d1": start.strftime("%Y%m%d"),
        "d2": end.strftime("%Y%m%d"),
        "i": "d",
    }
    try:
        r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": _YAHOO_UA})
        if r.status_code != 200 or not r.text or "Date," not in r.text[:200]:
            return []
        rows: list[dict] = []
        reader = csv.DictReader(io.StringIO(r.text))
        for row in reader:
            try:
                d = str(row.get("Date") or "")[:10]
                if not d or d < start.isoformat() or d > end.isoformat():
                    continue
                close = float(row.get("Close") or "nan")
                if close != close:  # NaN
                    continue
                def _f(k: str) -> Optional[float]:
                    try:
                        v = float(row.get(k) or "nan")
                        return v if v == v else None
                    except (TypeError, ValueError):
                        return None
                vol = _f("Volume")
                rows.append({
                    "date": d,
                    "close": close,
                    "open": _f("Open"),
                    "high": _f("High"),
                    "low": _f("Low"),
                    "volume": int(vol) if vol is not None else None,
                })
            except (ValueError, TypeError):
                continue
        return rows
    except Exception as e:
        logger.debug("stooq history failed %s: %s", ticker, e)
        return []


def fetch_yahoo_direct_history(
    ticker: str,
    start: date,
    end: date,
    timeout: int = 15,
) -> list[dict]:
    """Daily bars via Yahoo Chart v8 HTTP (no yfinance dep).

    Different code path from yfinance — sometimes answers when the
    yfinance scraper path is rate-limited (429).
    """
    if requests is None:
        return []
    t = (ticker or "").upper().strip()
    if not t:
        return []
    try:
        # period2 exclusive; pad like the yfinance path
        dt_start = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
        dt_end = datetime(end.year, end.month, end.day, tzinfo=timezone.utc)
        p1 = int(dt_start.timestamp())
        p2 = int(dt_end.timestamp()) + 86400
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}"
        r = requests.get(
            url,
            params={"period1": p1, "period2": p2, "interval": "1d", "events": "div|split"},
            timeout=timeout,
            headers={"User-Agent": _YAHOO_UA},
        )
        if r.status_code != 200:
            return []
        payload = r.json()
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            return []
        node = result[0]
        stamps = node.get("timestamp") or []
        quote = (node.get("indicators") or {}).get("quote") or [{}]
        q = quote[0] if quote else {}
        closes = q.get("close") or []
        opens = q.get("open") or []
        highs = q.get("high") or []
        lows = q.get("low") or []
        vols = q.get("volume") or []
        adj = (node.get("indicators") or {}).get("adjclose") or [{}]
        adjclose = (adj[0].get("adjclose") if adj else None) or []

        def _num(v: Any) -> Optional[float]:
            try:
                f = float(v)
                return f if f == f else None
            except (TypeError, ValueError):
                return None

        rows: list[dict] = []
        for i, ts in enumerate(stamps):
            try:
                d = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
            except (ValueError, TypeError, OSError):
                continue
            # prefer adjusted close when present
            c = _num(adjclose[i]) if i < len(adjclose) else None
            if c is None:
                c = _num(closes[i]) if i < len(closes) else None
            if c is None:
                continue
            v = vols[i] if i < len(vols) else None
            try:
                vol = int(v) if v is not None and float(v) == float(v) else None
            except (TypeError, ValueError):
                vol = None
            rows.append({
                "date": d,
                "close": c,
                "open": _num(opens[i]) if i < len(opens) else None,
                "high": _num(highs[i]) if i < len(highs) else None,
                "low": _num(lows[i]) if i < len(lows) else None,
                "volume": vol,
            })
        return [b for b in rows if start.isoformat() <= b["date"] <= end.isoformat()]
    except Exception as e:
        logger.debug("yahoo-direct history failed %s: %s", ticker, e)
        return []


def fetch_history_with_fallback(
    ticker: str,
    start: date,
    end: date,
    yf_fetcher=None,
    timeout: int = 15,
) -> tuple[list[dict], str]:
    """Try yfinance -> Yahoo direct -> Stooq. Returns (bars, source).

    yf_fetcher: optional callable(ticker, start, end) -> bars used for the
    primary leg (lets callers reuse their yfinance logic + tests inject fakes).
    source is one of: yfinance | yahoo_direct | stooq | empty.
    """
    # 1) primary (yfinance) — caller-supplied to avoid duplicating throttle/cache
    if yf_fetcher is not None:
        try:
            bars = yf_fetcher(ticker, start, end) or []
            if bars:
                return bars, "yfinance"
        except Exception as e:
            logger.debug("primary yf fetch failed %s: %s", ticker, e)
    # 2) Yahoo direct HTTP
    bars = fetch_yahoo_direct_history(ticker, start, end, timeout=timeout)
    if bars:
        return bars, "yahoo_direct"
    # 3) Stooq
    bars = fetch_stooq_history(ticker, start, end, timeout=timeout)
    if bars:
        return bars, "stooq"
    return [], "empty"


__all__ = [
    "fetch_history_with_fallback",
    "fetch_stooq_history",
    "fetch_yahoo_direct_history",
    "to_stooq_symbol",
]
