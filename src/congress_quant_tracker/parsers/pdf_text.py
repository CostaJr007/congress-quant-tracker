"""Page-level text extraction for disclosure PDFs, with OCR fallback.

House PTR filings arrive in two shapes:

  * born-digital PDFs with a real text layer (pdfplumber reads them)
  * scanned/hand-filled PDFs where every page is a single image and the text
    layer is empty — these used to be parsed as "empty" and silently produced
    zero trades.

This module extracts text page by page through a cascade:

  1. pdfplumber text layer
  2. pypdf text layer
  3. pypdfium2 text layer
  4. OCR of the rendered page image (RapidOCR, else pytesseract)

A page only falls through to the next backend when the previous one returned
(almost) nothing, so born-digital filings never pay the OCR cost. OCR pages
keep their word boxes so callers can use the form's column geometry (see
`ptr_form`), not just the raw text.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

from congress_quant_tracker.config import settings

logger = logging.getLogger(__name__)

# A page with less text than this is treated as image-only and OCR'd.
MIN_TEXT_CHARS = 60

# OCR engines, in preference order. Both are optional dependencies.
OCR_ENGINES = ("rapidocr", "tesseract")


@dataclass(frozen=True)
class TextBox:
    """One OCR word/line box in page pixel coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    confidence: float = 0.0

    @property
    def x_center(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return max(1.0, self.y1 - self.y0)


@dataclass
class PageText:
    page_number: int
    text: str
    method: str  # "text" | "ocr" | "none"
    confidence: float | None = None
    width: float = 0.0
    height: float = 0.0
    boxes: list[TextBox] = field(default_factory=list)


@dataclass
class DocumentText:
    pages: list[PageText]

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.pages if p.text)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def ocr_pages(self) -> list[int]:
        return [p.page_number for p in self.pages if p.method == "ocr"]

    @property
    def empty_pages(self) -> list[int]:
        return [p.page_number for p in self.pages if p.method == "none"]

    def method_summary(self) -> dict[str, int]:
        summary: dict[str, int] = {}
        for page in self.pages:
            summary[page.method] = summary.get(page.method, 0) + 1
        return summary

    def diagnostics(self) -> dict:
        return {
            "pages": self.page_count,
            "characters": len(self.text),
            "methods": self.method_summary(),
            "ocr_pages": self.ocr_pages,
            "empty_pages": self.empty_pages,
            "ocr_engine": ocr_engine(),
        }


# --------------------------------------------------------------------------
# OCR text repair
# --------------------------------------------------------------------------

# OCR confuses letters with digits inside dates/amounts ("O8/O7/26", "S0,000").
_AMBIGUOUS_DIGITS = str.maketrans({"O": "0", "o": "0", "Q": "0", "D": "0",
                                  "I": "1", "l": "1", "|": "1",
                                  "S": "5", "s": "5", "B": "8", "Z": "2"})
_DATEISH = re.compile(r"^[\dOoIlSsBbZQ|./-]{3,12}$")
_MONEYISH = re.compile(r"^\$[\dOoIlSsBbZQ,. ]{2,15}$")


def repair_ocr_token(token: str) -> str:
    """Fix OCR letter/digit confusion inside date- and money-shaped tokens.

    Only tokens that already look like a date or an amount are rewritten, so
    ordinary words ("Sale", "Bloom") are never mangled.
    """
    if not token:
        return token
    if "/" in token and _DATEISH.match(token):
        fixed = token.translate(_AMBIGUOUS_DIGITS)
        # "O8/O7/2b" -> still junk if no slash structure survives
        return fixed if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", fixed) else token
    if token.startswith("$") and _MONEYISH.match(token):
        fixed = token.translate(_AMBIGUOUS_DIGITS)
        fixed = re.sub(r"[^0-9,.$ ]", "", fixed)
        return fixed if re.search(r"\d", fixed) else token
    return token


def repair_ocr_text(text: str) -> str:
    if not text or not text.strip():
        return text
    return " ".join(repair_ocr_token(tok) for tok in text.split())


# --------------------------------------------------------------------------
# Text-layer backends
# --------------------------------------------------------------------------


def _pdfplumber_pages(path: Path, max_pages: int) -> list[str]:
    try:
        import pdfplumber
    except ImportError:
        return []
    out: list[str] = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages[:max_pages]:
                try:
                    out.append(page.extract_text() or "")
                except Exception as exc:  # malformed page must not kill the file
                    logger.debug("pdfplumber page failed in %s: %s", path.name, exc)
                    out.append("")
    except Exception as exc:
        logger.warning("pdfplumber failed on %s: %s", path.name, exc)
        return []
    return out


