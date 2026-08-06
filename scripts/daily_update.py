"""Daily update script for CongressQuantTracker.
Runs the full data pipeline: fetch -> parse -> enrich -> store.
Can be scheduled via cron, Task Scheduler, or run manually.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from congress_quant_tracker.config import settings
from congress_quant_tracker.services.data_updater import DataUpdateService


def run_update() -> None:
    """Execute a full data update cycle."""
    print("\n" + "=" * 60)
    print(f"CongressQuantTracker - Daily Update")
    print(f"Started at: {__import__('datetime').datetime.now()}")
    print("=" * 60 + "\n")

    service = DataUpdateService()
    try:
        stats = service.run_full_update()
        print("\n" + "=" * 60)
        print("Update completed successfully!")
        print(f"  House reports: {stats['house_reports_fetched']}")
        print(f"  Senate reports: {stats['senate_reports_fetched']}")
        print(f"  PDFs parsed: {stats['pdfs_parsed']}")
        print(f"  Trades added: {stats['trades_added']}")
        print(f"  Options added: {stats['options_added']}")
        print(f"  Companies enriched: {stats['companies_enriched']}")
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"\nERROR: Update failed: {e}")
        raise


def main() -> None:
    """Main entry point for the daily update script."""
    import argparse

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
        help="Run update once and exit",
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
