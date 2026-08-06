"""Analysis by sector and specific company."""

from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from congress_quant_tracker.database.models import Company, Politician, Trade


class SectorAnalyzer:
    """Analyzes trading patterns by sector and individual company."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_sector_volumes(self) -> pd.DataFrame:
        """Get total trade volume by sector across all politicians."""
        query = (
            self.session.query(
                Company.sector,
                func.count(Trade.id).label("trade_count"),
                func.count(func.distinct(Trade.politician_id)).label("unique_politicians"),
                func.count(func.distinct(Trade.ticker)).label("unique_tickers"),
                func.sum(Trade.value_max).label("total_value_max"),
            )
            .join(Trade, Trade.ticker == Company.ticker)
            .filter(Company.sector.isnot(None))
            .group_by(Company.sector)
            .order_by(func.count(Trade.id).desc())
        )

        return pd.DataFrame(
            query.all(),
            columns=[
                "sector", "trade_count", "unique_politicians",
                "unique_tickers", "total_value_max",
            ],
        )

    def get_sector_party_breakdown(self, sector: str) -> pd.DataFrame:
        """Break down a specific sector by party."""
        query = (
            self.session.query(
                Politician.party,
                func.count(Trade.id).label("trade_count"),
                func.sum(
                    func.case(
                        (Trade.transaction_type == "buy", Trade.value_max),
                        else_=0,
                    )
                ).label("total_buy_value"),
                func.sum(
                    func.case(
                        (Trade.transaction_type == "sell", Trade.value_max),
                        else_=0,
                    )
                ).label("total_sell_value"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .join(Company, Trade.ticker == Company.ticker)
            .filter(Company.sector == sector)
            .group_by(Politician.party)
            .order_by(func.count(Trade.id).desc())
        )

        df = pd.DataFrame(
            query.all(),
            columns=["party", "trade_count", "total_buy_value", "total_sell_value"],
        )

        if not df.empty:
            df["net_value"] = df["total_buy_value"] - df["total_sell_value"]

        return df

    def get_top_buyers_of_ticker(self, ticker: str, limit: int = 15) -> pd.DataFrame:
        """Get top politicians buying a specific stock."""
        ticker = ticker.upper()

        query = (
            self.session.query(
                Politician.name,
                Politician.chamber,
                Politician.party,
                Politician.state,
                func.count(Trade.id).label("trade_count"),
                func.sum(Trade.value_max).label("total_value"),
                func.max(Trade.trade_date).label("last_trade_date"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .filter(func.upper(Trade.ticker) == ticker)
            .group_by(Politician.id, Politician.name, Politician.chamber, Politician.party, Politician.state)
            .order_by(func.count(Trade.id).desc())
            .limit(limit)
        )

        return pd.DataFrame(
            query.all(),
            columns=["name", "chamber", "party", "state", "trade_count", "total_value", "last_trade_date"],
        )

    def get_ticker_trade_summary(self, ticker: str) -> dict:
        """Get summary statistics for a specific ticker."""
        ticker = ticker.upper()

        total_trades = (
            self.session.query(func.count(Trade.id))
            .filter(func.upper(Trade.ticker) == ticker)
            .scalar()
            or 0
        )

        buys = (
            self.session.query(func.count(Trade.id))
            .filter(func.upper(Trade.ticker) == ticker)
            .filter(Trade.transaction_type == "buy")
            .scalar()
            or 0
        )

        sells = (
            self.session.query(func.count(Trade.id))
            .filter(func.upper(Trade.ticker) == ticker)
            .filter(Trade.transaction_type == "sell")
            .scalar()
            or 0
        )

        unique_politicians = (
            self.session.query(func.count(func.distinct(Trade.politician_id)))
            .filter(func.upper(Trade.ticker) == ticker)
            .scalar()
            or 0
        )

        party_breakdown = (
            self.session.query(
                Politician.party,
                func.count(Trade.id).label("count"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .filter(func.upper(Trade.ticker) == ticker)
            .group_by(Politician.party)
            .all()
        )

        company = (
            self.session.query(Company)
            .filter(func.upper(Company.ticker) == ticker)
            .first()
        )

        return {
            "ticker": ticker,
            "company_name": company.name if company else ticker,
            "sector": company.sector if company else None,
            "industry": company.industry if company else None,
            "total_trades": total_trades,
            "buys": buys,
            "sells": sells,
            "unique_politicians": unique_politicians,
            "party_breakdown": dict(party_breakdown) if party_breakdown else {},
        }

    def get_hottest_tickers(self, limit: int = 20) -> pd.DataFrame:
        """Get most actively traded tickers across all politicians."""
        query = (
            self.session.query(
                Trade.ticker,
                func.count(Trade.id).label("trade_count"),
                func.count(func.distinct(Trade.politician_id)).label("unique_politicians"),
                func.count(
                    func.case((Trade.transaction_type == "buy", 1))
                ).label("buy_count"),
                func.count(
                    func.case((Trade.transaction_type == "sell", 1))
                ).label("sell_count"),
                func.max(Trade.trade_date).label("last_trade_date"),
            )
            .filter(Trade.ticker.isnot(None))
            .group_by(Trade.ticker)
            .order_by(func.count(Trade.id).desc())
            .limit(limit)
        )

        df = pd.DataFrame(
            query.all(),
            columns=[
                "ticker", "trade_count", "unique_politicians",
                "buy_count", "sell_count", "last_trade_date",
            ],
        )

        if not df.empty:
            df["buy_pct"] = (df["buy_count"] / df["trade_count"] * 100).round(1)

        return df
