"""Company data enrichment using yfinance."""

from datetime import datetime
from typing import Optional

import pandas as pd

from congress_quant_tracker.config import settings

try:
    import yfinance as yf
except ImportError:
    yf = None


class CompanyEnricher:
    """Enriches company data with sector, industry, and market data from yfinance."""

    CACHE: dict[str, dict] = {}

    def enrich_ticker(self, ticker: str) -> dict:
        """Fetch company info for a ticker from yfinance."""
        if ticker in self.CACHE:
            return self.CACHE[ticker]

        info: dict = {
            "ticker": ticker.upper(),
            "name": ticker.upper(),
            "sector": None,
            "industry": None,
            "market_cap": None,
            "beta": None,
        }

        from congress_quant_tracker.enrichers.sectors import TICKER_SECTOR

        info["sector"] = info["sector"] or TICKER_SECTOR.get(ticker.upper())

        if settings.NO_YF or yf is None:
            self.CACHE[ticker] = info
            return info

        try:
            stock = yf.Ticker(ticker)
            ticker_info = stock.info

            if ticker_info:
                info["name"] = ticker_info.get("longName") or ticker_info.get("shortName") or ticker
                info["sector"] = ticker_info.get("sector") or info["sector"]
                info["industry"] = ticker_info.get("industry")
                info["market_cap"] = ticker_info.get("marketCap")
                info["beta"] = ticker_info.get("beta")
        except Exception:
            pass

        self.CACHE[ticker] = info
        return info

    def enrich_batch(self, tickers: list[str]) -> list[dict]:
        """Enrich a batch of tickers."""
        return [self.enrich_ticker(t) for t in tickers]

    def get_or_create_company(self, session, ticker: str) -> "Company":
        """Get existing company record or create a new one."""
        from congress_quant_tracker.database.models import Company

        company = session.query(Company).filter_by(ticker=ticker.upper()).first()
        if company:
            return company

        info = self.enrich_ticker(ticker)
        company = Company(
            ticker=info["ticker"],
            name=info["name"],
            sector=info["sector"],
            industry=info["industry"],
            market_cap=info["market_cap"],
            beta=info["beta"],
            last_updated=datetime.utcnow(),
        )
        session.add(company)
        session.flush()
        return company

    def enrich_all_tickers_in_db(self, session) -> int:
        """Enrich all companies for tickers found in trades that are not in companies table."""
        from sqlalchemy import distinct
        from congress_quant_tracker.database.models import Trade, Company

        traded_tickers = [
            row[0]
            for row in session.query(distinct(Trade.ticker)).all()
            if row[0]
        ]

        existing_tickers = {
            row[0]
            for row in session.query(Company.ticker).all()
        }

        new_tickers = [t for t in traded_tickers if t.upper() not in existing_tickers]
        count = 0

        from congress_quant_tracker.enrichers.sectors import TICKER_SECTOR

        # Backfill static sector onto existing companies first (no network)
        for company in session.query(Company).filter(
            (Company.sector.is_(None)) | (Company.sector == "")
        ).all():
            mapped = TICKER_SECTOR.get((company.ticker or "").upper())
            if mapped:
                company.sector = mapped
                count += 1

        for ticker in new_tickers:
            self.get_or_create_company(session, ticker)
            count += 1

        session.commit()
        return count
