"""Fetcher for House of Representatives financial disclosures."""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from congress_quant_tracker.config import settings


HOUSE_DISCLOSURES_API = "https://disclosures-clerk.house.gov/FinancialDisclosure"
HOUSE_DOWNLOAD_BASE = "https://disclosures-clerk.house.gov"


class HouseFetcher:
    """Fetches financial disclosure reports from the House of Representatives."""

    def __init__(self) -> None:
        self.client = httpx.Client(timeout=settings.FETCH_TIMEOUT_SECONDS)
        self.download_dir = settings.PDF_DOWNLOAD_DIR / "house"

    def fetch_recent_filings(self, year: Optional[int] = None) -> list[dict]:
        """Fetch list of recent financial disclosures from House API."""
        if year is None:
            year = datetime.now().year

        reports: list[dict] = []
        url = f"{HOUSE_DISCLOSURES_API}/Search"

        params = {
            "FilingYear": str(year),
            "DocType": "Periodic Transaction Report",
        }

        try:
            response = self.client.post(url, data=params)
            response.raise_for_status()

            html = response.text
            reports = self._parse_search_results(html)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch House filings: {e}") from e

        return reports

    def _parse_search_results(self, html: str) -> list[dict]:
        """Parse the House disclosure search results HTML."""
        reports: list[dict] = []

        row_pattern = re.compile(
            r'<tr[^>]*>.*?'
            r'<a[^>]*href="([^"]*)"[^>]*>.*?</a>.*?'
            r'</tr>',
            re.DOTALL | re.IGNORECASE,
        )

        for match in row_pattern.finditer(html):
            href = match.group(1)
            if "/public_disc/ptr-pdfs/" in href or "/public_disc/ptr_pdfs/" in href:
                pdf_url = f"{HOUSE_DOWNLOAD_BASE}{href}" if href.startswith("/") else href
                report_id = hashlib.md5(pdf_url.encode()).hexdigest()[:12]
                reports.append({
                    "url": pdf_url,
                    "report_id": report_id,
                    "chamber": "house",
                    "source": "house_gov",
                })

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

    def get_all_periodic_transaction_reports(self, years: list[int] | None = None) -> list[dict]:
        """Fetch all PTR reports across multiple years."""
        if years is None:
            current_year = datetime.now().year
            years = list(range(current_year - 5, current_year + 1))

        all_reports: list[dict] = []
        for year in years:
            try:
                reports = self.fetch_recent_filings(year)
                all_reports.extend(reports)
            except Exception as e:
                print(f"Warning: Failed to fetch House filings for {year}: {e}")

        return all_reports
