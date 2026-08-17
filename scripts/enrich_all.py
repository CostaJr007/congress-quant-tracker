"""Fill sectors, photo URLs, extract options, rescore. Safe for Windows consoles."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("NO_YF", "1")  # sector+committee rescore; skip slow yfinance

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import Politician, get_engine, get_session
from congress_quant_tracker.enrichers.sectors import apply_sectors_to_session
from congress_quant_tracker.services.data_updater import DataUpdateService


def fill_photos() -> int:
    session = get_session(get_engine(settings.DATABASE_URL))
    n = 0
    try:
        for pol in session.query(Politician).all():
            if pol.bioguide_id and (
                not pol.photo_url or not pol.photo_url.startswith("/politicians/")
            ):
                pol.photo_url = f"/politicians/{pol.bioguide_id}.jpg"
                n += 1
        session.commit()
        return n
    finally:
        session.close()


def main() -> None:
    print("[enrich] sectors...")
    session = get_session(get_engine(settings.DATABASE_URL))
    try:
        sector_stats = apply_sectors_to_session(session)
    finally:
        session.close()
    print("[enrich] sectors:", sector_stats)

    print("[enrich] photo urls...")
    photos = fill_photos()
    print("[enrich] photos filled:", photos)

    print("[enrich] rescore + options (NO_YF=1)...")
    stats = DataUpdateService().rescore_all()
    print("[enrich] rescore:", stats)


if __name__ == "__main__":
    main()
