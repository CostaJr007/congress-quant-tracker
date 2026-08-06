"""Tavily-powered enrichment and filters for congressional trades.

Uses Tavily Search API to:
  - Resolve missing / ambiguous tickers from asset names
  - Flag trades with recent news (filter: noteworthy context)
  - Optional sector/company context
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx

from congress_quant_tracker.config import settings

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"


class TavilyEnricher:
    def __init__(self) -> None:
        self.api_key = settings.TAVILY_API_KEY
        self.enabled = bool(self.api_key)

    def search(self, query: str, max_results: int = 3) -> list[dict]:
        if not self.enabled:
            return []
        try:
            with httpx.Client(timeout=30) as client:
                r = client.post(
                    TAVILY_URL,
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": max_results,
                        "include_answer": True,
                    },
                )
                r.raise_for_status()
                data = r.json()
                return data.get("results") or []
        except Exception as e:
            logger.warning("Tavily search failed: %s", e)
            return []

    def resolve_ticker(self, asset_name: str, current: Optional[str] = None) -> Optional[str]:
        """If ticker missing/suspicious, ask Tavily for the stock symbol."""
        if current and re.fullmatch(r"[A-Z]{1,5}(\.[A-Z])?", current):
            return current.upper()
        if not self.enabled or not asset_name:
            return current

        results = self.search(
            f"stock ticker symbol for company \"{asset_name}\" site:finance.yahoo.com OR site:nasdaq.com",
            max_results=5,
        )
        blob = " ".join(
            f"{r.get('title','')} {r.get('content','')} {r.get('url','')}" for r in results
        )
        # Prefer explicit ticker patterns; reject common English false positives
        ban = {
            "A", "I", "AM", "PM", "CEO", "CFO", "USD", "USA", "THE", "FOR", "AND",
            "STOCK", "SHARE", "PRICE", "UNDER", "OVER", "NEW", "INC", "CORP",
        }
        candidates: list[str] = []
        for pat in (
            r"\$([A-Z]{1,5})\b",
            r"\b(?:NYSE|NASDAQ|Nasdaq|ticker)[:\s/]+([A-Z]{1,5})\b",
            r"finance\.yahoo\.com/quote/([A-Z]{1,5})\b",
            r"nasdaq\.com/market-activity/stocks/([a-z]{1,5})\b",
        ):
            for m in re.finditer(pat, blob, re.I):
                sym = m.group(1).upper()
                if sym not in ban and 1 < len(sym) <= 5:
                    candidates.append(sym)
        if candidates:
            # most frequent candidate wins
            return max(set(candidates), key=candidates.count)
        return current

    def news_filter(self, ticker: str, politician: str = "") -> dict[str, Any]:
        """Return news context for a ticker (used as soft filter / score boost)."""
        if not self.enabled or not ticker:
            return {"has_news": False, "headlines": [], "score_boost": 0}

        q = f"{ticker} stock news"
        if politician:
            q = f"{politician} {ticker} stock trade OR disclosure"
        results = self.search(q, max_results=3)
        headlines = [r.get("title") or "" for r in results if r.get("title")]
        boost = 0
        joined = " ".join(headlines).lower()
        for kw, pts in (
            ("insider", 5),
            ("investigation", 8),
            ("congress", 3),
            ("stock act", 5),
            ("ethics", 5),
            ("earnings", 2),
        ):
            if kw in joined:
                boost += pts
        return {
            "has_news": bool(headlines),
            "headlines": headlines[:3],
            "score_boost": min(boost, 15),
        }

    def enrich_trades(self, trades: list[dict], politician: str = "", limit: int = 15) -> list[dict]:
        """Enrich a small batch of trades (rate-limit conscious)."""
        if not self.enabled:
            return trades

        for i, t in enumerate(trades):
            if i >= limit:
                break
            ticker = t.get("ticker")
            if not ticker or ticker in ("N/A", "NONE", "UNKNOWN"):
                resolved = self.resolve_ticker(t.get("asset_name") or "", ticker)
                if resolved:
                    t["ticker"] = resolved
                    t["ticker_resolved_by"] = "tavily"

            # Light news filter only for larger trades
            if (t.get("value_max") or 0) >= 50_000 and t.get("ticker"):
                news = self.news_filter(t["ticker"], politician)
                t["news_headlines"] = news.get("headlines")
                t["news_score_boost"] = news.get("score_boost", 0)

        return trades
