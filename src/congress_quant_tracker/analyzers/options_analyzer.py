"""Advanced options trading analysis: calls vs puts, strikes, expiration patterns."""

from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from congress_quant_tracker.database.models import (
    Company,
    OptionsTrade,
    Politician,
    Trade,
)


class OptionsAnalyzer:
    """Analyzes options trading activity across politicians and parties."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_call_put_ratio_by_party(self) -> pd.DataFrame:
        """Get calls vs puts ratio for each party."""
        query = (
            self.session.query(
                Politician.party,
                OptionsTrade.option_type,
                func.count(OptionsTrade.id).label("count"),
                func.count(func.distinct(OptionsTrade.trade_id)).label("unique_trades"),
                func.sum(OptionsTrade.contracts_max).label("total_contracts"),
            )
            .join(Trade, Trade.id == OptionsTrade.trade_id)
            .join(Politician, Politician.id == Trade.politician_id)
            .group_by(Politician.party, OptionsTrade.option_type)
            .order_by(Politician.party, OptionsTrade.option_type)
        )

        df = pd.DataFrame(
            query.all(),
            columns=["party", "option_type", "count", "unique_trades", "total_contracts"],
        )

        return df

    def get_call_put_ratio_by_sector(self) -> pd.DataFrame:
        """Get calls vs puts breakdown by sector."""
        query = (
            self.session.query(
                Company.sector,
                OptionsTrade.option_type,
                func.count(OptionsTrade.id).label("count"),
            )
            .join(Trade, Trade.id == OptionsTrade.trade_id)
            .join(Company, Trade.ticker == Company.ticker, isouter=True)
            .filter(Company.sector.isnot(None))
            .group_by(Company.sector, OptionsTrade.option_type)
            .order_by(Company.sector, OptionsTrade.option_type)
        )

        df = pd.DataFrame(
            query.all(),
            columns=["sector", "option_type", "count"],
        )

        return df

    def get_popular_strikes(self, limit: int = 20) -> pd.DataFrame:
        """Get most common strike prices being traded."""
        query = (
            self.session.query(
                OptionsTrade.underlying_asset,
                OptionsTrade.option_type,
                OptionsTrade.strike,
                func.count(OptionsTrade.id).label("count"),
                func.count(func.distinct(OptionsTrade.trade_id)).label("unique_trades"),
            )
            .filter(OptionsTrade.strike.isnot(None))
            .filter(OptionsTrade.underlying_asset.isnot(None))
            .group_by(
                OptionsTrade.underlying_asset,
                OptionsTrade.option_type,
                OptionsTrade.strike,
            )
            .order_by(func.count(OptionsTrade.id).desc())
            .limit(limit)
        )

        return pd.DataFrame(
            query.all(),
            columns=["underlying", "option_type", "strike", "count", "unique_trades"],
        )

    def get_most_active_options_traders(self, limit: int = 15) -> pd.DataFrame:
        """Rank politicians by options trading activity."""
        query = (
            self.session.query(
                Politician.name,
                Politician.chamber,
                Politician.party,
                Politician.state,
                func.count(OptionsTrade.id).label("options_count"),
                func.count(
                    func.case((OptionsTrade.option_type == "call", 1))
                ).label("calls"),
                func.count(
                    func.case((OptionsTrade.option_type == "put", 1))
                ).label("puts"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .join(OptionsTrade, OptionsTrade.trade_id == Trade.id)
            .group_by(Politician.id, Politician.name, Politician.chamber, Politician.party, Politician.state)
            .order_by(func.count(OptionsTrade.id).desc())
            .limit(limit)
        )

        return pd.DataFrame(
            query.all(),
            columns=["name", "chamber", "party", "state", "options_count", "calls", "puts"],
        )

    def get_options_expiring_soon(self, months: int = 3) -> pd.DataFrame:
        """Get options trades with upcoming expiration dates."""
        from datetime import date, timedelta

        cutoff_date = date.today() + timedelta(days=30 * months)

        query = (
            self.session.query(
                Politician.name,
                Politician.party,
                OptionsTrade.underlying_asset,
                OptionsTrade.option_type,
                OptionsTrade.strike,
                OptionsTrade.expiration_date,
                OptionsTrade.contracts_max,
                OptionsTrade.premium_range,
            )
            .join(Trade, Trade.id == OptionsTrade.trade_id)
            .join(Politician, Politician.id == Trade.politician_id)
            .filter(OptionsTrade.expiration_date.isnot(None))
            .filter(OptionsTrade.expiration_date >= date.today())
            .filter(OptionsTrade.expiration_date <= cutoff_date)
            .order_by(OptionsTrade.expiration_date)
        )

        return pd.DataFrame(
            query.all(),
            columns=[
                "name", "party", "underlying", "option_type", "strike",
                "expiration_date", "contracts_max", "premium_range",
            ],
        )

    def get_options_by_ticker(self, ticker: str) -> pd.DataFrame:
        """Get all options trades for a specific ticker."""
        ticker = ticker.upper()

        query = (
            self.session.query(
                Politician.name,
                Politician.party,
                OptionsTrade.option_type,
                OptionsTrade.strike,
                OptionsTrade.expiration_date,
                OptionsTrade.contracts_min,
                OptionsTrade.contracts_max,
                OptionsTrade.premium_range,
                Trade.trade_date,
            )
            .join(Trade, Trade.id == OptionsTrade.trade_id)
            .join(Politician, Politician.id == Trade.politician_id)
            .filter(func.upper(OptionsTrade.underlying_asset) == ticker)
            .order_by(Trade.trade_date.desc())
        )

        return pd.DataFrame(
            query.all(),
            columns=[
                "name", "party", "option_type", "strike", "expiration_date",
                "contracts_min", "contracts_max", "premium_range", "trade_date",
            ],
        )

    def get_options_volume_summary(self) -> dict:
        """Overall options trading summary statistics."""
        total_options = (
            self.session.query(func.count(OptionsTrade.id)).scalar() or 0
        )
        total_calls = (
            self.session.query(func.count(OptionsTrade.id))
            .filter(OptionsTrade.option_type == "call")
            .scalar()
            or 0
        )
        total_puts = (
            self.session.query(func.count(OptionsTrade.id))
            .filter(OptionsTrade.option_type == "put")
            .scalar()
            or 0
        )
        unique_underlyings = (
            self.session.query(func.count(func.distinct(OptionsTrade.underlying_asset)))
            .scalar()
            or 0
        )

        return {
            "total_options": total_options,
            "calls": total_calls,
            "puts": total_puts,
            "call_put_ratio": round(total_calls / total_puts, 2) if total_puts > 0 else None,
            "unique_underlyings": unique_underlyings,
        }
