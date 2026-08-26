"""Senate disclosure fetchers — multi-strategy.

Problem:
  efdsearch.senate.gov is fronted by Akamai. Many cloud/datacenter IPs get
  HTTP 403 "Access Denied" even with a real browser (Playwright).

Strategies (tried in order when using SenatePipeline):
  1. CongressInvests free API (chamber=senate) — works remotely, may lag
  2. Playwright against efdsearch — works from many residential IPs
  3. Optional cookie file from a real browser session

Public search UI: https://efdsearch.senate.gov/search/home/
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, date
from typing import Any, Optional

import httpx

from congress_quant_tracker.common import normalize_transaction_type
from congress_quant_tracker.config import settings

logger = logging.getLogger(__name__)

EFD_HOME = "https://efdsearch.senate.gov/search/home/"
EFD_SEARCH = "https://efdsearch.senate.gov/search/"
EFD_DATA = "https://efdsearch.senate.gov/search/report/data/"
CONGRESSINVESTS = settings.CONGRESSINVESTS_API.rstrip("/")

# From the eFD search form (see senate_efd_http)
REPORT_TYPE_PTR = 11
FILER_TYPE_SENATOR = 1


def _parse_us_date(s: str) -> Optional[date]:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _probe_once(timeout: float, proxy: str | None) -> dict[str, Any]:
    try:
        kwargs: dict[str, Any] = {
            "timeout": timeout,
            "follow_redirects": True,
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
            },
        }
        if proxy:
            kwargs["proxy"] = proxy
        r = httpx.get(EFD_HOME, **kwargs)
        blocked = r.status_code == 403 or "Access Denied" in r.text[:500]
        return {
            "reachable": not blocked and r.status_code < 400 and len(r.content) > 500,
            "status_code": r.status_code,
            "blocked_by_akamai": blocked,
            "url": str(r.url),
            "proxy": proxy,
            "bytes": len(r.content),
        }
    except Exception as e:
        return {
            "reachable": False,
            "status_code": None,
            "blocked_by_akamai": False,
            "error": str(e),
            "proxy": proxy,
        }


def probe_efd_access(timeout: float = 20.0, proxy: str | None = None) -> dict[str, Any]:
    """Check whether this network (or optional proxy) can reach efdsearch.

    Tries direct first, then the configured proxy. A dead proxy must not
    hide a working direct path.
    """
    configured = (proxy if proxy is not None else settings.HTTP_PROXY) or None
    attempts: list[str | None] = [None]
    if configured:
        attempts.append(configured)

    last: dict[str, Any] = {"reachable": False}
    tried: list[dict[str, Any]] = []
    for px in attempts:
        result = _probe_once(timeout, px)
        tried.append(result)
        last = result
        if result.get("reachable"):
            result["attempts"] = [
                {"proxy": t.get("proxy"), "reachable": t.get("reachable"), "error": t.get("error")}
                for t in tried
            ]
            return result
    last["attempts"] = [
        {"proxy": t.get("proxy"), "reachable": t.get("reachable"), "error": t.get("error")}
        for t in tried
    ]
    return last


# ── Strategy A: CongressInvests ────────────────────────────────────────


async def fetch_senate_via_congressinvests(max_pages: int = 30) -> list[dict]:
    """Fetch senate trades from the free CongressInvests API."""
    from congress_quant_tracker.fetchers.congress_invests import (
        fetch_trades,
        _load_members_db,
        classify_asset,
        parse_option_details,
    )

    members = _load_members_db()
    all_trades: list[dict] = []
    offset = 0
    for _ in range(max_pages):
        batch = await fetch_trades(chamber="senate", limit=200, offset=offset)
        if not batch:
            break
        for t in batch:
            key = (t.get("member") or "").lower().strip()
            info = members.get(key, {})
            if not info and " " in key:
                info = members.get(key.split()[-1], {})
            t["party"] = info.get("party") or t.get("party") or "I"
            t["state"] = info.get("state") or t.get("state") or ""
            t["district"] = info.get("district")
            t["chamber"] = "senate"
            t["asset_type"] = classify_asset(t.get("asset_name", ""), t.get("ticker", ""))
            t["option_details"] = parse_option_details(
                t.get("asset_name", ""), t.get("asset_type", "")
            )
            t["source"] = "congressinvests_senate"
            all_trades.append(t)
        offset += 200
        if len(batch) < 200:
            break
    return all_trades


def fetch_senate_via_congressinvests_sync(max_pages: int = 30) -> list[dict]:
    import asyncio

    return asyncio.run(fetch_senate_via_congressinvests(max_pages=max_pages))


# ── Strategy B: Playwright eFD ─────────────────────────────────────────


class SenateEfdPlaywrightFetcher:
    """
    Browser automation for efdsearch.senate.gov.

    Typical flow (when not Akamai-blocked):
      1. Open /search/home/
      2. Accept the terms checkbox + submit
      3. POST search for Periodic Transaction Report
      4. Collect report links
      5. Open each PTR HTML page and parse the transaction table
    """

    def __init__(self, headless: bool = True, proxy: str | None = None) -> None:
        self.headless = headless
        self.proxy = (proxy if proxy is not None else settings.HTTP_PROXY) or None
        self.download_dir = settings.PDF_DOWNLOAD_DIR / "senate"
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def fetch_ptr_index(self, max_rows: int = 100) -> list[dict]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "playwright not installed. Run: uv add playwright && uv run playwright install chromium"
            ) from e

        reports: list[dict] = []
        with sync_playwright() as p:
            launch_kwargs: dict[str, Any] = {"headless": self.headless}
            if self.proxy:
                # Playwright expects server like http://host:port
                launch_kwargs["proxy"] = {"server": self.proxy}
            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()
            try:
                page.goto(EFD_HOME, wait_until="domcontentloaded", timeout=60_000)
                title = page.title()
                if "Access Denied" in title or "Access Denied" in page.content()[:800]:
                    raise RuntimeError(
                        "Akamai blocked efdsearch.senate.gov from this IP/proxy. "
                        "Set HTTP_PROXY to a working residential/exit IP, or use "
                        "CongressInvests fallback (strategy A)."
                    )

                # Agree to terms (checkbox + continue) — selectors vary over time
                self._accept_terms(page)

                # Go to search and filter PTR
                page.goto(EFD_SEARCH, wait_until="domcontentloaded", timeout=60_000)
                self._accept_terms(page)

                # Try report data endpoint via page.evaluate fetch with session cookies.
                # DataTables expects form-encoded params (mirrors SenateEfdHttpClient).
                result = page.evaluate(
                    """async (payload) => {
                        const params = new URLSearchParams();
                        for (const k in payload) params.set(k, payload[k]);
                        const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
                        const r = await fetch('/search/report/data/', {
                          method: 'POST',
                          headers: {
                            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': csrf,
                          },
                          body: params.toString(),
                          credentials: 'same-origin',
                        });
                        const text = await r.text();
                        return {status: r.status, text};
                    }""",
                    self._efd_payload(0, max_rows),
                )
                if result.get("status") == 200:
                    import json

                    data = json.loads(result["text"])
                    for row in data.get("data") or []:
                        reports.append(self._normalize_row(row))
                    if not reports:
                        # Empty result — fall back to scraping the rendered table
                        reports.extend(self._scrape_search_table(page))
                else:
                    logger.warning(
                        "eFD data endpoint status=%s body=%s",
                        result.get("status"),
                        (result.get("text") or "")[:200],
                    )
                    # Fallback: scrape HTML table if present
                    reports.extend(self._scrape_search_table(page))

            finally:
                browser.close()

        logger.info("Senate eFD Playwright: %s reports", len(reports))
        return reports

    def _accept_terms(self, page) -> None:
        for sel in (
            "input#agree_statement",
            "input[name='agree_statement']",
            "input[type='checkbox']",
        ):
            try:
                box = page.locator(sel).first
                if box.count() and box.is_visible():
                    box.check(force=True)
                    break
            except Exception:
                pass
        for sel in (
            "button:has-text('I Agree')",
            "button:has-text('Agree')",
            "input[type='submit']",
            "button[type='submit']",
            "text=Continue",
        ):
            try:
                btn = page.locator(sel).first
                if btn.count() and btn.is_visible():
                    btn.click(timeout=3000)
                    page.wait_for_timeout(1000)
                    break
            except Exception:
                pass

    def _efd_payload(self, start: int = 0, length: int = 100) -> dict[str, str]:
        """DataTables form-encoded payload (same shape as SenateEfdHttpClient)."""
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
            "submitted_start_date": "01/01/2025",
            "submitted_end_date": "",
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
        return data

    @staticmethod
    def _normalize_cells(cells: list) -> dict:
        """Normalize a DataTables row (list of HTML cell strings)."""
        def strip_html(s: str) -> str:
            return re.sub(r"<[^>]+>", "", s or "").strip()

        first = strip_html(cells[0]) if len(cells) > 0 else ""
        last = strip_html(cells[1]) if len(cells) > 1 else ""
        filing = strip_html(cells[4]) if len(cells) > 4 else ""
        href = ""
        blob = " ".join(str(c) for c in cells)
        m = re.search(r'href="([^"]*ptr[^"]*)"', blob, re.I)
        if m:
            href = m.group(1)
        if href and not href.startswith("http"):
            href = f"https://efdsearch.senate.gov{href}"
        rid = hashlib.md5((href or f"{first}{last}{filing}").encode()).hexdigest()[:12]
        return {
            "report_id": rid,
            "first_name": first,
            "last_name": last,
            "name": f"{first} {last}".strip(),
            "filing_date": _parse_us_date(filing),
            "url": href,
            "chamber": "senate",
            "source": "senate_efd_playwright",
        }

    def _normalize_row(self, row) -> dict:
        # DataTables may return list-of-cells rows or dict rows
        if isinstance(row, list):
            return self._normalize_cells(row)
        # Field names vary by eFD version
        first = row.get("first_name") or row.get("senator_first_name") or ""
        last = row.get("last_name") or row.get("senator_last_name") or ""
        # Sometimes HTML link in report field
        link = row.get("ptr_link") or row.get("report_type") or row.get("file") or ""
        if "<a" in str(link):
            m = re.search(r'href="([^"]+)"', str(link))
            link = m.group(1) if m else ""
        if link and not str(link).startswith("http"):
            link = f"https://efdsearch.senate.gov{link}"
        filing = row.get("date_received") or row.get("filing_date") or row.get("date_recieved") or ""
        rid = hashlib.md5(str(link or f"{first}{last}{filing}").encode()).hexdigest()[:12]
        return {
            "report_id": rid,
            "first_name": first,
            "last_name": last,
            "name": f"{first} {last}".strip(),
            "filing_date": _parse_us_date(str(filing)),
            "url": link,
            "chamber": "senate",
            "source": "senate_efd_playwright",
        }

    def _scrape_search_table(self, page) -> list[dict]:
        reports = []
        try:
            rows = page.locator("table tbody tr").all()
            for row in rows:
                cells = row.locator("td").all_text_contents()
                href = None
                try:
                    href = row.locator("a").first.get_attribute("href")
                except Exception:
                    pass
                if not href:
                    continue
                if not href.startswith("http"):
                    href = f"https://efdsearch.senate.gov{href}"
                first = cells[0].strip() if len(cells) > 0 else ""
                last = cells[1].strip() if len(cells) > 1 else ""
                filing = cells[3].strip() if len(cells) > 3 else ""
                rid = hashlib.md5(href.encode()).hexdigest()[:12]
                reports.append({
                    "report_id": rid,
                    "first_name": first,
                    "last_name": last,
                    "name": f"{first} {last}".strip(),
                    "filing_date": _parse_us_date(filing),
                    "url": href,
                    "chamber": "senate",
                    "source": "senate_efd_playwright_html",
                })
        except Exception as e:
            logger.warning("HTML table scrape failed: %s", e)
        return reports

    def fetch_ptr_html(self, url: str) -> str:
        """Open a single PTR page and return HTML (needs working eFD access)."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            try:
                page.goto(EFD_HOME, wait_until="domcontentloaded", timeout=60_000)
                self._accept_terms(page)
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                return page.content()
            finally:
                browser.close()


