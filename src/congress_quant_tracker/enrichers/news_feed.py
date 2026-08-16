"""Live Financial & Macro News Feed Aggregator (Yahoo Finance, FXStreet, MarketWatch, ForexFactory)."""

from __future__ import annotations

import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

_NEWS_CACHE: list[dict[str, Any]] = []
_NEWS_CACHE_TIME: float = 0.0
_NEWS_CACHE_TTL: float = 120.0  # 2 minutes cache

KNOWN_TICKERS = {
    "NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "GOOGL", "GOOG", "META", "AMD",
    "SPY", "QQQ", "DIA", "IWM", "BTC", "ETH", "XAU", "OIL", "US10Y", "BA",
    "LMT", "RTX", "NOC", "JPM", "GS", "BAC", "WMT", "DIS", "NFLX", "PLTR"
}

RSS_FEEDS = [
    {
        "name": "Yahoo Finance",
        "url": "https://finance.yahoo.com/news/rssindex",
        "cat_default": "EQUITIES"
    },
    {
        "name": "FXStreet Macro",
        "url": "https://www.fxstreet.com/rss/news",
        "cat_default": "MACRO"
    },
    {
        "name": "MarketWatch",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "cat_default": "MACRO"
    }
]


def _classify_category(title: str, summary: str, default: str) -> str:
    text = f" {title} {summary} ".upper()
    if any(k in text for k in [" ARTIFICIAL INTELLIGENCE ", " AI ", "CHATGPT", "OPENAI", "LLM", "GENERATIVE AI", "ANTHROPIC", "DEEPSEEK"]):
        return "AI"
    if any(k in text for k in ["CHIP", "NVIDIA", "SEMICONDUCTOR", "TECH", "APPLE", "MICROSOFT", "SOFTWARE", "GOOGLE", "ALPHABET", "META PLATFORMS", "AMAZON"]):
        return "TECH"
    if any(k in text for k in ["FED", "POWELL", "INTEREST RATE", "INFLATION", "CPI", "GDP", "YIELD", "TREASURY", "DOLLAR", "CENTRAL BANK", "RECESSION", "JOBS", "PAYROLL"]):
        return "MACRO"
    if any(k in text for k in ["CONGRESS", "SENATE", "HOUSE", "PELOSI", "LAWMAKER", "LEGISLATION", "INSIDER TRADING", "ETHICS", "CAPITOL"]):
        return "CONGRESS"
    if any(k in text for k in ["ENERGY", "OIL", "CRUDE", "GAS", "OPEC", "SOLAR", "PETROLEUM", "DRILLING"]):
        return "ENERGY"
    if any(k in text for k in ["BANK", "FINANCIAL", "WALL STREET", "JPMORGAN", "GOLDMAN", "CREDIT", "HEDGE FUND", "MORTGAGE"]):
        return "FINANCE"
    if any(k in text for k in ["DEFENSE", "PENTAGON", "MILITARY", "WEAPON", "LOCKHEED", "MISSILE", "UKRAINE", "WAR"]):
        return "DEFENSE"
    if any(k in text for k in ["EARNINGS", "REVENUE", "PROFIT", "QUARTERLY", "EPS", "GUIDANCE", "DIVIDEND"]):
        return "EARNINGS"
    if any(k in text for k in ["CRYPTO", "BITCOIN", "ETHEREUM", "SOLANA", "BINANCE", "COINBASE", "BLOCKCHAIN"]):
        return "CRYPTO"
    return default


def _extract_tickers(text: str) -> list[str]:
    found = set()
    upper = text.upper()
    for t in KNOWN_TICKERS:
        if re.search(rf"\b{t}\b", upper):
            found.add(t)
    # Also find any $TICKER format
    for m in re.finditer(r"\$([A-Z]{1,5})\b", text):
        found.add(m.group(1))
    return sorted(list(found))[:4]


def _parse_pubdate(pub_date_str: str) -> str:
    if not pub_date_str:
        return datetime.now(timezone.utc).isoformat()
    # RFC 822 format: e.g. "Sat, 15 Aug 2026 22:30:00 GMT"
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(pub_date_str.strip(), fmt)
            return dt.isoformat()
        except ValueError:
            continue
    return datetime.now(timezone.utc).isoformat()


def fetch_live_news(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch and aggregate live news from Yahoo Finance, FXStreet, and MarketWatch."""
    global _NEWS_CACHE, _NEWS_CACHE_TIME
    now = time.time()
    if _NEWS_CACHE and (now - _NEWS_CACHE_TIME) < _NEWS_CACHE_TTL:
        return _NEWS_CACHE[:limit]

    articles = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*"
    }

    with httpx.Client(timeout=8.0, follow_redirects=True) as client:
        for feed in RSS_FEEDS:
            try:
                resp = client.get(feed["url"], headers=headers)
                if resp.status_code != 200:
                    continue
                root = ET.fromstring(resp.text)
                items = root.findall(".//item")
                for it in items[:25]:
                    title = (it.findtext("title") or "").strip()
                    if not title or title.startswith("<"):
                        continue
                    link = (it.findtext("link") or "").strip()
                    desc = (it.findtext("description") or "").strip()
                    # Strip html tags from description
                    clean_desc = re.sub(r"<[^>]+>", "", desc).strip()
                    pub_date = it.findtext("pubDate") or ""
                    time_iso = _parse_pubdate(pub_date)

                    cat = _classify_category(title, clean_desc, feed["cat_default"])
                    tickers = _extract_tickers(f"{title} {clean_desc}")
                    uid = hashlib.md5(f"{title}{link}".encode("utf-8")).hexdigest()[:12]

                    articles.append({
                        "id": f"live-{uid}",
                        "time": time_iso,
                        "cat": cat,
                        "headline": title,
                        "source": feed["name"],
                        "summary": clean_desc[:300] if clean_desc else title,
                        "link": link,
                        "tickers": tickers,
                        "linkedMove": "n/a",
                        "asof": time_iso,
                        "demo": False,
                    })
            except Exception as e:
                logger.debug(f"Feed error {feed['name']}: {e}")
                continue

    if articles:
        # Sort newest first
        articles.sort(key=lambda x: x.get("time") or "", reverse=True)
        _NEWS_CACHE = articles
        _NEWS_CACHE_TIME = now
        return _NEWS_CACHE[:limit]

    return _NEWS_CACHE[:limit] if _NEWS_CACHE else []
