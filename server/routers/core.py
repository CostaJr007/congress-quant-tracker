"""Core endpoints: health, dashboard, search, meta."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import case, desc, extract, func

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import (
    Company,
    OptionsTrade,
    Politician,
    Trade,
)
from server.deps import (
    APP_VERSION,
    _data_age_days,
    _last_update,
    _pol_stats_map,
    _politician_dict_from_stats,
    _trade_dict_from_orm,
    get_db,
)

router = APIRouter()


@router.get("/api/health")
def api_health():
    session = get_db()
    try:
        total = session.query(func.count(Trade.id)).scalar() or 0
        last = _last_update(session)
        return {
            "status": "ok",
            "total_trades": total,
            "db": settings.DATABASE_URL,
            "version": APP_VERSION,
            "last_update": last,
            "data_age_days": _data_age_days(session),
        }
    finally:
        session.close()


def _monthly_activity(session) -> list[dict]:
    """Last 12 months of activity (count/buys/sells/volume) in ONE grouped query.

    Buckets by trade_date; months without trades are filled with zeros so the
    chart keeps a continuous 12-month axis.
    """
    today = date.today()

    # Window start = first day of the month 11 months ago
    y, m = today.year, today.month - 11
    while m <= 0:
        m += 12
        y -= 1
    start = date(y, m, 1)

    rows = (
        session.query(
            extract("year", Trade.trade_date).label("y"),
            extract("month", Trade.trade_date).label("m"),
            func.count(Trade.id),
            func.sum(case((Trade.transaction_type == "buy", 1), else_=0)),
            func.sum(case((Trade.transaction_type == "sell", 1), else_=0)),
            func.coalesce(func.sum(Trade.value_max), 0),
        )
        .filter(Trade.trade_date >= start)
        .group_by("y", "m")
        .all()
    )
    by_month = {
        f"{int(r[0]):04d}-{int(r[1]):02d}": {
            "count": int(r[2] or 0),
            "buys": int(r[3] or 0),
            "sells": int(r[4] or 0),
            "volume": int(r[5] or 0),
        }
        for r in rows
    }

    monthly = []
    yy, mm = y, m
    for _ in range(12):
        key = f"{yy:04d}-{mm:02d}"
        stats = by_month.get(key, {"count": 0, "buys": 0, "sells": 0, "volume": 0})
        monthly.append({"month": key, **stats})
        mm += 1
        if mm > 12:
            mm = 1
            yy += 1
    return monthly


@router.get("/api/dashboard")
def api_dashboard(
    enrich: bool = Query(False, description="Attach yfinance performance (slow)"),
):
    session = get_db()
    try:
        total_trades = session.query(func.count(Trade.id)).scalar() or 0
        unique_politicians = session.query(func.count(Politician.id)).scalar() or 0
        total_volume = session.query(func.sum(Trade.value_max)).scalar() or 0
        total_options = session.query(func.count(OptionsTrade.id)).scalar() or 0
        unique_assets = session.query(func.count(func.distinct(Trade.ticker))).scalar() or 0
        avg_score = session.query(func.avg(Trade.score)).scalar() or 0
        buy_count = (
            session.query(func.count(Trade.id))
            .filter(Trade.transaction_type == "buy")
            .scalar()
            or 0
        )
        sell_count = (
            session.query(func.count(Trade.id))
            .filter(Trade.transaction_type == "sell")
            .scalar()
            or 0
        )

        min_date = session.query(func.min(Trade.trade_date)).scalar()
        max_date = session.query(func.max(Trade.trade_date)).scalar()

        signal_dist: dict[str, int] = {}
        for tag_val in ("routine", "noteworthy", "suspicious", "high_alert"):
            signal_dist[tag_val] = (
                session.query(func.count(Trade.id)).filter(Trade.tag == tag_val).scalar()
                or 0
            )

        monthly = _monthly_activity(session)

        top_pols = (
            session.query(
                Politician.name,
                Politician.party,
                Politician.chamber,
                Politician.bioguide_id,
                Politician.photo_url,
                func.count(Trade.id).label("trades"),
                func.sum(Trade.value_max).label("total_volume"),
                func.avg(Trade.score).label("avg_score"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .group_by(Politician.id)
            .order_by(desc(func.count(Trade.id)))
            .limit(10)
            .all()
        )

        top_tickers = (
            session.query(
                Trade.ticker,
                func.count(Trade.id).label("trades"),
                func.sum(Trade.value_max).label("total_volume"),
            )
            .group_by(Trade.ticker)
            .order_by(desc(func.count(Trade.id)))
            .limit(10)
            .all()
        )
        company_names = {
            c.ticker: c.name
            for c in session.query(Company)
            .filter(Company.ticker.in_([r[0] for r in top_tickers if r[0]]))
            .all()
        }

        recent = (
            session.query(Trade)
            .join(Politician, Politician.id == Trade.politician_id)
            .order_by(desc(Trade.filing_date), desc(Trade.trade_date), desc(Trade.id))
            .limit(40)
            .all()
        )
        recent_trades = [_trade_dict_from_orm(t) for t in recent]
        if enrich:
            try:
                from congress_quant_tracker.enrichers.market_data import enrich_trades_batch

                # Photos already on dict; attach price change / shares / sparkline (capped tickers)
                recent_trades = enrich_trades_batch(recent_trades, max_unique_tickers=10)
            except Exception:
                pass

        this_month = monthly[-1]["count"] if monthly else 0
        prev_month = monthly[-2]["count"] if len(monthly) > 1 else 0
        trades_delta = (
            round(((this_month - prev_month) / prev_month) * 100, 1) if prev_month else None
        )
        this_vol = monthly[-1]["volume"] if monthly else 0
        prev_vol = monthly[-2]["volume"] if len(monthly) > 1 else 0
        volume_delta = (
            round(((this_vol - prev_vol) / prev_vol) * 100, 1) if prev_vol else None
        )

        # Party split
        party_rows = (
            session.query(Politician.party, func.count(Trade.id))
            .join(Trade, Trade.politician_id == Politician.id)
            .group_by(Politician.party)
            .all()
        )
        party_split = {r[0]: r[1] for r in party_rows if r[0]}

        return {
            "total_trades": total_trades,
            "total_politicians": unique_politicians,
            "unique_politicians": unique_politicians,
            "total_volume": total_volume,
            "total_options": total_options,
            "unique_assets": unique_assets,
            "avg_score": round(float(avg_score or 0), 1),
            "avg_win_rate": 0,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "high_alert_count": signal_dist.get("high_alert", 0),
            "suspicious_count": signal_dist.get("suspicious", 0),
            "noteworthy_count": signal_dist.get("noteworthy", 0),
            "signal_distribution": signal_dist,
            "activity_by_month": monthly,
            "party_split": party_split,
            "data_range": {
                "min_date": str(min_date) if min_date else None,
                "max_date": str(max_date) if max_date else None,
            },
            "data_age_days": _data_age_days(session),
            "last_update": _last_update(session),
            "deltas": {"trades": trades_delta, "volume": volume_delta},
            "top_politicians": [
                {
                    "name": r[0],
                    "party": r[1],
                    "chamber": r[2].title() if r[2] else None,
                    "bioguide_id": r[3],
                    "photo_url": r[4] or (f"/politicians/{r[3]}.jpg" if r[3] else None),
                    "trades": r[5],
                    "total_volume": r[6] or 0,
                    "avg_score": round(float(r[7] or 0), 1),
                }
                for r in top_pols
            ],
            "top_tickers": [
                {
                    "ticker": r[0],
                    "name": company_names.get(r[0], r[0]),
                    "trades": r[1],
                    "total_volume": r[2] or 0,
                }
                for r in top_tickers
            ],
            "recent_trades": recent_trades,
        }
    finally:
        session.close()


@router.get("/api/search")
def api_search(q: str = Query(..., min_length=1)):
    session = get_db()
    try:
        like = f"%{q}%"
        politicians = (
            session.query(Politician)
            .filter(Politician.name.ilike(like))
            .order_by(desc(Politician.total_trades))
            .limit(8)
            .all()
        )
        stats = _pol_stats_map(session)
        tickers = (
            session.query(
                Trade.ticker,
                func.count(Trade.id).label("trades"),
                func.sum(Trade.value_max).label("volume"),
            )
            .filter(Trade.ticker.ilike(like))
            .group_by(Trade.ticker)
            .order_by(desc(func.count(Trade.id)))
            .limit(8)
            .all()
        )
        return {
            "politicians": [
                _politician_dict_from_stats(p, **stats.get(p.id, {})) for p in politicians
            ],
            "tickers": [
                {
                    "ticker": t[0],
                    "name": t[0],
                    "trades": t[1],
                    "total_volume": t[2] or 0,
                    "unique_politicians": 0,
                    "avg_score": 0,
                }
                for t in tickers
            ],
        }
    finally:
        session.close()


@router.get("/api/meta")
def api_meta():
    session = get_db()
    try:
        states = (
            session.query(Politician.state)
            .filter(Politician.state.isnot(None), Politician.state != "")
            .distinct()
            .order_by(Politician.state)
            .all()
        )
        parties = (
            session.query(Politician.party)
            .filter(Politician.party.isnot(None))
            .distinct()
            .all()
        )
        chambers = (
            session.query(Politician.chamber)
            .filter(Politician.chamber.isnot(None))
            .distinct()
            .all()
        )
        total_trades = session.query(func.count(Trade.id)).scalar() or 0
        total_options = session.query(func.count(OptionsTrade.id)).scalar() or 0
        return {
            "states": [s[0] for s in states if s[0]],
            "parties": [p[0] for p in parties if p[0]],
            "chambers": [c[0].title() for c in chambers if c[0]],
            "data_age_days": _data_age_days(session),
            "total_trades": total_trades,
            "total_options": total_options,
            "last_update": _last_update(session),
            "version": APP_VERSION,
        }
    finally:
        session.close()
