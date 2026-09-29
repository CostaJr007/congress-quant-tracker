"""Read the printed table of a scanned House PTR page.

Scanned/hand-filled PTRs state the side and the amount with checked boxes, not
with text: the transaction type is an X under "Purchase", "Sale" or "Exch", and
the amount is an X in one of ten lettered columns (A $1,001-$15,000 ... J over
$50,000,000). No text layer says any of it, which is why those filings used to
parse as zero trades.

The grid is recovered from the page image:

  * rule lines from dark-pixel runs (horizontal lines across the page, vertical
    lines inside the table band)
  * the amount block is anchored on the printed column letters A..J (single
    characters the OCR reads reliably), which give the whole block because the
    ten amount cells are consecutive
  * the transaction-type cells sit at fixed offsets to the left of the amount
    block on this form, and the offsets are only accepted when the intervening
    date/notification cells really do hold the row dates
  * a cell counts as marked when it holds a dark blob, cross-checked with any X
    the OCR saw inside it

Anything that cannot be established this way is reported as unknown: a row with
no mark in a named type column is "unreadable", never assumed to be a buy.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import numpy as np

from congress_quant_tracker.parsers.pdf_text import PageText, TextBox

logger = logging.getLogger(__name__)

# STOCK Act amount ranges, as printed on the PTR form (columns A..J).
AMOUNT_BANDS: tuple[tuple[str, int, int | None], ...] = (
    ("A", 1_001, 15_000),
    ("B", 15_001, 50_000),
    ("C", 50_001, 100_000),
    ("D", 100_001, 250_000),
    ("E", 250_001, 500_000),
    ("F", 500_001, 1_000_000),
    ("G", 1_000_001, 5_000_000),
    ("H", 5_000_001, 25_000_000),
    ("I", 25_000_001, 50_000_000),
    ("J", 50_000_001, None),
)
AMOUNT_COLUMN_LETTERS = tuple(letter for letter, _lo, _hi in AMOUNT_BANDS)

# Cells between the amount block and the transaction-type block, on the printed
# form: [Purchase][Sale][Exch][Cap. Gains][Partial][Date][Notified][A]...
TYPE_CELL_OFFSETS = {"buy": 7, "sell": 6, "exchange": 5}
DATE_CELL_OFFSET = 2
NOTIFIED_CELL_OFFSET = 1

# Header labels that name the type columns (used as corroboration only).
LABEL_PURCHASE = re.compile(r"purch|purc|\bpnd\b|parck|porch", re.I)
LABEL_SALE = re.compile(r"\bsale\b|\bsaie\b|\b5ale\b|\bsal\b", re.I)
LABEL_EXCHANGE = re.compile(r"exch|exck|exoh|axch", re.I)
LETTER_LABEL = re.compile(r"^[A-J]$")
RANGE_LABEL = re.compile(r"^\$?\s*\d[\d,]{2,}$")
DATE_TOKEN = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")

DARK_LEVEL = 140
MARK_EDGE_MARGIN = 6  # ignore the printed rule itself
BASE_MARK_PIXELS = 30  # a checked box at the default scale; empty cells read 0
MIN_MARK_MARGIN = 2.0


def band_for_letter(letter: str) -> tuple[int, int, str] | None:
    """(value_min, value_max, display range) for a printed amount column."""
    for code, low, high in AMOUNT_BANDS:
        if code == letter:
            if high is None:
                return low, 0, f"Over ${low - 1:,}"
            return low, high, f"${low:,} - ${high:,}"
    return None


def band_for_value(value: int) -> str | None:
    """Column letter a header range label belongs to (label is min or max)."""
    matches = [
        code
        for code, low, high in AMOUNT_BANDS
        if value == low or (high is not None and value == high)
    ]
    return matches[0] if len(matches) == 1 else None


@dataclass
class FormGeometry:
    """Named cells of one scanned PTR page."""

    vlines: list[float]
    hlines: list[float]
    header_bottom: float
    scale: float
    cells: list[tuple[float, float]] = field(default_factory=list)
    type_cells: dict[str, tuple[float, float]] = field(default_factory=dict)
    amount_cells: dict[str, tuple[float, float]] = field(default_factory=dict)
    amount_ranges: dict[str, tuple[int, int, str]] = field(default_factory=dict)
    data_rows: list[tuple[float, float]] = field(default_factory=list)
    anchors: dict[str, float] = field(default_factory=dict)

    @property
    def usable_types(self) -> bool:
        return len(self.type_cells) >= 3

    @property
    def usable_amounts(self) -> bool:
        return len(self.amount_cells) >= 8

    def cell_index_for_x(self, x: float) -> int | None:
        for index, (x0, x1) in enumerate(self.cells):
            if x0 <= x < x1:
                return index
        return None


@dataclass
class FormRow:
    """One printed data row: its text plus the marks read from its cells."""

    y0: float
    y1: float
    text: str
    side: str | None = None
    amount_letter: str | None = None
    value_min: int = 0
    value_max: int = 0
    value_range: str = ""

    @property
    def marked(self) -> bool:
        return bool(self.side)


def _to_gray(image) -> np.ndarray:
    return np.asarray(image.convert("L"))


def _rule_lines(
    gray: np.ndarray,
    *,
    axis: int,
    span: tuple[int, int] | None,
    min_ratio: float = 0.55,
) -> list[float]:
    """Positions of dark rule lines along `axis` (0 = horizontal, 1 = vertical)."""
    if axis == 0:
        band = gray[:, span[0] : span[1]] if span else gray
        dark = (band < DARK_LEVEL).sum(axis=1)
        length = band.shape[1]
    else:
        band = gray[span[0] : span[1], :] if span else gray
        dark = (band < DARK_LEVEL).sum(axis=0)
        length = band.shape[0]
    if length == 0:
        return []

    positions = [i for i, count in enumerate(dark) if count > min_ratio * length]
    lines: list[float] = []
    group: list[int] = []
    for pos in positions:
        if group and pos - group[-1] <= 3:
            group.append(pos)
        else:
            if group:
                lines.append(float(np.mean(group)))
            group = [pos]
    if group:
        lines.append(float(np.mean(group)))
    return lines


def _grid(gray: np.ndarray) -> tuple[list[float], list[float]]:
    hlines = _rule_lines(gray, axis=0, span=None, min_ratio=0.55)
    if len(hlines) < 4:
        hlines = _rule_lines(gray, axis=0, span=None, min_ratio=0.4)
    if len(hlines) < 4:
        return hlines, []
    vlines = _rule_lines(gray, axis=1, span=(int(hlines[0]), int(hlines[-1])), min_ratio=0.5)
    if len(vlines) < 5:
        vlines = _rule_lines(gray, axis=1, span=(int(hlines[0]), int(hlines[-1])), min_ratio=0.35)
    return hlines, vlines


def _consensus_a_index(
    letter_votes: list[tuple[int, int]],
    range_votes: list[tuple[int, int]],
) -> int | None:
    """Column index of the "A" cell implied by the printed amount labels.

    `votes` are (letter position 0..9, cell index). Because the ten amount cells
    are consecutive, every label implies where the block starts; the index most
    labels agree on wins. A single letter is enough when a range label backs it
    up, and an explicit "A" letter is enough on its own.
    """
    tally: dict[int, int] = {}
    for letter_pos, cell_index in letter_votes + range_votes:
        tally[cell_index - letter_pos] = tally.get(cell_index - letter_pos, 0) + 1
    if not tally:
        return None
    best_index, best_votes = max(tally.items(), key=lambda kv: kv[1])
    if best_votes >= 2:
        return best_index
    explicit_a = any(pos == 0 and idx == best_index for pos, idx in letter_votes)
    backed_letter = any(idx - pos == best_index for pos, idx in letter_votes) and any(
        idx - pos == best_index for pos, idx in range_votes
    )
    if explicit_a or backed_letter:
        return best_index
    return None


def detect_geometry(
    image,
    boxes: list[TextBox],
    *,
    scale: float = 3.0,
    gray: np.ndarray | None = None,
) -> FormGeometry | None:
    """Recover the named grid of a scanned PTR page, or None when it has none."""
    if not boxes:
        return None
    gray = gray if gray is not None else _to_gray(image)
    hlines, vlines = _grid(gray)
    if len(vlines) < 8 or len(hlines) < 4:
        return None
    cells = list(zip(vlines, vlines[1:]))

    def cell_index_for(x: float) -> int | None:
        return next((i for i, (x0, x1) in enumerate(cells) if x0 <= x < x1), None)

    # --- amount block: anchored on the printed column letters ---------------
    letter_boxes = [
        box
        for box in boxes
        if LETTER_LABEL.match(box.text.strip()) and box.confidence >= 0.35
    ]
    letter_indexes = [
        (cell_index_for(box.x_center), box) for box in letter_boxes
    ]
    letter_votes: list[tuple[int, int]] = [
        (ord(box.text.strip()) - ord("A"), index)
        for index, box in letter_indexes
        if index is not None
    ]

    if letter_boxes:
        letter_y = [b.y_center for b in letter_boxes]
        letter_h = float(np.median([b.height for b in letter_boxes]))
    else:
        # No letter row read: fall back to the range labels' own y band.
        label_boxes = [
            b
            for b in boxes
            if RANGE_LABEL.match(b.text.strip().replace(" ", ""))
            and band_for_value(int(re.sub(r"[^\d]", "", b.text) or 0)) is not None
        ]
        if len(label_boxes) < 3:
            return None
        letter_y = [b.y_center for b in label_boxes]
        letter_h = float(np.median([b.height for b in label_boxes]))
    # The range labels sit one or two rows below the letter row on this form.
    header_y0 = min(letter_y) - 4 * letter_h
    header_y1 = max(letter_y) + 6 * letter_h

    # Range labels ("$15,001") corroborate the same anchor; a garbled one is
    # outvoted rather than fatal.
    range_votes: list[tuple[int, int]] = []
    for box in boxes:
        token = box.text.strip().replace(" ", "")
        if not (header_y0 <= box.y_center <= header_y1) or not RANGE_LABEL.match(token):
            continue
        letter = band_for_value(int(re.sub(r"[^\d]", "", token) or 0))
        index = cell_index_for(box.x_center)
        if letter and index is not None:
            range_votes.append((AMOUNT_COLUMN_LETTERS.index(letter), index))

    a_index = _consensus_a_index(letter_votes, range_votes)
    if a_index is None or a_index < 2 or a_index + len(AMOUNT_COLUMN_LETTERS) > len(cells):
        return None

    amount_cells: dict[str, tuple[float, float]] = {}
    amount_ranges: dict[str, tuple[int, int, str]] = {}
    for offset, letter in enumerate(AMOUNT_COLUMN_LETTERS):
        cell = cells[a_index + offset]
        amount_cells[letter] = cell
        band = band_for_letter(letter)
        if band:
            amount_ranges[letter] = band

    geometry = FormGeometry(
        vlines=vlines,
        hlines=hlines,
        header_bottom=0.0,
        scale=scale,
        cells=cells,
        amount_cells=amount_cells,
        amount_ranges=amount_ranges,
        anchors={"A": cells[a_index][0], "letters_y": float(np.mean(letter_y))},
    )

    # --- data rows (below the header block) ---------------------------------
    letter_band_bottom = max(letter_y) + 20
    header_line = max((line for line in hlines if line <= letter_band_bottom), default=None)
    if header_line is None:
        return None
    geometry.header_bottom = header_line
    min_height = 18 * (scale / 3.0)
    max_height = 160 * (scale / 3.0)
    geometry.data_rows = [
        (y0, y1)
        for y0, y1 in zip(hlines, hlines[1:])
        if y0 >= header_line - 2 and min_height <= (y1 - y0) <= max_height
    ]
    if not geometry.data_rows:
        return None

    # --- transaction-type cells, validated against the row dates ------------
    geometry.type_cells = _type_cells(geometry, boxes)
    return geometry


def _cell_has_date(
    geometry: FormGeometry, boxes: list[TextBox], y0: float, y1: float, index: int
) -> bool:
    x0, x1 = geometry.cells[index]
    return any(
        x0 <= box.x_center < x1 and DATE_TOKEN.search(box.text)
        for box in boxes
        if y0 <= box.y_center < y1
    )


def _type_cells(
    geometry: FormGeometry,
    boxes: list[TextBox],
) -> dict[str, tuple[float, float]]:
    """Type cells at their printed offsets, or {} when the layout differs.

    The offsets are only trusted when the date and notification cells they imply
    actually carry the row dates — that is what distinguishes this form from the
    newer table, where the same offsets point at unrelated columns.
    """
    a_index = geometry.cell_index_for_x(geometry.anchors.get("A", -1) + 1)
    if a_index is None:
        return {}
    date_index = a_index - DATE_CELL_OFFSET
    notified_index = a_index - NOTIFIED_CELL_OFFSET
    if date_index < 0 or a_index - TYPE_CELL_OFFSETS["buy"] < 0:
        return {}

    rows_with_dates = [
        (y0, y1)
        for y0, y1 in geometry.data_rows
        if _cell_has_date(geometry, boxes, y0, y1, date_index)
        or _cell_has_date(geometry, boxes, y0, y1, notified_index)
    ]
    if len(rows_with_dates) < max(1, len(geometry.data_rows) // 2):
        return {}

    return {
        kind: geometry.cells[a_index - offset]
        for kind, offset in TYPE_CELL_OFFSETS.items()
        if a_index - offset >= 0
    }


def _dark_pixels(gray: np.ndarray, cell: tuple[float, float], y0: float, y1: float) -> int:
    x0, x1 = int(cell[0]) + MARK_EDGE_MARGIN, int(cell[1]) - MARK_EDGE_MARGIN
    top, bottom = int(y0) + 5, int(y1) - 5
    if bottom - top < 4 or x1 - x0 < 4:
        return 0
    patch = gray[top:bottom, x0:x1]
    return int((patch < DARK_LEVEL).sum())


def _best_mark(
    gray: np.ndarray,
    cells: dict[str, tuple[float, float]],
    y0: float,
    y1: float,
    *,
    scale: float,
    x_marked: list[float],
    margin: float = MIN_MARK_MARGIN,
) -> str | None:
    """The single clearly-marked cell of a group, or None when it is ambiguous."""
    threshold = BASE_MARK_PIXELS * (scale / 3.0) ** 2
    scores: list[tuple[str, float]] = []
    for name, cell in cells.items():
        pixels = _dark_pixels(gray, cell, y0, y1)
        if any(cell[0] <= x <= cell[1] for x in x_marked):
            pixels = max(pixels, threshold * 1.5)
        scores.append((name, float(pixels)))
    if not scores:
        return None
    scores.sort(key=lambda kv: -kv[1])
    best_name, best_score = scores[0]
    second = scores[1][1] if len(scores) > 1 else 0.0
    if best_score < threshold or best_score < max(second, 1.0) * margin:
        return None
    return best_name


def read_rows(
    image,
    geometry: FormGeometry,
    boxes: list[TextBox],
    *,
    gray: np.ndarray | None = None,
) -> list[FormRow]:
    """Read every printed data row: its text, its side and its amount."""
    gray = gray if gray is not None else _to_gray(image)
    rows: list[FormRow] = []
    for y0, y1 in geometry.data_rows:
        row_boxes = [b for b in boxes if y0 <= b.y_center < y1]
        if not row_boxes:
            continue
        text = " ".join(b.text for b in sorted(row_boxes, key=lambda b: b.x0)).strip()
        if not text:
            continue
        x_marked = [b.x_center for b in row_boxes if b.text.strip().upper() in ("X", "×")]

        side = None
        if geometry.usable_types:
            cell_name = _best_mark(
                gray,
                geometry.type_cells,
                y0,
                y1,
                scale=geometry.scale,
                x_marked=x_marked,
            )
            side = cell_name if cell_name in ("buy", "sell", "exchange") else None

        amount_letter = None
        value_min = value_max = 0
        value_range = ""
        if geometry.usable_amounts:
            letter = _best_mark(
                gray,
                geometry.amount_cells,
                y0,
                y1,
                scale=geometry.scale,
                x_marked=x_marked,
            )
            band = geometry.amount_ranges.get(letter or "")
            if band:
                amount_letter = letter
                value_min, value_max, value_range = band

        rows.append(
            FormRow(
                y0=y0,
                y1=y1,
                text=text,
                side=side,
                amount_letter=amount_letter,
                value_min=value_min,
                value_max=value_max,
                value_range=value_range,
            )
        )
    return rows


def read_page(
    pdf_path, page: PageText, *, scale: float | None = None
) -> tuple[list[FormRow], FormGeometry | None]:
    """Detect the printed grid of one OCR page and read its rows.

    Returns ([], None) for pages that are not a ruled form — the caller then
    falls back to reading the OCR text on its own.
    """
    if page.method != "ocr" or not page.boxes:
        return [], None
    from congress_quant_tracker.config import settings
    from congress_quant_tracker.parsers.pdf_text import _render_page_image

    used_scale = scale or settings.OCR_RENDER_SCALE
    image = _render_page_image(pdf_path, page.page_number - 1, used_scale)
    if image is None:
        return [], None
    gray = _to_gray(image)
    geometry = detect_geometry(image, page.boxes, scale=used_scale, gray=gray)
    if geometry is None:
        return [], None
    return read_rows(image, geometry, page.boxes, gray=gray), geometry


__all__ = [
    "AMOUNT_BANDS",
    "FormGeometry",
    "FormRow",
    "band_for_letter",
    "band_for_value",
    "detect_geometry",
    "read_page",
    "read_rows",
]
