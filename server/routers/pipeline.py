"""Data pipeline endpoints (update, rescore, enrich)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from congress_quant_tracker.database.models import Politician
from server.deps import get_db

router = APIRouter()


@router.post("/api/pipeline/run")
def api_run_pipeline():
    from congress_quant_tracker.services.data_updater import DataUpdateService

    updater = DataUpdateService()
    stats = updater.run_full_update()
    return {"status": "completed", "stats": stats}


@router.post("/api/pipeline/house-official")
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


@router.get("/api/pipeline/senate-probe")
def api_senate_probe():
    """Check if efdsearch.senate.gov is reachable from this server."""
    from congress_quant_tracker.fetchers.senate_official import probe_efd_access

    return probe_efd_access()


@router.post("/api/pipeline/senate")
def api_senate_update(
    strategy: str = Query("auto", description="auto|congressinvests|efd"),
    pages: int = Query(25, ge=1, le=80),
):
    """Update Senate trades (auto falls back if eFD is Akamai-blocked)."""
    from congress_quant_tracker.services.senate_pipeline import SenatePipeline

    stats = SenatePipeline().run(strategy=strategy, max_pages=pages)
    return {"status": "completed", "stats": stats}


@router.post("/api/pipeline/rescore")
def api_rescore():
    """Reclassify assets, extract options, re-score all trades."""
    from congress_quant_tracker.services.data_updater import DataUpdateService

    updater = DataUpdateService()
    stats = updater.rescore_all()
    return {"status": "completed", "stats": stats}


@router.post("/api/pipeline/fix-parties")
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
            if info.get("district") is not None and str(pol.district or "") != str(
                info["district"]
            ):
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


@router.post("/api/pipeline/enrich")
def api_enrich():
    """Fill sectors, photo URLs, options rows, then rescore."""
    from congress_quant_tracker.enrichers.sectors import apply_sectors_to_session
    from congress_quant_tracker.services.data_updater import DataUpdateService

    session = get_db()
    try:
        sector_stats = apply_sectors_to_session(session)

        photos = 0
        for pol in session.query(Politician).all():
            if pol.bioguide_id and not pol.photo_url:
                pol.photo_url = f"/politicians/{pol.bioguide_id}.jpg"
                photos += 1
        session.commit()
    finally:
        session.close()

    rescore = DataUpdateService().rescore_all()
    return {
        "status": "completed",
        "sectors": sector_stats,
        "photos_filled": photos,
        "rescore": rescore,
    }
