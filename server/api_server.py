"""FastAPI server — CongressInvests Tracker API."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from sqlalchemy import case, desc, extract, func, or_

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import (
    Company,
    OptionsTrade,
    Politician,
    Trade,
    UpdateLog,
    get_engine,
    get_session,
    init_db,
)

engine = get_engine(settings.DATABASE_URL)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db(settings.DATABASE_URL)
    settings.ensure_dirs()
    yield


app = FastAPI(
    title="CongressInvests Tracker",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    return get_session(engine)


# ─── helpers ───────────────────────────────────────────────────────────


def _state_district(pol: Politician) -> str:
    if pol.district:
        return f"{pol.state}-{pol.district}" if pol.state else str(pol.district)
    return pol.state or ""


def _photo_for(pol: Optional[Politician]) -> Optional[str]:
    if not pol:
        return None
    if pol.photo_url:
        return pol.photo_url
    if pol.bioguide_id:
        # local static path; frontend falls back to unitedstates.io CDN
        return f"/politicians/{pol.bioguide_id}.jpg"
    return None


def _trade_dict_from_orm(trade: Trade, pol: Optional[Politician] = None) -> dict:
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


def _data_age_days(session) -> Optional[int]:
    max_filing = session.query(func.max(Trade.filing_date)).scalar()
    max_trade = session.query(func.max(Trade.trade_date)).scalar()
    # Prefer filing date (when public learned), clamp to non-future
    candidates = [d for d in (max_filing, max_trade) if d and d <= date.today()]
    if not candidates:
        return None
    return max(0, (date.today() - max(candidates)).days)


def _last_update(session) -> Optional[dict]:
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


# ─── routes ────────────────────────────────────────────────────────────


@app.get("/api/health")
def api_health():
    session = get_db()
    try:
        total = session.query(func.count(Trade.id)).scalar() or 0
        last = _last_update(session)
        return {
            "status": "ok",
            "total_trades": total,
            "db": settings.DATABASE_URL,
            "version": "2.1.0",
            "last_update": last,
            "data_age_days": _data_age_days(session),
        }
    finally:
        session.close()


@app.get("/api/dashboard")
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

        # Monthly activity with buy/sell split (last 12 months)
        monthly = []
        today = date.today()
        for i in range(11, -1, -1):
            y, m = today.year, today.month - i
            while m <= 0:
                m += 12
                y -= 1
            base = session.query(Trade).filter(
                extract("year", Trade.trade_date) == y,
                extract("month", Trade.trade_date) == m,
            )
            count = base.count()
            buys = base.filter(Trade.transaction_type == "buy").count()
            sells = base.filter(Trade.transaction_type == "sell").count()
            vol = (
                session.query(func.coalesce(func.sum(Trade.value_max), 0))
                .filter(
                    extract("year", Trade.trade_date) == y,
                    extract("month", Trade.trade_date) == m,
                )
                .scalar()
                or 0
            )
            monthly.append({
                "month": f"{y:04d}-{m:02d}",
                "count": count,
                "buys": buys,
                "sells": sells,
                "volume": int(vol),
            })

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


@app.get("/api/trades/months")
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
        names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
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


@app.get("/api/trades")
def api_trades(
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: Optional[str] = None,
    tag: Optional[str] = None,
    trade_type: Optional[str] = None,
    asset_type: Optional[str] = None,
    min_score: Optional[int] = None,
    party: Optional[str] = None,
    chamber: Optional[str] = None,
    month: Optional[str] = Query(None, description="YYYY-MM filter"),
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
                col = Trade.trade_date if date_field == "trade" or sort_by in ("trade_date", "tx_date") else Trade.filing_date
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


@app.get("/api/market/{ticker}")
def api_market_ticker(
    ticker: str,
    days: int = Query(180, ge=14, le=400),
    from_date: Optional[str] = None,
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


@app.get("/api/trades/{trade_id}/performance")
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


@app.get("/api/politicians")
def api_politicians(
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: Optional[str] = None,
    party: Optional[str] = None,
    chamber: Optional[str] = None,
    state: Optional[str] = None,
    sort_by: str = "trades",
):
    session = get_db()
    try:
        stats = _pol_stats_map(session)
        query = session.query(Politician)

        if q:
            query = query.filter(Politician.name.ilike(f"%{q}%"))
        if party:
            query = query.filter(Politician.party == party.upper())
        if chamber:
            query = query.filter(Politician.chamber == chamber.lower())
        if state:
            query = query.filter(Politician.state == state.upper())

        pols = query.all()

        def sort_key(p: Politician):
            s = stats.get(p.id, {})
            if sort_by == "volume":
                return s.get("total_volume", 0)
            if sort_by == "score":
                return s.get("avg_score", 0) or p.avg_score or 0
            return s.get("trades", 0) or p.total_trades or 0

        pols_sorted = sorted(pols, key=sort_key, reverse=True)
        total = len(pols_sorted)
        page = pols_sorted[offset : offset + limit]

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "politicians": [
                _politician_dict_from_stats(p, **stats.get(p.id, {})) for p in page
            ],
        }
    finally:
        session.close()


@app.get("/api/politicians/{politician_name:path}")
def api_politician_detail(politician_name: str):
    session = get_db()
    try:
        name = politician_name.replace("-", " ").strip()
        pol = (
            session.query(Politician)
            .filter(Politician.name.ilike(f"%{name}%"))
            .first()
        )
        if not pol:
            raise HTTPException(status_code=404, detail="Politician not found")

        trades = (
            session.query(Trade)
            .filter(Trade.politician_id == pol.id)
            .order_by(desc(Trade.trade_date), desc(Trade.id))
            .all()
        )

        buys = sum(1 for t in trades if t.transaction_type == "buy")
        sells = sum(1 for t in trades if t.transaction_type == "sell")
        unique_assets = len({t.ticker for t in trades if t.ticker})
        total_volume = sum(t.value_max or 0 for t in trades)
        scores = [t.score for t in trades if t.score]
        avg_score = round(sum(scores) / len(scores), 1) if scores else round(pol.avg_score or 0, 1)

        tag_counts = {"high_alert": 0, "suspicious": 0, "noteworthy": 0, "routine": 0}
        for t in trades:
            tag_counts[t.tag or "routine"] = tag_counts.get(t.tag or "routine", 0) + 1

        asset_map: dict[str, dict[str, Any]] = {}
        for t in trades:
            if not t.ticker:
                continue
            entry = asset_map.setdefault(
                t.ticker, {"ticker": t.ticker, "name": t.asset_name or t.ticker, "trades": 0, "volume": 0}
            )
            entry["trades"] += 1
            entry["volume"] += t.value_max or 0
        top_assets = sorted(asset_map.values(), key=lambda x: x["trades"], reverse=True)[:10]

        month_scores: dict[str, list[int]] = {}
        month_activity: dict[str, dict[str, int]] = {}
        for t in trades:
            if not t.trade_date:
                continue
            key = t.trade_date.strftime("%Y-%m")
            month_scores.setdefault(key, []).append(t.score or 0)
            act = month_activity.setdefault(key, {"buys": 0, "sells": 0, "count": 0})
            act["count"] += 1
            if t.transaction_type == "buy":
                act["buys"] += 1
            else:
                act["sells"] += 1

        score_trend = [
            {
                "month": m,
                "avg_score": round(sum(v) / len(v), 1),
                **month_activity.get(m, {}),
            }
            for m, v in sorted(month_scores.items())
        ]

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
            "total_trades": len(trades),
            "trades": len(trades),
            "total_volume": total_volume,
            "unique_assets": unique_assets,
            "buy_count": buys,
            "sell_count": sells,
            "buys": buys,
            "sells": sells,
            "avg_score": avg_score,
            "high_alert": tag_counts.get("high_alert", 0),
            "suspicious": tag_counts.get("suspicious", 0),
            "noteworthy": tag_counts.get("noteworthy", 0),
            "top_assets": top_assets,
            "score_trend": score_trend,
            "recent_trades": [_trade_dict_from_orm(t, pol) for t in trades[:50]],
            "politician": _politician_dict_from_stats(
                pol,
                trades=len(trades),
                total_volume=total_volume,
                buys=buys,
                sells=sells,
                unique_assets=unique_assets,
                avg_score=avg_score,
            ),
        }
    finally:
        session.close()


@app.get("/api/stocks")
def api_stocks(
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: Optional[str] = None,
    asset_type: Optional[str] = None,
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


@app.get("/api/stocks/{ticker}")
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
            entry = month_map.setdefault(key, {"month": key, "buys": 0, "sells": 0, "volume": 0, "count": 0})
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


@app.get("/api/leaderboard")
def api_leaderboard(
    metric: str = Query("score"),
    limit: int = Query(25, ge=1, le=100),
    party: Optional[str] = None,
    chamber: Optional[str] = None,
):
    session = get_db()
    try:
        query = (
            session.query(
                Politician.id,
                Politician.name,
                Politician.party,
                Politician.chamber,
                Politician.state,
                Politician.district,
                Politician.bioguide_id,
                Politician.photo_url,
                func.count(Trade.id).label("trades"),
                func.sum(Trade.value_max).label("total_volume"),
                func.avg(Trade.score).label("avg_score"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .group_by(Politician.id)
            .having(func.count(Trade.id) >= 3)
        )
        if party:
            query = query.filter(Politician.party == party.upper())
        if chamber:
            query = query.filter(Politician.chamber == chamber.lower())

        if metric == "volume":
            query = query.order_by(desc(func.sum(Trade.value_max)))
        elif metric == "trades":
            query = query.order_by(desc(func.count(Trade.id)))
        else:
            query = query.order_by(desc(func.avg(Trade.score)))

        rows = query.limit(limit).all()
        return {
            "total": len(rows),
            "leaderboard": [
                {
                    "rank": i + 1,
                    "id": r[0],
                    "name": r[1],
                    "party": r[2],
                    "chamber": r[3].title() if r[3] else None,
                    "state": r[4],
                    "state_district": f"{r[4]}-{r[5]}" if r[4] and r[5] else (r[4] or ""),
                    "bioguide_id": r[6],
                    "photo_url": r[7] or (f"/politicians/{r[6]}.jpg" if r[6] else None),
                    "trades": r[8],
                    "total_volume": r[9] or 0,
                    "avg_score": round(float(r[10] or 0), 1),
                }
                for i, r in enumerate(rows)
            ],
        }
    finally:
        session.close()


@app.get("/api/signals")
def api_signals(
    tag: Optional[str] = None,
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


@app.get("/api/search")
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


@app.get("/api/meta")
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
            "version": "2.1.0",
        }
    finally:
        session.close()


@app.post("/api/pipeline/run")
def api_run_pipeline():
    from congress_quant_tracker.services.data_updater import DataUpdateService

    updater = DataUpdateService()
    stats = updater.run_full_update()
    return {"status": "completed", "stats": stats}


@app.post("/api/pipeline/house-official")
def api_house_official(
    max_filings: int = Query(60, ge=1, le=300),
    days: int = Query(150, ge=7, le=730),
):
    """Pull newest House PTRs from the official Clerk site (XML + PDF)."""
    from congress_quant_tracker.services.official_pipeline import OfficialHousePipeline

    stats = OfficialHousePipeline().run(
        max_filings=max_filings,
        since_days=days,
        use_tavily=True,
    )
    return {"status": "completed", "stats": stats}


@app.get("/api/pipeline/senate-probe")
def api_senate_probe():
    """Check if efdsearch.senate.gov is reachable from this server."""
    from congress_quant_tracker.fetchers.senate_official import probe_efd_access

    return probe_efd_access()


@app.post("/api/pipeline/senate")
def api_senate_update(
    strategy: str = Query("auto", description="auto|congressinvests|efd"),
    pages: int = Query(25, ge=1, le=80),
):
    """Update Senate trades (auto falls back if eFD is Akamai-blocked)."""
    from congress_quant_tracker.services.senate_pipeline import SenatePipeline

    stats = SenatePipeline().run(strategy=strategy, max_pages=pages)
    return {"status": "completed", "stats": stats}


@app.post("/api/pipeline/rescore")
def api_rescore():
    """Reclassify assets, extract options, re-score all trades."""
    from congress_quant_tracker.services.data_updater import DataUpdateService

    updater = DataUpdateService()
    stats = updater.rescore_all()
    return {"status": "completed", "stats": stats}


@app.post("/api/pipeline/fix-parties")
def api_fix_parties():
    from congress_quant_tracker.fetchers.congress_invests import _load_members_db

    session = get_db()
    try:
        members = _load_members_db()
        updated = 0
        for pol in session.query(Politician).all():
            info = members.get(pol.name.lower().strip(), {})
            if not info and " " in pol.name:
                # try without middle initial: "David J. Taylor" -> "david taylor"
                parts = pol.name.lower().split()
                if len(parts) >= 3 and len(parts[1].rstrip(".")) <= 2:
                    key = f"{parts[0]} {parts[-1]}"
                    info = members.get(key, {})
                if not info:
                    info = members.get(pol.name.lower().split()[-1], {})
            if not info:
                continue
            changed = False
            party = info.get("party")
            if party in ("D", "R", "I") and pol.party != party:
                pol.party = party
                changed = True
            if info.get("state") and pol.state != info["state"]:
                pol.state = info["state"]
                changed = True
            if info.get("district") is not None and str(pol.district or "") != str(info["district"]):
                pol.district = str(info["district"])
                changed = True
            if info.get("bioguide_id") and not pol.bioguide_id:
                pol.bioguide_id = info["bioguide_id"]
                changed = True
            if changed:
                updated += 1
        session.commit()
        return {"status": "ok", "politicians_updated": updated}
    finally:
        session.close()


# ─── CI://TERMINAL LIVE feed (yfinance + congress) + static canvas ─────

_GMT_DIR = Path(__file__).resolve().parent.parent / "kimi_gmt_terminal"


@app.get("/api/terminal/health")
def api_terminal_health():
    from congress_quant_tracker.enrichers.terminal_market import health
    h = health()
    h["congress"] = "ok"
    return h


@app.get("/api/terminal/dataset")
def api_terminal_dataset(dataset: str = Query("tape", description="tape|stocks|aapl60|metals|sectors|news|quotes|meta")):
    """LIVE market adapter for CI://TERMINAL (yfinance)."""
    from congress_quant_tracker.enrichers.terminal_market import get_dataset

    try:
        return get_dataset(dataset)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LIVE feed unavailable: {e}") from e


