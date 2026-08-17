"""Deterministic Tool definitions and executors for CongressQuant AI Copilot."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import func, desc, or_, and_, text

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import Politician, Trade, get_engine, get_session

logger = logging.getLogger(__name__)

TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_trades",
            "description": "Search and filter congressional stock and options trades by politician, ticker, party, transaction type, date range, or suspicion score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "politician": {
                        "type": "string",
                        "description": "Name or partial name of the politician (e.g. 'Nancy Pelosi', 'Josh Gottheimer', 'John McGuire')."
                    },
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol in uppercase (e.g. 'NVDA', 'MSFT', 'AAPL', 'BLK')."
                    },
                    "party": {
                        "type": "string",
                        "enum": ["D", "R", "I"],
                        "description": "Political party: D (Democrat), R (Republican), I (Independent)."
                    },
                    "transaction_type": {
                        "type": "string",
                        "enum": ["buy", "sell", "exchange"],
                        "description": "Transaction side/type."
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (filters by filing_date or trade_date)."
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format."
                    },
                    "asset_type": {
                        "type": "string",
                        "description": "Filter by asset type keyword: 'call', 'put', 'stock', 'option', 'etf'."
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["score", "date", "volume"],
                        "description": "Sort order: 'score' (highest suspicion score first), 'date' (most recent first), 'volume' (largest trade size first)."
                    },
                    "min_score": {
                        "type": "number",
                        "description": "Minimum suspicion score from 0 to 100."
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of trades to return (default 15, max 50)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_options_trades",
            "description": "Query congressional stock options (Calls and Puts). Use for questions about who bought calls or puts, option contracts, or options activity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "option_type": {
                        "type": "string",
                        "enum": ["call", "put", "all"],
                        "description": "Filter by 'call' (call options), 'put' (put options), or 'all' options."
                    },
                    "politician": {
                        "type": "string",
                        "description": "Filter by politician name (e.g. 'Nancy Pelosi')."
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum entries to return (default 15)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_leaderboard",
            "description": "Get rankings of highest return politicians (profitability), most active traders, most traded tickers, highest suspicion politicians, or party volume comparisons.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": ["highest_returns", "most_active_traders", "most_traded_tickers", "highest_suspicion_traders", "party_breakdown"],
                        "description": "Metric to rank by: 'highest_returns' (ranked by average % profit/return since trade date), 'most_active_traders', 'most_traded_tickers', 'highest_suspicion_traders', 'party_breakdown'."
                    },
                    "period_year": {
                        "type": "number",
                        "description": "Filter by year, e.g. 2026."
                    },
                    "limit": {
                        "type": "number",
                        "description": "Number of top entries to return (default 10)."
                    }
                },
                "required": ["metric"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ticker_positioning_rankings",
            "description": "Rank tickers by Put/Call ratio, highest Buy % (bullish accumulation), highest Sell % (bearish distribution), or most accumulated by members of Congress. Use for positioning, sentiment, or 'which stocks are they buying' questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentiment_filter": {
                        "type": "string",
                        "enum": ["bullish", "bearish", "all"],
                        "description": "Filter by 'bullish' (best Put/Call ratio for buying, highest Buy % >=65%), 'bearish' (highest Sell % >=65%), or 'all'."
                    },
                    "min_trades": {
                        "type": "number",
                        "description": "Minimum total trades required (default 3 to avoid one-off stocks)."
                    },
                    "limit": {
                        "type": "number",
                        "description": "Number of top tickers to return (default 10)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_politician_profile",
            "description": "Retrieve full profile, committee memberships, state/district, total trade count, average suspicion score, and recent trades for a specific member of Congress.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Politician name or partial name."
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_safe_sql",
            "description": "Execute a raw READ-ONLY SQL query against the SQLite database for advanced analytics, groupings, or custom statistical aggregations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A valid SQLite SELECT query. Must only be SELECT (no INSERT/UPDATE/DELETE/DROP). Limit will be capped to 50."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_market_news",
            "description": "Search current live web news and financial developments via Tavily Search regarding congress trading, tickers, or regulatory hearings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for financial or political news."
                    }
                },
                "required": ["query"]
            }
        }
    }
]


def execute_query_trades(
    politician: Optional[str] = None,
    ticker: Optional[str] = None,
    party: Optional[str] = None,
    transaction_type: Optional[str] = None,
    asset_type: Optional[str] = None,
    sort_by: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_score: Optional[Any] = None,
    limit: Any = 15,
) -> Dict[str, Any]:
    session = get_session(get_engine(settings.DATABASE_URL))
    try:
        q = session.query(Trade).join(Politician, Trade.politician_id == Politician.id)
        if politician:
            q = q.filter(Politician.name.ilike(f"%{politician.strip()}%"))
        if ticker:
            q = q.filter(Trade.ticker.ilike(ticker.strip()))
        if party:
            q = q.filter(Politician.party == party.upper().strip())
        if transaction_type:
            q = q.filter(Trade.transaction_type.ilike(transaction_type.strip()))
        if asset_type:
            q = q.filter(or_(Trade.asset_type.ilike(f"%{asset_type.strip()}%"), Trade.asset_name.ilike(f"%{asset_type.strip()}%")))
        if start_date:
            q = q.filter(Trade.filing_date >= start_date)
        if end_date:
            q = q.filter(Trade.filing_date <= end_date)
        if min_score is not None:
            try:
                q = q.filter(Trade.score >= int(min_score))
            except Exception:
                pass

        try:
            limit_val = min(max(1, int(limit)), 50)
        except Exception:
            limit_val = 15

        total_matches = q.count()
        if sort_by == "score" or (min_score is not None and not sort_by):
            trades = q.order_by(Trade.score.desc(), Trade.filing_date.desc(), Trade.id.desc()).limit(limit_val).all()
        elif sort_by == "volume":
            trades = q.order_by(Trade.value_max.desc(), Trade.filing_date.desc(), Trade.id.desc()).limit(limit_val).all()
        else:
            trades = q.order_by(Trade.filing_date.desc(), Trade.trade_date.desc(), Trade.id.desc()).limit(limit_val).all()

        results = []
        for t in trades:
            pol = t.politician
            results.append({
                "politician": f"{pol.name} ({pol.party}-{pol.state or ''})" if pol else "",
                "ticker": t.ticker,
                "asset_name": t.asset_name,
                "type": t.transaction_type.upper(),
                "trade_date": t.trade_date.isoformat() if t.trade_date else None,
                "filing_date": t.filing_date.isoformat() if t.filing_date else None,
                "amount": t.value_range or f"${t.value_min:,} - ${t.value_max:,}",
                "score": t.score,
                "tag": t.tag,
                "reason": t.reason,
            })

        out = {"total_matching": total_matches, "trades_sample": results}

        # If filtered by ticker, calculate compact positioning summary
        if ticker:
            all_ticker_trades = q.all()
            total_buys = sum(1 for t in all_ticker_trades if (t.transaction_type or "").lower() in ("buy", "purchase"))
            total_sells = sum(1 for t in all_ticker_trades if (t.transaction_type or "").lower() in ("sell", "sale"))
            buy_vol = sum(t.value_max or 0 for t in all_ticker_trades if (t.transaction_type or "").lower() in ("buy", "purchase"))
            sell_vol = sum(t.value_max or 0 for t in all_ticker_trades if (t.transaction_type or "").lower() in ("sell", "sale"))
            total_c = max(1, total_buys + total_sells)
            buy_pct = round((total_buys / total_c) * 100, 1)
            pcr = round(total_sells / max(1, total_buys), 2)
            pols = list({f"{t.politician.name} ({t.politician.party})" for t in all_ticker_trades if t.politician})

            sentiment = "BULLISH ACCUMULATION" if buy_pct >= 65 else ("BEARISH DISTRIBUTION" if buy_pct <= 35 else "NEUTRAL / BALANCED")
            out["positioning_summary"] = {
                "ticker": ticker.upper(),
                "total_trades": total_matches,
                "buy_count": total_buys,
                "sell_count": total_sells,
                "buy_volume_est": f"${buy_vol:,.0f}",
                "sell_volume_est": f"${sell_vol:,.0f}",
                "buy_percentage": f"{buy_pct}%",
                "sell_percentage": f"{round(100 - buy_pct, 1)}%",
                "put_call_ratio": pcr,
                "sentiment": sentiment,
                "politicians_involved": pols[:8],
            }
        return out
    finally:
        session.close()


def execute_get_leaderboard(
    metric: str = "highest_returns",
    period_year: Optional[int] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    session = get_session(get_engine(settings.DATABASE_URL))
    limit_val = min(max(1, limit), 30)
    try:
        if metric in ("highest_returns", "returns", "profitability"):
            from congress_quant_tracker.enrichers.terminal_congress import build_returns_leaderboard
            res = build_returns_leaderboard(session, mode="member", limit=limit_val)
            rows = res.get("data", {}).get("rows", [])
            return {
                "metric": "highest_returns",
                "description": "Congress members ranked by calculated side-adjusted % return since trade date",
                "ranking": [
                    {
                        "rank": i + 1,
                        "name": r.get("politician"),
                        "party": r.get("party"),
                        "state_district": r.get("state_district"),
                        "avg_return_pct": f"{r.get('avg_return_adj', 0):+.2f}%",
                        "total_pnl_est": f"${r.get('total_pnl_est', 0):+,.0f}",
                        "trades_evaluated": r.get("trades_evaluated"),
                        "best_trade": f"{r['best_trade']['ticker']} {r['best_trade']['side']} ({r['best_trade']['return_side_adj']:+.2f}%)" if r.get("best_trade") else None,
                    }
                    for i, r in enumerate(rows)
                ]
            }

        elif metric == "most_active_traders":
            q = (
                session.query(
                    Politician.name,
                    Politician.party,
                    Politician.state,
                    func.count(Trade.id).label("total_trades"),
                    func.avg(Trade.score).label("avg_score")
                )
                .join(Trade, Politician.id == Trade.politician_id)
            )
            if period_year:
                from sqlalchemy import extract
                q = q.filter(extract("year", Trade.filing_date) == period_year)
            rows = q.group_by(Politician.id).order_by(desc("total_trades")).limit(limit_val).all()
            return {
                "metric": metric,
                "ranking": [
                    {
                        "rank": i + 1,
                        "name": r[0],
                        "party": r[1],
                        "state": r[2],
                        "total_trades": r[3],
                        "avg_suspicion_score": round(float(r[4] or 0), 1),
                    }
                    for i, r in enumerate(rows)
                ]
            }

        elif metric == "most_traded_tickers":
            q = session.query(
                Trade.ticker,
                func.count(Trade.id).label("trade_count"),
                func.count(func.distinct(Trade.politician_id)).label("unique_politicians")
            ).filter(Trade.ticker != "", Trade.ticker.isnot(None))
            if period_year:
                from sqlalchemy import extract
                q = q.filter(extract("year", Trade.filing_date) == period_year)
            rows = q.group_by(Trade.ticker).order_by(desc("trade_count")).limit(limit_val).all()
            return {
                "metric": metric,
                "ranking": [
                    {
                        "rank": i + 1,
                        "ticker": r[0],
                        "trade_count": r[1],
                        "unique_politicians": r[2]
                    }
                    for i, r in enumerate(rows)
                ]
            }

        elif metric == "highest_suspicion_traders":
            q = (
                session.query(
                    Politician.name,
                    Politician.party,
                    Politician.state,
                    func.count(Trade.id).label("total_trades"),
                    func.avg(Trade.score).label("avg_score"),
                    func.max(Trade.score).label("max_score")
                )
                .join(Trade, Politician.id == Trade.politician_id)
                .group_by(Politician.id)
                .having(func.count(Trade.id) >= 3)
                .order_by(desc("avg_score"))
                .limit(limit_val)
            )
            rows = q.all()
            return {
                "metric": metric,
                "ranking": [
                    {
                        "rank": i + 1,
                        "name": r[0],
                        "party": r[1],
                        "state": r[2],
                        "total_trades": r[3],
                        "avg_score": round(float(r[4] or 0), 1),
                        "max_score": r[5]
                    }
                    for i, r in enumerate(rows)
                ]
            }

        elif metric == "party_breakdown":
            rows = (
                session.query(
                    Politician.party,
                    func.count(Trade.id).label("total_trades"),
                    func.count(func.distinct(Politician.id)).label("politicians_count"),
                    func.avg(Trade.score).label("avg_score")
                )
                .join(Trade, Politician.id == Trade.politician_id)
                .group_by(Politician.party)
                .all()
            )
            return {
                "metric": metric,
                "parties": [
                    {
                        "party": r[0] or "Unknown",
                        "total_trades": r[1],
                        "politicians_count": r[2],
                        "avg_score": round(float(r[3] or 0), 1)
                    }
                    for r in rows
                ]
            }
        return {"error": f"Unknown metric: {metric}"}
    finally:
        session.close()


def execute_get_politician_profile(name: str) -> Dict[str, Any]:
    session = get_session(get_engine(settings.DATABASE_URL))
    try:
        pol = session.query(Politician).filter(Politician.name.ilike(f"%{name.strip()}%")).first()
        if not pol:
            return {"error": f"Politician '{name}' not found."}

        trades = session.query(Trade).filter(Trade.politician_id == pol.id).order_by(Trade.filing_date.desc()).all()
        recent = []
        tickers_freq: Dict[str, int] = {}
        for t in trades[:10]:
            recent.append({
                "ticker": t.ticker,
                "type": t.transaction_type.upper(),
                "trade_date": str(t.trade_date),
                "filing_date": str(t.filing_date),
                "amount": t.value_range,
                "score": t.score,
                "tag": t.tag,
                "reason": t.reason
            })
        for t in trades:
            if t.ticker:
                tickers_freq[t.ticker] = tickers_freq.get(t.ticker, 0) + 1

        top_tickers = sorted(tickers_freq.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "id": pol.id,
            "name": pol.name,
            "party": pol.party,
            "chamber": pol.chamber,
            "state": pol.state,
            "district": pol.district,
            "bioguide_id": pol.bioguide_id,
            "photo_url": pol.photo_url,
            "committees": pol.committees.split(",") if pol.committees else [],
            "total_trades": len(trades),
            "avg_suspicion_score": round(pol.avg_score or 0.0, 1),
            "top_traded_assets": [{"ticker": t[0], "count": t[1]} for t in top_tickers],
            "recent_trades": recent
        }
    finally:
        session.close()


def execute_safe_sql(query: str) -> Dict[str, Any]:
    cleaned = query.strip().rstrip(";")
    upper = cleaned.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        return {"error": "Security Error: Only SELECT queries are permitted."}

    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "PRAGMA", "ATTACH", "DETACH", "CREATE", "REPLACE"]
    for kw in forbidden:
        if re.search(rf"\b{kw}\b", upper):
            return {"error": f"Security Error: Keyword '{kw}' is strictly prohibited."}

    if "LIMIT" not in upper:
        cleaned += " LIMIT 50"

    session = get_session(get_engine(settings.DATABASE_URL))
    try:
        res = session.execute(text(cleaned))
        columns = list(res.keys())
        rows = [dict(zip(columns, row)) for row in res.fetchall()]
        return {"columns": columns, "row_count": len(rows), "rows": rows}
    except Exception as e:
        return {"error": f"SQL Execution Error: {str(e)}"}
    finally:
        session.close()


def execute_tavily_search(query: str) -> Dict[str, Any]:
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        return {"error": "TAVILY_API_KEY not configured"}

    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "include_answer": True,
                "max_results": 3
            },
            timeout=12
        )
        if resp.status_code != 200:
            return {"error": f"Tavily API error: {resp.status_code}"}
        data = resp.json()
        return {
            "answer": data.get("answer"),
            "results": [
                {
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "content": r.get("content")
                }
                for r in data.get("results", [])
            ]
        }
    except Exception as e:
        return {"error": f"Tavily search failed: {str(e)}"}


def execute_get_ticker_positioning_rankings(
    sentiment_filter: str = "bullish",
    min_trades: int = 3,
    limit: int = 10,
) -> Dict[str, Any]:
    session = get_session(get_engine(settings.DATABASE_URL))
    try:
        from collections import defaultdict
        trades = session.query(Trade).join(Politician, Trade.politician_id == Politician.id).filter(Trade.ticker.isnot(None), Trade.ticker != "").all()
        by_tk = defaultdict(lambda: {"buys": 0, "sells": 0, "buy_vol": 0.0, "sell_vol": 0.0, "pols": set(), "names": set()})
        for t in trades:
            tk = t.ticker.upper().strip()
            side = (t.transaction_type or "").lower()
            mid = ((t.value_min or 0) + (t.value_max or 0)) / 2.0 or float(t.value_max or t.value_min or 10000)
            ent = by_tk[tk]
            if side in ("buy", "purchase"):
                ent["buys"] += 1
                ent["buy_vol"] += mid
            else:
                ent["sells"] += 1
                ent["sell_vol"] += mid
            if t.politician:
                ent["pols"].add(f"{t.politician.name} ({t.politician.party})")
            if t.asset_name:
                ent["names"].add(t.asset_name)

        ranked = []
        for tk, d in by_tk.items():
            total = d["buys"] + d["sells"]
            if total < min_trades:
                continue
            buy_pct = round((d["buys"] / total) * 100, 1)
            pcr = round(d["sells"] / max(1, d["buys"]), 2)
            if buy_pct >= 65:
                sent = "BULLISH ACCUMULATION"
            elif buy_pct <= 35:
                sent = "BEARISH DISTRIBUTION"
            else:
                sent = "NEUTRAL / BALANCED"

            raw_name = list(d["names"])[0] if d["names"] else tk
            clean_name = re.sub(r"\s+[PS]\s+\d{2}/\d{2}/\d{4}.*", "", raw_name).strip()
            clean_name = re.sub(r"^(DC|SP)\s+", "", clean_name).strip()
            if not clean_name:
                clean_name = tk

            ranked.append({
                "ticker": tk,
                "company_name": clean_name,
                "total_trades": total,
                "buy_count": d["buys"],
                "sell_count": d["sells"],
                "buy_pct": f"{buy_pct}%",
                "sell_pct": f"{round(100 - buy_pct, 1)}%",
                "buy_volume": f"${d['buy_vol']:,.0f}",
                "sell_volume": f"${d['sell_vol']:,.0f}",
                "put_call_ratio": pcr,
                "sentiment": sent,
                "politicians": list(d["pols"])[:5],
                "_raw_pcr": pcr,
                "_raw_buys": d["buys"],
                "_raw_buy_pct": buy_pct,
                "_raw_buy_vol": d["buy_vol"],
                "_raw_sells": d["sells"],
            })

        sf = (sentiment_filter or "bullish").lower()
        if sf == "bullish":
            # Lowest Put/Call Ratio (sells/buys) & Highest Buy Count / Volume
            filtered = [r for r in ranked if r["sentiment"] == "BULLISH ACCUMULATION" and r["_raw_buys"] >= 2]
            filtered.sort(key=lambda x: (x["_raw_pcr"], -x["_raw_buys"], -x["_raw_buy_vol"]))
        elif sf == "bearish":
            filtered = [r for r in ranked if r["sentiment"] == "BEARISH DISTRIBUTION" and r["_raw_sells"] >= 2]
            filtered.sort(key=lambda x: (-x["_raw_pcr"], -x["_raw_sells"]))
        else:
            filtered = sorted(ranked, key=lambda x: -x["total_trades"])

        res_list = []
        for r in filtered[:limit]:
            clean = {k: v for k, v in r.items() if not k.startswith("_")}
            res_list.append(clean)

        return {
            "filter": sf,
            "description": "Ranking of stocks by Congressional Put/Call ratio and institutional accumulation",
            "top_tickers": res_list
        }
    finally:
        session.close()


def execute_query_options_trades(
    option_type: str = "all",
    politician: Optional[str] = None,
    limit: int = 15,
) -> Dict[str, Any]:
    session = get_session(get_engine(settings.DATABASE_URL))
    try:
        q = session.query(Trade).join(Politician, Trade.politician_id == Politician.id)
        if politician:
            q = q.filter(Politician.name.ilike(f"%{politician.strip()}%"))
        ot = (option_type or "all").lower()
        if ot == "call":
            q = q.filter(or_(Trade.asset_type.ilike("%call%"), Trade.asset_name.ilike("%call%"), Trade.reason.ilike("%call%")))
        elif ot == "put":
            q = q.filter(or_(Trade.asset_type.ilike("%put%"), Trade.asset_name.ilike("%put%"), Trade.reason.ilike("%put%")))
        else:
            q = q.filter(or_(Trade.asset_type.ilike("%option%"), Trade.asset_type.ilike("%call%"), Trade.asset_type.ilike("%put%"), Trade.asset_name.ilike("%call%"), Trade.asset_name.ilike("%put%")))

        limit_val = min(max(1, int(limit)), 50)
        total_cnt = q.count()
        rows = q.order_by(Trade.filing_date.desc(), Trade.trade_date.desc()).limit(limit_val).all()
        trades_list = []
        pols_map = {}
        for t in rows:
            p = t.politician
            pname = f"{p.name} ({p.party}-{p.state or ''})" if p else ""
            if p:
                pols_map[pname] = pols_map.get(pname, 0) + 1
            trades_list.append({
                "politician": pname,
                "ticker": t.ticker,
                "asset_name": t.asset_name,
                "asset_type": t.asset_type,
                "side": (t.transaction_type or "").upper(),
                "trade_date": t.trade_date.isoformat() if t.trade_date else None,
                "filing_date": t.filing_date.isoformat() if t.filing_date else None,
                "amount": t.value_range or f"${t.value_min:,} - ${t.value_max:,}",
                "score": t.score,
                "tag": t.tag,
                "reason": t.reason,
            })

        return {
            "option_type": ot,
            "total_options_trades_found": total_cnt,
            "politicians_trading_options": [f"{k} ({v} trades)" for k, v in pols_map.items()],
            "trades": trades_list
        }
    finally:
        session.close()


TOOL_EXECUTORS = {
    "query_trades": execute_query_trades,
    "query_options_trades": execute_query_options_trades,
    "get_leaderboard": execute_get_leaderboard,
    "get_ticker_positioning_rankings": execute_get_ticker_positioning_rankings,
    "get_politician_profile": execute_get_politician_profile,
    "execute_safe_sql": execute_safe_sql,
    "search_market_news": execute_tavily_search,
}