def _pypdf_pages(path: Path, max_pages: int) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    out: list[str] = []
    try:
        reader = PdfReader(str(path))
        for page in reader.pages[:max_pages]:
            try:
                out.append(page.extract_text() or "")
            except Exception:
                out.append("")
    except Exception as exc:
        logger.debug("pypdf failed on %s: %s", path.name, exc)
        return []
    return out


def _pdfium_pages(path: Path, max_pages: int) -> list[str]:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return []
    out: list[str] = []
    try:
        doc = pdfium.PdfDocument(str(path))
        for i in range(min(len(doc), max_pages)):
            try:
                out.append(doc[i].get_textpage().get_text_range() or "")
            except Exception:
                out.append("")
    except Exception as exc:
        logger.debug("pypdfium2 text failed on %s: %s", path.name, exc)
        return []
    return out


def _best_text_layer(path: Path, max_pages: int, page_count: int) -> list[str]:
    """Longest text per page across the available text-layer backends."""
    if page_count <= 0:
        return []
    best = [""] * page_count
    for backend in (_pdfplumber_pages, _pypdf_pages, _pdfium_pages):
        try:
            pages = backend(path, max_pages)
        except Exception as exc:  # a broken backend must not stop the cascade
            logger.debug("%s crashed on %s: %s", backend.__name__, path.name, exc)
            continue
        for i, text in enumerate(pages[:page_count]):
            if len(text or "") > len(best[i]):
                best[i] = text or ""
        if all(len(t) >= MIN_TEXT_CHARS for t in best):
            break
    return best


def _pdf_page_count(path: Path) -> int:
    for counter in (
        lambda: __import__("pdfplumber").open(path).__len__(),
        lambda: len(__import__("pypdf").PdfReader(str(path)).pages),
        lambda: len(__import__("pypdfium2").PdfDocument(str(path))),
    ):
        try:
            return int(counter())
        except Exception:
            continue
    return 0


# --------------------------------------------------------------------------
# Rendering + OCR backends
# --------------------------------------------------------------------------


def _render_page_image(path: Path, index: int, scale: float):
    """Rasterize one page (0-based). Returns a PIL image or None."""
    try:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(path))
        return doc[index].render(scale=scale).to_pil()
    except Exception as exc:
        logger.debug("pypdfium2 render failed on %s p%s: %s", path.name, index + 1, exc)

    # Fallback: a scanned page is one big embedded image.
    try:
        from io import BytesIO

        from PIL import Image
        from pypdf import PdfReader

        page = PdfReader(str(path)).pages[index]
        for img in page.images:
            with Image.open(BytesIO(img.data)) as im:
                return im.convert("RGB")
    except Exception as exc:
        logger.debug("embedded-image fallback failed on %s p%s: %s", path.name, index + 1, exc)
    return None


def _rapidocr():
    try:
        from rapidocr_onnxruntime import RapidOCR

        return RapidOCR()
    except Exception:
        return None


_TESSERACT_WARNED = False


def _tesseract():
    global _TESSERACT_WARNED
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return pytesseract
    except Exception as exc:
        if not _TESSERACT_WARNED:
            logger.debug("tesseract unavailable: %s", exc)
            _TESSERACT_WARNED = True
        return None


_OCR_ENGINE_CACHE: list[str | None] = []


def ocr_engine() -> str | None:
    """Name of the usable OCR backend ("rapidocr"/"tesseract"), else None."""
    if _OCR_ENGINE_CACHE:
        return _OCR_ENGINE_CACHE[0]
    engine: str | None = None
    if _rapidocr() is not None:
        engine = "rapidocr"
    elif _tesseract() is not None:
        engine = "tesseract"
    _OCR_ENGINE_CACHE.append(engine)
    return engine


def _ocr_rapidocr(image) -> tuple[str, list[TextBox], float]:
    ocr = _rapidocr()
    if ocr is None:
        return "", [], 0.0
    result, _elapsed = ocr(image)
    boxes: list[TextBox] = []
    for item in result or []:
        try:
            points, text, conf = item[0], str(item[1]), float(item[2])
        except (IndexError, TypeError, ValueError):
            continue
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        text = repair_ocr_text(text.strip())
        if not text:
            continue
        boxes.append(
            TextBox(min(xs), min(ys), max(xs), max(ys), text, conf)
        )
    return _boxes_to_lines(boxes), boxes, _mean_confidence(boxes)


