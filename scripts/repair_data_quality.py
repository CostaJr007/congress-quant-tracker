"""One-off repair for rows written before the data-quality fixes.

Fixes:
  1. Absurd dates (e.g. OCR-fabricated year 2608): the whole row is garbage
     (asset_name is usually a date fragment), so it is deleted.
  2. value_min/value_max = 0 meaning "unknown": converted to NULL so $0 never
     pollutes volume sums, sorting or the UI.
  3. Misclassified options (common stock stored as option_call with a NULL
     strike child): delegated to rescore_all, which reclassifies by name and
     drops orphaned options rows.

Usage:
    python scripts/repair_data_quality.py            # report only
    python scripts/repair_data_quality.py --apply    # write changes
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

from congress_quant_tracker.config import settings  # noqa: E402
from congress_quant_tracker.database.models import (  # noqa: E402
    Trade,
    get_engine,
    get_session,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the fixes")
    args = parser.parse_args()

    engine = get_engine(settings.DATABASE_URL)
    session = get_session(engine)
    try:
        max_year = date.today().year + 1
        bad_dates = [
            t
            for t in session.query(Trade).all()
            if (t.trade_date and (t.trade_date.year > max_year or t.trade_date.year < 2000))
            or (t.filing_date and (t.filing_date.year > max_year or t.filing_date.year < 2000))
        ]
        zero_values = (
            session.query(Trade)
            .filter((Trade.value_min == 0) | (Trade.value_max == 0))
            .all()
        )

        print(f"absurd-date trades: {len(bad_dates)}")
        for t in bad_dates[:10]:
            print(f"  id={t.id} trade={t.trade_date} filing={t.filing_date} asset={t.asset_name!r}")
        print(f"zero-value trades:  {len(zero_values)}")

        if not args.apply:
            print("\ndry run — re-run with --apply to write")
            return 0

        for t in bad_dates:
            session.delete(t)
        for t in zero_values:
            if t.value_min == 0:
                t.value_min = None
            if t.value_max == 0:
                t.value_max = None
        session.commit()
        print(f"[repair] deleted {len(bad_dates)}, nulled {len(zero_values)}")

        from congress_quant_tracker.services.data_updater import DataUpdateService

        stats = DataUpdateService().rescore_all()
        print(f"[repair] rescore: {stats}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
