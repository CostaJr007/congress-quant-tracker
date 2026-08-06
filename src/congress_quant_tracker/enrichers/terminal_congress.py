"""Congress intel payloads for CI://TERMINAL (Bloomberg desk merge).

Shapes are optimized for dense terminal widgets:
  wire | holders | sector | politician | summary | sectors
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import case, desc, func, or_

from congress_quant_tracker.database.models import Company, Politician, Trade

logger = logging.getLogger(__name__)

# Fallback sector map when Trade.sector / Company.sector are empty (common in this DB).
# Keys uppercase tickers → sector label used by SECTOR DESK.
TICKER_SECTOR: dict[str, str] = {
    # Tech / AI
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology", "GOOGL": "Technology",
    "GOOG": "Technology", "META": "Technology", "AMZN": "Technology", "AMD": "Technology",
    "AVGO": "Technology", "TSM": "Technology", "ASML": "Technology", "ORCL": "Technology",
    "CRM": "Technology", "PLTR": "Technology", "MU": "Technology", "INTC": "Technology",
    "TSLA": "Technology", "NFLX": "Technology", "ADBE": "Technology", "CSCO": "Technology",
    "QCOM": "Technology", "IBM": "Technology", "NOW": "Technology", "SNOW": "Technology",
    "PANW": "Technology", "CRWD": "Technology", "NET": "Technology", "SHOP": "Technology",
    "QCOM": "Technology", "AMAT": "Technology", "LRCX": "Technology", "KLAC": "Technology",
    "SNPS": "Technology", "CDNS": "Technology", "ANSS": "Technology", "AMZN": "Technology",
    "TSLA": "Technology", "NFLX": "Technology", "ADBE": "Technology", "CSCO": "Technology",
    "IBM": "Technology", "NOW": "Technology", "SNOW": "Technology",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy", "EOG": "Energy",
    "OXY": "Energy", "MPC": "Energy", "PSX": "Energy", "VLO": "Energy", "KMI": "Energy",
    "WMB": "Energy", "HAL": "Energy", "BKR": "Energy", "DVN": "Energy", "FANG": "Energy",
    "OKE": "Energy",
    # Financials
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials", "MS": "Financials",
    "WFC": "Financials", "BLK": "Financials", "V": "Financials", "MA": "Financials",
    "AXP": "Financials", "C": "Financials", "SCHW": "Financials", "PYPL": "Financials",
    "BRK.B": "Financials", "BRKB": "Financials", "USB": "Financials", "PNC": "Financials",
    "COF": "Financials", "TFC": "Financials", "SPGI": "Financials", "BK": "Financials",
    # Healthcare
    "UNH": "Healthcare", "JNJ": "Healthcare", "LLY": "Healthcare", "PFE": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare", "TMO": "Healthcare", "ABT": "Healthcare",
    # Consumer
    "HD": "Consumer", "WMT": "Consumer", "COST": "Consumer", "MCD": "Consumer",
    "NKE": "Consumer", "SBUX": "Consumer", "TGT": "Consumer", "LOW": "Consumer",
    # Industrials / other
    "BA": "Industrials", "CAT": "Industrials", "GE": "Industrials", "HON": "Industrials",
    "LMT": "Industrials", "RTX": "Industrials", "UPS": "Industrials",
    "LTH": "Consumer", "CHRW": "Industrials", "STE": "Healthcare",
}


def resolve_sector(ticker: Optional[str], trade_sector: Optional[str] = None, company_sector: Optional[str] = None) -> Optional[str]:
    if trade_sector and str(trade_sector).strip():
        return str(trade_sector).strip()
    if company_sector and str(company_sector).strip():
        return str(company_sector).strip()
    if ticker:
        return TICKER_SECTOR.get(ticker.upper().strip())
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _state_district(pol: Optional[Politician]) -> str:
    if not pol:
        return ""
    if pol.district:
        return f"{pol.state}-{pol.district}" if pol.state else str(pol.district)
    return pol.state or ""


def trade_row(trade: Trade, pol: Optional[Politician] = None) -> dict[str, Any]:
    pol = pol or trade.politician
    side = "BUY" if (trade.transaction_type or "").lower() in ("buy", "purchase", "p") else "SELL"
    return {
        "id": trade.id,
        "ticker": (trade.ticker or "").upper() or None,
        "asset": trade.asset_name,
        "side": side,
        "transaction_type": side,
        "trade_date": str(trade.trade_date) if trade.trade_date else None,
        "filing_date": str(trade.filing_date) if trade.filing_date else None,
        "amount_min": trade.value_min,
        "amount_max": trade.value_max,
        "amount": trade.value_range,
        "score": trade.score or 0,
        "tag": trade.tag or "routine",
        "sector": trade.sector,
        "owner": trade.owner,
        "pdf_url": trade.pdf_url,
        "politician": pol.name if pol else None,
        "party": pol.party if pol else None,
        "chamber": (pol.chamber.title() if pol and pol.chamber else None),
        "state_district": _state_district(pol),
        "bioguide_id": pol.bioguide_id if pol else None,
        "photo_url": (
            pol.photo_url
            or (f"/politicians/{pol.bioguide_id}.jpg" if pol and pol.bioguide_id else None)
        ),
        # market enrich (optional)
        "price_change_pct": None,
        "shares_est": None,
        "pnl_mid_est": None,
        "price_now": None,
        "price_at_trade": None,
    }


def build_months(session, by: str = "filing") -> dict[str, Any]:
    """Months with trades, newest first — same idea as /api/trades/months."""
    from sqlalchemy import extract

    col = Trade.trade_date if (by or "").lower() == "trade" else Trade.filing_date
    rows = (
        session.query(
            extract("year", col).label("y"),
            extract("month", col).label("m"),
            func.count(Trade.id),
        )
        .filter(col.isnot(None))
        .group_by("y", "m")
        .order_by(desc("y"), desc("m"))
        .all()
    )
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    months = []
    for y, m, count in rows:
        if y is None or m is None:
            continue
        yi, mi = int(y), int(m)
        months.append({
            "month": f"{yi:04d}-{mi:02d}",
            "year": yi,
            "month_num": mi,
            "label": f"{names[mi - 1]} {yi}",
            "count": int(count),
        })
    return {
        "data": months,
        "by": "trade" if (by or "").lower() == "trade" else "filing",
        "asof": _now_iso(),
        "mode": "LIVE",
        "source": "sqlite",
    }


def build_wire(
    session,
    *,
    limit: int = 120,
    offset: int = 0,
    chamber: Optional[str] = None,
    party: Optional[str] = None,
    side: Optional[str] = None,
    month: Optional[str] = None,
    date_field: str = "filing",
    q: Optional[str] = None,
    tag: Optional[str] = None,
    min_score: Optional[int] = None,
    enrich: bool = False,
) -> dict[str, Any]:
    date_col = Trade.trade_date if (date_field or "").lower() == "trade" else Trade.filing_date
    order_cols = (
        [desc(Trade.trade_date), desc(Trade.filing_date), desc(Trade.id)]
        if (date_field or "").lower() == "trade"
        else [desc(Trade.filing_date), desc(Trade.trade_date), desc(Trade.id)]
    )
    query = (
        session.query(Trade)
        .join(Politician, Politician.id == Trade.politician_id)
        .order_by(*order_cols)
    )
    if chamber:
        ch = chamber.lower().strip()
        if ch in ("house", "senate"):
            query = query.filter(Politician.chamber == ch)
    if party:
        p = party.upper().strip()
        if p in ("D", "R", "I", "DEMOCRAT", "REPUBLICAN", "INDEPENDENT"):
            if p.startswith("DEM"):
                p = "D"
            elif p.startswith("REP"):
                p = "R"
            elif p.startswith("IND"):
                p = "I"
            query = query.filter(Politician.party == p)
    if side:
        s = side.lower().strip()
        if s in ("buy", "purchase"):
            query = query.filter(Trade.transaction_type == "buy")
        elif s in ("sell", "sale"):
            query = query.filter(Trade.transaction_type == "sell")
    if tag:
        query = query.filter(Trade.tag == tag.lower().strip())
    if min_score is not None:
        query = query.filter(Trade.score >= int(min_score))
    if month and len(month) >= 7:
        # YYYY-MM
        try:
            y = int(month[:4])
            m = int(month[5:7])
            from sqlalchemy import extract
            query = query.filter(
                date_col.isnot(None),
                extract("year", date_col) == y,
                extract("month", date_col) == m,
            )
        except ValueError:
            pass
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Trade.ticker.ilike(like),
                Trade.asset_name.ilike(like),
                Politician.name.ilike(like),
            )
        )

    total = query.count()
    trades = query.offset(max(0, offset)).limit(min(limit, 300)).all()
    rows = [trade_row(t) for t in trades]

    if enrich and rows:
        try:
            from congress_quant_tracker.enrichers.market_data import enrich_trades_batch

            enriched = enrich_trades_batch(
                [
                    {
                        "id": r["id"],
                        "ticker": r["ticker"],
                        "transaction_date": r["trade_date"],
                        "amount_min": r["amount_min"],
                        "amount_max": r["amount_max"],
                        "transaction_type": "buy" if r["side"] == "BUY" else "sell",
                    }
                    for r in rows
                ],
                max_unique_tickers=12,
            )
            by_id = {e.get("id"): e for e in enriched}
            for r in rows:
                e = by_id.get(r["id"]) or {}
                mkt = e.get("market") or {}
                r["price_change_pct"] = e.get("price_change_pct") or mkt.get("change_pct")
                sh = e.get("shares_est")
                if sh is None and isinstance(mkt.get("shares"), dict):
                    sh = mkt["shares"].get("shares_est")
                r["shares_est"] = sh
                r["pnl_mid_est"] = e.get("pnl_mid_est") or mkt.get("pnl_mid_est")
                r["price_now"] = e.get("current_price") or mkt.get("price_now")
                r["price_at_trade"] = mkt.get("price_at_trade")
        except Exception as ex:
            logger.debug("wire enrich skip: %s", ex)

    # group key stats for UI
    by_pol: dict[str, int] = defaultdict(int)
    for r in rows:
        if r.get("politician"):
            by_pol[r["politician"]] += 1

    return {
        "data": rows,
        "asof": _now_iso(),
        "count": len(rows),
        "total": total,
        "offset": offset,
        "limit": limit,
        "month": month or "",
        "date_field": "trade" if (date_field or "").lower() == "trade" else "filing",
        "mode": "LIVE",
        "source": "sqlite congress disclosures",
        "convention": "Official House/Senate PTR ranges. Filter by month uses filing or trade date.",
        "group_counts": dict(by_pol),
    }


def build_holders(session, ticker: str) -> dict[str, Any]:
    ticker = (ticker or "").upper().strip()
    if not ticker:
        raise ValueError("ticker required")

    company = session.query(Company).filter(Company.ticker == ticker).first()
    trades = (
        session.query(Trade)
        .filter(Trade.ticker == ticker)
        .order_by(desc(Trade.trade_date), desc(Trade.id))
        .all()
    )

    by_pol: dict[int, dict[str, Any]] = {}
    for t in trades:
        pol = t.politician
        if not pol:
            continue
        ent = by_pol.get(pol.id)
        if not ent:
            ent = {
                "name": pol.name,
                "party": pol.party,
                "chamber": pol.chamber.title() if pol.chamber else None,
                "state_district": _state_district(pol),
                "bioguide_id": pol.bioguide_id,
                "photo_url": (
                    pol.photo_url
                    or (f"/politicians/{pol.bioguide_id}.jpg" if pol.bioguide_id else None)
                ),
                "trades": 0,
                "buys": 0,
                "sells": 0,
                "volume": 0,
                "last_side": None,
                "last_date": None,
                "last_score": None,
            }
            by_pol[pol.id] = ent
        ent["trades"] += 1
        ent["volume"] += t.value_max or 0
        if (t.transaction_type or "").lower() == "buy":
            ent["buys"] += 1
        else:
            ent["sells"] += 1
        td = str(t.trade_date) if t.trade_date else None
        if td and (ent["last_date"] is None or td > ent["last_date"]):
            ent["last_date"] = td
            ent["last_side"] = "BUY" if (t.transaction_type or "").lower() == "buy" else "SELL"
            ent["last_score"] = t.score or 0

    holders = sorted(by_pol.values(), key=lambda x: (-x["trades"], -x["volume"]))
    house = sum(1 for h in holders if (h.get("chamber") or "").lower() == "house")
    senate = sum(1 for h in holders if (h.get("chamber") or "").lower() == "senate")

    return {
        "data": {
            "ticker": ticker,
            "name": company.name if company else (trades[0].asset_name if trades else ticker),
            "sector": company.sector if company else (trades[0].sector if trades else None),
            "holders": holders,
            "unique_politicians": len(holders),
            "house_count": house,
            "senate_count": senate,
            "total_trades": len(trades),
            "total_volume": sum(t.value_max or 0 for t in trades),
        },
        "asof": _now_iso(),
        "mode": "LIVE",
        "source": "sqlite congress disclosures",
        "convention": "Holders = politicians with ≥1 disclosed trade on ticker (not current 13F holdings).",
    }


def list_sectors(session) -> dict[str, Any]:
    counts: dict[str, int] = defaultdict(int)
    # DB sectors if present
    rows = (
        session.query(Trade.sector, func.count(Trade.id))
        .filter(Trade.sector.isnot(None), Trade.sector != "")
        .group_by(Trade.sector)
        .all()
    )
    for sec, n in rows:
        if sec and str(sec).strip():
            counts[str(sec).strip()] += int(n or 0)

    # Ticker map fallback — count trades whose ticker maps to a known sector
    ticker_rows = (
        session.query(Trade.ticker, func.count(Trade.id))
        .filter(Trade.ticker.isnot(None), Trade.ticker != "")
        .group_by(Trade.ticker)
        .all()
    )
    for tk, n in ticker_rows:
        sec = resolve_sector(tk)
        if sec:
            counts[sec] += int(n or 0)

    sectors = [{"sector": k, "n": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]
    return {
        "data": sectors,
        "asof": _now_iso(),
        "mode": "LIVE",
        "source": "Trade.sector + static ticker→sector map (DB sectors often empty)",
        "convention": "Static map covers major US liquid names; unmapped tickers excluded from sector desk.",
    }


def build_sector(session, sector: str) -> dict[str, Any]:
    sector = (sector or "").strip()
    if not sector:
        secs = list_sectors(session)["data"]
        if not secs:
            return {
                "data": {"sector": None, "politicians": [], "tickers": [], "house_count": 0, "senate_count": 0},
                "asof": _now_iso(),
                "mode": "LIVE",
                "source": "sqlite",
            }
        sector = secs[0]["sector"]

    # Tickers that belong to this sector via map or DB
    map_tickers = {t for t, s in TICKER_SECTOR.items() if s == sector}
    company_tickers = {
        c.ticker
        for c in session.query(Company.ticker).filter(Company.sector == sector).all()
        if c.ticker
    }
    want = map_tickers | company_tickers

    q = session.query(Trade)
    if want:
        trades = q.filter(or_(Trade.sector == sector, Trade.ticker.in_(list(want)))).all()
    else:
        trades = q.filter(Trade.sector == sector).all()
    # also include any trade whose resolve_sector matches even if not in want (belt/suspenders)
    if not trades:
        all_t = session.query(Trade).filter(Trade.ticker.isnot(None)).limit(5000).all()
        trades = [t for t in all_t if resolve_sector(t.ticker, t.sector) == sector]

    by_pol: dict[int, dict] = {}
    by_ticker: dict[str, dict] = {}
    for t in trades:
        pol = t.politician
        if pol:
            ent = by_pol.get(pol.id)
            if not ent:
                ent = {
                    "name": pol.name,
                    "party": pol.party,
                    "chamber": pol.chamber.title() if pol.chamber else None,
                    "state_district": _state_district(pol),
                    "trades": 0,
                    "volume": 0,
                    "tickers": set(),
                }
                by_pol[pol.id] = ent
            ent["trades"] += 1
            ent["volume"] += t.value_max or 0
            if t.ticker:
                ent["tickers"].add(t.ticker.upper())
        if t.ticker:
            tk = t.ticker.upper()
            te = by_ticker.get(tk)
            if not te:
                te = {"ticker": tk, "trades": 0, "volume": 0, "pols": set()}
                by_ticker[tk] = te
            te["trades"] += 1
            te["volume"] += t.value_max or 0
            if pol:
                te["pols"].add(pol.name)

    politicians = []
    for ent in by_pol.values():
        politicians.append({
            **{k: v for k, v in ent.items() if k != "tickers"},
            "unique_tickers": len(ent["tickers"]),
            "ticker_list": sorted(ent["tickers"])[:12],
        })
    politicians.sort(key=lambda x: (-x["trades"], -x["volume"]))

    tickers = []
    for te in by_ticker.values():
        tickers.append({
            "ticker": te["ticker"],
            "trades": te["trades"],
            "volume": te["volume"],
            "unique_politicians": len(te["pols"]),
        })
    tickers.sort(key=lambda x: (-x["trades"], -x["volume"]))

    house = sum(1 for p in politicians if (p.get("chamber") or "").lower() == "house")
    senate = sum(1 for p in politicians if (p.get("chamber") or "").lower() == "senate")

    return {
        "data": {
            "sector": sector,
            "politicians": politicians[:60],
            "tickers": tickers[:40],
            "house_count": house,
            "senate_count": senate,
            "unique_politicians": len(politicians),
            "unique_tickers": len(tickers),
            "total_trades": len(trades),
        },
        "asof": _now_iso(),
        "mode": "LIVE",
        "source": "sqlite congress disclosures",
        "convention": "Sector from Trade.sector or Company.sector; overlap = shared sector activity, not portfolio weight.",
    }


def build_politician(session, name: str) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        # most active
        row = (
            session.query(Politician)
            .join(Trade)
            .group_by(Politician.id)
            .order_by(desc(func.count(Trade.id)))
            .first()
        )
        if not row:
            return {
                "data": None,
                "asof": _now_iso(),
                "mode": "LIVE",
                "source": "sqlite",
            }
        pol = row
    else:
        pol = (
            session.query(Politician)
            .filter(Politician.name.ilike(f"%{name}%"))
            .first()
        )
        if not pol:
            return {
                "data": None,
                "asof": _now_iso(),
                "mode": "LIVE",
                "error": f"politician not found: {name}",
                "source": "sqlite",
            }

    trades = (
        session.query(Trade)
        .filter(Trade.politician_id == pol.id)
        .order_by(desc(Trade.trade_date), desc(Trade.id))
        .all()
    )
    rows = [trade_row(t, pol) for t in trades[:200]]

    by_tk: dict[str, dict] = {}
    for t in trades:
        if not t.ticker:
            continue
        tk = t.ticker.upper()
        e = by_tk.get(tk)
        td = str(t.trade_date) if t.trade_date else None
        fd = str(t.filing_date) if t.filing_date else None
        side = "BUY" if (t.transaction_type or "").lower() == "buy" else "SELL"
        if not e:
            e = {
                "ticker": tk,
                "trades": 0,
                "buys": 0,
                "sells": 0,
                "volume": 0,
                "sector": t.sector or resolve_sector(tk),
                "last_trade_date": td,
                "last_filing_date": fd,
                "last_side": side,
                "first_trade_date": td,
            }
            by_tk[tk] = e
        e["trades"] += 1
        e["volume"] += t.value_max or 0
        if side == "BUY":
            e["buys"] += 1
        else:
            e["sells"] += 1
        if not e.get("sector"):
            e["sector"] = t.sector or resolve_sector(tk)
        # trades are ordered desc by trade_date — first seen = latest
        if td and (not e.get("last_trade_date") or td > e["last_trade_date"]):
            e["last_trade_date"] = td
            e["last_side"] = side
            if fd:
                e["last_filing_date"] = fd
        if td and (not e.get("first_trade_date") or td < e["first_trade_date"]):
            e["first_trade_date"] = td
        if fd and (not e.get("last_filing_date") or fd > (e.get("last_filing_date") or "")):
            # keep latest filing seen if trade date missing
            if not e.get("last_filing_date"):
                e["last_filing_date"] = fd

    tickers = sorted(by_tk.values(), key=lambda x: (-x["trades"], -x["volume"]))

    return {
        "data": {
            "name": pol.name,
            "party": pol.party,
            "chamber": pol.chamber.title() if pol.chamber else None,
            "state_district": _state_district(pol),
            "bioguide_id": pol.bioguide_id,
            "photo_url": pol.photo_url or (f"/politicians/{pol.bioguide_id}.jpg" if pol.bioguide_id else None),
            "trades_total": len(trades),
            "unique_tickers": len(tickers),
            "tickers": tickers[:50],
            "recent_trades": rows,
        },
        "asof": _now_iso(),
        "mode": "LIVE",
        "source": "sqlite congress disclosures",
    }


def build_returns_leaderboard(
    session,
    *,
    month: Optional[str] = None,
    date_field: str = "filing",
    side: Optional[str] = None,
    chamber: Optional[str] = None,
    mode: str = "trade",
    limit: int = 40,
    max_tickers: int = 36,
) -> dict[str, Any]:
    """Rank trades (or members) by estimated price return since trade date.

    Uses yfinance via trade_performance. Disk cache keeps repeats cheap.
    change_pct = underlying move since trade (BUY and SELL both show asset move).
    return_side_adj = +change for BUY, -change for SELL (benefit if sold then fell).
    pnl_mid_est = estimated $ using disclosure range midpoint.
    """
    from sqlalchemy import extract
    from congress_quant_tracker.enrichers.market_data import trade_performance

    date_col = Trade.trade_date if (date_field or "").lower() == "trade" else Trade.filing_date
    query = (
        session.query(Trade)
        .join(Politician, Politician.id == Trade.politician_id)
        .filter(Trade.ticker.isnot(None), Trade.ticker != "", Trade.trade_date.isnot(None))
        .order_by(desc(Trade.trade_date), desc(Trade.id))
    )
    if month and len(month) >= 7:
        try:
            y, m = int(month[:4]), int(month[5:7])
            query = query.filter(
                date_col.isnot(None),
                extract("year", date_col) == y,
                extract("month", date_col) == m,
            )
        except ValueError:
            pass
    if side:
        s = side.lower().strip()
        if s in ("buy", "purchase"):
            query = query.filter(Trade.transaction_type == "buy")
        elif s in ("sell", "sale"):
            query = query.filter(Trade.transaction_type == "sell")
    if chamber:
        ch = chamber.lower().strip()
        if ch in ("house", "senate"):
            query = query.filter(Politician.chamber == ch)

    # pull a pool larger than limit so after price-filter we still have ranks
    pool = query.limit(min(max(limit * 4, 80), 250)).all()
    rows_raw = [trade_row(t) for t in pool]

    # unique tickers (prefer more recent first) — cap yfinance load
    seen_tk: list[str] = []
    for r in rows_raw:
        tk = (r.get("ticker") or "").upper()
        if tk and tk not in seen_tk:
            seen_tk.append(tk)
        if len(seen_tk) >= max_tickers:
            break

    ranked: list[dict[str, Any]] = []
    skipped = 0
    for r in rows_raw:
        tk = (r.get("ticker") or "").upper()
        td = r.get("trade_date")
        if not tk or not td or tk not in seen_tk:
            skipped += 1
            continue
        perf = trade_performance(
            tk,
            td,
            value_min=r.get("amount_min"),
            value_max=r.get("amount_max"),
            transaction_type="buy" if r.get("side") == "BUY" else "sell",
            chart_points=8,
        )
        chg = perf.get("change_pct")
        if chg is None:
            skipped += 1
            continue
        side_u = r.get("side") or "BUY"
        # side-adjusted: sell benefits if price fell
        adj = -chg if side_u == "SELL" else chg
        ranked.append({
            "id": r["id"],
            "politician": r.get("politician"),
            "party": r.get("party"),
            "chamber": r.get("chamber"),
            "state_district": r.get("state_district"),
            "bioguide_id": r.get("bioguide_id"),
            "photo_url": r.get("photo_url"),
            "ticker": tk,
            "side": side_u,
            "trade_date": td,
            "filing_date": r.get("filing_date"),
            "amount": r.get("amount"),
            "score": r.get("score"),
            "price_at_trade": perf.get("price_at_trade"),
            "price_now": perf.get("price_now"),
            "change_pct": chg,
            "return_side_adj": round(adj, 2),
            "pnl_mid_est": perf.get("pnl_mid_est"),
            "shares_est": (perf.get("shares") or {}).get("shares_est") if isinstance(perf.get("shares"), dict) else None,
            "source": perf.get("source") or "yfinance",
        })

    # sort by side-adjusted return (best “outcome” first)
    ranked.sort(key=lambda x: (x.get("return_side_adj") is None, -(x.get("return_side_adj") or 0)))

    member_agg: list[dict[str, Any]] = []
    if (mode or "trade").lower() == "member":
        by_m: dict[str, dict] = {}
        for r in ranked:
            name = r.get("politician") or "?"
            ent = by_m.get(name)
            if not ent:
                ent = {
                    "politician": name,
                    "party": r.get("party"),
                    "chamber": r.get("chamber"),
                    "state_district": r.get("state_district"),
                    "bioguide_id": r.get("bioguide_id"),
                    "photo_url": r.get("photo_url"),
                    "n": 0,
                    "sum_adj": 0.0,
                    "sum_pnl": 0.0,
                    "best": None,
                    "worst": None,
                    "tickers": set(),
                }
                by_m[name] = ent
            ent["n"] += 1
            adj = float(r.get("return_side_adj") or 0)
            ent["sum_adj"] += adj
            if r.get("pnl_mid_est") is not None:
                ent["sum_pnl"] += float(r["pnl_mid_est"])
            if r.get("ticker"):
                ent["tickers"].add(r["ticker"])
            if ent["best"] is None or adj > ent["best"]["return_side_adj"]:
                ent["best"] = r
            if ent["worst"] is None or adj < ent["worst"]["return_side_adj"]:
                ent["worst"] = r
        for ent in by_m.values():
            n = max(ent["n"], 1)
            member_agg.append({
                "politician": ent["politician"],
                "party": ent["party"],
                "chamber": ent["chamber"],
                "state_district": ent["state_district"],
                "bioguide_id": ent["bioguide_id"],
                "photo_url": ent["photo_url"],
                "trades": ent["n"],
                "avg_return_adj": round(ent["sum_adj"] / n, 2),
                "sum_pnl_mid_est": round(ent["sum_pnl"], 2),
                "unique_tickers": len(ent["tickers"]),
                "best_trade": {
                    "ticker": ent["best"]["ticker"],
                    "side": ent["best"]["side"],
                    "trade_date": ent["best"]["trade_date"],
                    "return_side_adj": ent["best"]["return_side_adj"],
                } if ent["best"] else None,
                "worst_trade": {
                    "ticker": ent["worst"]["ticker"],
                    "side": ent["worst"]["side"],
                    "trade_date": ent["worst"]["trade_date"],
                    "return_side_adj": ent["worst"]["return_side_adj"],
                } if ent["worst"] else None,
            })
        member_agg.sort(key=lambda x: -x["avg_return_adj"])
        member_agg = member_agg[:limit]

    return {
        "data": {
            "mode": "member" if (mode or "").lower() == "member" else "trade",
            "rows": (member_agg if (mode or "").lower() == "member" else ranked[:limit]),
            "scored": len(ranked),
            "skipped": skipped,
            "month": month or "",
            "date_field": "trade" if (date_field or "").lower() == "trade" else "filing",
            "tickers_priced": len(seen_tk),
        },
        "asof": _now_iso(),
        "mode": "LIVE",
        "source": "sqlite + yfinance trade_performance",
        "convention": (
            "ESTIMATED returns: price at/after trade_date vs latest close (auto_adjust). "
            "change_pct = underlying asset move. return_side_adj = BUY:+Δ% / SELL:−Δ%. "
            "pnl_mid_est uses disclosure $ range midpoint / price — not actual shares. "
            "Not investment advice; delayed quotes."
        ),
    }


def build_summary(session) -> dict[str, Any]:
    total_trades = session.query(func.count(Trade.id)).scalar() or 0
    total_pols = session.query(func.count(Politician.id)).scalar() or 0
    max_filing = session.query(func.max(Trade.filing_date)).scalar()
    max_trade = session.query(func.max(Trade.trade_date)).scalar()
    candidates = [d for d in (max_filing, max_trade) if d and d <= date.today()]
    age = max(0, (date.today() - max(candidates)).days) if candidates else None

    top_tickers = (
        session.query(Trade.ticker, func.count(Trade.id), func.sum(Trade.value_max))
        .filter(Trade.ticker.isnot(None), Trade.ticker != "")
        .group_by(Trade.ticker)
        .order_by(desc(func.count(Trade.id)))
        .limit(12)
        .all()
    )

    house_t = (
        session.query(func.count(Trade.id))
        .join(Politician)
        .filter(Politician.chamber == "house")
        .scalar()
        or 0
    )
    senate_t = (
        session.query(func.count(Trade.id))
        .join(Politician)
        .filter(Politician.chamber == "senate")
        .scalar()
        or 0
    )

    return {
        "data": {
            "total_trades": total_trades,
            "total_politicians": total_pols,
            "data_age_days": age,
            "house_trades": house_t,
            "senate_trades": senate_t,
            "top_tickers": [
                {"ticker": r[0], "trades": r[1], "volume": int(r[2] or 0)}
                for r in top_tickers
            ],
        },
        "asof": _now_iso(),
        "mode": "LIVE",
        "source": "sqlite congress_quant_tracker",
    }
