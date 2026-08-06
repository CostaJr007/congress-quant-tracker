"""PDF parser using Claude 3.5 Sonnet for structured extraction of financial disclosures."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pdfplumber
from anthropic import Anthropic

from congress_quant_tracker.config import settings


EXTRACTION_PROMPT = """Extract ALL stock and options trades from this congressional financial disclosure report.

Return a JSON object with this structure:
{
  "politician": {
    "name": "Full Name",
    "chamber": "house" or "senate",
    "state": "XX (2-letter code)",
    "party": "D" or "R" or "I"
  },
  "trades": [
    {
      "ticker": "AAPL",
      "asset_name": "Apple Inc.",
      "asset_type": "stock" or "option",
      "transaction_type": "buy" or "sell" or "exchange",
      "trade_date": "YYYY-MM-DD",
      "filing_date": "YYYY-MM-DD",
      "value_min": 15000,
      "value_max": 50000,
      "value_range": "$15,001 - $50,000",
      "shares_min": null,
      "shares_max": null,
      "report_type": "Periodic Transaction Report"
    }
  ],
  "options": [
    {
      "ticker": "AAPL",
      "option_type": "call" or "put",
      "strike": 150.00,
      "expiration_date": "YYYY-MM-DD",
      "contracts_min": 1,
      "contracts_max": 5,
      "premium_min": 15000,
      "premium_max": 50000,
      "premium_range": "$15,001 - $50,000",
      "underlying_asset": "AAPL",
      "trade_date": "YYYY-MM-DD",
      "transaction_type": "buy" or "sell"
    }
  ]
}

IMPORTANT RULES:
1. Extract EVERY trade listed - do not skip any.
2. For value ranges, use exact values from the document (like $1,001 - $15,000).
3. Only estimate shares if the document explicitly mentions them.
4. For options, extract strike price and expiration date EXACTLY as shown.
5. If no trades are found, return empty arrays: {"politician": null, "trades": [], "options": []}
6. Map transaction type: Purchase = buy, Sale = sell, Exchange = exchange.
7. For ticker, use the stock symbol if available. Otherwise use the company name as asset_name and leave ticker null.
"""


class PDFTradeExtractor:
    """Extracts structured trade data from congressional financial disclosure PDFs
    using Claude 3.5 Sonnet for high-accuracy parsing."""

    def __init__(self) -> None:
        client_kwargs: dict = {"api_key": settings.ANTHROPIC_API_KEY}
        if settings.ANTHROPIC_BASE_URL:
            client_kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
        self.client = Anthropic(**client_kwargs)

    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract raw text from a PDF using pdfplumber."""
        text_parts: list[str] = []

        with pdfplumber.open(pdf_path) as pdf:
            pages_to_read = min(len(pdf.pages), settings.MAX_PDF_PAGES)
            for page_num in range(pages_to_read):
                page = pdf.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

                tables = page.extract_tables()
                for table in tables:
                    if table:
                        table_text = "\n".join(
                            " | ".join(str(cell) if cell else "" for cell in row)
                            for row in table
                        )
                        text_parts.append(table_text)

        return "\n\n--- PAGE BREAK ---\n\n".join(text_parts)

    def extract_trades_with_llm(self, pdf_text: str) -> dict:
        """Send PDF text to Claude for structured extraction."""
        response = self.client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=4096,
            system="You are a precise data extraction tool. Extract financial disclosure data exactly as it appears. Never hallucinate or make up data. Only extract what is explicitly stated in the document.",
            messages=[
                {"role": "user", "content": f"{EXTRACTION_PROMPT}\n\nDOCUMENT TEXT:\n{pdf_text[:70000]}"},
            ],
        )

        raw_text = response.content[0].text if isinstance(response.content, list) else response.content

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                return {"politician": None, "trades": [], "options": []}

        return data

    def parse_pdf(self, pdf_path: Path) -> dict:
        """Full pipeline: extract text from PDF and parse with LLM."""
        pdf_text = self.extract_text_from_pdf(pdf_path)

        if not pdf_text.strip():
            return {"politician": None, "trades": [], "options": []}

        return self.extract_trades_with_llm(pdf_text)

    def parse_pdf_batch(self, pdf_paths: list[Path]) -> list[dict]:
        """Parse multiple PDFs."""
        results: list[dict] = []
        for pdf_path in pdf_paths:
            try:
                result = self.parse_pdf(pdf_path)
                result["report_id"] = pdf_path.stem
                result["source_pdf"] = str(pdf_path)
                results.append(result)
            except Exception as e:
                results.append({
                    "report_id": pdf_path.stem,
                    "source_pdf": str(pdf_path),
                    "error": str(e),
                    "politician": None,
                    "trades": [],
                    "options": [],
                })
        return results
