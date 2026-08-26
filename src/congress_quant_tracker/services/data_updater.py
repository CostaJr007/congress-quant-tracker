"""Core data update service: fetches congressional trade data via CongressInvests API."""

import asyncio
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from congress_quant_tracker.common import (
    find_politician,
    refresh_politician_stats,
    score_trades,
)
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
from congress_quant_tracker.enrichers.company_enricher import CompanyEnricher
from congress_quant_tracker.fetchers.congress_invests import (
    classify_asset,
    fetch_all_trades,
    parse_option_details,
)
from congress_quant_tracker.scoring.scorer import TradeScorer

logger = logging.getLogger(__name__)


class DataUpdateService:
    """Orchestrates the full data pipeline: fetch -> score -> enrich -> store."""

    def __init__(self) -> None:
        settings.ensure_dirs()
        self.engine = get_engine(settings.DATABASE_URL)
        init_db(settings.DATABASE_URL)
        self.enricher = CompanyEnricher()
        self.scorer = TradeScorer()

    def run_full_update(self) -> dict:
        """Run a complete data update cycle using CongressInvests API."""
        session = get_session(self.engine)

        log = UpdateLog(
            update_type="full_update",
            status="started",
            started_at=datetime.utcnow(),
        )
        session.add(log)
        session.commit()

        stats = {
            "trades_fetched": 0,
            "trades_added": 0,
            "politicians_added": 0,
            "companies_enriched": 0,
            "trades_scored": 0,
            "options_added": 0,
        }

        try:
            log.status = "in_progress"
            session.commit()

            # Phase 1: Fetch from CongressInvests API
            print("[Phase 1/4] Fetching trades from CongressInvests API...")
            all_trades = asyncio.run(fetch_all_trades())
            stats["trades_fetched"] = len(all_trades)
            print(f"  -> Fetched {len(all_trades)} trades from API")

            # Phase 2: Store in database
            print("[Phase 2/4] Storing trades in database...")
            for i, trade_data in enumerate(all_trades, 1):
                try:
                    with session.begin_nested():
                        self._store_trade(session, trade_data, stats)
                except Exception as e:
                    logger.debug(f"Error storing trade: {e}")
                    continue
                if i % 500 == 0:
                    session.commit()

            # Phase 3: Score trades
            print("[Phase 3/4] Scoring trades...")
            self._score_all_trades(session, stats)
            print(f"  -> Scored {stats['trades_scored']} trades")

            # Phase 4: Enrich company data
            print("[Phase 4/4] Enriching company data...")
            stats["companies_enriched"] = self.enricher.enrich_all_tickers_in_db(session)

            # Update politician aggregates
            self._update_politician_stats(session)

            log.status = "completed"
            log.records_processed = stats["trades_added"]
            log.completed_at = datetime.utcnow()
            log.details = str(stats)
            session.commit()
            # ASCII-only: Windows consoles often fail on emoji (cp1252)
            print(f"\n[OK] Update complete! Added {stats['trades_added']} new trades")
            try:
                from congress_quant_tracker.notifiers.discord_notifier import notify_pipeline_result

                notify_pipeline_result("full_update", stats)
            except Exception:
                pass

        except Exception as e:
            # Never let logging/encoding turn a successful run into a crash
            err = str(e).encode("ascii", "replace").decode("ascii")
            try:
                log.status = "failed"
                log.error_message = err[:500]
                log.completed_at = datetime.utcnow()
                session.commit()
            except Exception:
                pass
            raise

        finally:
            try:
                session.close()
            except Exception:
                pass

        return stats

    def _merge_into_existing(self, existing: Trade, trade_data: dict) -> bool:
        """Backfill/widen an existing duplicate instead of dropping data (delegates
        to the shared ingestion module)."""
        from congress_quant_tracker.services.ingest import merge_into_existing

        return merge_into_existing(existing, self._canonical_view(trade_data))

    @staticmethod
    def _canonical_view(trade_data: dict) -> dict:
        """CongressInvests-shaped dict → canonical ingest keys."""
        return {
            "politician_name": trade_data.get("member", ""),
            "ticker": trade_data.get("ticker"),
            "asset_name": trade_data.get("asset_name"),
            "transaction_type": trade_data.get("transaction_type"),
            "trade_date": trade_data.get("trade_date"),
            "filing_date": trade_data.get("filing_date"),
            "value_min": trade_data.get("amount_min"),
            "value_max": trade_data.get("amount_max"),
            "value_range": trade_data.get("amount_range"),
            "pdf_url": trade_data.get("pdf_url"),
            "owner": trade_data.get("owner"),
            "sector": trade_data.get("sector"),
        }

    def _store_trade(self, session: Session, trade_data: dict, stats: dict) -> None:
        """Store a single trade from CongressInvests API."""
        from congress_quant_tracker.services.ingest import normalize_record, store_trade

        member_name = str(trade_data.get("member") or "").strip()
        if not member_name:
            return

        rec, reason = normalize_record(trade_data)
        if not rec:
            if reason == "sample_data_rejected":
                stats["samples_rejected"] = stats.get("samples_rejected", 0) + 1
            return

        # Ensure the politician FIRST — a skipped/duplicate trade must never
        # hide a member who appears in the feed.
        politician = find_politician(session, member_name)

        if not politician:
            chamber = (trade_data.get("chamber") or "house").lower()
            party = trade_data.get("party") or "I"
            if party not in ("D", "R", "I"):
                party = "I"
            politician = Politician(
                name=member_name,
                chamber=chamber if chamber in ("house", "senate") else "house",
                party=party,
                state=(trade_data.get("state") or "")[:2],
                district=str(trade_data.get("district", "")) if trade_data.get("district") else None,
                bioguide_id=trade_data.get("bioguide_id"),
            )
            session.add(politician)
            session.flush()
            stats["politicians_added"] += 1
        else:
            # Backfill party/state when we previously defaulted to Independent
            party = trade_data.get("party")
            if party in ("D", "R", "I") and (not politician.party or politician.party == "I"):
                if party != "I":
                    politician.party = party
            if trade_data.get("state") and not politician.state:
                politician.state = str(trade_data["state"])[:2]
            if trade_data.get("bioguide_id") and not politician.bioguide_id:
                politician.bioguide_id = trade_data["bioguide_id"]

        inner: dict = {}
        status = store_trade(session, rec, politician, inner)
        if status == "added":
            stats["trades_added"] += 1
            if str(rec["asset_type"]).startswith("option"):
                stats["options_added"] = stats.get("options_added", 0) + 1
        elif status == "merged":
            stats["trades_updated"] = stats.get("trades_updated", 0) + 1
        else:
            stats["trades_deduped"] = stats.get("trades_deduped", 0) + 1

    def _score_all_trades(self, session: Session, stats: dict, force: bool = False) -> None:
        """Score trades (unscored only, or all if force=True)."""
        if force:
            trades = session.query(Trade).all()
        else:
            trades = session.query(Trade).filter(Trade.tag.is_(None)).all()
        score_trades(session, trades, stats)

    def fix_bad_dates(self) -> dict:
        """Sanitize trade dates that look like option expirations / parse errors."""
        from congress_quant_tracker.fetchers.congress_invests import sanitize_trade_dates

        session = get_session(self.engine)
        fixed = 0
        try:
            for t in session.query(Trade).all():
                new_td, new_fd, corrected = sanitize_trade_dates(
                    t.trade_date, t.filing_date, t.asset_name or ""
                )
                if corrected and new_td and new_td != t.trade_date:
                    t.trade_date = new_td
                    if new_fd and new_fd != t.filing_date:
                        t.filing_date = new_fd
                    fixed += 1
            session.commit()
            return {"dates_fixed": fixed}
        finally:
            session.close()

    def rescore_all(self) -> dict:
        """Re-run scoring + option extraction on the whole DB."""
        session = get_session(self.engine)
        stats = {"trades_scored": 0, "options_added": 0, "reclassified": 0, "dates_fixed": 0}
        try:
            from congress_quant_tracker.fetchers.congress_invests import sanitize_trade_dates

            # Reclassify asset types + fix bad trade dates
            for t in session.query(Trade).all():
                new_type = classify_asset(t.asset_name or "", t.ticker or "")
                if new_type != (t.asset_type or "stock"):
                    t.asset_type = new_type
                    stats["reclassified"] += 1
                new_td, new_fd, corrected = sanitize_trade_dates(
                    t.trade_date, t.filing_date, t.asset_name or ""
                )
                if corrected and new_td and new_td != t.trade_date:
                    t.trade_date = new_td
                    if new_fd:
                        t.filing_date = new_fd
                    stats["dates_fixed"] += 1

            # Fill missing options rows
            existing_opt_ids = {
                r[0]
                for r in session.query(OptionsTrade.trade_id).all()
            }
            for t in session.query(Trade).filter(
                Trade.asset_type.in_(["option_call", "option_put"])
            ).all():
                if t.id in existing_opt_ids:
                    continue
                opt = parse_option_details(t.asset_name or "", t.asset_type or "")
                if not opt:
                    opt = {
                        "option_type": "put" if t.asset_type == "option_put" else "call",
                        "strike": None,
                        "expiration_date": None,
                    }
                session.add(
                    OptionsTrade(
                        trade_id=t.id,
                        option_type=opt.get("option_type") or "call",
                        strike=opt.get("strike"),
                        expiration_date=opt.get("expiration_date"),
                        underlying_asset=t.ticker,
                        premium_min=t.value_min,
                        premium_max=t.value_max,
                        premium_range=t.value_range,
                    )
                )
                stats["options_added"] += 1

            session.commit()
            from congress_quant_tracker.enrichers.sectors import apply_sectors_to_session

            sector_stats = apply_sectors_to_session(session)
            stats["sectors_trades"] = sector_stats.get("trades_updated", 0)
            stats["sectors_companies"] = sector_stats.get("companies_updated", 0) + sector_stats.get(
                "companies_created", 0
            )
            self._score_all_trades(session, stats, force=True)
            self._update_politician_stats(session)
            return stats
        finally:
            session.close()

    def _update_politician_stats(self, session: Session) -> None:
        """Update aggregate stats for all politicians."""
        refresh_politician_stats(session)

    def run_incremental_update(self) -> dict:
        """Run an update for recent filings only."""
        return self.run_full_update()
