"""Stock aggregation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import case, desc, func, or_

from congress_quant_tracker.database.models import Company, Politician, Trade
from server.deps import _trade_dict_from_orm, get_db

router = APIRouter()


@router.get("/api/stocks")
def api_stocks(
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = None,
    asset_type: str | None = None,
    sort_by: str = "trades",
):
    session = get_db()
    try:
        query = session.query(
            Trade.ticker,
            func.count(Trade.id).label("trades"),
            func.sum(Trade.value_max).label("total_volume"),
            func.count(func.distinct(Trade.politician_id)).label("unique_politicians"),
            func.avg(Trade.score).label("avg_score"),
            func.sum(case((Trade.transaction_type == "buy", 1), else_=0)).label("buys"),
            func.sum(case((Trade.transaction_type == "sell", 1), else_=0)).label("sells"),
        ).group_by(Trade.ticker)

        if q:
            like = f"%{q}%"
            # match ticker or company name
            matching = [
                c.ticker
                for c in session.query(Company.ticker)
                .filter(or_(Company.ticker.ilike(like), Company.name.ilike(like)))
                .all()
            ]
            if matching:
                query = query.filter(or_(Trade.ticker.ilike(like), Trade.ticker.in_(matching)))
            else:
                query = query.filter(Trade.ticker.ilike(like))
        if asset_type:
            query = query.filter(Trade.asset_type == asset_type)

        total_q = query.subquery()
        total = session.query(func.count()).select_from(total_q).scalar() or 0

        if sort_by == "volume":
            query = query.order_by(desc(func.sum(Trade.value_max)))
        elif sort_by == "politicians":
            query = query.order_by(desc(func.count(func.distinct(Trade.politician_id))))
        elif sort_by == "score":
            query = query.order_by(desc(func.avg(Trade.score)))
        else:
            query = query.order_by(desc(func.count(Trade.id)))

        rows = query.offset(offset).limit(limit).all()
        tickers = [r[0] for r in rows if r[0]]
        companies = {
            c.ticker: c
            for c in session.query(Company).filter(Company.ticker.in_(tickers)).all()
        } if tickers else {}

        stocks = []
        for r in rows:
            company = companies.get(r[0])
            stocks.append({
                "ticker": r[0],
                "trades": r[1],
                "total_volume": r[2] or 0,
                "unique_politicians": r[3] or 0,
                "avg_score": round(float(r[4] or 0), 1),
                "buys": int(r[5] or 0),
                "sells": int(r[6] or 0),
                "sector": company.sector if company else None,
                "industry": company.industry if company else None,
                "name": company.name if company else r[0],
                "current_price": None,
            })
        return {"total": total, "limit": limit, "offset": offset, "stocks": stocks}
    finally:
        session.close()


@router.get("/api/stocks/{ticker}")
def api_stock_detail(ticker: str):
    session = get_db()
    try:
        ticker = ticker.upper()
        company = session.query(Company).filter(Company.ticker == ticker).first()
        trades = (
            session.query(Trade)
            .filter(Trade.ticker == ticker)
            .order_by(desc(Trade.trade_date))
            .all()
        )
        if not trades and not company:
            raise HTTPException(status_code=404, detail="Ticker not found")

        pol_stats = (
            session.query(
                Politician.name,
                Politician.party,
                func.count(Trade.id).label("trades"),
                func.sum(Trade.value_max).label("volume"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .filter(Trade.ticker == ticker)
            .group_by(Politician.id)
            .order_by(desc(func.count(Trade.id)))
            .all()
        )

        # Volume / buy-sell trend by month
        month_map: dict[str, dict[str, int]] = {}
        for t in trades:
            if not t.trade_date:
                continue
            key = t.trade_date.strftime("%Y-%m")
            entry = month_map.setdefault(
                key, {"month": key, "buys": 0, "sells": 0, "volume": 0, "count": 0}
            )
            entry["count"] += 1
            entry["volume"] += t.value_max or 0
            if t.transaction_type == "buy":
                entry["buys"] += 1
            else:
                entry["sells"] += 1
        volume_trend = [month_map[k] for k in sorted(month_map.keys())]

        buys = sum(1 for t in trades if t.transaction_type == "buy")
        sells = sum(1 for t in trades if t.transaction_type == "sell")

        return {
            "ticker": ticker,
            "name": company.name if company else (trades[0].asset_name if trades else ticker),
            "sector": company.sector if company else (trades[0].sector if trades else None),
            "industry": company.industry if company else None,
            "total_trades": len(trades),
            "trades": len(trades),
            "total_volume": sum(t.value_max or 0 for t in trades),
            "unique_politicians": len(pol_stats),
            "buy_count": buys,
            "sell_count": sells,
            "avg_score": (
                round(sum(t.score for t in trades) / len(trades), 1) if trades else 0
            ),
            "politicians": [
                {"name": r[0], "party": r[1], "trades": r[2], "volume": r[3] or 0}
                for r in pol_stats
            ],
            "volume_trend": volume_trend,
            "recent_trades": [_trade_dict_from_orm(t) for t in trades[:50]],
        }
    finally:
        session.close()
