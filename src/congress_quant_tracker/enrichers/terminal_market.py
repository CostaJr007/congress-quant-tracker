"""GMT terminal market feed — yfinance bulk quotes shaped for LIVE adapter schema.

Produces datasets matching kimi_gmt_terminal fixtures:
  tape | stocks | aapl60 | metals | sectors | news | quotes | meta

Never fabricates news. News stays DEMO-labeled fixtures unless Tavily is configured.
All prices disclose source=yfinance and as-of timestamps.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
except ImportError:
    yf = None

# ─── Universe definitions ──────────────────────────────────────────────

# Display sym → Yahoo ticker
TAPE_MAP: list[dict[str, str]] = [
    {"sym": "SPX", "yf": "^GSPC", "name": "S&P 500", "kind": "INDEX", "src": "S&P / Yahoo", "ccy": "USD", "tz": "America/New_York", "region": "AMERICAS"},
    {"sym": "IXIC", "yf": "^IXIC", "name": "NASDAQ Comp", "kind": "INDEX", "src": "Nasdaq / Yahoo", "ccy": "USD", "tz": "America/New_York", "region": "AMERICAS"},
    {"sym": "DJI", "yf": "^DJI", "name": "Dow Jones", "kind": "INDEX", "src": "S&P / Yahoo", "ccy": "USD", "tz": "America/New_York", "region": "AMERICAS"},
    {"sym": "STOXX50E", "yf": "^STOXX50E", "name": "STOXX 50", "kind": "INDEX", "src": "STOXX / Yahoo", "ccy": "EUR", "tz": "Europe/Berlin", "region": "EUROPE"},
    {"sym": "FTSE", "yf": "^FTSE", "name": "FTSE 100", "kind": "INDEX", "src": "FTSE / Yahoo", "ccy": "GBP", "tz": "Europe/London", "region": "EUROPE"},
    {"sym": "N225", "yf": "^N225", "name": "Nikkei 225", "kind": "INDEX", "src": "Nikkei / Yahoo", "ccy": "JPY", "tz": "Asia/Tokyo", "region": "APAC"},
    {"sym": "HSI", "yf": "^HSI", "name": "Hang Seng", "kind": "INDEX", "src": "HSI / Yahoo", "ccy": "HKD", "tz": "Asia/Hong_Kong", "region": "APAC"},
    {"sym": "SSE", "yf": "000001.SS", "name": "SSE Composite", "kind": "INDEX", "src": "SSE / Yahoo", "ccy": "CNY", "tz": "Asia/Shanghai", "region": "APAC"},
    {"sym": "XAU", "yf": "GC=F", "name": "Gold Spot*", "kind": "METAL", "src": "COMEX GC=F proxy", "ccy": "USD", "tz": "Etc/UTC", "region": "METALS"},
    {"sym": "WTI", "yf": "CL=F", "name": "WTI Crude", "kind": "COMMODITY", "src": "NYMEX CL=F", "ccy": "USD", "tz": "America/New_York", "region": "COMMODITY"},
    {"sym": "DXY", "yf": "DX-Y.NYB", "name": "US Dollar Idx", "kind": "FX", "src": "ICE / Yahoo", "ccy": "USD", "tz": "America/New_York", "region": "FX"},
]

STOCK_UNIVERSE: list[dict[str, str]] = [
    # AI / TECH (expanded from Kimi market-dashboard + megacaps)
    {"t": "NVDA", "name": "NVIDIA Corp", "sector": "AI-TECH", "sub": "SEMIS"},
    {"t": "MSFT", "name": "Microsoft Corp", "sector": "AI-TECH", "sub": "MEGACAP"},
    {"t": "AAPL", "name": "Apple Inc", "sector": "AI-TECH", "sub": "MEGACAP"},
    {"t": "GOOGL", "name": "Alphabet Inc A", "sector": "AI-TECH", "sub": "MEGACAP"},
    {"t": "META", "name": "Meta Platforms", "sector": "AI-TECH", "sub": "MEGACAP"},
    {"t": "AVGO", "name": "Broadcom Inc", "sector": "AI-TECH", "sub": "SEMIS"},
    {"t": "AMD", "name": "Adv Micro Devices", "sector": "AI-TECH", "sub": "SEMIS"},
    {"t": "TSM", "name": "TSMC ADR", "sector": "AI-TECH", "sub": "SEMIS"},
    {"t": "ASML", "name": "ASML Holding ADR", "sector": "AI-TECH", "sub": "SEMIS"},
    {"t": "ORCL", "name": "Oracle Corp", "sector": "AI-TECH", "sub": "SOFTWARE"},
    {"t": "CRM", "name": "Salesforce Inc", "sector": "AI-TECH", "sub": "SOFTWARE"},
    {"t": "PLTR", "name": "Palantir Tech", "sector": "AI-TECH", "sub": "SOFTWARE"},
    {"t": "MU", "name": "Micron Technology", "sector": "AI-TECH", "sub": "SEMIS"},
    {"t": "INTC", "name": "Intel Corp", "sector": "AI-TECH", "sub": "SEMIS"},
    {"t": "QCOM", "name": "Qualcomm Inc", "sector": "AI-TECH", "sub": "SEMIS"},
    {"t": "AMAT", "name": "Applied Materials", "sector": "AI-TECH", "sub": "SEMIS"},
    {"t": "LRCX", "name": "Lam Research", "sector": "AI-TECH", "sub": "SEMIS"},
    {"t": "KLAC", "name": "KLA Corp", "sector": "AI-TECH", "sub": "SEMIS"},
    {"t": "SNPS", "name": "Synopsys Inc", "sector": "AI-TECH", "sub": "SOFTWARE"},
    {"t": "CDNS", "name": "Cadence Design", "sector": "AI-TECH", "sub": "SOFTWARE"},
    {"t": "ANSS", "name": "Ansys Inc", "sector": "AI-TECH", "sub": "SOFTWARE"},
    {"t": "AMZN", "name": "Amazon.com", "sector": "AI-TECH", "sub": "MEGACAP"},
    {"t": "TSLA", "name": "Tesla Inc", "sector": "AI-TECH", "sub": "MEGACAP"},
    # ENERGY
    {"t": "XOM", "name": "Exxon Mobil", "sector": "ENERGY", "sub": "INTEGRATED"},
    {"t": "CVX", "name": "Chevron Corp", "sector": "ENERGY", "sub": "INTEGRATED"},
    {"t": "COP", "name": "ConocoPhillips", "sector": "ENERGY", "sub": "INTEGRATED"},
    {"t": "SLB", "name": "SLB Ltd", "sector": "ENERGY", "sub": "SERVICES"},
    {"t": "EOG", "name": "EOG Resources", "sector": "ENERGY", "sub": "E&P"},
    {"t": "OXY", "name": "Occidental Pete", "sector": "ENERGY", "sub": "E&P"},
    {"t": "MPC", "name": "Marathon Pete", "sector": "ENERGY", "sub": "REFINING"},
    {"t": "PSX", "name": "Phillips 66", "sector": "ENERGY", "sub": "REFINING"},
    {"t": "VLO", "name": "Valero Energy", "sector": "ENERGY", "sub": "REFINING"},
    {"t": "KMI", "name": "Kinder Morgan", "sector": "ENERGY", "sub": "MIDSTREAM"},
    {"t": "WMB", "name": "Williams Cos", "sector": "ENERGY", "sub": "MIDSTREAM"},
    {"t": "OKE", "name": "ONEOK Inc", "sector": "ENERGY", "sub": "MIDSTREAM"},
    {"t": "HAL", "name": "Halliburton", "sector": "ENERGY", "sub": "SERVICES"},
    {"t": "BKR", "name": "Baker Hughes", "sector": "ENERGY", "sub": "SERVICES"},
    {"t": "DVN", "name": "Devon Energy", "sector": "ENERGY", "sub": "E&P"},
    {"t": "FANG", "name": "Diamondback", "sector": "ENERGY", "sub": "E&P"},
    # FINANCIALS
    {"t": "JPM", "name": "JPMorgan Chase", "sector": "FINANCIALS", "sub": "BANKS"},
    {"t": "BAC", "name": "Bank of America", "sector": "FINANCIALS", "sub": "BANKS"},
    {"t": "GS", "name": "Goldman Sachs", "sector": "FINANCIALS", "sub": "CAP MKTS"},
    {"t": "MS", "name": "Morgan Stanley", "sector": "FINANCIALS", "sub": "CAP MKTS"},
    {"t": "WFC", "name": "Wells Fargo", "sector": "FINANCIALS", "sub": "BANKS"},
    {"t": "BLK", "name": "BlackRock Inc", "sector": "FINANCIALS", "sub": "CAP MKTS"},
    {"t": "V", "name": "Visa Inc A", "sector": "FINANCIALS", "sub": "PAYMENTS"},
    {"t": "MA", "name": "Mastercard A", "sector": "FINANCIALS", "sub": "PAYMENTS"},
    {"t": "AXP", "name": "American Express", "sector": "FINANCIALS", "sub": "PAYMENTS"},
    {"t": "C", "name": "Citigroup Inc", "sector": "FINANCIALS", "sub": "BANKS"},
    {"t": "SCHW", "name": "Charles Schwab", "sector": "FINANCIALS", "sub": "CAP MKTS"},
    {"t": "PYPL", "name": "PayPal Holdings", "sector": "FINANCIALS", "sub": "PAYMENTS"},
    {"t": "USB", "name": "US Bancorp", "sector": "FINANCIALS", "sub": "BANKS"},
    {"t": "PNC", "name": "PNC Financial", "sector": "FINANCIALS", "sub": "BANKS"},
    {"t": "TFC", "name": "Truist Financial", "sector": "FINANCIALS", "sub": "BANKS"},
    {"t": "COF", "name": "Capital One", "sector": "FINANCIALS", "sub": "BANKS"},
    {"t": "BK", "name": "Bank of NY Mellon", "sector": "FINANCIALS", "sub": "BANKS"},
]

METAL_MAP: list[dict[str, str]] = [
    {"sym": "XAU", "yf": "GC=F", "name": "Gold (COMEX)", "unit": "USD/t oz", "ccy": "USD"},
    {"sym": "XAG", "yf": "SI=F", "name": "Silver (COMEX)", "unit": "USD/t oz", "ccy": "USD"},
    {"sym": "XPT", "yf": "PL=F", "name": "Platinum (NYMEX)", "unit": "USD/t oz", "ccy": "USD"},
    {"sym": "XPD", "yf": "PA=F", "name": "Palladium (NYMEX)", "unit": "USD/t oz", "ccy": "USD"},
]

CONVENTION = (
    "LIVE via yfinance (Yahoo Finance public quotes). "
    "US equities: auto_adjust=True (split/div adjusted closes). "
    "Indices: Yahoo index levels, not tradable ETFs. "
    "Metals: continuous futures (GC=F/SI=F/PL=F/PA=F) used as spot proxies — "
    "Gold/Silver ratio and spreads use homogeneous futures definitions. "
    "Sessions: weekday bars only; no holiday calendar fill. "
    "Delayed quotes typical 0–15 min. Not investment advice."
)

# TTL caches
_cache: dict[str, dict[str, Any]] = {}
_CACHE_TTL = 120  # 2 min for terminal quotes
_HIST_TTL = 600  # 10 min for history series


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _enabled() -> bool:
    if yf is None:
        return False
    try:
        from congress_quant_tracker.config import settings
        if getattr(settings, "MARKET_DATA_ENABLED", True) is False:
            return False
    except Exception:
        pass
    return True


def _cache_get(key: str, ttl: float = _CACHE_TTL) -> Optional[Any]:
    ent = _cache.get(key)
    if not ent:
        return None
    if time.time() - ent["at"] > ttl:
        return None
    return ent["data"]


def _cache_set(key: str, data: Any) -> None:
    _cache[key] = {"at": time.time(), "data": data}


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _bars_from_ohlcv_frame(frame) -> list[dict]:
    """Parse a single-ticker OHLCV DataFrame (flat or MultiIndex columns) into bar dicts."""
    rows: list[dict] = []
    if frame is None or getattr(frame, "empty", True):
        return rows
    try:
        frame = frame.copy()
        if hasattr(frame.columns, "nlevels") and frame.columns.nlevels > 1:
            # Prefer the level that contains OHLCV field names
            lvl0 = [str(x).lower() for x in frame.columns.get_level_values(0)]
            price_names = {"open", "high", "low", "close", "volume", "adj close"}
            if any(x in price_names for x in lvl0):
                frame.columns = [c[0] if isinstance(c, tuple) else c for c in frame.columns]
            else:
                # group_by=ticker → (Ticker, Price)
                frame.columns = [c[1] if isinstance(c, tuple) else c for c in frame.columns]
        # normalize column names
        rename = {c: str(c).strip().title() if str(c).lower() != "adj close" else "Close" for c in frame.columns}
        # Title-case Open/High/Low/Close/Volume
        fixed = {}
        for c in frame.columns:
            cl = str(c).lower()
            if cl in ("open", "high", "low", "close", "volume"):
                fixed[c] = cl.capitalize() if cl != "volume" else "Volume"
            elif cl in ("adj close", "adjclose"):
                fixed[c] = "Close"
            else:
                fixed[c] = c
        frame = frame.rename(columns=fixed)
    except Exception as e:
        logger.debug("column normalize: %s", e)

    for idx, row in frame.iterrows():
        try:
            d = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])
        except Exception:
            continue
        close = _safe_float(row["Close"]) if "Close" in row.index else None
        if close is None:
            continue
        o = _safe_float(row["Open"]) if "Open" in row.index else None
        h = _safe_float(row["High"]) if "High" in row.index else None
        l = _safe_float(row["Low"]) if "Low" in row.index else None
        vol = None
        if "Volume" in row.index:
            try:
                vf = float(row["Volume"])
                if vf == vf:
                    vol = int(vf)
            except Exception:
                pass
        rows.append({
            "date": d.isoformat(),
            "open": o, "high": h, "low": l, "close": close, "volume": vol,
        })
    return rows


def _download_history(tickers: list[str], days: int = 100) -> dict[str, list[dict]]:
    """Batch download daily OHLCV. Returns {yahoo_ticker: [bars]}."""
    if not _enabled() or not tickers:
        return {}

    key = "hist:" + ",".join(sorted(tickers)) + f":{days}"
    cached = _cache_get(key, _HIST_TTL)
    if cached is not None:
        return cached

    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=days + 20)
    out: dict[str, list[dict]] = {t: [] for t in tickers}

    try:
        df = yf.download(
            tickers=tickers if len(tickers) > 1 else tickers[0],
            start=start.isoformat(),
            end=end.isoformat(),
            progress=False,
            auto_adjust=True,
            threads=False,
            group_by="ticker",
        )
    except Exception as e:
        logger.warning("yfinance batch download failed: %s", e)
        return out

    if df is None or df.empty:
        return out

    try:
        if len(tickers) == 1:
            out[tickers[0]] = _bars_from_ohlcv_frame(df)
        else:
            cols = df.columns
            if hasattr(cols, "nlevels") and cols.nlevels > 1:
                level0 = set(str(x) for x in cols.get_level_values(0))
                if any(t in level0 for t in tickers):
                    for t in tickers:
                        try:
                            out[t] = _bars_from_ohlcv_frame(df[t])
                        except Exception:
                            out[t] = []
                else:
                    for t in tickers:
                        try:
                            out[t] = _bars_from_ohlcv_frame(df.xs(t, axis=1, level=1))
                        except Exception:
                            out[t] = []
            else:
                out[tickers[0]] = _bars_from_ohlcv_frame(df)
    except Exception as e:
        logger.warning("parse batch history: %s", e)

    # Fallback: per-ticker history if batch left empties
    for t in tickers:
        if out.get(t):
            continue
        try:
            th = yf.Ticker(t).history(
                start=start.isoformat(),
                end=end.isoformat(),
                auto_adjust=True,
            )
            out[t] = _bars_from_ohlcv_frame(th)
        except Exception as e:
            logger.debug("fallback history %s: %s", t, e)

    _cache_set(key, out)
    return out


def _quote_from_bars(bars: list[dict]) -> Optional[dict]:
    if not bars or len(bars) < 1:
        return None
    last = bars[-1]
    prev = bars[-2] if len(bars) >= 2 else last
    last_c = last["close"]
    prev_c = prev["close"]
    if last_c is None or prev_c is None or prev_c == 0:
        return None
    chg = last_c - prev_c
    chg_pct = (chg / prev_c) * 100.0
    return {
        "last": round(last_c, 4),
        "prevClose": round(prev_c, 4),
        "chg": round(chg, 4),
        "chgPct": round(chg_pct, 2),
        "open": round(last["open"], 4) if last.get("open") is not None else None,
        "high": round(last["high"], 4) if last.get("high") is not None else None,
        "low": round(last["low"], 4) if last.get("low") is not None else None,
        "volume": last.get("volume"),
        "date": last["date"],
    }


def _market_state(tz_name: str) -> str:
    """Coarse OPEN/CLOSED for display (US-centric cash hours heuristic)."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(tz_name))
    except Exception:
        return "UNKNOWN"
    # Weekends closed
    if now.weekday() >= 5:
        return "CLOSED"
    # Asia cash ~9:00–15:00 local (rough)
    if tz_name in ("Asia/Tokyo", "Asia/Hong_Kong", "Asia/Shanghai"):
        hm = now.hour * 60 + now.minute
        if 9 * 60 <= hm < 11 * 60 + 30:
            return "OPEN"
        if 11 * 60 + 30 <= hm < 12 * 60 + 30 and tz_name != "Asia/Tokyo":
            return "LUNCH"
        if 12 * 60 + 30 <= hm < 15 * 60 + 30:
            return "OPEN"
        if 8 * 60 <= hm < 9 * 60:
            return "PRE"
        return "CLOSED"
    if tz_name in ("Europe/London", "Europe/Berlin"):
        hm = now.hour * 60 + now.minute
        if 8 * 60 <= hm < 16 * 60 + 30:
            return "OPEN"
        if 7 * 60 <= hm < 8 * 60:
            return "PRE"
        return "CLOSED"
    if tz_name == "America/New_York":
        hm = now.hour * 60 + now.minute
        if 9 * 60 + 30 <= hm < 16 * 60:
            return "OPEN"
        if 4 * 60 <= hm < 9 * 60 + 30:
            return "PRE"
        return "CLOSED"
    return "OPEN" if 0 <= now.hour < 22 else "CLOSED"


