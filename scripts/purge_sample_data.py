"""Remove generated/demo data from the production database.

Purges:
  * Trades whose notes mark them as samples ("Sample trade for ...")
  * Orphaned OptionsTrade rows left behind by those trades
  * Random market_cap/beta values injected by the old seeder
    (fake precision — real values come from yfinance enrichment)

Also refreshes politician aggregates afterwards.

Usage:
  uv run python scripts/purge_sample_data.py            # dry-run report
  uv run python scripts/purge_sample_data.py --apply    # actually delete
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import or_

from congress_quant_tracker.common import refresh_politician_stats
from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import (
    Company,
    OptionsTrade,
    Politician,
    Trade,
    get_engine,
    get_session,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Purge generated/sample data")
    ap.add_argument("--apply", action="store_true", help="Execute the purge (default: dry-run)")
    args = ap.parse_args()

    session = get_session(get_engine(settings.DATABASE_URL))
    try:
        sample_trades = (
            session.query(Trade)
            .filter(
                or_(
                    Trade.notes.ilike("sample trade%"),
                    Trade.notes.ilike("sample % option"),
                )
            )
            .all()
        )
        sample_ids = [t.id for t in sample_trades]
        opt_children = (
            session.query(OptionsTrade).filter(OptionsTrade.trade_id.in_(sample_ids)).all()
            if sample_ids
            else []
        )

        seeded_companies = session.query(Company).filter(Company.market_cap.isnot(None)).all()

        print(f"Sample trades found:        {len(sample_ids)}")
        print(f"Orphaned options to remove: {len(opt_children)}")
        print(f"Companies w/ random caps:   {len(seeded_companies)}")

        politicians = session.query(Politician).count()
        total = session.query(Trade).count()
        print(f"DB before: {total} trades / {politicians} politicians")

        if not args.apply:
            print("\nDRY-RUN only. Re-run with --apply to execute.")
            return

        if opt_children:
            for opt in opt_children:
                session.delete(opt)
        for t in sample_trades:
            session.delete(t)

        # Fake numeric metadata from the seeder — real values come from enrichment
        for c in seeded_companies:
            c.market_cap = None
            c.beta = None

        session.commit()

        refresh_politician_stats(session)

        remaining = session.query(Trade).count()
        print(f"\n[PURGED] {len(sample_ids)} sample trades removed.")
        print(f"DB after: {remaining} trades / {session.query(Politician).count()} politicians")
    finally:
        session.close()


if __name__ == "__main__":
    main()
