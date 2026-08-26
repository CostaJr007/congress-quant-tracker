# scoring/scorer.py — 9-signal suspicion scoring system for congressional trades
# Merged from disclose project, adapted for congress-quant-tracker ORM

import logging
import re
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from congress_quant_tracker.config import settings

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
except ImportError:
    yf = None

SCORE_HIGH_ALERT = 76
SCORE_SUSPICIOUS = 51
SCORE_NOTEWORTHY = 26

POINTS_COMMITTEE_MATCH = 25
POINTS_WAYS_AND_MEANS = 10
POINTS_LARGE_TRADE_100K = 15
POINTS_LARGE_TRADE_50K = 10
POINTS_DELAY_NEAR_LIMIT = 15
POINTS_DELAY_LATE = 8
POINTS_CLUSTER_3_PLUS = 20
POINTS_CLUSTER_2 = 15
POINTS_SPOUSE_DEPENDENT = 10
POINTS_CONTRARIAN_BUY = 10
POINTS_EARNINGS_PROXIMITY = 20
POINTS_OPTIONS_TRADE = 5

CONTRARIAN_DROP_THRESHOLD = -10
CONTRARIAN_LOOKBACK_DAYS = 35

COMMITTEE_SECTOR_MAP = {
    "Energy and Commerce": ["Energy", "Healthcare", "Communication Services", "Consumer Discretionary"],
    "Financial Services": ["Financial Services", "Real Estate"],
    "Armed Services": ["Industrials"],
    "Agriculture": ["Consumer Staples", "Materials"],
    "Science": ["Information Technology"],
    "Technology": ["Information Technology"],
    "Transportation": ["Industrials", "Energy"],
    "Judiciary": ["Information Technology", "Communication Services"],
    "Health": ["Healthcare"],
    "Banking": ["Financial Services", "Real Estate"],
    "Intelligence": ["Information Technology", "Industrials"],
    "Foreign Relations": ["Industrials", "Energy"],
    "Homeland Security": ["Industrials", "Information Technology"],
    "Veterans": ["Healthcare"],
    "Budget": ["Financial Services"],
    "Finance": ["Financial Services", "Healthcare", "Energy"],
    "Appropriations": ["Industrials", "Information Technology", "Healthcare"],
}


def tag_from_score(score: int) -> str:
    if score >= SCORE_HIGH_ALERT: return "high_alert"
    if score >= SCORE_SUSPICIOUS: return "suspicious"
    if score >= SCORE_NOTEWORTHY: return "noteworthy"
    return "routine"


def _parse_date(date_val) -> Optional[datetime]:
    if not date_val: return None
    if isinstance(date_val, datetime): return date_val
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try: return datetime.strptime(str(date_val), fmt)
        except ValueError: continue
    return None


def _parse_amount_upper(amount_str: str) -> int:
    if not amount_str: return 0
    amounts = re.findall(r"\$([\d,]+)", amount_str)
    return int(amounts[-1].replace(",", "")) if amounts else 0


