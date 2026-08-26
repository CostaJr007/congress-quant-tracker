"""Analyzer endpoints (party / sector / options / suspicious / compare)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from congress_quant_tracker.database.models import Politician
from server.deps import get_db

router = APIRouter()


def _df_records(df) -> list[dict]:
    if df is None:
        return []
    try:
        if getattr(df, "empty", False):
            return []
        return df.where(df.notna(), None).to_dict(orient="records")
    except Exception:
        return []


@router.get("/api/analyze/overview")
def api_analyze_overview():
    """Wire party / sector / options / suspicious analyzers for the web UI."""
    session = get_db()
    try:
        from congress_quant_tracker.analyzers.options_analyzer import OptionsAnalyzer
        from congress_quant_tracker.analyzers.party_analyzer import PartyAnalyzer
        from congress_quant_tracker.analyzers.sector_analyzer import SectorAnalyzer
        from congress_quant_tracker.analyzers.suspicious_analyzer import SuspiciousAnalyzer

        party = PartyAnalyzer(session)
        sector = SectorAnalyzer(session)
        options = OptionsAnalyzer(session)
        suspicious = SuspiciousAnalyzer(session)

        party_volume = _df_records(party.get_party_trade_volume())
        sector_volumes = _df_records(sector.get_sector_volumes())
        try:
            call_put = _df_records(options.get_call_put_ratio_by_party())
        except Exception:
            call_put = []
        high_value = _df_records(suspicious.get_high_value_trades(min_value=250_000))
        try:
            rapid = _df_records(suspicious.get_rapid_trades(days_threshold=14))
        except Exception:
            rapid = []

        return {
            "party": party_volume,
            "sector": sector_volumes,
            "options": call_put,
            "suspicious": high_value[:25],
            "party_volume": party_volume,
            "sectors": sector_volumes,
            "options_by_party": call_put,
            "high_value": high_value[:25],
            "rapid": rapid[:25],
        }
    finally:
        session.close()


@router.get("/api/analyze/party")
def api_analyze_party():
    session = get_db()
    try:
        from congress_quant_tracker.analyzers.party_analyzer import PartyAnalyzer

        return {"rows": _df_records(PartyAnalyzer(session).get_party_trade_volume())}
    finally:
        session.close()


@router.get("/api/analyze/sectors")
def api_analyze_sectors():
    session = get_db()
    try:
        from congress_quant_tracker.analyzers.sector_analyzer import SectorAnalyzer

        return {"rows": _df_records(SectorAnalyzer(session).get_sector_volumes())}
    finally:
        session.close()


@router.get("/api/analyze/options")
def api_analyze_options():
    session = get_db()
    try:
        from congress_quant_tracker.analyzers.options_analyzer import OptionsAnalyzer

        ana = OptionsAnalyzer(session)
        payload: dict[str, Any] = {}
        for name in (
            "get_call_put_ratio_by_party",
            "get_options_by_sector",
            "get_most_traded_strikes",
            "get_top_options_traders",
        ):
            fn = getattr(ana, name, None)
            if callable(fn):
                try:
                    payload[name] = _df_records(fn())
                except Exception:
                    payload[name] = []
        return payload
    finally:
        session.close()


@router.get("/api/analyze/suspicious")
def api_analyze_suspicious():
    session = get_db()
    try:
        from congress_quant_tracker.analyzers.suspicious_analyzer import SuspiciousAnalyzer

        ana = SuspiciousAnalyzer(session)
        return {
            "high_value": _df_records(ana.get_high_value_trades(min_value=250_000))[:40],
            "rapid": _df_records(ana.get_rapid_trades(days_threshold=14))[:40],
        }
    finally:
        session.close()


@router.get("/api/analyze/compare")
def api_analyze_compare(names: str = Query(..., description="Comma-separated politician names")):
    session = get_db()
    try:
        from congress_quant_tracker.analyzers.compare_analyzer import CompareAnalyzer

        ids: list[int] = []
        for raw in names.split(","):
            name = raw.strip()
            if not name:
                continue
            pol = session.query(Politician).filter(Politician.name.ilike(f"%{name}%")).first()
            if pol:
                ids.append(pol.id)
        if len(ids) < 2:
            raise HTTPException(status_code=400, detail="Need at least two matching politicians")
        return {"rows": _df_records(CompareAnalyzer(session).compare_stats(ids))}
    finally:
        session.close()