def _ocr_tesseract(image) -> tuple[str, list[TextBox], float]:
    pytesseract = _tesseract()
    if pytesseract is None:
        return "", [], 0.0
    from pytesseract import Output

    data = pytesseract.image_to_data(image, output_type=Output.DICT)
    boxes: list[TextBox] = []
    for i, word in enumerate(data.get("text", [])):
        word = repair_ocr_text(str(word).strip())
        if not word:
            continue
        try:
            conf = float(data["conf"][i]) / 100.0
        except (KeyError, IndexError, TypeError, ValueError):
            conf = 0.0
        if conf < 0:
            continue
        x, y = float(data["left"][i]), float(data["top"][i])
        w, h = float(data["width"][i]), float(data["height"][i])
        boxes.append(TextBox(x, y, x + w, y + h, word, conf))
    return _boxes_to_lines(boxes), boxes, _mean_confidence(boxes)


def _mean_confidence(boxes: list[TextBox]) -> float:
    if not boxes:
        return 0.0
    weight = sum(max(1, len(b.text)) for b in boxes)
    return round(sum(b.confidence * max(1, len(b.text)) for b in boxes) / weight, 3)


def _boxes_to_lines(boxes: list[TextBox], y_tolerance_ratio: float = 0.6) -> str:
    """Rebuild reading-order lines from OCR boxes (top-to-bottom, left-to-right)."""
    if not boxes:
        return ""
    tolerance = max(4.0, median(b.height for b in boxes) * y_tolerance_ratio)
    ordered = sorted(boxes, key=lambda b: (b.y_center, b.x0))
    lines: list[list[TextBox]] = []
    for box in ordered:
        if lines and abs(box.y_center - median(b.y_center for b in lines[-1])) <= tolerance:
            lines[-1].append(box)
        else:
            lines.append([box])
    text_lines = []
    for line in lines:
        parts = [b.text for b in sorted(line, key=lambda b: b.x0)]
        text_lines.append(" ".join(parts).strip())
    return "\n".join(t for t in text_lines if t)


def ocr_page_image(image) -> tuple[str, list[TextBox], float, str]:
    """OCR one page image. Returns (text, boxes, confidence, engine)."""
    engine = ocr_engine()
    if engine == "rapidocr":
        text, boxes, conf = _ocr_rapidocr(image)
        return text, boxes, conf, engine
    if engine == "tesseract":
        text, boxes, conf = _ocr_tesseract(image)
        return text, boxes, conf, engine
    return "", [], 0.0, "unavailable"


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def extract_document(
    pdf_path: Path | str,
    *,
    max_pages: int | None = None,
    allow_ocr: bool | None = None,
    ocr_max_pages: int | None = None,
) -> DocumentText:
    """Extract per-page text, OCR'ing image-only pages when possible."""
    path = Path(pdf_path)
    limit = max_pages or settings.MAX_PDF_PAGES
    if allow_ocr is None:
        allow_ocr = bool(settings.OCR_ENABLED)
    ocr_budget = ocr_max_pages if ocr_max_pages is not None else settings.OCR_MAX_PAGES

    page_count = _pdf_page_count(path)
    if page_count <= 0:
        return DocumentText(pages=[])
    page_count = min(page_count, limit)

    text_pages = _best_text_layer(path, limit, page_count)

    pages: list[PageText] = []
    ocr_used = 0
    for index in range(page_count):
        raw = text_pages[index] if index < len(text_pages) else ""
        if len(raw.strip()) >= MIN_TEXT_CHARS:
            pages.append(PageText(index + 1, raw, "text"))
            continue

        if not allow_ocr or ocr_used >= ocr_budget or ocr_engine() is None:
            pages.append(PageText(index + 1, raw, "text" if raw.strip() else "none"))
            continue

        image = _render_page_image(path, index, settings.OCR_RENDER_SCALE)
        if image is None:
            pages.append(PageText(index + 1, raw, "text" if raw.strip() else "none"))
            continue

        text, boxes, conf, engine = ocr_page_image(image)
        ocr_used += 1
        if len(text.strip()) < 10:
            pages.append(
                PageText(index + 1, raw, "text" if raw.strip() else "none", boxes=boxes)
            )
            continue
        pages.append(
            PageText(
                page_number=index + 1,
                text=text,
                method="ocr",
                confidence=conf,
                width=float(image.width),
                height=float(image.height),
                boxes=boxes,
            )
        )
        logger.debug("OCR %s page %s (%s, conf=%.2f)", path.name, index + 1, engine, conf)

    return DocumentText(pages=pages)


def extract_text(pdf_path: Path | str, **kwargs) -> str:
    """Convenience wrapper returning the whole-document text."""
    return extract_document(pdf_path, **kwargs).text


__all__ = [
    "DocumentText",
    "MIN_TEXT_CHARS",
    "PageText",
    "TextBox",
    "extract_document",
    "extract_text",
    "ocr_engine",
    "ocr_page_image",
    "repair_ocr_text",
    "repair_ocr_token",
]
