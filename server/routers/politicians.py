"""Politician list/detail + leaderboard endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, func

from congress_quant_tracker.database.models import Politician, Trade
from server.deps import (
    _pol_stats_map,
    _politician_dict_from_stats,
    _state_district,
    _trade_dict_from_orm,
    get_db,
)

router = APIRouter()


@router.get("/api/politicians")
def api_politicians(
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str | None = None,
    party: str | None = None,
    chamber: str | None = None,
    state: str | None = None,
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


@router.get("/api/leaderboard")
def api_leaderboard(
    metric: str = Query("score"),
    limit: int = Query(25, ge=1, le=100),
    party: str | None = None,
    chamber: str | None = None,
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


@router.get("/api/politicians/{politician_name:path}")
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
                t.ticker,
                {"ticker": t.ticker, "name": t.asset_name or t.ticker, "trades": 0, "volume": 0},
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

        photo_url = None
        if pol.photo_url:
            photo_url = pol.photo_url
        elif pol.bioguide_id:
            photo_url = f"/politicians/{pol.bioguide_id}.jpg"

        return {
            "name": pol.name,
            "party": pol.party,
            "chamber": pol.chamber.title() if pol.chamber else None,
            "state": pol.state,
            "district": pol.district,
            "state_district": _state_district(pol),
            "committees": [c.strip() for c in (pol.committees or "").split(",") if c.strip()],
            "bioguide_id": pol.bioguide_id,
            "photo_url": photo_url,
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
