"""Re-parse already-downloaded House PTR PDFs with the current parser.

Fixes filings the pipeline read as "empty" before OCR support existed: every
cached PDF under data/pdfs/house is parsed again and its rows go through the
shared ingestion path (so duplicates merge instead of doubling).

Usage:
    python scripts/reparse_ptr_pdfs.py                 # all cached PDFs
    python scripts/reparse_ptr_pdfs.py --year 2026     # one directory of PDFs
    python scripts/reparse_ptr_pdfs.py --doc 9116328   # a single filing
    python scripts/reparse_ptr_pdfs.py --dry-run       # report, write nothing
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

from congress_quant_tracker.config import settings  # noqa: E402
from congress_quant_tracker.database.models import (  # noqa: E402
    UpdateLog,
    get_engine,
    get_session,
    init_db,
)
from congress_quant_tracker.fetchers.congress_invests import _load_members_db  # noqa: E402
from congress_quant_tracker.parsers.house_ptr_parser import parse_house_ptr  # noqa: E402
from congress_quant_tracker.services.official_pipeline import OfficialHousePipeline  # noqa: E402

logger = logging.getLogger("reparse_ptr_pdfs")


def _filing_meta(path: Path) -> dict:
    """Minimal filing metadata when the original index row is not available."""
    year = int(path.parent.name) if path.parent.name.isdigit() else datetime.now().year
    return {
        "doc_id": path.stem,
        "year": year,
        "name": "",  # the PDF's own name block is used when the index is absent
        "pdf_url": (
            "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/"
            f"{year}/{path.stem}.pdf"
        ),
        "filing_date": None,
    }


def _iter_pdfs(root: Path, doc_id: str | None, year: int | None) -> list[Path]:
    base = settings.PDF_DOWNLOAD_DIR / "house"
    if not base.exists():
        return []
    if doc_id:
        return sorted(base.rglob(f"{doc_id}.pdf"))
    files = sorted(base.rglob("*.pdf"))
    if year:
        files = [f for f in files if f.parent.name == str(year)]
    return files


def _known_filings(session) -> dict[str, dict]:
    """DocID -> member name / filing date, learned from rows already stored.

    Scanned filings carry no usable name block, and a PDF that was never
    ingested has no row at all — those keep whatever the PDF shows.
    """
    from congress_quant_tracker.database.models import Politician, Trade

    known: dict[str, dict] = {}
    rows = (
        session.query(Trade.pdf_url, Trade.filing_date, Politician.name)
        .join(Politician, Trade.politician_id == Politician.id)
        .all()
    )
    for url, filing_date, name in rows:
        if not url:
            continue
        doc_id = Path(str(url)).stem
        if doc_id and doc_id not in known:
            known[doc_id] = {"name": name, "filing_date": filing_date}
    return known


def _index_filings(years: list[int]) -> dict[str, dict]:
    """DocID -> member name / filing date from the Clerk's public index.

    Authoritative for scanned filings, whose own name block OCRs badly.
    """
    from congress_quant_tracker.fetchers.house_official import HouseOfficialFetcher

    try:
        with HouseOfficialFetcher() as fetcher:
            filings = fetcher.fetch_ptr_index(years=years)
    except Exception as exc:
        logger.warning("Clerk index unavailable (%s); using DB and PDF names", exc)
        return {}
    index: dict[str, dict] = {}
    for filing in filings:
        doc_id = str(filing.get("doc_id") or "")
        if doc_id:
            index[doc_id] = {
                "name": filing.get("name") or "",
                "filing_date": filing.get("filing_date"),
                "pdf_url": filing.get("pdf_url"),
            }
    logger.info("Clerk index: %s PTR filings", len(index))
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", help="single DocID (e.g. 9116328)")
    parser.add_argument("--year", type=int, help="only PDFs in this year folder")
    parser.add_argument("--limit", type=int, default=0, help="cap number of files")
    parser.add_argument("--dry-run", action="store_true", help="report only, no DB writes")
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="skip the Clerk index lookup (names come from the DB and the PDF)",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    files = _iter_pdfs(settings.PDF_DOWNLOAD_DIR, args.doc, args.year)
    if args.limit:
        files = files[: args.limit]
    if not files:
        print("No cached PDFs found under %s" % (settings.PDF_DOWNLOAD_DIR / "house"))
        return 1

    pipeline = OfficialHousePipeline.__new__(OfficialHousePipeline)
    pipeline.scorer = None
    pipeline.tavily = None
    # Party/state/bioguide lookups: without them a scanned filing's OCR name
    # ("Rohrt Khanna") would be registered as a second politician.
    pipeline.members = _load_members_db()
    engine = get_engine(settings.DATABASE_URL)
    if not args.dry_run:
        init_db(settings.DATABASE_URL)
    session = get_session(engine)
    known_filings = _known_filings(session)
    if not args.no_index:
        years = [args.year] if args.year else [datetime.now().year, datetime.now().year - 1]
        for doc_id, filing in _index_filings(years).items():
            known_filings.setdefault(doc_id, filing)

    stats: dict = Counter()
    log = None
    if not args.dry_run:
        log = UpdateLog(
            update_type="reparse_ptr_pdfs",
            status="in_progress",
            started_at=datetime.utcnow(),
        )
        session.add(log)
        session.commit()

    try:
        for index, path in enumerate(files, 1):
            filing = _filing_meta(path)
            known = known_filings.get(path.stem)
            if known:
                filing["name"] = known.get("name") or ""
                if known.get("filing_date"):
                    filing["filing_date"] = known["filing_date"]
                if known.get("pdf_url"):
                    filing["pdf_url"] = known["pdf_url"]
            try:
                parsed = parse_house_ptr(path, filing)
            except Exception as exc:
                stats["parse_errors"] += 1
                logger.warning("parse failed %s: %s", path.name, exc)
                continue

            method = parsed.get("method", "?")
            stats[f"method:{method}"] += 1
            trades = parsed.get("trades") or []
            stats["rows_parsed"] += len(trades)
            if not trades:
                stats["files_without_rows"] += 1

            name = (parsed.get("politician") or {}).get("name") or ""
            if args.dry_run:
                print(
                    f"[{index}/{len(files)}] {path.name} method={method} "
                    f"trades={len(trades)} name={name!r}"
                )
                continue

            inserted = 0
            for trade in trades:
                raw = {
                    **trade,
                    "politician_name": name,
                    "pdf_url": trade.get("pdf_url") or filing["pdf_url"],
                    "source": "house_ptr_reparse",
                }
                if not raw.get("filing_date"):
                    raw["filing_date"] = filing.get("filing_date")
                if pipeline._store_trade(
                    session, raw, name, filing=filing, pol_info={}, stats=stats
                ):
                    inserted += 1
            stats["trades_added"] += inserted
            session.commit()
            if index % 10 == 0 or index == len(files):
                logger.info(
                    "[%s/%s] %s trades=%s new=%s",
                    index,
                    len(files),
                    path.name,
                    len(trades),
                    inserted,
                )

        if log is not None:
            log.status = "completed"
            log.completed_at = datetime.utcnow()
            log.records_processed = stats.get("added", 0)
            log.details = str(dict(stats))[:2000]
            session.commit()

        print("\n[reparse] summary")
        for key in sorted(stats):
            print(f"  {key}: {stats[key]}")
        return 0
    except Exception:
        if log is not None:
            log.status = "failed"
            log.error_message = "reparse failed"
            log.completed_at = datetime.utcnow()
            session.commit()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
