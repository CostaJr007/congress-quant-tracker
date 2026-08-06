"""Compare politicians side by side."""

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from congress_quant_tracker.database.models import Company, Politician, Trade


class CompareAnalyzer:
    """Compare two or more politicians' trading patterns."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def compare_stats(self, politician_ids: list[int]) -> pd.DataFrame:
        """Get comparison stats for multiple politicians."""
        rows = []
        for pid in politician_ids:
            pol = self.session.query(Politician).filter_by(id=pid).first()
            if not pol:
                continue

            total = (
                self.session.query(func.count(Trade.id))
                .filter(Trade.politician_id == pid)
                .scalar()
            ) or 0
            buys = (
                self.session.query(func.count(Trade.id))
                .filter(Trade.politician_id == pid, Trade.transaction_type == "buy")
                .scalar()
            ) or 0
            sells = (
                self.session.query(func.count(Trade.id))
                .filter(Trade.politician_id == pid, Trade.transaction_type == "sell")
                .scalar()
            ) or 0
            unique_tickers = (
                self.session.query(func.count(func.distinct(Trade.ticker)))
                .filter(Trade.politician_id == pid)
                .scalar()
            ) or 0

            total_value = (
                self.session.query(func.sum(Trade.value_max))
                .filter(Trade.politician_id == pid)
                .scalar()
            ) or 0

            rows.append({
                "id": pid,
                "nome": pol.name,
                "partido": pol.party,
                "camara": pol.chamber,
                "total_trades": total,
                "compras": buys,
                "vendas": sells,
                "tickers_unicos": unique_tickers,
                "valor_total_max": total_value,
            })

        return pd.DataFrame(rows)

    def compare_sectors(self, politician_ids: list[int]) -> pd.DataFrame:
        """Compare sector exposure across politicians."""
        query = (
            self.session.query(
                Politician.name,
                Company.sector,
                func.count(Trade.id).label("trade_count"),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .join(Company, Trade.ticker == Company.ticker, isouter=True)
            .filter(Politician.id.in_(politician_ids))
            .filter(Company.sector.isnot(None))
            .group_by(Politician.name, Company.sector)
            .order_by(func.count(Trade.id).desc())
        )

        return pd.DataFrame(query.all(), columns=["politico", "setor", "trades"])

    def compare_overlap(self, id1: int, id2: int) -> pd.DataFrame:
        """Find tickers traded by both politicians."""
        tickers1 = {
            row[0]
            for row in self.session.query(Trade.ticker)
            .filter(Trade.politician_id == id1)
            .filter(Trade.ticker.isnot(None))
            .all()
        }
        tickers2 = {
            row[0]
            for row in self.session.query(Trade.ticker)
            .filter(Trade.politician_id == id2)
            .filter(Trade.ticker.isnot(None))
            .all()
        }
        overlap = tickers1 & tickers2

        pol1 = self.session.query(Politician).filter_by(id=id1).first()
        pol2 = self.session.query(Politician).filter_by(id=id2).first()

        rows = []
        for ticker in overlap:
            c1 = (
                self.session.query(func.count(Trade.id))
                .filter(Trade.politician_id == id1, Trade.ticker == ticker)
                .scalar()
            ) or 0
            c2 = (
                self.session.query(func.count(Trade.id))
                .filter(Trade.politician_id == id2, Trade.ticker == ticker)
                .scalar()
            ) or 0
            rows.append({
                "ticker": ticker,
                pol1.name if pol1 else "P1": c1,
                pol2.name if pol2 else "P2": c2,
            })

        return pd.DataFrame(rows)
