"""Fill remaining Company/Trade sectors via yfinance. Bounded + cached."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import Company, Trade, get_engine, get_session
from congress_quant_tracker.enrichers.company_enricher import CompanyEnricher
from congress_quant_tracker.enrichers.sectors import apply_sectors_to_session


def main(limit: int = 80) -> None:
    settings.NO_YF = False
    session = get_session(get_engine(settings.DATABASE_URL))
    try:
        apply_sectors_to_session(session)
        missing = [
            row[0]
            for row in session.query(Trade.ticker)
            .filter((Trade.sector.is_(None)) | (Trade.sector == ""))
            .distinct()
            .all()
            if row[0]
        ]
        print(f"[yf-sector] missing tickers: {len(missing)} (capping {limit})")
        enricher = CompanyEnricher()
        filled = 0
        for ticker in missing[:limit]:
            info = enricher.enrich_ticker(ticker)
            sector = info.get("sector")
            if not sector:
                continue
            company = session.query(Company).filter(Company.ticker == ticker.upper()).first()
            if company:
                if not company.sector:
                    company.sector = sector
                if info.get("name") and company.name == company.ticker:
                    company.name = info["name"]
                if info.get("industry") and not company.industry:
                    company.industry = info["industry"]
            session.query(Trade).filter(
                Trade.ticker == ticker.upper(),
                (Trade.sector.is_(None)) | (Trade.sector == ""),
            ).update({"sector": sector}, synchronize_session=False)
            filled += 1
            print(f"  {ticker} -> {sector}")
        session.commit()
        print(f"[yf-sector] filled {filled}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
