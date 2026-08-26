"""Senate data pipeline with fallback strategies."""

from __future__ import annotations

import logging
from datetime import datetime

from congress_quant_tracker.common import (
    find_politician,
    refresh_politician_stats,
    score_trades,
)
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
    _load_members_db,
    _normalize_party,
)
from congress_quant_tracker.fetchers.senate_official import (
    SenateEfdPlaywrightFetcher,
    fetch_senate_via_congressinvests_sync,
    probe_efd_access,
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
            "reports_indexed": 0,
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
                    from congress_quant_tracker.fetchers.senate_official import (
                        parse_senate_ptr_html,
                    )

                    with SenateEfdHttpClient(probe=probe) as efd:
                        agree = efd.accept_terms()
                        print(f"[Senate] eFD agree: {agree}")
                        # Larger index so every senator who filed is registered,
                        # even when report detail parsing is capped.
                        index_reports = efd.fetch_ptr_index(max_rows=max(max_efd_reports, 200))
                        stats["reports_indexed"] = len(index_reports)
                        print(f"[Senate] eFD reports: {len(index_reports)}")
                        for rep in index_reports:
                            rname = (rep.get("name") or "").strip()
                            if not rname:
                                continue
                            try:
                                with session.begin_nested():
                                    _, created = self._ensure_senator(session, rname)
                                    if created:
                                        stats["politicians_added"] += 1
                            except Exception as e:
                                stats["errors"] += 1
                                logger.debug("Senator register fail %s: %s", rname, e)
                        session.commit()
                        for rep in index_reports[:max_efd_reports]:
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
                        index_reports = fetcher.fetch_ptr_index(max_rows=max(max_efd_reports, 200))
                        stats["reports_indexed"] = len(index_reports)
                        print(f"[Senate] eFD Playwright reports: {len(index_reports)}")
                        for rep in index_reports:
                            rname = (rep.get("name") or "").strip()
                            if not rname:
                                continue
                            try:
                                with session.begin_nested():
                                    _, created = self._ensure_senator(session, rname)
                                    if created:
                                        stats["politicians_added"] += 1
                            except Exception as e:
                                stats["errors"] += 1
                                logger.debug("Senator register fail %s: %s", rname, e)
                        session.commit()
                        for rep in index_reports[:max_efd_reports]:
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
                    with session.begin_nested():
                        if self._store(session, t, stats):
                            stats["trades_added"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    logger.debug("store fail: %s", e)
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

    def _ensure_senator(self, session, name: str) -> tuple[Politician, bool]:
        """Find or create a Senate politician. Returns (politician, created)."""
        pol = find_politician(session, name, chamber="senate")
        if pol:
            return pol, False
        key = name.lower()
        info = self.members.get(key, {})
        if not info and " " in key:
            info = self.members.get(f"{key.split()[0]} {key.split()[-1]}", {}) or {}
        party = info.get("party") or "I"
        if party not in ("D", "R", "I"):
            party = _normalize_party(str(party))
        bio_id = info.get("bioguide_id")
        if bio_id:
            by_bio = session.query(Politician).filter(Politician.bioguide_id == bio_id).first()
            if by_bio:
                return by_bio, False
        pol = Politician(
            name=name,
            chamber="senate",
            party=party,
            state=(info.get("state") or "")[:2],
            bioguide_id=bio_id,
        )
        session.add(pol)
        session.flush()
        return pol, True

    def _store(self, session, trade: dict, stats: dict) -> bool:
        """Store one Senate trade via the shared ingestion path.

        Returns True only when a NEW row was inserted; duplicates are merged
        (never silently dropped) by the ingest layer.
        """
        from congress_quant_tracker.services.ingest import normalize_record, store_trade

        raw = {**trade, "source": trade.get("source") or "senate"}
        rec, reason = normalize_record(raw)
        if not rec:
            if reason == "sample_data_rejected":
                stats["samples_rejected"] = stats.get("samples_rejected", 0) + 1
            return False

        name = rec["politician_name"]
        pol, created = self._ensure_senator(session, name)
        if created:
            stats["politicians_added"] += 1

        status = store_trade(session, rec, pol)
        if status == "merged":
            stats["trades_merged"] = stats.get("trades_merged", 0) + 1
        return status == "added"

    def _score(self, session, stats: dict) -> None:
        trades = session.query(Trade).filter(Trade.tag.is_(None)).all()
        score_trades(session, trades, stats)

    def _update_pols(self, session) -> None:
        refresh_politician_stats(session, chamber="senate")