def build_tape() -> list[dict]:
    yf_list = [x["yf"] for x in TAPE_MAP]
    hist = _download_history(yf_list, days=10)
    asof = _now_iso()
    rows = []
    for meta in TAPE_MAP:
        q = _quote_from_bars(hist.get(meta["yf"], []))
        if not q:
            continue
        rows.append({
            "sym": meta["sym"],
            "name": meta["name"],
            "kind": meta["kind"],
            "src": meta["src"],
            "ccy": meta["ccy"],
            "last": q["last"],
            "chg": q["chg"],
            "chgPct": q["chgPct"],
            "prevClose": q["prevClose"],
            "state": _market_state(meta["tz"]),
            "tz": meta["tz"],
            "region": meta["region"],
            "asof": asof,
        })
    return rows


def build_stocks() -> list[dict]:
    tickers = [s["t"] for s in STOCK_UNIVERSE]
    hist = _download_history(tickers, days=15)
    rows = []
    for meta in STOCK_UNIVERSE:
        bars = hist.get(meta["t"], [])
        q = _quote_from_bars(bars)
        if not q:
            continue
        mkt_cap = None
        # rough mktCap from last * shares if we had it — leave None; area uses |CHG%|
        rows.append({
            "t": meta["t"],
            "name": meta["name"],
            "sector": meta["sector"],
            "sub": meta["sub"],
            "prevClose": q["prevClose"],
            "chgPct": q["chgPct"],
            "open": q["open"] if q["open"] is not None else q["prevClose"],
            "high": q["high"] if q["high"] is not None else q["last"],
            "low": q["low"] if q["low"] is not None else q["last"],
            "last": q["last"],
            "chg": q["chg"],
            "volume": q["volume"] or 0,
            "mktCap": mkt_cap,
        })
    return rows