@app.get("/api/terminal/congress/summary")
def api_terminal_congress_summary():
    from congress_quant_tracker.enrichers.terminal_congress import build_summary

    session = get_db()
    try:
        return build_summary(session)
    finally:
        session.close()


@app.get("/api/terminal/congress/months")
def api_terminal_congress_months(
    by: str = Query("filing", description="filing | trade"),
):
    from congress_quant_tracker.enrichers.terminal_congress import build_months

    session = get_db()
    try:
        return build_months(session, by=by)
    finally:
        session.close()


@app.get("/api/terminal/congress/wire")
def api_terminal_congress_wire(
    limit: int = Query(120, ge=1, le=300),
    offset: int = Query(0, ge=0),
    chamber: Optional[str] = None,
    party: Optional[str] = None,
    side: Optional[str] = None,
    month: Optional[str] = Query(None, description="YYYY-MM"),
    date_field: str = Query("filing", description="filing | trade"),
    q: Optional[str] = None,
    tag: Optional[str] = None,
    min_score: Optional[int] = None,
    enrich: bool = Query(False),
):
    from congress_quant_tracker.enrichers.terminal_congress import build_wire

    session = get_db()
    try:
        return build_wire(
            session,
            limit=limit,
            offset=offset,
            chamber=chamber,
            party=party,
            side=side,
            month=month,
            date_field=date_field,
            q=q,
            tag=tag,
            min_score=min_score,
            enrich=enrich,
        )
    finally:
        session.close()


