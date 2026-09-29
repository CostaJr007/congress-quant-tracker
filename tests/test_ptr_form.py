"""Tests for the printed-grid reader used on scanned PTR pages.

The form is synthesized here (rules + header letters + check marks) so the
geometry, the cell naming and the "unknown rather than guessed" behaviour are
all covered without shipping a scanned PDF.
"""

from datetime import date

import pytest
from PIL import Image, ImageDraw

from congress_quant_tracker.parsers.pdf_text import TextBox
from congress_quant_tracker.parsers.ptr_form import (
    AMOUNT_BANDS,
    band_for_letter,
    band_for_value,
    detect_geometry,
    read_rows,
)

SCALE = 3.0
# Cell layout of the printed form: owner, asset, Purchase, Sale, Exch,
# Cap.Gains, Partial, Date, Notified, then the ten amount columns A..J.
VLINES = [
    10, 60, 220, 280, 330, 380, 440, 500, 560, 620,
    680, 740, 800, 860, 920, 980, 1040, 1100, 1160, 1220,
]
A_INDEX = 9
HLINES = [40, 90, 130, 160, 200, 240, 280, 320]


def _letter_boxes() -> list[TextBox]:
    boxes = []
    for offset, letter in enumerate("ABCDEFGHIJ"):
        x = (VLINES[A_INDEX + offset] + VLINES[A_INDEX + offset + 1]) / 2
        boxes.append(TextBox(x - 6, 108, x + 6, 122, letter, 0.95))
    # Header words (used only as corroboration)
    for x, text in ((250, "Purchase"), (305, "Sale"), (355, "Exch"), (330, "Amount")):
        boxes.append(TextBox(x, 100, x + 40, 120, text, 0.9))
    return boxes


def _date_boxes(row_y: float, asset: str = "AMRIZE LTD CMN") -> list[TextBox]:
    return [
        TextBox(510, row_y - 8, 550, row_y + 8, "08/07/26", 0.95),
        TextBox(570, row_y - 8, 610, row_y + 8, "09/01/26", 0.95),
        TextBox(150, row_y - 8, 210, row_y + 8, asset, 0.9),
    ]


# Two data rows, each with its own date cells (bands 160-200 and 240-280)
ROW_ONE_Y = 180
ROW_TWO_Y = 260
ROW_ONE_BAND = (160, 200)
BLANK_BAND = (280, 320)


def _all_row_boxes() -> list[TextBox]:
    return (
        _letter_boxes()
        + _date_boxes(ROW_ONE_Y)
        + _date_boxes(ROW_TWO_Y, "FACTSET RESEARCH SYSTEMS")
    )


def _image_with_marks(marks: list[tuple[float, float]], size=(1280, 340)) -> Image.Image:
    image = Image.new("L", size, 255)
    draw = ImageDraw.Draw(image)
    for x in VLINES:
        draw.line([(x, HLINES[0]), (x, HLINES[-1])], fill=0, width=2)
    for y in HLINES:
        draw.line([(VLINES[0], y), (VLINES[-1], y)], fill=0, width=2)
    for mx, my in marks:
        draw.line([(mx - 10, my - 10), (mx + 10, my + 10)], fill=0, width=4)
        draw.line([(mx - 10, my + 10), (mx + 10, my - 10)], fill=0, width=4)
    return image


def test_band_tables_are_consistent():
    assert band_for_letter("A") == (1_001, 15_000, "$1,001 - $15,000")
    assert band_for_letter("J")[0] == 50_000_001
    for letter, low, high in AMOUNT_BANDS:
        assert band_for_value(low) == letter
        if high is not None:
            assert band_for_value(high) == letter
    assert band_for_value(12_345) is None


def test_detect_geometry_names_cells_from_the_amount_letters():
    boxes = _all_row_boxes()
    geometry = detect_geometry(_image_with_marks([]), boxes, scale=SCALE)
    assert geometry is not None
    assert list(geometry.amount_cells) == list("ABCDEFGHIJ")
    assert geometry.amount_cells["A"][0] == pytest.approx(VLINES[A_INDEX], abs=2)
    assert geometry.amount_ranges["B"] == (15_001, 50_000, "$15,001 - $50,000")
    # Purchase / Sale / Exch sit at their printed offsets left of the amounts
    assert geometry.type_cells["buy"][0] == pytest.approx(VLINES[A_INDEX - 7], abs=2)
    assert geometry.type_cells["sell"][0] == pytest.approx(VLINES[A_INDEX - 6], abs=2)
    assert geometry.type_cells["exchange"][0] == pytest.approx(VLINES[A_INDEX - 5], abs=2)
    assert geometry.usable_types and geometry.usable_amounts


