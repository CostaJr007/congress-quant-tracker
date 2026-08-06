"""Fetcher for Senate financial disclosures."""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from congress_quant_tracker.config import settings


SENATE_REPORTS_URL = "https://efdsearch.senate.gov/search/report/data/"

SENATE_SEARCH_PAYLOAD = {
    "draw": 1,
    "columns": [
        {"data": "first_name", "name": "", "searchable": True, "orderable": True},
        {"data": "last_name", "name": "", "searchable": True, "orderable": True},
        {"data": "report_type", "name": "", "searchable": True, "orderable": False},
        {"data": "filing_date", "name": "", "searchable": True, "orderable": True},
        {"data": "transaction_date", "name": "", "searchable": True, "orderable": False},
        {"data": "submitted_date", "name": "", "searchable": True, "orderable": False},
        {"data": "ptr_link", "name": "", "searchable": True, "orderable": False},
    ],
    "order": [{"column": 3, "dir": "desc"}],
    "start": 0,
    "length": 100,
    "search": {"value": "Periodic Transaction Report", "regex": False},
}


class SenateFetcher:
    """Fetches periodic transaction reports from the Senate."""

    def __init__(self) -> None:
        self.client = httpx.Client(timeout=settings.FETCH_TIMEOUT_SECONDS)
        self.download_dir = settings.PDF_DOWNLOAD_DIR / "senate"

    def fetch_reports(self, max_pages: int = 50) -> list[dict]:
        """Fetch list of PTR reports from Senate disclosure search."""
        reports: list[dict] = []

        for page in range(max_pages):
            payload = dict(SENATE_SEARCH_PAYLOAD)
            payload["start"] = page * 100

            try:
                response = self.client.post(
                    "https://efdsearch.senate.gov/search/report/data/",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()

                if "data" not in data or not data["data"]:
                    break

                for row in data["data"]:
                    ptr_link = row.get("ptr_link", "")
                    if not ptr_link:
                        continue

                    report_id = hashlib.md5(ptr_link.encode()).hexdigest()[:12]
                    reports.append({
                        "url": ptr_link if ptr_link.startswith("http") else f"https://efdsearch.senate.gov{ptr_link}",
                        "report_id": report_id,
                        "first_name": row.get("first_name", ""),
                        "last_name": row.get("last_name", ""),
                        "filing_date": row.get("filing_date", ""),
                        "chamber": "senate",
                        "source": "senate_gov",
                    })

            except Exception as e:
                print(f"Warning: Failed to fetch Senate page {page}: {e}")
                break

        return reports

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def download_pdf(self, url: str, report_id: str) -> Path:
        """Download a single PDF report."""
        self.download_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.download_dir / f"{report_id}.pdf"

        if filepath.exists():
            return filepath

        with self.client.stream("GET", url) as response:
            response.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)

        return filepath
