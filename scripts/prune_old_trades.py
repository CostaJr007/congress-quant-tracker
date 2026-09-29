"""Drop trades older than the collection window (default 2 years).

The pipelines only fetch inside DATA_WINDOW_DAYS, so this removes the legacy
tail (2020/2024 rows) that predates the window. Options children go with
their trades via cascade; politician aggregates are refreshed.

Usage:
    python scripts/prune_old_trades.py            # report only
    python scripts/prune_old_trades.py --apply    # delete
    python scripts/prune_old_trades.py --days 365 --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

from congress_quant_tracker.common import refresh_politician_stats  # noqa: E402
from congress_quant_tracker.config import settings  # noqa: E402
from congress_quant_tracker.database.models import (  # noqa: E402
    Trade,
    get_engine,
    get_session,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=None,
                        help="keep only rows newer than N days (default: DATA_WINDOW_DAYS)")
    parser.add_argument("--apply", action="store_true", help="delete the rows")
    args = parser.parse_args()

    window = args.days or settings.DATA_WINDOW_DAYS
    cutoff = date.today() - timedelta(days=window)
    engine = get_engine(settings.DATABASE_URL)
    session = get_session(engine)
    try:
        old = session.query(Trade).filter(Trade.trade_date < cutoff).all()
        print(f"cutoff: {cutoff}  trades older: {len(old)}")
        if not args.apply:
            print("dry run — re-run with --apply to delete")
            return 0
        for t in old:
            session.delete(t)
        session.commit()
        refresh_politician_stats(session)
        print(f"[prune] deleted {len(old)} trades older than {cutoff}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
