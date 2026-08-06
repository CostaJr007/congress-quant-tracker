"""Suspicious trade detection — flags patterns like short-term trading, high volume, etc."""

from datetime import date, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from congress_quant_tracker.database.models import Politician, Trade


class SuspiciousAnalyzer:
    """Detects potentially suspicious trading patterns."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_high_value_trades(self, min_value: int = 1_000_000) -> pd.DataFrame:
        """Find trades above a high value threshold."""
        query = (
            self.session.query(
                Politician.name,
                Politician.party,
                Politician.chamber,
                Trade.ticker,
                Trade.transaction_type,
                Trade.trade_date,
                Trade.value_max,
                Trade.value_range,
                Trade.report_type,
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .filter(Trade.value_max >= min_value)
            .order_by(desc(Trade.value_max))
            .limit(50)
        )

        return pd.DataFrame(
            query.all(),
            columns=[
                "nome", "partido", "camara", "ticker",
                "tipo", "data", "valor_max", "range", "relatorio",
            ],
        )

    def get_rapid_trades(self, days_threshold: int = 7) -> pd.DataFrame:
        """Find politicians who buy and sell the same ticker rapidly."""
        trades = (
            self.session.query(
                Politician.name,
                Politician.party,
                Trade.ticker,
                Trade.transaction_type,
                Trade.trade_date,
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .order_by(Trade.politician_id, Trade.ticker, Trade.trade_date)
            .all()
        )

        suspicious: list[dict] = []
        grouped: dict[tuple[int, str], list] = {}

        for row in trades:
            key = (row[0], row[2]) if len(row) >= 3 else None
            if not key:
                continue
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(row)

        for (name, ticker), entries in grouped.items():
            for i in range(len(entries) - 1):
                curr = entries[i]
                next_t = entries[i + 1]
                if (curr[3] != next_t[3] and
                    abs((next_t[4] - curr[4]).days) <= days_threshold):
                    suspicious.append({
                        "politico": name,
                        "ticker": ticker,
                        "acao_1": f"{curr[3]} em {curr[4]}",
                        "acao_2": f"{next_t[3]} em {next_t[4]}",
                        "dias": abs((next_t[4] - curr[4]).days),
                    })

        return pd.DataFrame(suspicious)

    def get_sector_concentration(self, sector: str | None = None) -> pd.DataFrame:
        """Find politicians heavily concentrated in a specific sector."""
        from congress_quant_tracker.database.models import Company

        query = (
            self.session.query(
                Politician.name,
                Politician.party,
                Company.sector,
                func.count(Trade.id).label("trade_count"),
                func.count(func.distinct(Trade.ticker)).label("unique_tickers"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .join(Company, Trade.ticker == Company.ticker)
            .filter(Company.sector.isnot(None))
        )

        if sector:
            query = query.filter(Company.sector == sector)

        query = query.group_by(Politician.name, Politician.party, Company.sector)
        query = query.having(func.count(Trade.id) >= 5)
        query = query.order_by(desc(func.count(Trade.id)))
        query = query.limit(50)

        return pd.DataFrame(
            query.all(),
            columns=["nome", "partido", "setor", "trades", "tickers_unicos"],
        )

    def get_filing_delays(self, min_days: int = 30) -> pd.DataFrame:
        """Find trades with significant delays between trade date and filing date."""
        query = (
            self.session.query(
                Politician.name,
                Politician.party,
                Trade.ticker,
                Trade.transaction_type,
                Trade.trade_date,
                Trade.filing_date,
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .filter(Trade.filing_date.isnot(None))
            .filter(Trade.trade_date.isnot(None))
            .all()
        )

        delays: list[dict] = []
        for row in query:
            if row[4] and row[5]:
                delay = (row[5] - row[4]).days
                if delay >= min_days:
                    delays.append({
                        "politico": row[0],
                        "partido": row[1],
                        "ticker": row[2],
                        "tipo": row[3],
                        "data_trade": row[4],
                        "data_filing": row[5],
                        "dias_atraso": delay,
                    })

        df = pd.DataFrame(delays)
        if not df.empty:
            df = df.sort_values("dias_atraso", ascending=False)
        return df
