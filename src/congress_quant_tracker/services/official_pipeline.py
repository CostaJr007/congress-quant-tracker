"""Official House disclosure pipeline → SQLite.

Pulls PTR index + PDFs from disclosures-clerk.house.gov,
parses with regex (+ optional Groq), enriches with Tavily,
stores trades and scores them.
"""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import (
    OptionsTrade,
    Politician,
    Trade,
    UpdateLog,
    get_engine,
    get_session,
    init_db,
)
from congress_quant_tracker.enrichers.tavily_enricher import TavilyEnricher
from congress_quant_tracker.fetchers.congress_invests import (
    classify_asset,
    parse_date,
    parse_option_details,
    sanitize_trade_dates,
    _load_members_db,
    _normalize_party,
)
from congress_quant_tracker.fetchers.house_official import HouseOfficialFetcher
from congress_quant_tracker.parsers.house_ptr_parser import parse_house_ptr
from congress_quant_tracker.scoring.scorer import TradeScorer

logger = logging.getLogger(__name__)


class OfficialHousePipeline:
    """House Clerk → PDF → parse → enrich → DB."""

    def __init__(self) -> None:
        settings.ensure_dirs()
        self.engine = get_engine(settings.DATABASE_URL)
        init_db(settings.DATABASE_URL)
        self.scorer = TradeScorer()
        self.tavily = TavilyEnricher()
        self.members = _load_members_db()

    def run(
        self,
        years: Optional[list[int]] = None,
        max_filings: int = 80,
        since_days: Optional[int] = 120,
        use_tavily: bool = True,
        skip_download_if_exists: bool = True,
    ) -> dict:
        """
        Run official House update.

        max_filings: cap PDF downloads this run (newest first)
        since_days: only filings within N days (None = all in index)
        """
        session = get_session(self.engine)
        log = UpdateLog(
            update_type="house_official",
            status="started",
            started_at=datetime.utcnow(),
        )
        session.add(log)
        session.commit()

        stats = {
            "filings_indexed": 0,
            "filings_selected": 0,
            "pdfs_downloaded": 0,
            "pdfs_parsed": 0,
            "trades_added": 0,
            "trades_seen": 0,
            "politicians_added": 0,
            "parse_methods": {},
            "errors": 0,
            "tavily_enabled": bool(self.tavily.enabled and use_tavily),
            "groq_enabled": bool(settings.GROQ_API_KEY),
        }

        try:
            log.status = "in_progress"
            session.commit()

            with HouseOfficialFetcher() as fetcher:
                index = fetcher.fetch_ptr_index(years=years)
                stats["filings_indexed"] = len(index)

                cutoff = None
                if since_days is not None:
                    cutoff = date.today() - timedelta(days=since_days)

                selected = []
                for f in index:
                    if cutoff and f.get("filing_date") and f["filing_date"] < cutoff:
                        continue
                    selected.append(f)
                    if len(selected) >= max_filings:
                        break

                stats["filings_selected"] = len(selected)
                print(f"[House Official] indexed={stats['filings_indexed']} selected={len(selected)}")

                for i, filing in enumerate(selected, 1):
                    try:
                        path = fetcher.download_pdf(filing, force=not skip_download_if_exists)
                        if not path:
                            stats["errors"] += 1
                            continue
                        stats["pdfs_downloaded"] += 1

                        parsed = parse_house_ptr(path, filing)
                        method = parsed.get("method", "?")
                        stats["parse_methods"][method] = stats["parse_methods"].get(method, 0) + 1
                        stats["pdfs_parsed"] += 1

                        pol_info = parsed.get("politician") or {}
                        name = pol_info.get("name") or filing.get("name") or ""
                        trades = parsed.get("trades") or []

                        if use_tavily and self.tavily.enabled and trades:
                            trades = self.tavily.enrich_trades(trades, politician=name, limit=8)

                        for t in trades:
                            stats["trades_seen"] += 1
                            added = self._store_trade(
                                session,
                                trade=t,
                                politician_name=name,
                                filing=filing,
                                pol_info=pol_info,
                                stats=stats,
                            )
                            if added:
                                stats["trades_added"] += 1

                        session.commit()
                        if i % 10 == 0 or i == len(selected):
                            print(
                                f"  [{i}/{len(selected)}] {name or filing.get('name')} "
                                f"trades={len(trades)} method={method} +{stats['trades_added']} new"
                            )
                    except Exception as e:
                        stats["errors"] += 1
                        logger.exception("Filing failed %s: %s", filing.get("doc_id"), e)
                        session.rollback()
                        continue

            # Score new/zero-score trades
            print("[House Official] Scoring...")
            try:
                from congress_quant_tracker.enrichers.sectors import apply_sectors_to_session

                apply_sectors_to_session(session)
            except Exception:
                pass
            score_stats = {"trades_scored": 0}
            self._score_unscored(session, score_stats)
            stats["trades_scored"] = score_stats["trades_scored"]
            self._update_politician_stats(session)

            log.status = "completed"
            log.records_processed = stats["trades_added"]
            log.completed_at = datetime.utcnow()
            log.details = str(stats)
            session.commit()
            print("[OK] House official done: %s" % {k: stats[k] for k in stats if k != "parse_methods"})
            try:
                from congress_quant_tracker.notifiers.discord_notifier import notify_pipeline_result

                notify_pipeline_result("house_official", stats)
            except Exception:
                pass
            return stats

        except Exception as e:
            err = str(e).encode("ascii", "replace").decode("ascii")
            try:
                log.status = "failed"
                log.error_message = err[:500]
                log.completed_at = datetime.utcnow()
                log.details = str(stats)
                session.commit()
            except Exception:
                pass
            raise
        finally:
            session.close()

    def _lookup_party(self, name: str) -> tuple[str, str, Optional[str]]:
        key = (name or "").lower().strip()
        info = self.members.get(key, {})
        if not info and " " in key:
            parts = key.split()
            info = self.members.get(f"{parts[0]} {parts[-1]}", {}) or self.members.get(parts[-1], {})
        party = info.get("party") or "I"
        if party not in ("D", "R", "I"):
            party = _normalize_party(str(party))
        return party, info.get("state") or "", info.get("district")

    def _store_trade(
        self,
        session: Session,
        trade: dict,
        politician_name: str,
        filing: dict,
        pol_info: dict,
        stats: dict,
    ) -> bool:
        ticker = (trade.get("ticker") or "").upper().strip()
        if not ticker or not politician_name:
            return False

        trade_date = parse_date(str(trade.get("trade_date") or ""))
        filing_date = parse_date(str(trade.get("filing_date") or "")) or filing.get("filing_date")
        trade_date, filing_date, _ = sanitize_trade_dates(
            trade_date, filing_date, trade.get("asset_name") or ""
        )
        if not trade_date:
            return False

        # Politician
        pol = (
            session.query(Politician)
            .filter(Politician.name.ilike(f"%{politician_name}%"))
            .first()
        )
        if not pol:
            party, state, district = self._lookup_party(politician_name)
            state = pol_info.get("state") or filing.get("state") or state or ""
            district = pol_info.get("district") or filing.get("district") or (
                str(district) if district is not None else None
            )
            pol = Politician(
                name=politician_name,
                chamber="house",
                party=party if party in ("D", "R", "I") else "I",
                state=(state or "")[:2],
                district=str(district) if district else None,
            )
            session.add(pol)
            session.flush()
            stats["politicians_added"] += 1
        else:
            party, state, district = self._lookup_party(politician_name)
            if party in ("D", "R") and pol.party == "I":
                pol.party = party
            if state and not pol.state:
                pol.state = state[:2]

        tx_type = (trade.get("transaction_type") or "buy").lower()
        if tx_type not in ("buy", "sell", "exchange"):
            tx_type = "buy"

        existing = (
            session.query(Trade)
            .filter(
                Trade.politician_id == pol.id,
                Trade.ticker == ticker,
                Trade.trade_date == trade_date,
                Trade.transaction_type == tx_type,
            )
            .first()
        )
        if existing:
            # refresh pdf url if missing
            if not existing.pdf_url and filing.get("pdf_url"):
                existing.pdf_url = filing["pdf_url"]
            return False

        asset_name = trade.get("asset_name") or ticker
        asset_type = trade.get("asset_type") or classify_asset(asset_name, ticker)
        value_min = int(trade.get("value_min") or trade.get("amount_min") or 0)
        value_max = int(trade.get("value_max") or trade.get("amount_max") or 0)

        # Tavily news soft boost stored in reason later via scorer
        boost = int(trade.get("news_score_boost") or 0)

        row = Trade(
            politician_id=pol.id,
            ticker=ticker,
            asset_name=asset_name,
            asset_type=asset_type,
            transaction_type=tx_type,
            trade_date=trade_date,
            filing_date=filing_date,
            value_min=value_min,
            value_max=value_max,
            value_range=trade.get("value_range") or "",
            pdf_url=filing.get("pdf_url") or trade.get("pdf_url") or "",
            owner=trade.get("owner") or "",
            sector=trade.get("sector") or "",
            score=boost,  # temporary; rescore overwrites if 0-only path — set 0 and apply boost after
            tag="routine",
            reason="",
            notes="house_official",
        )
        # Keep score 0 so scorer runs; boost applied after
        row.score = 0
        session.add(row)
        session.flush()

        if boost:
            row.notes = f"house_official;tavily_boost={boost}"

        opt = parse_option_details(asset_name, asset_type)
        if opt and asset_type and str(asset_type).startswith("option"):
            session.add(
                OptionsTrade(
                    trade_id=row.id,
                    option_type=opt.get("option_type") or "call",
                    strike=opt.get("strike"),
                    expiration_date=opt.get("expiration_date"),
                    underlying_asset=ticker,
                    premium_min=value_min,
                    premium_max=value_max,
                    premium_range=row.value_range,
                )
            )
        return True

    def _score_unscored(self, session: Session, stats: dict) -> None:
        trades = (
            session.query(Trade)
            .filter((Trade.score == 0) | (Trade.score.is_(None)))
            .all()
        )
        if not trades:
            return
        pols = {p.id: p for p in session.query(Politician).all()}
        trade_dicts = []
        for t in trades:
            pol = pols.get(t.politician_id)
            trade_dicts.append({
                "id": t.id,
                "politician_id": t.politician_id,
                "politician_name": pol.name if pol else "",
                "ticker": t.ticker,
                "trade_date": str(t.trade_date) if t.trade_date else None,
                "filing_date": str(t.filing_date) if t.filing_date else None,
                "transaction_type": t.transaction_type,
                "value_max": t.value_max or 0,
                "asset_type": t.asset_type or "stock",
                "owner": t.owner or "",
            })
        committee_map = {
            pid: [c.strip() for c in (p.committees or "").split(",") if c.strip()]
            for pid, p in pols.items()
            if p.committees
        }
        from congress_quant_tracker.enrichers.sectors import resolve_sector, scorer_sector

        sector_map = {}
        for t in trades:
            label = resolve_sector(t.ticker, t.sector)
            if label:
                sector_map[t.ticker] = scorer_sector(label)
        scored = self.scorer.score_batch(trade_dicts, committee_map, sector_map)
        by_id = {s["id"]: s for s in scored}
        for t in trades:
            s = by_id.get(t.id)
            if not s:
                continue
            score = int(s.get("score") or 0)
            # apply tavily boost from notes
            if t.notes and "tavily_boost=" in t.notes:
                try:
                    boost = int(t.notes.split("tavily_boost=")[1].split(";")[0])
                    score = min(100, score + boost)
                except Exception:
                    pass
            t.score = score
            t.tag = s.get("tag", "routine")
            t.reason = s.get("reason", "")
            stats["trades_scored"] += 1
        session.commit()

    def _update_politician_stats(self, session: Session) -> None:
        for pol in session.query(Politician).all():
            trades = session.query(Trade).filter(Trade.politician_id == pol.id).all()
            pol.total_trades = len(trades)
            scores = [t.score for t in trades if t.score]
            pol.avg_score = sum(scores) / len(scores) if scores else 0.0
        session.commit()
