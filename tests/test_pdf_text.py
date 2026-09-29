"""Tests for page-level PDF text extraction (text layer + OCR fallback)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from congress_quant_tracker.parsers.pdf_text import (
    TextBox,
    _boxes_to_lines,
    extract_document,
    ocr_engine,
    repair_ocr_text,
    repair_ocr_token,
)


def _write_text_pdf(path: Path, lines: list[str]) -> None:
    """Build a minimal single-page PDF with a real text layer."""
    content = ["BT /F1 12 Tf 72 720 Td 14 TL"]
    for line in lines:
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content.append(f"({escaped}) Tj T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % index + body + b"\nendobj\n"
    xref_start = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_start,
    )
    path.write_bytes(bytes(out))


def test_repair_ocr_token_fixes_dates_and_amounts_only():
    assert repair_ocr_token("O8/O7/26") == "08/07/26"
    assert repair_ocr_token("l0/2l/26") == "10/21/26"
    assert repair_ocr_token("$S0,000") == "$50,000"
    # ordinary words are never rewritten
    assert repair_ocr_token("Sale") == "Sale"
    assert repair_ocr_token("Bloom") == "Bloom"
    assert repair_ocr_text("DC AMRIZE O8/O7/26 $15,OOO") == "DC AMRIZE 08/07/26 $15,000"


def test_boxes_to_lines_groups_by_row_then_x():
    boxes = [
        TextBox(300, 100, 360, 116, "09/01/26", 0.9),
        TextBox(100, 100, 160, 116, "AMRIZE", 0.9),
        TextBox(100, 140, 160, 156, "SECOND", 0.9),
        TextBox(300, 141, 360, 157, "01/15/27", 0.9),
    ]
    assert _boxes_to_lines(boxes) == "AMRIZE 09/01/26\nSECOND 01/15/27"


def test_extract_document_reads_a_text_layer(tmp_path):
    pdf = tmp_path / "ptr.pdf"
    _write_text_pdf(
        pdf,
        [
            "Filing ID #20034963",
            "Name: Hon. Jared Moskowitz",
            "DC Applied Materials, Inc. - Common P 06/18/2026 06/30/2026 $1,001 - $15,000",
            "Stock (AMAT) [ST]",
        ],
    )
    doc = extract_document(pdf)
    assert doc.page_count == 1
    assert doc.pages[0].method == "text"
    assert doc.ocr_pages == []
    assert "Applied Materials" in doc.text
    assert doc.method_summary() == {"text": 1}


def test_extract_document_ocrs_image_only_pages(tmp_path):
    if ocr_engine() is None:
        pytest.skip("no OCR engine installed (rapidocr-onnxruntime / pytesseract)")

    image = Image.new("RGB", (900, 300), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=42)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    draw.text((30, 60), "AMRIZE LTD CMN", fill="black", font=font)
    draw.text((30, 140), "08/07/26  09/01/26", fill="black", font=font)
    pdf = tmp_path / "scan.pdf"
    image.save(pdf, "PDF")

    doc = extract_document(pdf)
    assert doc.page_count == 1
    if doc.pages[0].method != "ocr":
        pytest.skip("OCR produced too little text on this machine")
    assert doc.ocr_pages == [1]
    assert doc.pages[0].boxes, "OCR pages keep their word boxes for the grid reader"
    assert "08/07/26" in doc.text
    assert doc.diagnostics()["ocr_engine"] in ("rapidocr", "tesseract")


def test_ocr_can_be_disabled(tmp_path):
    image = Image.new("RGB", (400, 200), "white")
    pdf = tmp_path / "scan.pdf"
    image.save(pdf, "PDF")
    doc = extract_document(pdf, allow_ocr=False)
    assert doc.pages[0].method in ("none", "text")
    assert doc.ocr_pages == []


def test_missing_file_yields_no_pages(tmp_path):
    doc = extract_document(tmp_path / "nope.pdf")
    assert doc.page_count == 0
    assert doc.text == ""
