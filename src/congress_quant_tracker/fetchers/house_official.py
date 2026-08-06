"""Official House PTR pipeline — index from FD.zip/XML + PDF download.

Source of truth:
  https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip
  https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{DocID}.pdf
"""

from __future__ import annotations

import io
import logging
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from congress_quant_tracker.config import settings

logger = logging.getLogger(__name__)

HOUSE_FD_ZIP = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
HOUSE_PTR_PDF = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"

# FilingType codes in the bulk XML
FILING_PTR = "P"

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


def _parse_us_date(s: str) -> Optional[date]:
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


class HouseOfficialFetcher:
    """Download House disclosure index + PTR PDFs from the Clerk of the House."""

    def __init__(self) -> None:
        self.download_dir = settings.PDF_DOWNLOAD_DIR / "house"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(timeout=settings.FETCH_TIMEOUT_SECONDS, headers=UA, follow_redirects=True)

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    def download_fd_zip(self, year: int) -> bytes:
        url = HOUSE_FD_ZIP.format(year=year)
        logger.info("Downloading House FD index: %s", url)
        r = self.client.get(url)
        r.raise_for_status()
        return r.content

    def fetch_ptr_index(self, years: Optional[list[int]] = None) -> list[dict]:
        """Return all PTR (FilingType=P) filings for the given years, newest first."""
        if years is None:
            y = datetime.now().year
            years = [y, y - 1]

        filings: list[dict] = []
        for year in years:
            try:
                raw = self.download_fd_zip(year)
            except Exception as e:
                logger.warning("Failed FD.zip for %s: %s", year, e)
                continue

            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    xml_name = next((n for n in zf.namelist() if n.lower().endswith(".xml")), None)
                    if not xml_name:
                        logger.warning("No XML in FD.zip for %s", year)
                        continue
                    root = ET.fromstring(zf.read(xml_name))
            except Exception as e:
                logger.warning("Bad FD.zip for %s: %s", year, e)
                continue

            for m in root.findall("Member"):
                ft = (m.findtext("FilingType") or "").strip()
                if ft != FILING_PTR:
                    continue
                doc_id = (m.findtext("DocID") or "").strip()
                if not doc_id:
                    continue
                y = (m.findtext("Year") or str(year)).strip()
                first = (m.findtext("First") or "").strip()
                last = (m.findtext("Last") or "").strip()
                prefix = (m.findtext("Prefix") or "").strip()
                state_dst = (m.findtext("StateDst") or "").strip()
                filing_raw = (m.findtext("FilingDate") or "").strip()
                state = state_dst[:2] if len(state_dst) >= 2 else state_dst
                district = state_dst[2:] if len(state_dst) > 2 else None
                name = f"{first} {last}".strip()
                if prefix and prefix.lower() not in name.lower():
                    # keep Hon. out of name for matching
                    pass
                filings.append({
                    "doc_id": doc_id,
                    "year": int(y) if y.isdigit() else year,
                    "first_name": first,
                    "last_name": last,
                    "name": name,
                    "prefix": prefix,
                    "state": state,
                    "district": district,
                    "state_dst": state_dst,
                    "filing_date": _parse_us_date(filing_raw),
                    "filing_date_raw": filing_raw,
                    "chamber": "house",
                    "source": "house_official",
                    "pdf_url": HOUSE_PTR_PDF.format(year=y, doc_id=doc_id),
                })

        filings.sort(
            key=lambda x: x["filing_date"] or date.min,
            reverse=True,
        )
        logger.info("House PTR index: %s filings across years %s", len(filings), years)
        return filings

    def pdf_path(self, doc_id: str) -> Path:
        return self.download_dir / f"{doc_id}.pdf"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    def download_pdf(self, filing: dict, force: bool = False) -> Optional[Path]:
        """Download PTR PDF; return local path or None on failure."""
        doc_id = filing["doc_id"]
        path = self.pdf_path(doc_id)
        if path.exists() and path.stat().st_size > 1000 and not force:
            return path

        url = filing.get("pdf_url") or HOUSE_PTR_PDF.format(
            year=filing.get("year", datetime.now().year),
            doc_id=doc_id,
        )
        try:
            r = self.client.get(url)
            if r.status_code != 200 or "pdf" not in (r.headers.get("content-type") or "").lower():
                # try content sniff
                if not r.content.startswith(b"%PDF"):
                    logger.warning("Not a PDF for %s (%s): %s", doc_id, r.status_code, url)
                    return None
            path.write_bytes(r.content)
            return path
        except Exception as e:
            logger.warning("Download failed %s: %s", url, e)
            return None