def build_aapl60() -> list[dict]:
    hist = _download_history(["AAPL"], days=120)
    bars = hist.get("AAPL", [])
    # last 60 valid sessions
    last60 = bars[-60:] if len(bars) >= 60 else bars
    return [
        {
            "d": b["date"],
            "o": round(b["open"], 2) if b.get("open") is not None else round(b["close"], 2),
            "h": round(b["high"], 2) if b.get("high") is not None else round(b["close"], 2),
            "l": round(b["low"], 2) if b.get("low") is not None else round(b["close"], 2),
            "c": round(b["close"], 2),
            "v": b.get("volume") or 0,
        }
        for b in last60
    ]


def build_metals() -> list[dict]:
    yf_list = [m["yf"] for m in METAL_MAP]
    hist = _download_history(yf_list, days=120)
    asof = _now_iso()
    out = []
    for meta in METAL_MAP:
        bars = hist.get(meta["yf"], [])
        q = _quote_from_bars(bars)
        if not q:
            continue
        last60 = bars[-60:] if len(bars) >= 60 else bars
        series = [
            {
                "d": b["date"],
                "c": round(b["close"], 2),
                "h": round(b["high"], 2) if b.get("high") is not None else round(b["close"], 2),
                "l": round(b["low"], 2) if b.get("low") is not None else round(b["close"], 2),
            }
            for b in last60
        ]
        out.append({
            "sym": meta["sym"],
            "name": meta["name"],
            "unit": meta["unit"],
            "ccy": meta["ccy"],
            "last": q["last"],
            "chg": q["chg"],
            "chgPct": q["chgPct"],
            "prevClose": q["prevClose"],
            "asof": asof,
            "series": series,
            "definition": f"Yahoo {meta['yf']} continuous futures used as spot proxy",
        })
    return out


