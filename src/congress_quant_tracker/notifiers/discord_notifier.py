# notifiers/discord_notifier.py — Discord webhook alerts for flagged trades

import requests
import os
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


def send_trade_alert(trade: Dict, pdf_url: str = "") -> bool:
    if not DISCORD_WEBHOOK_URL: return False
    score = trade.get("score", 0)
    tag = trade.get("tag", "routine").upper()
    color_map = {"HIGH_ALERT": 0xDC2626, "SUSPICIOUS": 0xD97706, "NOTEWORTHY": 0x2563EB, "ROUTINE": 0x6B7280}
    emoji = "🔴" if score >= 76 else "🟠" if score >= 51 else "🔵" if score >= 26 else "⚪"

    embed = {
        "title": f"{emoji} {trade.get('transaction_type', 'Trade').upper()}: {trade.get('ticker', 'N/A')}",
        "description": trade.get("reason", ""),
        "color": color_map.get(tag, 0x6B7280),
        "fields": [
            {"name": "Politician", "value": trade.get("politician_name", "Unknown"), "inline": True},
            {"name": "Asset", "value": trade.get("asset_name", trade.get("ticker", "N/A")), "inline": True},
            {"name": "Value", "value": trade.get("value_range", "N/A"), "inline": True},
            {"name": "Trade Date", "value": str(trade.get("trade_date", "N/A")), "inline": True},
            {"name": "Filed", "value": str(trade.get("filing_date", "N/A")), "inline": True},
            {"name": "Score", "value": f"{score}/100 — {tag.replace('_',' ').title()}", "inline": True},
        ],
        "footer": {"text": "Disclose — Congressional Trading Intelligence"},
    }
    if pdf_url: embed["url"] = pdf_url
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
        return resp.status_code in (200, 204)
    except Exception as e:
        logger.error(f"Discord send failed: {e}")
        return False


def send_daily_summary(trades: List[Dict], filings_count: int, new_trades: int) -> bool:
    if not DISCORD_WEBHOOK_URL: return False
    high = [t for t in trades if t.get("tag") == "high_alert"]
    suspicious = [t for t in trades if t.get("tag") == "suspicious"]
    noteworthy = [t for t in trades if t.get("tag") == "noteworthy"]
    embed = {
        "title": "Congressional Trade Alert — Daily Summary",
        "color": 0x1A365D,
        "fields": [
            {"name": "Filings Scanned", "value": str(filings_count), "inline": True},
            {"name": "New Trades", "value": str(new_trades), "inline": True},
            {"name": "🔴 High Alert", "value": str(len(high)), "inline": True},
            {"name": "🟠 Suspicious", "value": str(len(suspicious)), "inline": True},
            {"name": "🔵 Noteworthy", "value": str(len(noteworthy)), "inline": True},
        ],
        "footer": {"text": "Disclose — Congressional Trading Intelligence"},
    }
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
        return resp.status_code in (200, 204)
    except Exception as e:
        logger.error(f"Discord summary failed: {e}")
        return False
