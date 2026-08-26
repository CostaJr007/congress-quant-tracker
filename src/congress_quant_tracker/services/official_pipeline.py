"""Official House disclosure pipeline → SQLite.

Pulls PTR index + PDFs from disclosures-clerk.house.gov,
parses with regex (+ optional Groq), enriches with Tavily,
stores trades and scores them.
"""

from __future__ import annotations

import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

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
from congress_quant_tracker.enrichers.tavily_enricher import TavilyEnricher
from congress_quant_tracker.fetchers.congress_invests import (
    _load_members_db,
    _normalize_party,
)
from congress_quant_tracker.fetchers.house_official import HouseOfficialFetcher
from congress_quant_tracker.parsers.house_ptr_parser import parse_house_ptr
from congress_quant_tracker.scoring.scorer import TradeScorer

logger = logging.getLogger(__name__)

try:
    from scripts.fix_politician_photos import MANUAL_MAP, download_photo_if_missing
except Exception:
    # scripts/ is not always importable (e.g. API server context)
    _ROOT = Path(__file__).resolve().parents[3]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    try:
        from scripts.fix_politician_photos import MANUAL_MAP, download_photo_if_missing
    except Exception:
        MANUAL_MAP: dict = {}
        download_photo_if_missing = lambda bio_id: False  # noqa: E731


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
        years: list[int] | None = None,
        max_filings: int = 80,
        since_days: int | None = 120,
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
            "filers_indexed": 0,
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

                # Register every filer in the index (any filing type) before
                # any PDF work — no politician can pass hidden, even when
                # parsing is capped or a PDF fails.
                filers = fetcher.fetch_all_filers(years=years)
                stats["filers_indexed"] = len(filers)
                seen_names: set[str] = set()
                for f in filers:
                    fname = (f.get("name") or "").strip()
                    if not fname or fname.lower() in seen_names:
                        continue
                    seen_names.add(fname.lower())
                    try:
                        with session.begin_nested():
                            _, created = self._ensure_politician(session, fname, filing=f)
                            if created:
                                stats["politicians_added"] += 1
                    except Exception as e:
                        stats["errors"] += 1
                        logger.debug("Filer registration failed %s: %s", fname, e)
                session.commit()
                print(
                    f"[House Official] indexed={stats['filings_indexed']} "
                    f"filers={stats['filers_indexed']} "
                    f"politicians_registered={stats['politicians_added']}"
                )

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

    def _lookup_member(self, name: str) -> tuple[str, str, str | None, str | None]:
        import re
        key = (name or "").lower().strip()
        cleaned = re.sub(r"\b(mr|dr|hon|mrs|ms|jr|sr|ii|iii|iv)\b", "", key, flags=re.I)
        cleaned = " ".join(cleaned.split())

        info = MANUAL_MAP.get(cleaned) or MANUAL_MAP.get(key) or {}

        if not info:
            info = self.members.get(cleaned, {}) or self.members.get(key, {})
        if not info and " " in cleaned:
            parts = cleaned.split()
            info = self.members.get(f"{parts[0]} {parts[-1]}", {}) or self.members.get(parts[-1], {})

        party = info.get("party") or "I"
        if party not in ("D", "R", "I"):
            party = _normalize_party(str(party))
        bio_id = info.get("bioguide_id")
        return party, info.get("state") or "", info.get("district"), bio_id

    def _ensure_politician(
        self,
        session: Session,
        name: str,
        filing: dict | None = None,
        pol_info: dict | None = None,
    ) -> tuple[Politician, bool]:
        """Find or create a House politician. Returns (politician, created).

        Name variants are deduplicated via bioguide_id and via
        (state, district) so the same person is never registered twice.
        """
        pol = find_politician(session, name, chamber="house")
        party, state, district, bio_id = self._lookup_member(name)
        filing = filing or {}
        pol_info = pol_info or {}
        if not pol and bio_id:
            pol = session.query(Politician).filter(Politician.bioguide_id == bio_id).first()
        # Same state+district = same person even if the name varies
        lookup_state = pol_info.get("state") or filing.get("state") or state or ""
        lookup_district = pol_info.get("district") or filing.get("district") or (
            str(district) if district is not None else None
        )
        if not pol and lookup_state and lookup_district:
            pol = (
                session.query(Politician)
                .filter(
                    Politician.chamber == "house",
                    Politician.state == lookup_state[:2],
                    Politician.district == str(lookup_district),
                )
                .first()
            )
        if pol:
            if party in ("D", "R") and pol.party == "I":
                pol.party = party
            if state and not pol.state:
                pol.state = state[:2]
            if bio_id and not pol.bioguide_id:
                pol.bioguide_id = bio_id
                pol.photo_url = f"/politicians/{bio_id}.jpg"
            return pol, False

        state = pol_info.get("state") or filing.get("state") or state or ""
        district = pol_info.get("district") or filing.get("district") or (
            str(district) if district is not None else None
        )
        pol = Politician(
            name=name,
            chamber="house",
            party=party if party in ("D", "R", "I") else "I",
            state=(state or "")[:2],
            district=str(district) if district else None,
            bioguide_id=bio_id,
            photo_url=f"/politicians/{bio_id}.jpg" if bio_id else None,
        )
        session.add(pol)
        session.flush()
        return pol, True

    def _store_trade(
        self,
        session: Session,
        trade: dict,
        politician_name: str,
        filing: dict,
        pol_info: dict,
        stats: dict,
    ) -> bool:
        """Store one parsed PTR trade via the shared ingestion path.

        Returns True only when a NEW row was inserted; duplicates are merged
        by the ingest layer (never silently dropped).
        """
        from congress_quant_tracker.services.ingest import normalize_record, store_trade

        raw = {**trade}
        raw.setdefault("politician_name", politician_name)
        # Index-level filing date fills rows the parser could not read
        if not raw.get("filing_date"):
            raw["filing_date"] = filing.get("filing_date")
        raw["pdf_url"] = raw.get("pdf_url") or filing.get("pdf_url") or ""
        raw["source"] = "house_official"

        rec, reason = normalize_record(raw)
        if not rec:
            if reason == "sample_data_rejected":
                stats["samples_rejected"] = stats.get("samples_rejected", 0) + 1
            return False

        pol, created = self._ensure_politician(
            session, rec["politician_name"], filing=filing, pol_info=pol_info
        )
        if created:
            stats["politicians_added"] += 1

        if pol.bioguide_id:
            try:
                download_photo_if_missing(pol.bioguide_id)
            except Exception:
                pass

        status = store_trade(session, rec, pol)
        if status == "merged":
            stats["trades_merged"] = stats.get("trades_merged", 0) + 1
        return status == "added"

    def _score_unscored(self, session: Session, stats: dict) -> None:
        trades = session.query(Trade).filter(Trade.tag.is_(None)).all()
        score_trades(session, trades, stats, apply_tavily_boost=True)

    def _update_politician_stats(self, session: Session) -> None:
        refresh_politician_stats(session)