def build_sectors(stocks: Optional[list[dict]] = None) -> list[dict]:
    """Equal-weight sector avg change + synthetic 24-point path from open→last."""
    stocks = stocks if stocks is not None else build_stocks()
    asof = _now_iso()
    by_sec: dict[str, list[float]] = {"AI-TECH": [], "ENERGY": [], "FINANCIALS": []}
    for s in stocks:
        sec = s.get("sector")
        if sec in by_sec and s.get("chgPct") is not None:
            by_sec[sec].append(float(s["chgPct"]))

    out = []
    for sec, vals in by_sec.items():
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        # linear ramp open=0 → avg at end, 24 samples
        points = [round(avg * (i / 23.0), 3) for i in range(24)]
        out.append({
            "sector": sec,
            "avg": round(avg, 2),
            "n": len(vals),
            "weighting": "equal-weight",
            "baseline": "open=0%",
            "points": points,
            "asof": asof,
            "note": "Intraday path is linear interpolation of session % change (not true tick VWAP).",
        })
    return out


def build_news_demo_labeled() -> list[dict]:
    """Return no fabricated news — empty list; UI falls back to DEMO fixtures via hub on empty optional.

    Spec: never fabricate. We expose empty live news so DEMO adapter supplies labeled fixtures
    only when the hub falls back; for partial live we return [] and widgets show empty / demo banner.
    """
    # Prefer returning empty so frontend DEMO fixtures stay the source of demo headlines.
    # Hub only falls back on error; so we return a tiny DEMO-labeled set with explicit flags
    # so LIVE mode still has a wire without claiming real APIs.
    asof = _now_iso()
    return [
        {
            "id": "live-info-1",
            "time": asof,
            "cat": "MACRO",
            "headline": "[LIVE FEED] Price data via yfinance — news wire remains DEMO fixtures only",
            "source": "DEMO WIRE",
            "demo": True,
            "summary": (
                "Live market quotes are served from Yahoo Finance via yfinance. "
                "Headline news is not available from a licensed wire in this build. "
                "This notice is labeled DEMO so it is never mistaken for a real report."
            ),
            "link": "#demo-news",
            "tickers": [],
            "linkedMove": "n/a",
            "asof": asof,
        }
    ]