def test_read_rows_reports_side_amount_and_text():
    buy_x = (VLINES[A_INDEX - 7] + VLINES[A_INDEX - 6]) / 2
    amount_x = (VLINES[A_INDEX + 2] + VLINES[A_INDEX + 3]) / 2  # column C
    boxes = _all_row_boxes()
    image = _image_with_marks([(buy_x, ROW_ONE_Y), (amount_x, ROW_ONE_Y)])
    geometry = detect_geometry(image, boxes, scale=SCALE)
    rows = read_rows(image, geometry, boxes)
    row = next(r for r in rows if "AMRIZE" in r.text)
    assert row.side == "buy"
    assert row.amount_letter == "C"
    assert row.value_range == "$50,001 - $100,000"
    assert "08/07/26" in row.text
    # the neighbouring row keeps its own (empty) marks
    other = next(r for r in rows if "FACTSET" in r.text)
    assert other.side is None and other.amount_letter is None


def test_rows_without_a_mark_are_unknown_not_assumed():
    boxes = _all_row_boxes()
    image = _image_with_marks([])
    geometry = detect_geometry(image, boxes, scale=SCALE)
    rows = read_rows(image, geometry, boxes)
    assert rows
    assert all(r.side is None for r in rows)
    assert all(r.amount_letter is None for r in rows)


def test_unlabelled_cells_are_not_guessed():
    """Letters missing from the header still resolve, thanks to the offsets."""
    boxes = (
        [b for b in _letter_boxes() if b.text in ("A", "E", "H")]
        + _date_boxes(ROW_ONE_Y)
        + _date_boxes(ROW_TWO_Y, "FACTSET")
    )
    geometry = detect_geometry(_image_with_marks([]), boxes, scale=SCALE)
    assert geometry is not None
    assert geometry.amount_cells["J"][0] == pytest.approx(VLINES[A_INDEX + 9], abs=2)
    assert geometry.amount_ranges["H"] == (5_000_001, 25_000_000, "$5,000,001 - $25,000,000")


def test_page_without_a_grid_is_rejected():
    plain = Image.new("L", (600, 400), 255)
    assert detect_geometry(plain, _letter_boxes(), scale=SCALE) is None
    assert detect_geometry(_image_with_marks([]), [], scale=SCALE) is None


def test_marked_band_without_dates_yields_no_trade():
    """A stray mark below the table can never become a trade."""
    from congress_quant_tracker.parsers.ptr_rows import parse_row

    boxes = _all_row_boxes()
    image = _image_with_marks([(250, 300), (800, 300)])
    geometry = detect_geometry(image, boxes, scale=SCALE)
    rows = read_rows(image, geometry, boxes)
    # the marked band carries no date cells, so it produces no trade row
    assert all("AMRIZE" in r.text or "FACTSET" in r.text for r in rows)
    assert parse_row("AMRIZE LTD CMN X", side="buy", value_min=1_001) is None


def test_parse_row_accepts_grid_values_used_by_the_reader():
    """The values the reader emits are what ptr_rows consumes."""
    from congress_quant_tracker.parsers.ptr_rows import parse_row

    boxes = _all_row_boxes()
    amount_x = (VLINES[A_INDEX] + VLINES[A_INDEX + 1]) / 2  # column A
    marks = [(250, ROW_ONE_Y), (amount_x, ROW_ONE_Y)]
    image = _image_with_marks(marks)
    geometry = detect_geometry(image, boxes, scale=SCALE)
    rows = read_rows(image, geometry, boxes)
    row = next(r for r in rows if "AMRIZE" in r.text)
    trade = parse_row(
        row.text,
        side=row.side,
        value_min=row.value_min,
        value_max=row.value_max,
        value_range=row.value_range,
        amount_column=row.amount_letter or "",
    )
    assert trade["trade_date"] == date(2026, 8, 7).isoformat()
    assert trade["filing_date"] == date(2026, 9, 1).isoformat()
    assert trade["value_min"] == 1_001
    assert trade["amount_column"] == "A"
