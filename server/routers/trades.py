"""Trade list/detail endpoints + market chart data."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, extract, func, or_

from congress_quant_tracker.database.models import Politician, Trade
from server.deps import _trade_dict_from_orm, get_db

router = APIRouter()


@router.get("/api/trades/months")
def api_trade_months(
    by: str = Query("filing", description="filing | trade — which date to bucket by"),
):
    """Return months that have trades, newest first, with counts."""
    session = get_db()
    try:
        col = Trade.trade_date if by == "trade" else Trade.filing_date
        # Prefer filing_date; fall back rows with null filing via coalesce in app layer
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
        months = []
        names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
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
        return {"by": by, "months": months, "total_months": len(months)}
    finally:
        session.close()


@router.get("/api/trades")
def api_trades(
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = None,
    tag: str | None = None,
    trade_type: str | None = None,
    asset_type: str | None = None,
    min_score: int | None = None,
    party: str | None = None,
    chamber: str | None = None,
    month: str | None = Query(None, description="YYYY-MM filter"),
    date_field: str = Query("filing", description="filing | trade — month filter field"),
    sort_by: str = "date",
    enrich: bool = Query(False, description="Attach yfinance performance (rate-limited)"),
):
    session = get_db()
    try:
        query = session.query(Trade).join(Politician, Politician.id == Trade.politician_id)

        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    Trade.ticker.ilike(like),
                    Trade.asset_name.ilike(like),
                    Politician.name.ilike(like),
                )
            )
        if tag:
            query = query.filter(Trade.tag == tag)
        if trade_type:
            tt = trade_type.lower()
            if tt in ("purchase", "buy"):
                query = query.filter(Trade.transaction_type == "buy")
            elif tt in ("sale", "sell"):
                query = query.filter(Trade.transaction_type == "sell")
        if asset_type:
            query = query.filter(Trade.asset_type == asset_type)
        if min_score is not None:
            query = query.filter(Trade.score >= min_score)
        if party:
            query = query.filter(Politician.party == party.upper())
        if chamber:
            query = query.filter(Politician.chamber == chamber.lower())

        # Month bucket (YYYY-MM) on filing or trade date
        if month:
            try:
                y_str, m_str = month.split("-", 1)
                yi, mi = int(y_str), int(m_str)
                col = (
                    Trade.trade_date
                    if date_field == "trade" or sort_by in ("trade_date", "tx_date")
                    else Trade.filing_date
                )
                # If filtering by filing but some rows only have trade_date, use coalesce-like OR
                if col is Trade.filing_date:
                    query = query.filter(
                        or_(
                            (
                                (extract("year", Trade.filing_date) == yi)
                                & (extract("month", Trade.filing_date) == mi)
                            ),
                            (
                                Trade.filing_date.is_(None)
                                & (extract("year", Trade.trade_date) == yi)
                                & (extract("month", Trade.trade_date) == mi)
                            ),
                        )
                    )
                else:
                    query = query.filter(
                        extract("year", Trade.trade_date) == yi,
                        extract("month", Trade.trade_date) == mi,
                    )
            except ValueError:
                pass

        total = query.count()

        # Sorting contract (frontend labels must match):
        #   date       → most recently DISCLOSED (filing_date) — default "Newest"
        #   trade_date → actual transaction date
        #   score / volume
        if sort_by == "score":
            query = query.order_by(desc(Trade.score), desc(Trade.filing_date), desc(Trade.id))
        elif sort_by == "volume":
            query = query.order_by(desc(Trade.value_max), desc(Trade.filing_date), desc(Trade.id))
        elif sort_by in ("trade_date", "tx_date"):
            query = query.order_by(desc(Trade.trade_date), desc(Trade.filing_date), desc(Trade.id))
        else:
            # Newest disclosures first (not future option-expiration artifacts)
            query = query.order_by(
                desc(Trade.filing_date),
                desc(Trade.trade_date),
                desc(Trade.id),
            )

        rows = query.offset(offset).limit(limit).all()
        trades = [_trade_dict_from_orm(t) for t in rows]
        if enrich:
            from congress_quant_tracker.enrichers.market_data import enrich_trades_batch

            # Cap unique tickers so list pages stay responsive
            trades = enrich_trades_batch(trades, max_unique_tickers=min(10, max(3, limit // 2)))
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "month": month,
            "date_field": date_field,
            "enriched": enrich,
            "trades": trades,
        }
    finally:
        session.close()


@router.get("/api/market/{ticker}")
def api_market_ticker(
    ticker: str,
    days: int = Query(180, ge=14, le=400),
    from_date: str | None = None,
):
    """OHLCV series + latest price for charts (cached/rate-limited yfinance)."""
    from congress_quant_tracker.enrichers.market_data import get_history, get_latest_price

    ticker = ticker.upper().strip()
    end = date.today()
    if from_date:
        try:
            start = date.fromisoformat(from_date[:10])
        except ValueError:
            start = end - timedelta(days=days)
    else:
        start = end - timedelta(days=days)

    bars = get_history(ticker, start, end)
    latest = get_latest_price(ticker)
    change_pct = None
    if bars and len(bars) >= 2 and bars[0]["close"]:
        change_pct = round((bars[-1]["close"] - bars[0]["close"]) / bars[0]["close"] * 100, 2)

    return {
        "ticker": ticker,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "latest": latest,
        "change_pct_window": change_pct,
        "bars": bars,
        "count": len(bars),
        "source": "yfinance" if bars else "unavailable",
    }


@router.get("/api/signals")
def api_signals(
    tag: str | None = None,
    min_score: int = Query(26),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    session = get_db()
    try:
        query = (
            session.query(Trade)
            .join(Politician, Politician.id == Trade.politician_id)
            .filter(Trade.score >= min_score)
        )
        if tag:
            query = query.filter(Trade.tag == tag)

        total = query.count()
        rows = (
            query.order_by(desc(Trade.score), desc(Trade.trade_date))
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "tag": tag or "all",
            "signals": [_trade_dict_from_orm(t) for t in rows],
        }
    finally:
        session.close()


@router.get("/api/trades/{trade_id}/performance")
def api_trade_performance(trade_id: int):
    """Price move since trade date + estimated shares/PnL for one disclosure row."""
    from congress_quant_tracker.enrichers.market_data import trade_performance

    session = get_db()
    try:
        trade = session.query(Trade).filter(Trade.id == trade_id).first()
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        perf = trade_performance(
            trade.ticker or "",
            trade.trade_date,
            value_min=trade.value_min,
            value_max=trade.value_max,
            transaction_type=trade.transaction_type or "buy",
            chart_points=48,
        )
        return {
            "trade": _trade_dict_from_orm(trade),
            "performance": perf,
        }
    finally:
        session.close()
