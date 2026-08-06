"""Pull latest House PTRs from the official Clerk site and load into SQLite.

Usage:
  uv run python scripts/update_official.py
  uv run python scripts/update_official.py --max 40 --days 90
  uv run python scripts/update_official.py --years 2026 2025 --max 100

Optional env:
  GROQ_API_KEY=...     # LLM cleanup / extraction
  TAVILY_API_KEY=...   # ticker resolve + news filters
  LLM_ENABLED=1        # force Groq even when regex works
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from congress_quant_tracker.services.official_pipeline import OfficialHousePipeline


def main() -> None:
    p = argparse.ArgumentParser(description="Official House PTR update")
    p.add_argument("--max", type=int, default=60, help="Max newest PTR filings to process")
    p.add_argument("--days", type=int, default=150, help="Only filings in the last N days")
    p.add_argument("--years", type=int, nargs="*", default=None, help="Filing years (default: this+last)")
    p.add_argument("--no-tavily", action="store_true", help="Skip Tavily enrichment")
    p.add_argument("--force-pdf", action="store_true", help="Re-download PDFs")
    args = p.parse_args()

    pipe = OfficialHousePipeline()
    stats = pipe.run(
        years=args.years,
        max_filings=args.max,
        since_days=args.days,
        use_tavily=not args.no_tavily,
        skip_download_if_exists=not args.force_pdf,
    )
    print("STATS:", stats)


if __name__ == "__main__":
    main()