class TradeScorer:
    """Scores individual trades and batches for suspicion."""

    def score_committee_match(self, committees: List[str], sector: str) -> Tuple[int, str]:
        if not committees or not sector: return 0, ""
        from congress_quant_tracker.enrichers.sectors import scorer_sector
        sector_canon = scorer_sector(sector) or sector
        for comm in committees:
            if "Ways and Means" in comm:
                return POINTS_WAYS_AND_MEANS, f"Ways & Means → {sector_canon} (+{POINTS_WAYS_AND_MEANS})"
        for comm in committees:
            for keyword, sectors in COMMITTEE_SECTOR_MAP.items():
                if keyword.lower() in comm.lower() and (sector in sectors or sector_canon in sectors):
                    return POINTS_COMMITTEE_MATCH, f"{comm} → {sector_canon} (+{POINTS_COMMITTEE_MATCH})"
        return 0, ""

    def score_trade_size(self, value_max: int) -> Tuple[int, str]:
        if value_max > 1_000_000: return 25, "Trade >$1M (+25)"
        if value_max > 100_000: return POINTS_LARGE_TRADE_100K, f"Trade >$100K (+{POINTS_LARGE_TRADE_100K})"
        if value_max > 50_000: return POINTS_LARGE_TRADE_50K, f"Trade >$50K (+{POINTS_LARGE_TRADE_50K})"
        return 0, ""

    def score_disclosure_delay(self, trade_date, filing_date) -> Tuple[int, str]:
        tx_date = _parse_date(trade_date)
        disc_date = _parse_date(filing_date)
        if not tx_date or not disc_date: return 0, ""
        delay = (disc_date - tx_date).days
        if delay < 0: return 0, ""
        if delay >= 46: return 25, f"Delay: {delay}d (OVER LIMIT, +25)"
        if 38 <= delay <= 45: return POINTS_DELAY_NEAR_LIMIT, f"Delay: {delay}d (+{POINTS_DELAY_NEAR_LIMIT})"
        if 30 <= delay <= 37: return POINTS_DELAY_LATE, f"Delay: {delay}d (+{POINTS_DELAY_LATE})"
        return 0, ""

    def compute_cluster_scores(self, trades: List[Dict]) -> Dict[str, Tuple[int, List[str]]]:
        ticker_members = defaultdict(set)
        for t in trades:
            ticker = t.get("ticker", "")
            if ticker: ticker_members[ticker].add(t.get("politician_name", ""))
        results = {}
        for ticker, members in ticker_members.items():
            if len(members) >= 3: results[ticker] = (POINTS_CLUSTER_3_PLUS, list(members))
            elif len(members) >= 2: results[ticker] = (POINTS_CLUSTER_2, list(members))
        return results

    def score_contrarian(self, ticker: str, trade_date, transaction_type: str) -> Tuple[int, str]:
        if settings.NO_YF or yf is None or not ticker or "buy" not in transaction_type.lower():
            return 0, ""
        tx_date = _parse_date(trade_date)
        if not tx_date: return 0, ""
        try:
            start = tx_date - timedelta(days=CONTRARIAN_LOOKBACK_DAYS)
            end = tx_date - timedelta(days=1)
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
            if hist.empty or len(hist) < 5: return 0, ""
            price_start = hist["Close"].iloc[0]
            price_end = hist["Close"].iloc[-1]
            pct_change = ((price_end - price_start) / price_start) * 100
            if pct_change < CONTRARIAN_DROP_THRESHOLD:
                return POINTS_CONTRARIAN_BUY, f"Contrarian: {ticker} {pct_change:.1f}% (+{POINTS_CONTRARIAN_BUY})"
        except Exception as e:
            logger.debug("Contrarian lookup failed for %s: %s", ticker, e)
        return 0, ""

    def score_options_trade(self, asset_type: str) -> Tuple[int, str]:
        if asset_type and asset_type.lower() in ("option", "option_call", "option_put"):
            return POINTS_OPTIONS_TRADE, f"Options trade (+{POINTS_OPTIONS_TRADE})"
        return 0, ""

    def score_owner(self, owner: str) -> Tuple[int, str]:
        o = (owner or "").strip().upper()
        if o in ("SP", "SPOUSE"):
            return POINTS_SPOUSE_DEPENDENT, f"Spouse trade (+{POINTS_SPOUSE_DEPENDENT})"
        if o in ("DC", "DEPENDENT"):
            return POINTS_SPOUSE_DEPENDENT, f"Dependent trade (+{POINTS_SPOUSE_DEPENDENT})"
        if o in ("JT", "JOINT"):
            return 5, "Joint account trade (+5)"
        return 0, ""

    def score_earnings_proximity(self, ticker: str, trade_date) -> Tuple[int, str]:
        if settings.NO_YF or yf is None or not ticker:
            return 0, ""
        tx_date = _parse_date(trade_date)
        if not tx_date: return 0, ""
        try:
            stock = yf.Ticker(ticker)
            earnings = stock.earnings_dates
            if earnings is None or earnings.empty: return 0, ""
            for edate_val in earnings.index[:4]:
                delta = abs((tx_date - edate_val).days)
                if delta <= 7:
                    return POINTS_EARNINGS_PROXIMITY, f"Within {delta}d of earnings (+{POINTS_EARNINGS_PROXIMITY})"
        except Exception as e:
            logger.debug("Earnings proximity lookup failed for %s: %s", ticker, e)
        return 0, ""

    def score_trade(self, trade: Dict, cluster_results: Dict = None, sector: str = "",
                    committees: List[str] = None) -> Dict:
        total = 0
        reasons = []

        pts, reason = self.score_committee_match(committees or [], sector)
        if pts: total += pts; reasons.append(reason)

        pts, reason = self.score_trade_size(trade.get("value_max", 0))
        if pts: total += pts; reasons.append(reason)

        pts, reason = self.score_disclosure_delay(trade.get("trade_date"), trade.get("filing_date"))
        if pts: total += pts; reasons.append(reason)

        pts, reason = self.score_contrarian(
            trade.get("ticker"), trade.get("trade_date"), trade.get("transaction_type", ""))
        if pts: total += pts; reasons.append(reason)

        pts, reason = self.score_options_trade(trade.get("asset_type", ""))
        if pts: total += pts; reasons.append(reason)

        pts, reason = self.score_owner(trade.get("owner", ""))
        if pts: total += pts; reasons.append(reason)

        pts, reason = self.score_earnings_proximity(trade.get("ticker"), trade.get("trade_date"))
        if pts: total += pts; reasons.append(reason)

        ticker = trade.get("ticker", "")
        if cluster_results and ticker in cluster_results:
            cluster_pts, cluster_members = cluster_results[ticker]
            other = [m for m in cluster_members if m != trade.get("politician_name")]
            if other:
                total += cluster_pts
                sample = ", ".join(other[:3])
                extra = f" +{len(other) - 3} more" if len(other) > 3 else ""
                reasons.append(f"Cluster: {sample}{extra} (+{cluster_pts})")

        total = min(total, 100)
        tag = tag_from_score(total)
        return {"score": total, "tag": tag, "reason": " | ".join(reasons) if reasons else "No signals"}

    def score_batch(self, trades: List[Dict], committee_map: Dict[int, List[str]] = None,
                    sector_map: Dict[str, str] = None) -> List[Dict]:
        cluster = self.compute_cluster_scores(trades)
        scored = []
        for t in trades:
            politician_id = t.get("politician_id")
            comms = committee_map.get(politician_id, []) if committee_map else []
            sector = sector_map.get(t.get("ticker", ""), "") if sector_map else ""
            result = self.score_trade(t, cluster, sector, comms)
            t.update(result)
            scored.append(t)
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored
