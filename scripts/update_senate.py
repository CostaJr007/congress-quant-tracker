"""Update Senate trades.

The official site (efdsearch.senate.gov) is protected by Akamai and often
returns 403 from cloud/datacenter IPs — even with Playwright.

Strategies:
  auto              try eFD browser first, else CongressInvests (default)
  congressinvests   free API only (works from blocked networks)
  efd               Playwright only (use on residential IP / home PC)

Usage:
  uv run python scripts/update_senate.py
  uv run python scripts/update_senate.py --strategy congressinvests
  uv run python scripts/update_senate.py --strategy efd --headed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from congress_quant_tracker.fetchers.senate_official import probe_efd_access
from congress_quant_tracker.services.senate_pipeline import SenatePipeline


def main() -> None:
    p = argparse.ArgumentParser(description="Senate disclosure update")
    p.add_argument(
        "--strategy",
        choices=["auto", "congressinvests", "efd"],
        default="auto",
        help="Data source strategy",
    )
    p.add_argument("--pages", type=int, default=25, help="CongressInvests max pages (200 rows each)")
    p.add_argument("--efd-max", type=int, default=40, help="Max eFD reports if using Playwright")
    p.add_argument("--headed", action="store_true", help="Show browser window (efd strategy)")
    p.add_argument("--probe-only", action="store_true", help="Only test eFD access")
    args = p.parse_args()

    probe = probe_efd_access()
    print("eFD access probe:", probe)
    if args.probe_only:
        if probe.get("blocked_by_akamai"):
            print(
                "BLOCKED by Akamai from this network.\n"
                "Options:\n"
                "  1) Run on your home PC (residential IP):  uv run python scripts/update_senate.py --strategy efd\n"
                "  2) Use CongressInvests fallback:          uv run python scripts/update_senate.py --strategy congressinvests\n"
            )
        elif probe.get("reachable"):
            print("eFD is reachable — Playwright strategy should work.")
        else:
            print("eFD not reachable:", probe)
        return

    stats = SenatePipeline().run(
        strategy=args.strategy,
        max_pages=args.pages,
        max_efd_reports=args.efd_max,
        headless=not args.headed,
    )
    print("STATS:", stats)


if __name__ == "__main__":
    main()