def build_meta() -> dict:
    return {
        "name": "GMT // GLOBAL MARKET TERMINAL",
        "fixturesVersion": "live-yfinance-1.0",
        "generatedAt": _now_iso(),
        "demoAsOf": _now_iso(),
        "metalsAsOf": _now_iso(),
        "convention": CONVENTION,
        "source": "yfinance",
        "aapl52w": None,
    }


def get_dataset(dataset: str) -> dict[str, Any]:
    """Return {data, asof, convention} for LIVE adapter.

    Raises RuntimeError if yfinance disabled or dataset fails completely.
    """
    if not _enabled():
        raise RuntimeError("yfinance unavailable or MARKET_DATA_ENABLED=0")

    ds = (dataset or "tape").lower().strip()
    asof = _now_iso()

    # full payload cache (2 min)
    ck = f"ds:{ds}"
    cached = _cache_get(ck, _CACHE_TTL)
    if cached is not None:
        return cached

    if ds in ("tape", "quotes"):
        data = build_tape()
        if not data:
            raise RuntimeError("tape empty — yfinance returned no index quotes")
    elif ds == "stocks":
        data = build_stocks()
        if not data:
            raise RuntimeError("stocks empty")
    elif ds == "aapl60":
        data = build_aapl60()
        if len(data) < 5:
            raise RuntimeError("aapl60 insufficient sessions")
    elif ds == "metals":
        data = build_metals()
        if len(data) < 2:
            raise RuntimeError("metals insufficient")
    elif ds == "sectors":
        stocks = build_stocks()
        data = build_sectors(stocks)
        if not data:
            raise RuntimeError("sectors empty")
    elif ds == "news":
        data = build_news_demo_labeled()
    elif ds == "meta":
        data = [build_meta()]
    else:
        raise RuntimeError(f"unknown dataset {dataset}")

    payload = {
        "data": data,
        "asof": asof,
        "convention": CONVENTION,
        "source": "yfinance",
        "mode": "LIVE",
    }
    _cache_set(ck, payload)
    return payload


def health() -> dict[str, Any]:
    return {
        "yfinance_installed": yf is not None,
        "enabled": _enabled(),
        "cache_keys": list(_cache.keys()),
        "convention": CONVENTION,
    }