def parse_senate_ptr_html(html: str, meta: Optional[dict] = None) -> list[dict]:
    """Parse transaction rows from a Senate PTR HTML page."""
    meta = meta or {}
    trades: list[dict] = []
    # Table rows often: Transaction Date | Owner | Ticker | Asset | Type | Amount
    # Be liberal with regex over plain text extraction
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    plain = re.sub(r"<[^>]+>", " | ", text)
    plain = re.sub(r"\s+", " ", plain)

    # Look for ticker links yahoo style or plain tickers near Purchase/Sale
    row_pat = re.compile(
        r"(?P<td>\d{1,2}/\d{1,2}/\d{4})\s*\|\s*"
        r"(?P<owner>Self|Spouse|Joint|Child|Dependent)?\s*\|?\s*"
        r"(?P<ticker>[A-Z]{1,5}|--)\s*\|?\s*"
        r"(?P<asset>.{5,80}?)\s*\|\s*"
        r"(?P<tx>Purchase|Sale(?:\s*\((?:Partial|Full)\))?|Exchange)\s*\|?\s*"
        r"(?P<amt>\$[\d,]+(?:\s*-\s*\$[\d,]+)?)",
        re.I,
    )
    for m in row_pat.finditer(plain):
        tx = normalize_transaction_type(m.group("tx"))
        ticker = (m.group("ticker") or "").upper()
        if ticker in ("--", "N/A", ""):
            # try extract from asset
            tm = re.search(r"\(([A-Z]{1,5})\)", m.group("asset") or "")
            ticker = tm.group(1) if tm else ""
        if not ticker:
            continue
        amin, amax = 0, 0
        nums = re.findall(r"[\d,]+", m.group("amt") or "")
        vals = []
        for n in nums:
            try:
                vals.append(int(n.replace(",", "")))
            except ValueError:
                pass
        if len(vals) >= 2:
            amin, amax = vals[0], vals[1]
        elif vals:
            amin = amax = vals[0]
        td = _parse_us_date(m.group("td"))
        trades.append({
            "member": meta.get("name") or f"{meta.get('first_name','')} {meta.get('last_name','')}".strip(),
            "chamber": "senate",
            "ticker": ticker,
            "asset_name": (m.group("asset") or "").strip(),
            "transaction_type": tx,
            "trade_date": td.isoformat() if td else None,
            "filing_date": (
                meta["filing_date"].isoformat()
                if isinstance(meta.get("filing_date"), date)
                else meta.get("filing_date")
            ),
            "amount_min": amin,
            "amount_max": amax,
            "amount_range": m.group("amt"),
            "owner": m.group("owner") or "",
            "pdf_url": meta.get("url") or "",
            "source": "senate_efd_html",
        })
    return trades
