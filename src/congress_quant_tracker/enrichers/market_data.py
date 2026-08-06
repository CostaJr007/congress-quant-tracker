"""Market data helpers with yfinance + disk cache + rate limiting.

Official disclosures only give value *ranges* (e.g. $1,001–$15,000), not
share price or quantity. We estimate:

  mid_value   = (value_min + value_max) / 2   (or value_max if min missing)
  price_open  ≈ close on trade_date (or next trading day)
  shares_est  ≈ mid_value / price_open
  return_pct  = (price_now - price_open) / price_open * 100

Rate limits / resilience:
  - Disk cache of OHLCV per ticker (JSON) for 12h
  - In-process memory cache
  - Global min interval between yfinance calls
  - Batch download when possible
  - Fail soft (return nulls, never crash API)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from congress_quant_tracker.config import settings

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
except ImportError:
    yf = None

_lock = threading.Lock()
_last_call = 0.0
_mem_hist: dict[str, dict[str, Any]] = {}
_mem_quote: dict[str, dict[str, Any]] = {}

# Conservative defaults — Yahoo throttles aggressive scrapers
MIN_INTERVAL_SEC = 1.25
CACHE_TTL_SEC = 12 * 3600  # 12 hours
MAX_HISTORY_DAYS = 400
QUOTE_TTL_SEC = 15 * 60  # 15 min for "current" price


def _cache_dir() -> Path:
    d = settings.DATA_DIR / "cache" / "prices"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _throttle() -> None:
    global _last_call
    with _lock:
        now = time.time()
        wait = MIN_INTERVAL_SEC - (now - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()


def _enabled() -> bool:
    if yf is None:
        return False
    # Allow market endpoints even if NO_YF=1 for scorer — use MARKET_DATA
    if getattr(settings, "MARKET_DATA_ENABLED", True) is False:
        return False
    return True


def _load_disk(ticker: str) -> Optional[dict]:
    path = _cache_dir() / f"{ticker.upper()}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - data.get("fetched_at", 0) > CACHE_TTL_SEC:
            return None
        return data
    except Exception:
        return None


def _save_disk(ticker: str, data: dict) -> None:
    path = _cache_dir() / f"{ticker.upper()}.json"
    try:
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception as e:
        logger.debug("cache write fail %s: %s", ticker, e)


def _fetch_history(ticker: str, start: date, end: date) -> list[dict]:
    """Download daily bars; returns [{date, close, open, high, low, volume}, ...]."""
    if not _enabled():
        return []

    ticker = ticker.upper().strip()
    # expand window slightly
    start = start - timedelta(days=5)
    end = end + timedelta(days=2)
    if end <= start:
        end = start + timedelta(days=7)

    _throttle()
    try:
        # progress=False avoids spam; threads=False is safer for rate limits
        df = yf.download(
            ticker,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        if df is None or df.empty:
            # fallback single ticker object
            _throttle()
            t = yf.Ticker(ticker)
            df = t.history(
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                auto_adjust=True,
            )
        if df is None or df.empty:
            return []

        # Flatten multiindex columns if present
        if hasattr(df.columns, "levels") and getattr(df.columns, "nlevels", 1) > 1:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        rows = []
        for idx, row in df.iterrows():
            try:
                d = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])
            except Exception:
                continue
            close = row.get("Close")
            if close is None or (isinstance(close, float) and close != close):  # NaN
                continue
            rows.append({
                "date": d.isoformat(),
                "close": float(close),
                "open": float(row["Open"]) if "Open" in row and row["Open"] == row["Open"] else None,
                "high": float(row["High"]) if "High" in row and row["High"] == row["High"] else None,
                "low": float(row["Low"]) if "Low" in row and row["Low"] == row["Low"] else None,
                "volume": int(row["Volume"]) if "Volume" in row and row["Volume"] == row["Volume"] else None,
            })
        return rows
    except Exception as e:
        logger.warning("yfinance history failed %s: %s", ticker, e)
        return []


def get_history(
    ticker: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> list[dict]:
    """Cached daily history for ticker between start/end (inclusive)."""
    ticker = (ticker or "").upper().strip()
    if not ticker or ticker in ("--", "N/A"):
        return []

    end = end or date.today()
    start = start or (end - timedelta(days=180))
    # clamp ridiculous windows
    if (end - start).days > MAX_HISTORY_DAYS:
        start = end - timedelta(days=MAX_HISTORY_DAYS)

    cache_key = f"{ticker}:{start}:{end}"
    if cache_key in _mem_hist:
        return _mem_hist[cache_key]["bars"]

    disk = _load_disk(ticker)
    if disk and disk.get("bars"):
        bars = [
            b for b in disk["bars"]
            if start.isoformat() <= b["date"] <= end.isoformat()
        ]
        # if disk has enough coverage use it
        if bars and bars[0]["date"] <= start.isoformat() and bars[-1]["date"] >= (end - timedelta(days=5)).isoformat():
            _mem_hist[cache_key] = {"bars": bars, "at": time.time()}
            return bars
        # maybe full series on disk is usable
        all_bars = disk["bars"]
        if all_bars:
            filtered = [b for b in all_bars if start.isoformat() <= b["date"] <= end.isoformat()]
            if len(filtered) >= 3:
                _mem_hist[cache_key] = {"bars": filtered, "at": time.time()}
                return filtered

    # fetch wider for better disk reuse
    fetch_start = min(start, date.today() - timedelta(days=365))
    fetch_end = max(end, date.today())
    bars_full = _fetch_history(ticker, fetch_start, fetch_end)
    if bars_full:
        _save_disk(ticker, {"fetched_at": time.time(), "bars": bars_full})
    filtered = [b for b in bars_full if start.isoformat() <= b["date"] <= end.isoformat()]
    _mem_hist[cache_key] = {"bars": filtered, "at": time.time()}
    return filtered


def get_price_on_or_after(ticker: str, on: date) -> Optional[dict]:
    """Close price on trade date or next available trading day (within 10 days)."""
    bars = get_history(ticker, on - timedelta(days=3), on + timedelta(days=14))
    for b in bars:
        if b["date"] >= on.isoformat():
            return {"date": b["date"], "price": b["close"]}
    return None


def get_latest_price(ticker: str) -> Optional[dict]:
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return None
    now = time.time()
    cached = _mem_quote.get(ticker)
    if cached and now - cached.get("at", 0) < QUOTE_TTL_SEC:
        return cached.get("data")

    bars = get_history(ticker, date.today() - timedelta(days=14), date.today())
    if not bars:
        return None
    last = bars[-1]
    data = {"date": last["date"], "price": last["close"]}
    _mem_quote[ticker] = {"at": now, "data": data}
    return data


def mid_value(value_min: Optional[int], value_max: Optional[int]) -> Optional[float]:
    lo = value_min or 0
    hi = value_max or 0
    if lo and hi:
        return (lo + hi) / 2.0
    if hi:
        return float(hi)
    if lo:
        return float(lo)
    return None


def estimate_shares(
    value_min: Optional[int],
    value_max: Optional[int],
    price: Optional[float],
) -> Optional[dict]:
    if not price or price <= 0:
        return None
    mid = mid_value(value_min, value_max)
    if not mid:
        return None
    shares_mid = mid / price
    shares_min = (value_min / price) if value_min else None
    shares_max = (value_max / price) if value_max else None
    return {
        "shares_est": round(shares_mid, 1),
        "shares_min_est": round(shares_min, 1) if shares_min else None,
        "shares_max_est": round(shares_max, 1) if shares_max else None,
        "value_mid": round(mid, 2),
        "note": "Estimated from disclosure range midpoint / price on trade date",
    }


def trade_performance(
    ticker: str,
    trade_date: date | str,
    value_min: Optional[int] = None,
    value_max: Optional[int] = None,
    transaction_type: str = "buy",
    chart_points: int = 40,
) -> dict[str, Any]:
    """Full performance package for one trade."""
    empty = {
        "ticker": ticker,
        "price_at_trade": None,
        "price_at_trade_date": None,
        "price_now": None,
        "price_now_date": None,
        "change_pct": None,
        "change_abs": None,
        "direction": None,
        "pnl_mid_est": None,
        "shares": None,
        "chart": [],
        "source": "unavailable",
        "error": None,
    }
    if not _enabled():
        empty["error"] = "market_data_disabled"
        return empty

    try:
        if isinstance(trade_date, str):
            trade_date = date.fromisoformat(trade_date[:10])
    except Exception:
        empty["error"] = "bad_trade_date"
        return empty

    try:
        at = get_price_on_or_after(ticker, trade_date)
        now = get_latest_price(ticker)
        if not at or not now:
            empty["error"] = "no_price_data"
            return empty

        p0 = at["price"]
        p1 = now["price"]
        change_abs = p1 - p0
        change_pct = (change_abs / p0) * 100.0 if p0 else None
        shares = estimate_shares(value_min, value_max, p0)

        # For buys, positive change = good; for sells, short-ish interpretation:
        # we still show raw underlying move; pnl_mid assumes long if buy, inverse if sell
        pnl = None
        if shares and change_abs is not None:
            raw = shares["shares_est"] * change_abs
            tt = (transaction_type or "buy").lower()
            if tt in ("sell", "sale", "s"):
                pnl = -raw  # sold: benefit if price fell
            else:
                pnl = raw

        # chart from trade date → today
        bars = get_history(ticker, trade_date, date.today())
        if len(bars) > chart_points:
            # downsample evenly
            step = max(1, len(bars) // chart_points)
            chart = bars[::step]
            if chart[-1] != bars[-1]:
                chart.append(bars[-1])
        else:
            chart = bars

        return {
            "ticker": ticker.upper(),
            "price_at_trade": round(p0, 4),
            "price_at_trade_date": at["date"],
            "price_now": round(p1, 4),
            "price_now_date": now["date"],
            "change_pct": round(change_pct, 2) if change_pct is not None else None,
            "change_abs": round(change_abs, 4),
            "direction": "up" if change_pct and change_pct > 0 else ("down" if change_pct and change_pct < 0 else "flat"),
            "pnl_mid_est": round(pnl, 2) if pnl is not None else None,
            "shares": shares,
            "chart": [{"date": b["date"], "close": b["close"]} for b in chart],
            "source": "yfinance",
            "error": None,
        }
    except Exception as e:
        logger.warning("trade_performance failed %s: %s", ticker, e)
        empty["error"] = str(e)[:120]
        return empty


def enrich_trades_batch(trades: list[dict], max_unique_tickers: int = 12) -> list[dict]:
    """Attach performance to a list of trade dicts (mutates copies).

    Limits unique tickers to avoid yfinance rate limits on list endpoints.
    """
    if not _enabled() or not trades:
        return trades

    # pick first N unique tickers that have dates
    seen: list[str] = []
    for t in trades:
        tk = (t.get("ticker") or "").upper()
        if tk and tk not in seen:
            seen.append(tk)
        if len(seen) >= max_unique_tickers:
            break

    out = []
    for t in trades:
        t2 = dict(t)
        tk = (t.get("ticker") or "").upper()
        td = t.get("transaction_date") or t.get("trade_date")
        if tk in seen and td:
            perf = trade_performance(
                tk,
                td,
                value_min=t.get("amount_min") or t.get("value_min"),
                value_max=t.get("amount_max") or t.get("value_max"),
                transaction_type=t.get("transaction_type") or "buy",
                chart_points=24,
            )
            t2["market"] = perf
            t2["current_price"] = perf.get("price_now")
            t2["price_change_pct"] = perf.get("change_pct")
            t2["shares_est"] = (perf.get("shares") or {}).get("shares_est")
            t2["pnl_mid_est"] = perf.get("pnl_mid_est")
        else:
            t2["market"] = None
        out.append(t2)
    return out
