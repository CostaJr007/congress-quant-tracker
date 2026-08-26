"""CI://TERMINAL live feed endpoints (market + congress + copilot)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from congress_quant_tracker.config import settings
from server.deps import get_db

router = APIRouter()


class ChatRequest(BaseModel):
    messages: list[dict]
    provider: str = "groq"


@router.get("/api/terminal/health")
def api_terminal_health():
    from congress_quant_tracker.enrichers.terminal_market import health
    h = health()
    h["congress"] = "ok"
    return h


@router.get("/api/terminal/dataset")
def api_terminal_dataset(
    dataset: str = Query(
        "tape", description="tape|stocks|aapl60|metals|sectors|news|quotes|meta"
    ),
):
    """LIVE market adapter for CI://TERMINAL (yfinance)."""
    from congress_quant_tracker.enrichers.terminal_market import get_dataset

    try:
        return get_dataset(dataset)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LIVE feed unavailable: {e}") from e


@router.get("/api/terminal/congress/summary")
def api_terminal_congress_summary():
    from congress_quant_tracker.enrichers.terminal_congress import build_summary

    session = get_db()
    try:
        return build_summary(session)
    finally:
        session.close()


@router.get("/api/terminal/congress/months")
def api_terminal_congress_months(
    by: str = Query("filing", description="filing | trade"),
):
    from congress_quant_tracker.enrichers.terminal_congress import build_months

    session = get_db()
    try:
        return build_months(session, by=by)
    finally:
        session.close()


@router.get("/api/terminal/congress/wire")
def api_terminal_congress_wire(
    limit: int = Query(120, ge=1, le=300),
    offset: int = Query(0, ge=0),
    chamber: str | None = None,
    party: str | None = None,
    side: str | None = None,
    month: str | None = Query(None, description="YYYY-MM"),
    date_field: str = Query("filing", description="filing | trade"),
    q: str | None = None,
    tag: str | None = None,
    min_score: int | None = None,
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


@router.get("/api/terminal/congress/holders/{ticker}")
def api_terminal_congress_holders(ticker: str):
    from congress_quant_tracker.enrichers.terminal_congress import build_holders

    session = get_db()
    try:
        return build_holders(session, ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        session.close()


@router.get("/api/terminal/congress/sectors")
def api_terminal_congress_sectors():
    from congress_quant_tracker.enrichers.terminal_congress import list_sectors

    session = get_db()
    try:
        return list_sectors(session)
    finally:
        session.close()


@router.get("/api/terminal/congress/sector")
def api_terminal_congress_sector(sector: str | None = None):
    from congress_quant_tracker.enrichers.terminal_congress import build_sector

    session = get_db()
    try:
        return build_sector(session, sector or "")
    finally:
        session.close()


@router.get("/api/terminal/congress/returns")
def api_terminal_congress_returns(
    month: str | None = Query(None, description="YYYY-MM"),
    date_field: str = Query("filing"),
    side: str | None = None,
    chamber: str | None = None,
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


@router.get("/api/terminal/congress/politician")
def api_terminal_congress_politician(name: str | None = None):
    from congress_quant_tracker.enrichers.terminal_congress import build_politician

    session = get_db()
    try:
        return build_politician(session, name or "")
    finally:
        session.close()


@router.get("/api/terminal/market/{ticker}")
def api_terminal_market_chart(
    ticker: str,
    sessions: int = Query(120, ge=20, le=400),
    from_date: str | None = Query(
        None,
        description="ISO date — chart starts early enough to include this trade day (daily bars)",
    ),
):
    """Daily OHLCV for FOCUSED ASSET CHART.

    Always daily (weekday sessions). If from_date is set (trade date), the window
    starts ~15 calendar days before that date through today so distant trades stay
    on-scale with a visible marker — not clipped to a short 60-bar window.
    """
    from sqlalchemy import desc

    from congress_quant_tracker.database.models import Trade
    from congress_quant_tracker.enrichers.market_data import get_history

    ticker = ticker.upper().strip()
    end = date.today()
    start = end - timedelta(days=max(sessions * 2, 180))

    trade_d: date | None = None
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
        t_rows = (
            session.query(
                Trade.trade_date,
                Trade.transaction_type,
                Trade.value_min,
                Trade.value_max,
            )
            .filter(Trade.ticker == ticker, Trade.trade_date.isnot(None))
            .order_by(desc(Trade.trade_date))
            .all()
        )
        buy_vol = 0.0
        buy_shares = 0.0
        sell_vol = 0.0
        sell_shares = 0.0
        price_by_date = {b["date"]: b["close"] for b in bars}
        sorted_dates = sorted(price_by_date.keys())
        for td_str, side, vmin, vmax in t_rows:
            d_str = str(td_str)[:10]
            p = price_by_date.get(d_str)
            if not p:
                for b_date in sorted_dates:
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
        "convention": (
            "daily bars (weekday sessions), auto_adjust=True; "
            "window expands to include trade date"
        ),
    }


@router.get("/api/terminal/chat/models")
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
                "name": "Local Llama Server",
                "badge": "100% OFFLINE / PRIVATE",
                "available": True,
                "is_default": False,
            },
        ],
        "default_provider": "groq",
    }


@router.post("/api/terminal/chat")
async def api_chat(req: ChatRequest):
    """Execute CongressQuant AI Copilot analysis."""
    from congress_quant_tracker.agent.copilot import CopilotAgent

    agent = CopilotAgent(provider=req.provider)
    result = await agent.chat(req.messages)
    return result


@router.get("/api/terminal/{dataset}")
def api_terminal_dataset_path(dataset: str):
    """Alias: /api/terminal/tape → same as ?dataset=tape.
    Skip reserved path segments handled by more specific routes above.
    """
    if dataset in ("congress", "market", "health", "dataset", "chat"):
        raise HTTPException(status_code=404, detail="use nested terminal routes")
    return api_terminal_dataset(dataset=dataset)
