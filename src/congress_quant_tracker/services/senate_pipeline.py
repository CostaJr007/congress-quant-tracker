"""Senate data pipeline with fallback strategies."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import (
    Politician,
    Trade,
    UpdateLog,
    get_engine,
    get_session,
    init_db,
)
from congress_quant_tracker.fetchers.congress_invests import (
    parse_date,
    sanitize_trade_dates,
    classify_asset,
    _load_members_db,
    _normalize_party,
)
from congress_quant_tracker.fetchers.senate_official import (
    probe_efd_access,
    fetch_senate_via_congressinvests_sync,
    SenateEfdPlaywrightFetcher,
    parse_senate_ptr_html,
)
from congress_quant_tracker.scoring.scorer import TradeScorer

logger = logging.getLogger(__name__)


class SenatePipeline:
    """
    Load Senate trades into SQLite.

    strategy:
      auto            — try eFD Playwright, else CongressInvests
      congressinvests — only free API
      efd             — only Playwright eFD (needs unblocked IP)
    """

    def __init__(self) -> None:
        settings.ensure_dirs()
        self.engine = get_engine(settings.DATABASE_URL)
        init_db(settings.DATABASE_URL)
        self.scorer = TradeScorer()
        self.members = _load_members_db()

    def run(
        self,
        strategy: str = "auto",
        max_pages: int = 25,
        max_efd_reports: int = 40,
        headless: bool = True,
    ) -> dict:
        session = get_session(self.engine)
        log = UpdateLog(
            update_type="senate_update",
            status="started",
            started_at=datetime.utcnow(),
        )
        session.add(log)
        session.commit()

        stats = {
            "strategy_requested": strategy,
            "strategy_used": None,
            "efd_probe": None,
            "trades_fetched": 0,
            "trades_added": 0,
            "politicians_added": 0,
            "trades_scored": 0,
            "errors": 0,
        }

        try:
            log.status = "in_progress"
            session.commit()

            trades: list[dict] = []
            probe = probe_efd_access()
            stats["efd_probe"] = probe
            print(f"[Senate] eFD probe: {probe}")

            use = strategy
            if strategy == "auto":
                use = "efd" if probe.get("reachable") else "congressinvests"
                print(f"[Senate] auto -> {use}")

            if use == "efd":
                try:
                    # Prefer lightweight HTTP session (proxy-friendly)
                    from congress_quant_tracker.fetchers.senate_efd_http import SenateEfdHttpClient
                    from congress_quant_tracker.fetchers.senate_official import parse_senate_ptr_html

                    with SenateEfdHttpClient() as efd:
                        agree = efd.accept_terms()
                        print(f"[Senate] eFD agree: {agree}")
                        reports = efd.fetch_ptr_index(max_rows=max_efd_reports)
                        print(f"[Senate] eFD reports: {len(reports)}")
                        for rep in reports[:max_efd_reports]:
                            try:
                                if not rep.get("url"):
                                    continue
                                html = efd.fetch_ptr_html(rep["url"])
                                parsed = parse_senate_ptr_html(html, rep)
                                trades.extend(parsed)
                            except Exception as e:
                                stats["errors"] += 1
                                logger.warning("PTR parse fail %s: %s", rep.get("url"), e)
                    stats["strategy_used"] = "efd_http"
                except Exception as e:
                    print(f"[Senate] eFD HTTP failed ({e}); trying Playwright...")
                    try:
                        fetcher = SenateEfdPlaywrightFetcher(headless=headless)
                        reports = fetcher.fetch_ptr_index(max_rows=max_efd_reports)
                        print(f"[Senate] eFD Playwright reports: {len(reports)}")
                        for rep in reports[:max_efd_reports]:
                            try:
                                if not rep.get("url"):
                                    continue
                                html = fetcher.fetch_ptr_html(rep["url"])
                                parsed = parse_senate_ptr_html(html, rep)
                                trades.extend(parsed)
                            except Exception as e2:
                                stats["errors"] += 1
                                logger.warning("PTR parse fail %s: %s", rep.get("url"), e2)
                        stats["strategy_used"] = "efd_playwright"
                    except Exception as e2:
                        print(f"[Senate] eFD failed ({e2}); falling back to CongressInvests")
                        trades = fetch_senate_via_congressinvests_sync(max_pages=max_pages)
                        stats["strategy_used"] = "congressinvests_fallback"
                        stats["errors"] += 1
                        stats["efd_error"] = str(e2)[:300]
            else:
                trades = fetch_senate_via_congressinvests_sync(max_pages=max_pages)
                stats["strategy_used"] = "congressinvests"

            stats["trades_fetched"] = len(trades)
            print(f"[Senate] fetched {len(trades)} trades via {stats['strategy_used']}")

            for t in trades:
                try:
                    if self._store(session, t, stats):
                        stats["trades_added"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    logger.debug("store fail: %s", e)
                    session.rollback()
            session.commit()

            print("[Senate] Scoring...")
            try:
                from congress_quant_tracker.enrichers.sectors import apply_sectors_to_session

                apply_sectors_to_session(session)
            except Exception:
                pass
            self._score(session, stats)
            self._update_pols(session)

            log.status = "completed"
            log.records_processed = stats["trades_added"]
            log.completed_at = datetime.utcnow()
            log.details = str(stats)
            session.commit()
            print("[OK] Senate done: trades_added=%s fetched=%s strategy=%s" % (
                stats.get("trades_added"),
                stats.get("trades_fetched"),
                stats.get("strategy_used"),
            ))
            try:
                from congress_quant_tracker.notifiers.discord_notifier import notify_pipeline_result

                notify_pipeline_result("senate_update", stats)
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

    def _store(self, session, trade: dict, stats: dict) -> bool:
        # Normalize both congressinvests shape and efd html shape
        name = (trade.get("member") or trade.get("name") or "").strip()
        ticker = (trade.get("ticker") or "").upper().strip()
        if not name or not ticker or ticker in ("--", "N/A"):
            return False

        trade_date = parse_date(str(trade.get("trade_date") or ""))
        filing_date = parse_date(str(trade.get("filing_date") or ""))
        trade_date, filing_date, _ = sanitize_trade_dates(
            trade_date, filing_date, trade.get("asset_name") or ""
        )
        if not trade_date:
            return False

        pol = session.query(Politician).filter(Politician.name.ilike(f"%{name}%")).first()
        if not pol:
            key = name.lower()
            info = self.members.get(key, {})
            if not info and " " in key:
                info = self.members.get(f"{key.split()[0]} {key.split()[-1]}", {}) or {}
            party = info.get("party") or trade.get("party") or "I"
            if party not in ("D", "R", "I"):
                party = _normalize_party(str(party))
            pol = Politician(
                name=name,
                chamber="senate",
                party=party,
                state=(info.get("state") or trade.get("state") or "")[:2],
                bioguide_id=info.get("bioguide_id"),
            )
            session.add(pol)
            session.flush()
            stats["politicians_added"] += 1
        else:
            if pol.chamber != "senate":
                # don't overwrite house members with same name edge cases
                pass

        tx = (trade.get("transaction_type") or "buy").lower()
        if tx in ("purchase", "p"):
            tx = "buy"
        elif tx in ("sale", "s", "sale_partial", "sale_full"):
            tx = "sell"

        exists = (
            session.query(Trade)
            .filter(
                Trade.politician_id == pol.id,
                Trade.ticker == ticker,
                Trade.trade_date == trade_date,
                Trade.transaction_type == tx,
            )
            .first()
        )
        if exists:
            return False

        asset_name = trade.get("asset_name") or ticker
        row = Trade(
            politician_id=pol.id,
            ticker=ticker,
            asset_name=asset_name,
            asset_type=trade.get("asset_type") or classify_asset(asset_name, ticker),
            transaction_type=tx,
            trade_date=trade_date,
            filing_date=filing_date,
            value_min=int(trade.get("amount_min") or trade.get("value_min") or 0),
            value_max=int(trade.get("amount_max") or trade.get("value_max") or 0),
            value_range=trade.get("amount_range") or trade.get("value_range") or "",
            pdf_url=trade.get("pdf_url") or trade.get("url") or "",
            owner=trade.get("owner") or "",
            notes=trade.get("source") or "senate",
            score=0,
            tag="routine",
        )
        session.add(row)
        return True

    def _score(self, session, stats: dict) -> None:
        trades = session.query(Trade).filter((Trade.score == 0) | (Trade.score.is_(None))).all()
        if not trades:
            return
        pols = {p.id: p for p in session.query(Politician).all()}
        dicts = []
        for t in trades:
            pol = pols.get(t.politician_id)
            dicts.append({
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
        from congress_quant_tracker.enrichers.sectors import resolve_sector, scorer_sector

        sector_map = {}
        for t in trades:
            label = resolve_sector(t.ticker, t.sector)
            if label:
                sector_map[t.ticker] = scorer_sector(label)
        scored = self.scorer.score_batch(dicts, {}, sector_map)
        by_id = {s["id"]: s for s in scored}
        for t in trades:
            s = by_id.get(t.id)
            if not s:
                continue
            t.score = s.get("score", 0)
            t.tag = s.get("tag", "routine")
            t.reason = s.get("reason", "")
            stats["trades_scored"] += 1
        session.commit()

    def _update_pols(self, session) -> None:
        for pol in session.query(Politician).filter(Politician.chamber == "senate").all():
            trades = session.query(Trade).filter(Trade.politician_id == pol.id).all()
            pol.total_trades = len(trades)
            scores = [t.score for t in trades if t.score]
            pol.avg_score = sum(scores) / len(scores) if scores else 0.0
        session.commit()
