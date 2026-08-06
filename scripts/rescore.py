"""Reclassify assets, extract options, and re-score all trades."""

from congress_quant_tracker.services.data_updater import DataUpdateService


def main() -> None:
    print("[rescore] Running full rescore + option extraction...")
    stats = DataUpdateService().rescore_all()
    print("[rescore] Done:", stats)


if __name__ == "__main__":
    main()
