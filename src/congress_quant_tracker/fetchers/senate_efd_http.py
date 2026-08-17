"""Senate eFD HTTP client (session + CSRF + DataTables).

Works when efdsearch is reachable (direct or via HTTP_PROXY).
Flow:
  1. GET /search/home/
  2. POST agreement (checkbox + csrf)
  3. POST /search/report/data/ (DataTables JSON)

Report type 11 = Periodic Transactions
Filer type 1   = Senator
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, date
from typing import Any, Optional

import httpx

from congress_quant_tracker.config import settings

logger = logging.getLogger(__name__)

EFD_HOME = "https://efdsearch.senate.gov/search/home/"
EFD_SEARCH = "https://efdsearch.senate.gov/search/"
EFD_DATA = "https://efdsearch.senate.gov/search/report/data/"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# From eFD search form
REPORT_TYPE_PTR = 11
FILER_TYPE_SENATOR = 1


def _parse_us_date(s: str) -> Optional[date]:
    if not s:
        return None
    s = re.sub(r"<[^>]+>", "", s).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


class SenateEfdHttpClient:
    def __init__(self, proxy: str | None = None) -> None:
        if proxy is not None:
            self.proxy = proxy or None
        else:
            from congress_quant_tracker.fetchers.senate_official import probe_efd_access

            probe = probe_efd_access()
            self.proxy = probe.get("proxy") if probe.get("reachable") else (
                settings.HTTP_PROXY or None
            )
        self.client = httpx.Client(
            proxy=self.proxy,
            timeout=settings.FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*"},
        )
        self._agreed = False

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def accept_terms(self) -> dict[str, Any]:
        r = self.client.get(EFD_HOME)
        r.raise_for_status()
        if "Access Denied" in r.text[:500]:
            raise RuntimeError("Akamai blocked eFD home (Access Denied)")
        m = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', r.text)
        if not m:
            # maybe already past agreement
            if "Find Reports" in r.text or "searchForm" in r.text:
                self._agreed = True
                return {"ok": True, "already_agreed": True}
            raise RuntimeError("No CSRF token on eFD home")
        token = m.group(1)
        r2 = self.client.post(
            EFD_HOME,
            data={"prohibition_agreement": "1", "csrfmiddlewaretoken": token},
            headers={
                "Referer": EFD_HOME,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        r2.raise_for_status()
        self._agreed = True
        return {
            "ok": True,
            "status": r2.status_code,
            "url": str(r2.url),
            "title": _title(r2.text),
        }

    def search_ptrs(
        self,
        start: int = 0,
        length: int = 50,
        start_date: str = "01/01/2025",
        end_date: str = "",
    ) -> dict[str, Any]:
        if not self._agreed:
            self.accept_terms()

        csrf = self.client.cookies.get("csrftoken") or ""
        data: dict[str, str] = {
            "draw": "1",
            "start": str(start),
            "length": str(length),
            "order[0][column]": "4",
            "order[0][dir]": "desc",
            "search[value]": "",
            "search[regex]": "false",
            "report_types": f"[{REPORT_TYPE_PTR}]",
            "filer_types": f"[{FILER_TYPE_SENATOR}]",
            "submitted_start_date": start_date or "",
            "submitted_end_date": end_date or "",
            "candidate_state": "",
            "senator_state": "",
            "office_id": "",
            "first_name": "",
            "last_name": "",
        }
        for i in range(5):
            data[f"columns[{i}][data]"] = str(i)
            data[f"columns[{i}][name]"] = ""
            data[f"columns[{i}][searchable]"] = "true"
            data[f"columns[{i}][orderable]"] = "true"
            data[f"columns[{i}][search][value]"] = ""
            data[f"columns[{i}][search][regex]"] = "false"

        r = self.client.post(
            EFD_DATA,
            data=data,
            headers={
                "User-Agent": UA,
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": csrf,
                "Referer": EFD_SEARCH,
                "Origin": "https://efdsearch.senate.gov",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
        )
        if r.status_code == 503 or "Under Maintenance" in r.text[:400]:
            raise RuntimeError(
                "eFD report data API is under maintenance (503). "
                "Home/search HTML works; try again later."
            )
        if r.status_code == 403:
            raise RuntimeError(f"eFD data API 403 (csrf/session). body={r.text[:200]}")
        r.raise_for_status()
        return r.json()

    def fetch_ptr_index(self, max_rows: int = 100) -> list[dict]:
        """Return normalized PTR report metadata rows."""
        out: list[dict] = []
        start = 0
        page = 50
        while start < max_rows:
            length = min(page, max_rows - start)
            payload = self.search_ptrs(start=start, length=length)
            rows = payload.get("data") or []
            if not rows:
                break
            for row in rows:
                out.append(self._normalize_datatable_row(row))
            start += length
            total = payload.get("recordsFiltered") or payload.get("recordsTotal") or 0
            if start >= int(total):
                break
        return out

    def fetch_ptr_html(self, url: str) -> str:
        if not self._agreed:
            self.accept_terms()
        if url.startswith("/"):
            url = f"https://efdsearch.senate.gov{url}"
        r = self.client.get(url, headers={"Referer": EFD_SEARCH, "User-Agent": UA})
        r.raise_for_status()
        return r.text

    def _normalize_datatable_row(self, row: Any) -> dict:
        # DataTables returns list of HTML cell strings
        cells = row if isinstance(row, list) else list(row.values()) if isinstance(row, dict) else []
        def strip_html(s: str) -> str:
            return re.sub(r"<[^>]+>", "", s or "").strip()

        first = strip_html(cells[0]) if len(cells) > 0 else ""
        last = strip_html(cells[1]) if len(cells) > 1 else ""
        office = strip_html(cells[2]) if len(cells) > 2 else ""
        report_type = strip_html(cells[3]) if len(cells) > 3 else ""
        date_raw = strip_html(cells[4]) if len(cells) > 4 else ""

        href = ""
        blob = " ".join(str(c) for c in cells)
        m = re.search(r'href="([^"]*ptr[^"]*)"', blob, re.I)
        if m:
            href = m.group(1)
        if href and not href.startswith("http"):
            href = f"https://efdsearch.senate.gov{href}"

        rid = hashlib.md5((href or f"{first}{last}{date_raw}").encode()).hexdigest()[:12]
        return {
            "report_id": rid,
            "first_name": first,
            "last_name": last,
            "name": f"{first} {last}".strip(),
            "office": office,
            "report_type": report_type,
            "filing_date": _parse_us_date(date_raw),
            "url": href,
            "chamber": "senate",
            "source": "senate_efd_http",
        }


def _title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return m.group(1).strip() if m else ""
