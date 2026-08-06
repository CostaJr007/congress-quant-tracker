"""Analysis by individual politician: ranking, history, sector exposure."""

from datetime import date, datetime
from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from congress_quant_tracker.database.models import Company, Politician, Trade


class PoliticianAnalyzer:
    """Analyzes trading behavior at the individual politician level."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_top_traders(self, limit: int = 20, chamber: Optional[str] = None) -> pd.DataFrame:
        """Rank politicians by total number of trades."""
        query = (
            self.session.query(
                Politician.id,
                Politician.name,
                Politician.chamber,
                Politician.party,
                Politician.state,
                func.count(Trade.id).label("trade_count"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
        )

        if chamber:
            query = query.filter(Politician.chamber == chamber)

        query = query.group_by(Politician.id).order_by(func.count(Trade.id).desc()).limit(limit)

        return pd.DataFrame(
            query.all(),
            columns=["id", "name", "chamber", "party", "state", "trade_count"],
        )

    def get_politician_trade_history(
        self,
        politician_id: int,
        ticker: Optional[str] = None,
        transaction_type: Optional[str] = None,
    ) -> pd.DataFrame:
        """Get complete trade history for a politician."""
        query = (
            self.session.query(
                Trade.id,
                Trade.ticker,
                Trade.asset_name,
                Trade.transaction_type,
                Trade.trade_date,
                Trade.filing_date,
                Trade.value_min,
                Trade.value_max,
                Trade.value_range,
                Trade.report_type,
            )
            .filter(Trade.politician_id == politician_id)
        )

        if ticker:
            query = query.filter(Trade.ticker == ticker.upper())
        if transaction_type:
            query = query.filter(Trade.transaction_type == transaction_type)

        query = query.order_by(Trade.trade_date.desc())

        return pd.DataFrame(
            query.all(),
            columns=[
                "id", "ticker", "asset_name", "transaction_type",
                "trade_date", "filing_date", "value_min", "value_max",
                "value_range", "report_type",
            ],
        )

    def get_politician_sector_exposure(self, politician_id: int) -> pd.DataFrame:
        """Get sector exposure breakdown for a politician."""
        query = (
            self.session.query(
                Company.sector,
                func.count(Trade.id).label("trade_count"),
                func.sum(Trade.value_max).label("total_value_max"),
                func.sum(Trade.value_min).label("total_value_min"),
            )
            .join(Trade, Trade.ticker == Company.ticker)
            .filter(Trade.politician_id == politician_id)
            .filter(Company.sector.isnot(None))
            .group_by(Company.sector)
            .order_by(func.count(Trade.id).desc())
        )

        rows = query.all()
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(
            rows,
            columns=["sector", "trade_count", "total_value_max", "total_value_min"],
        )
        return df

    def search_politicians(self, name_query: str) -> pd.DataFrame:
        """Search politicians by name (case-insensitive partial match)."""
        query = (
            self.session.query(
                Politician.id,
                Politician.name,
                Politician.chamber,
                Politician.party,
                Politician.state,
                Politician.district,
            )
            .filter(Politician.name.ilike(f"%{name_query}%"))
            .order_by(Politician.name)
            .limit(50)
        )

        return pd.DataFrame(
            query.all(),
            columns=["id", "name", "chamber", "party", "state", "district"],
        )

    def get_politician_buy_sell_ratio(self, politician_id: int) -> dict:
        """Get buy vs sell ratio for a politician."""
        buys = (
            self.session.query(func.count(Trade.id))
            .filter(Trade.politician_id == politician_id)
            .filter(Trade.transaction_type == "buy")
            .scalar()
            or 0
        )
        sells = (
            self.session.query(func.count(Trade.id))
            .filter(Trade.politician_id == politician_id)
            .filter(Trade.transaction_type == "sell")
            .scalar()
            or 0
        )

        total = buys + sells
        return {
            "politician_id": politician_id,
            "buys": buys,
            "sells": sells,
            "total": total,
            "buy_pct": round(buys / total * 100, 1) if total > 0 else 0,
            "sell_pct": round(sells / total * 100, 1) if total > 0 else 0,
        }
