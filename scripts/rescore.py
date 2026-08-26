"""Reclassify assets, extract options, and re-score all trades.

NO_YF=1 keeps the rescore fast and avoids yfinance rate limits
(contrarian/earnings signals need live market data; run those in
scripts/enrich_all.py instead).
"""

import os

os.environ.setdefault("NO_YF", "1")

from congress_quant_tracker.services.data_updater import DataUpdateService


def main() -> None:
    print("[rescore] Running full rescore + option extraction...")
    stats = DataUpdateService().rescore_all()
    print("[rescore] Done:", stats)


if __name__ == "__main__":
    main()
