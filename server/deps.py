"""Shared dependencies and serializers for the API routers."""

from __future__ import annotations

from datetime import date

from sqlalchemy import case, desc, func

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import (
    Politician,
    Trade,
    UpdateLog,
    get_engine,
    get_session,
)

APP_VERSION = "2.1.0"

engine = get_engine(settings.DATABASE_URL)


def get_db():
    return get_session(engine)


# ─── serializers ───────────────────────────────────────────────────────


def _state_district(pol: Politician) -> str:
    if pol.district:
        return f"{pol.state}-{pol.district}" if pol.state else str(pol.district)
    return pol.state or ""


def _photo_for(pol: Politician | None) -> str | None:
    if not pol:
        return None
    if pol.photo_url:
        return pol.photo_url
    if pol.bioguide_id:
        # local static path; frontend falls back to unitedstates.io CDN
        return f"/politicians/{pol.bioguide_id}.jpg"
    return None


def _trade_dict_from_orm(trade: Trade, pol: Politician | None = None) -> dict:
    pol = pol or trade.politician
    return {
        "id": trade.id,
        "ticker": trade.ticker,
        "asset": trade.asset_name,
        "transaction_type": "Purchase" if trade.transaction_type == "buy" else "Sale",
        "transaction_date": str(trade.trade_date) if trade.trade_date else None,
        "notification_date": str(trade.filing_date) if trade.filing_date else None,
        "amount_min": trade.value_min,
        "amount_max": trade.value_max,
        "amount": trade.value_range,
        "asset_type": trade.asset_type,
        "score": trade.score or 0,
        "tag": trade.tag or "routine",
        "reason": trade.reason,
        "pdf_url": trade.pdf_url,
        "owner": trade.owner,
        "sector": trade.sector,
        "representative": pol.name if pol else None,
        "party": pol.party if pol else None,
        "chamber": (pol.chamber.title() if pol and pol.chamber else None),
        "state_district": _state_district(pol) if pol else None,
        "bioguide_id": pol.bioguide_id if pol else None,
        "photo_url": _photo_for(pol),
        # filled when enrich=1
        "current_price": None,
        "price_change_pct": None,
        "shares_est": None,
        "pnl_mid_est": None,
        "market": None,
    }


def _politician_dict_from_stats(
    pol: Politician,
    trades: int = 0,
    total_volume: int = 0,
    buys: int = 0,
    sells: int = 0,
    unique_assets: int = 0,
    avg_score: float = 0.0,
) -> dict:
    return {
        "name": pol.name,
        "party": pol.party,
        "chamber": pol.chamber.title() if pol.chamber else None,
        "state": pol.state,
        "district": pol.district,
        "state_district": _state_district(pol),
        "committees": [c.strip() for c in (pol.committees or "").split(",") if c.strip()],
        "bioguide_id": pol.bioguide_id,
        "photo_url": _photo_for(pol),
        "trades": trades or pol.total_trades or 0,
        "total_trades": trades or pol.total_trades or 0,
        "avg_score": round(avg_score or pol.avg_score or 0, 1),
        "total_volume": total_volume or 0,
        "buys": buys,
        "sells": sells,
        "unique_assets": unique_assets,
    }


# ─── aggregate helpers ─────────────────────────────────────────────────


def _data_age_days(session) -> int | None:
    max_filing = session.query(func.max(Trade.filing_date)).scalar()
    max_trade = session.query(func.max(Trade.trade_date)).scalar()
    # Prefer filing date (when public learned), clamp to non-future
    candidates = [d for d in (max_filing, max_trade) if d and d <= date.today()]
    if not candidates:
        return None
    return max(0, (date.today() - max(candidates)).days)


def _last_update(session) -> dict | None:
    row = (
        session.query(UpdateLog)
        .order_by(desc(UpdateLog.started_at))
        .first()
    )
    if not row:
        return None
    return {
        "status": row.status,
        "started_at": str(row.started_at) if row.started_at else None,
        "completed_at": str(row.completed_at) if row.completed_at else None,
        "records_processed": row.records_processed,
        "error_message": row.error_message,
    }


def _pol_stats_map(session) -> dict[int, dict]:
    """One query: aggregates per politician."""
    rows = (
        session.query(
            Trade.politician_id,
            func.count(Trade.id),
            func.coalesce(func.sum(Trade.value_max), 0),
            func.sum(case((Trade.transaction_type == "buy", 1), else_=0)),
            func.sum(case((Trade.transaction_type == "sell", 1), else_=0)),
            func.count(func.distinct(Trade.ticker)),
            func.avg(Trade.score),
        )
        .group_by(Trade.politician_id)
        .all()
    )
    return {
        r[0]: {
            "trades": int(r[1] or 0),
            "total_volume": int(r[2] or 0),
            "buys": int(r[3] or 0),
            "sells": int(r[4] or 0),
            "unique_assets": int(r[5] or 0),
            "avg_score": float(r[6] or 0),
        }
        for r in rows
    }
