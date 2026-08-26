"""Daily update script for CongressQuantTracker.

Runs the standard ingestion pipeline:
  1. House Official (Clerk FD.zip/PDF)   — equivalent to scripts/update_official.py
  2. Senate (eFD with fallbacks)          — equivalent to scripts/update_senate.py
  3. Company enrichment (new tickers only)

Can be scheduled via cron, Task Scheduler, or run manually.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import get_engine, get_session
from congress_quant_tracker.enrichers.company_enricher import CompanyEnricher
from congress_quant_tracker.services.official_pipeline import OfficialHousePipeline
from congress_quant_tracker.services.senate_pipeline import SenatePipeline


def run_update() -> dict:
    """Execute the standard daily pipeline: House -> Senate -> enrich."""
    print("\n" + "=" * 60)
    print("CongressQuantTracker - Daily Update")
    print(f"Started at: {__import__('datetime').datetime.now()}")
    print("=" * 60 + "\n")

    house = OfficialHousePipeline().run(max_filings=80, since_days=150)
    print("House done:", {k: house[k] for k in ("filings_indexed", "filings_selected", "trades_added", "trades_scored")})

    senate = SenatePipeline().run(strategy="auto")
    print("Senate done:", {k: senate[k] for k in ("strategy_used", "trades_fetched", "trades_added", "trades_scored")})

    session = get_session(get_engine(settings.DATABASE_URL))
    try:
        enriched = CompanyEnricher().enrich_all_tickers_in_db(session)
    finally:
        session.close()
    print(f"Companies enriched: {enriched}")

    summary = {
        "house": house,
        "senate": senate,
        "companies_enriched": enriched,
    }
    print("\n" + "=" * 60)
    print("Update completed successfully!")
    print(f"  House: +{house.get('trades_added', 0)} trades, {house.get('pdfs_parsed', 0)} PDFs parsed")
    print(f"  Senate: +{senate.get('trades_added', 0)} trades via {senate.get('strategy_used', '?')}")
    print(f"  Companies enriched: {enriched}")
    print("=" * 60 + "\n")
    return summary


def main() -> None:
    """Main entry point for the daily update script."""
    parser = argparse.ArgumentParser(
        description="CongressQuantTracker Daily Update"
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run in scheduled mode (default: 9 AM daily)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="(compat) run once and exit — this is the default behavior",
    )

    args = parser.parse_args()

    if args.schedule:
        print("Starting scheduler: daily update at 9:00 AM")
        scheduler = BlockingScheduler()
        scheduler.add_job(run_update, CronTrigger(hour=9, minute=0))
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            print("\nScheduler stopped.")
    else:
        run_update()


if __name__ == "__main__":
    main()
