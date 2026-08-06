"""Analysis by party: Democrat vs Republican trading behavior comparison."""

from datetime import date, datetime
from typing import Optional

import pandas as pd
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from congress_quant_tracker.database.models import (
    Company,
    OptionsTrade,
    Politician,
    Trade,
)


class PartyAnalyzer:
    """Compares trading behavior between Democrats and Republicans."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_party_trade_volume(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Get total buy/sell volume by party."""
        query = (
            self.session.query(
                Politician.party,
                Trade.transaction_type,
                func.count(Trade.id).label("count"),
                func.sum(Trade.value_max).label("total_value_max"),
                func.sum(Trade.value_min).label("total_value_min"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
        )

        if start_date:
            query = query.filter(Trade.trade_date >= start_date)
        if end_date:
            query = query.filter(Trade.trade_date <= end_date)

        query = query.group_by(Politician.party, Trade.transaction_type).order_by(
            Politician.party, Trade.transaction_type
        )

        return pd.DataFrame(
            query.all(),
            columns=["party", "transaction_type", "count", "total_value_max", "total_value_min"],
        )

    def get_party_sector_exposure(self) -> pd.DataFrame:
        """Get sector exposure by party — which sectors each party trades most."""
        query = (
            self.session.query(
                Politician.party,
                Company.sector,
                func.count(Trade.id).label("trade_count"),
                func.sum(
                    case(
                        (Trade.transaction_type == "buy", Trade.value_max),
                        else_=0,
                    )
                ).label("total_buy_value"),
                func.sum(
                    case(
                        (Trade.transaction_type == "sell", Trade.value_max),
                        else_=0,
                    )
                ).label("total_sell_value"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .join(Company, Trade.ticker == Company.ticker, isouter=True)
            .filter(Company.sector.isnot(None))
            .group_by(Politician.party, Company.sector)
            .order_by(func.count(Trade.id).desc())
        )

        df = pd.DataFrame(
            query.all(),
            columns=["party", "sector", "trade_count", "total_buy_value", "total_sell_value"],
        )

        if not df.empty:
            df["net_value"] = df["total_buy_value"] - df["total_sell_value"]

        return df

    def get_party_sector_heatmap(self) -> pd.DataFrame:
        """Build a party vs sector matrix for heatmap visualization."""
        df = self.get_party_sector_exposure()

        if df.empty:
            return pd.DataFrame()

        pivot = df.pivot_table(
            index="sector",
            columns="party",
            values="trade_count",
            aggfunc="sum",
            fill_value=0,
        )

        return pivot

    def get_party_net_buying_by_sector(self) -> pd.DataFrame:
        """Net buying (buys - sells) by sector for each party."""
        df = self.get_party_sector_exposure()

        if df.empty:
            return pd.DataFrame()

        net = (
            df.groupby(["party", "sector"])["net_value"]
            .sum()
            .reset_index()
            .sort_values("net_value", ascending=False)
        )

        return net

    def get_party_behavior_diff(
        self, sector: Optional[str] = None
    ) -> pd.DataFrame:
        """Get difference in behavior between parties: what sectors each prefers."""
        buy_query = (
            self.session.query(
                Politician.party,
                Company.sector,
                func.count(Trade.id).label("buy_count"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .join(Company, Trade.ticker == Company.ticker, isouter=True)
            .filter(Trade.transaction_type == "buy")
            .filter(Company.sector.isnot(None))
        )

        if sector:
            buy_query = buy_query.filter(Company.sector == sector)

        buy_query = buy_query.group_by(Politician.party, Company.sector)
        buy_df = pd.DataFrame(
            buy_query.all(),
            columns=["party", "sector", "buy_count"],
        )

        sell_query = (
            self.session.query(
                Politician.party,
                Company.sector,
                func.count(Trade.id).label("sell_count"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .join(Company, Trade.ticker == Company.ticker, isouter=True)
            .filter(Trade.transaction_type == "sell")
            .filter(Company.sector.isnot(None))
        )

        if sector:
            sell_query = sell_query.filter(Company.sector == sector)

        sell_query = sell_query.group_by(Politician.party, Company.sector)
        sell_df = pd.DataFrame(
            sell_query.all(),
            columns=["party", "sector", "sell_count"],
        )

        if buy_df.empty and sell_df.empty:
            return pd.DataFrame()

        merged = pd.merge(buy_df, sell_df, on=["party", "sector"], how="outer").fillna(0)
        merged["buy_count"] = merged["buy_count"].astype(int)
        merged["sell_count"] = merged["sell_count"].astype(int)
        merged["net_count"] = merged["buy_count"] - merged["sell_count"]

        return merged.sort_values("net_count", ascending=False)

    def get_party_trading_timeline(
        self, months: int = 12
    ) -> pd.DataFrame:
        """Get monthly trading volume by party for the last N months."""
        from sqlalchemy import extract

        query = (
            self.session.query(
                func.date_trunc("month", Trade.trade_date).label("month"),
                Politician.party,
                func.count(Trade.id).label("trade_count"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .group_by(func.date_trunc("month", Trade.trade_date), Politician.party)
            .order_by("month")
        )

        df = pd.DataFrame(
            query.all(),
            columns=["month", "party", "trade_count"],
        )

        return df

    def get_top_party_tickers(self, party: str, limit: int = 10) -> pd.DataFrame:
        """Get most traded tickers by a specific party."""
        query = (
            self.session.query(
                Trade.ticker,
                func.count(Trade.id).label("trade_count"),
                func.count(case((Trade.transaction_type == "buy", 1)).label("buys")),
                func.count(case((Trade.transaction_type == "sell", 1)).label("sells")),
            )
            .join(Politician, Politician.id == Trade.politician_id)
            .filter(Politician.party == party)
            .filter(Trade.ticker.isnot(None))
            .group_by(Trade.ticker)
            .order_by(func.count(Trade.id).desc())
            .limit(limit)
        )

        return pd.DataFrame(
            query.all(),
            columns=["ticker", "trade_count", "buys", "sells"],
        )

    def get_party_summary_stats(self) -> dict:
        """Quick summary stats for each party."""
        stats: dict[str, dict] = {}

        for party in ["D", "R", "I"]:
            politician_count = (
                self.session.query(func.count(Politician.id))
                .filter(Politician.party == party)
                .scalar()
                or 0
            )

            trade_count = (
                self.session.query(func.count(Trade.id))
                .join(Politician, Politician.id == Trade.politician_id)
                .filter(Politician.party == party)
                .scalar()
                or 0
            )

            buy_count = (
                self.session.query(func.count(Trade.id))
                .join(Politician, Politician.id == Trade.politician_id)
                .filter(Politician.party == party)
                .filter(Trade.transaction_type == "buy")
                .scalar()
                or 0
            )

            sell_count = (
                self.session.query(func.count(Trade.id))
                .join(Politician, Politician.id == Trade.politician_id)
                .filter(Politician.party == party)
                .filter(Trade.transaction_type == "sell")
                .scalar()
                or 0
            )

            stats[party] = {
                "politicians": politician_count,
                "total_trades": trade_count,
                "buys": buy_count,
                "sells": sell_count,
            }

        return stats