@app.get("/api/terminal/congress/holders/{ticker}")
def api_terminal_congress_holders(ticker: str):
    from congress_quant_tracker.enrichers.terminal_congress import build_holders

    session = get_db()
    try:
        return build_holders(session, ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        session.close()


@app.get("/api/terminal/congress/sectors")
def api_terminal_congress_sectors():
    from congress_quant_tracker.enrichers.terminal_congress import list_sectors

    session = get_db()
    try:
        return list_sectors(session)
    finally:
        session.close()


@app.get("/api/terminal/congress/sector")
def api_terminal_congress_sector(sector: Optional[str] = None):
    from congress_quant_tracker.enrichers.terminal_congress import build_sector

    session = get_db()
    try:
        return build_sector(session, sector or "")
    finally:
        session.close()


@app.get("/api/terminal/congress/returns")
def api_terminal_congress_returns(
    month: Optional[str] = Query(None, description="YYYY-MM"),
    date_field: str = Query("filing"),
    side: Optional[str] = None,
    chamber: Optional[str] = None,
    mode: str = Query("member", description="member | trade"),
    limit: int = Query(40, ge=5, le=100),
):
    """Returns leaderboard: ranked by estimated side-adjusted % since trade."""
    from congress_quant_tracker.enrichers.terminal_congress import build_returns_leaderboard

    session = get_db()
    try:
        return build_returns_leaderboard(
            session,
            month=month,
            date_field=date_field,
            side=side,
            chamber=chamber,
            mode=mode,
            limit=limit,
        )
    finally:
        session.close()


@app.get("/api/terminal/congress/politician")
def api_terminal_congress_politician(name: Optional[str] = None):
    from congress_quant_tracker.enrichers.terminal_congress import build_politician

    session = get_db()
    try:
        return build_politician(session, name or "")
    finally:
        session.close()


@app.get("/api/terminal/market/{ticker}")
def api_terminal_market_chart(
    ticker: str,
    sessions: int = Query(120, ge=20, le=400),
    from_date: Optional[str] = Query(
        None,
        description="ISO date — chart starts early enough to include this trade day (daily bars)",
    ),
):
    """Daily OHLCV for FOCUSED ASSET CHART.

    Always daily (weekday sessions). If from_date is set (trade date), the window
    starts ~15 calendar days before that date through today so distant trades stay
    on-scale with a visible marker — not clipped to a short 60-bar window.
    """
    from congress_quant_tracker.enrichers.market_data import get_history

    ticker = ticker.upper().strip()
    end = date.today()
    start = end - timedelta(days=max(sessions * 2, 180))

    trade_d: Optional[date] = None
    if from_date:
        try:
            trade_d = date.fromisoformat(from_date[:10])
            # pad before trade so marker is not on the left edge
            start = min(start, trade_d - timedelta(days=20))
            # ensure we never request absurd windows
            if (end - start).days > 420:
                start = end - timedelta(days=420)
        except ValueError:
            trade_d = None

    bars = get_history(ticker, start, end)
    # If no from_date, still keep a healthy daily history (not tiny 60 only)
    if not from_date and len(bars) > sessions:
        bars = bars[-sessions:]

    series = [
        {
            "d": b["date"],
            "o": b.get("open") if b.get("open") is not None else b["close"],
            "h": b.get("high") if b.get("high") is not None else b["close"],
            "l": b.get("low") if b.get("low") is not None else b["close"],
            "c": b["close"],
            "v": b.get("volume") or 0,
        }
        for b in bars
    ]

    # Calculate Congressional VWAP (Average Buy and Sell price)
    avg_buy_price = None
    avg_sell_price = None
    session = get_db()
    try:
        t_rows = session.query(Trade.trade_date, Trade.transaction_type, Trade.value_min, Trade.value_max).filter(Trade.ticker == ticker, Trade.trade_date.isnot(None)).all()
        buy_vol = 0.0
        buy_shares = 0.0
        sell_vol = 0.0
        sell_shares = 0.0
        price_by_date = {b["date"]: b["close"] for b in bars}
        for td_str, side, vmin, vmax in t_rows:
            d_str = str(td_str)[:10]
            p = price_by_date.get(d_str)
            if not p:
                for b_date in sorted(price_by_date.keys()):
                    if b_date >= d_str:
                        p = price_by_date[b_date]
                        break
            if p and p > 0:
                mid = ((vmin or 0) + (vmax or 0)) / 2.0 or float(vmax or vmin or 10000)
                sh = mid / p
                if (side or "").lower() in ("buy", "purchase"):
                    buy_vol += mid
                    buy_shares += sh
                else:
                    sell_vol += mid
                    sell_shares += sh
        avg_buy_price = round(buy_vol / buy_shares, 2) if buy_shares > 0 else None
        avg_sell_price = round(sell_vol / sell_shares, 2) if sell_shares > 0 else None
    except Exception:
        pass
    finally:
        session.close()

    return {
        "data": {
            "ticker": ticker,
            "series": series,
            "sessions": len(series),
            "from_date": from_date[:10] if from_date else None,
            "scale": "daily",
            "start": series[0]["d"] if series else None,
            "end": series[-1]["d"] if series else None,
            "avg_buy_price": avg_buy_price,
            "avg_sell_price": avg_sell_price,
        },
        "asof": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "LIVE" if series else "EMPTY",
        "source": "yfinance",
        "convention": "daily bars (weekday sessions), auto_adjust=True; window expands to include trade date",
    }


@app.get("/api/terminal/{dataset}")
def api_terminal_dataset_path(dataset: str):
    """Alias: /api/terminal/tape → same as ?dataset=tape.
    Skip reserved path segments handled by more specific routes above.
    """
    if dataset in ("congress", "market", "health", "dataset"):
        raise HTTPException(status_code=404, detail="use nested terminal routes")
    return api_terminal_dataset(dataset=dataset)


@app.get("/")
def root_index():
    """Redirect root to CI://TERMINAL."""
    return RedirectResponse(url="/terminal/", status_code=302)


class ChatRequest(BaseModel):
    messages: list[dict]
    provider: str = "groq"


@app.get("/api/terminal/chat/models")
def api_chat_models():
    """List available AI Copilot models and providers."""
    return {
        "providers": [
            {
                "id": "groq",
                "name": "Groq — Llama 3.3 70B",
                "badge": "FREE / ULTRA-FAST",
                "available": bool(settings.GROQ_API_KEY),
                "is_default": True,
            },
            {
                "id": "openai",
                "name": "OpenAI — GPT-4o Mini",
                "badge": "ADVANCED REASONING",
                "available": bool(settings.OPENAI_API_KEY),
                "is_default": False,
            },
            {
                "id": "local",
                "name": "Local Llama Server (Kolmogorov)",
                "badge": "100% OFFLINE / PRIVATE",
                "available": True,
                "is_default": False,
            },
        ],
        "default_provider": "groq",
    }


@app.post("/api/terminal/chat")
async def api_chat(req: ChatRequest):
    """Execute CongressQuant AI Copilot analysis."""
    from congress_quant_tracker.agent.copilot import CopilotAgent

    agent = CopilotAgent(provider=req.provider)
    result = await agent.chat(req.messages)
    return result


@app.get("/terminal")
@app.get("/terminal/")
def terminal_index():
    """Serve Bloomberg × ASCII global market terminal."""
    index = _GMT_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="GMT terminal not installed (kimi_gmt_terminal/ missing)")
    return FileResponse(index, media_type="text/html")


# Politician headshots (bioguide jpgs) for CI://TERMINAL + API clients
_POL_PHOTO_DIRS = [
    Path(__file__).resolve().parent.parent / "data" / "politicians",
    Path(__file__).resolve().parent.parent / "web_fused" / "public" / "politicians",
    Path(__file__).resolve().parent.parent / "web" / "public" / "politicians",
]
for _pol_dir in _POL_PHOTO_DIRS:
    if _pol_dir.is_dir():
        app.mount(
            "/politicians",
            StaticFiles(directory=str(_pol_dir)),
            name="politician_photos",
        )
        break

# Mount static assets for terminal (css, js, fonts) — after routes so /terminal hits HTML first
if _GMT_DIR.is_dir():
    app.mount(
        "/terminal",
        StaticFiles(directory=str(_GMT_DIR), html=True),
        name="gmt_terminal",
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
