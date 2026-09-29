"""Tests for House PTR row parsing across the layouts real filings use."""

from datetime import date

from congress_quant_tracker.parsers.ptr_rows import (
    dedupe_key,
    logical_rows,
    parse_ptr_date,
    parse_row,
    parse_rows,
)

MODERN_PTR = """Filing ID #20034963
P T R
Name: Hon. Jared Moskowitz
DC Applied Materials, Inc. - Common P 06/18/2026 06/30/2026 $1,001 - $15,000
Stock (AMAT) [ST]
F S: New
S O: Morgan Stanley Active Assets (5)
DC HCA Healthcare, Inc. Common Stock P 06/17/2026 06/30/2026 $1,001 - $15,000
(HCA) [ST]
"""

# Amount split across lines, ticker only on the continuation line
SPLIT_AMOUNT_PTR = """Name: Hon. Sam T. Liccardo
NVIDIA Corporation - Common Stock S (partial) 07/21/2026 07/22/2026 $15,001 -
(NVDA) [ST] $50,000
F S: New
S O: Schwab > Schwab Roth IRA -- Sam Liccardo
D: 100 shares
"""

# No ticker anywhere: private fund, government/municipal security, commodity
NO_TICKER_PTR = """Name: Hon. Sheri Biggs
SP Oaktree Strategic Credit Fund Class S P 06/30/2026 07/09/2026 $1,001 - $15,000
[OT]
F S: New
DC U.S. Treasury Note 4.25% 2032 P 05/02/2026 05/20/2026 $15,001 - $50,000
[GS]
"""

OPTION_PTR = """Name: Hon. Tom Suozzi
SP Bloom Energy Corporation Class A P 07/24/2026 07/24/2026 $1,000,001 -
Common Stock (BE) [OP] $5,000,000
F S: New
D: Purchased 100 call options with a strike price of $100 and an expiration date of 01/15/2027.
"""

# Scanned form: side and amount come from the printed grid, not from the text
SCANNED_ROW = "DC AMRIZE LTD CMN X 08/07/26 09/01/26 X"


def test_parse_ptr_date_accepts_two_digit_years():
    assert parse_ptr_date("08/07/26") == date(2026, 8, 7)
    assert parse_ptr_date("08/07/2026") == date(2026, 8, 7)
    assert parse_ptr_date("O8/O7/26") == date(2026, 8, 7)
    assert parse_ptr_date("") is None
    assert parse_ptr_date("not a date") is None


def test_logical_rows_keeps_continuation_lines_with_their_row():
    rows = logical_rows(MODERN_PTR)
    assert len(rows) == 2
    assert rows[0].startswith("DC Applied Materials")
    assert "(AMAT) [ST]" in rows[0]
    assert rows[1].startswith("DC HCA Healthcare")


def test_modern_layout_row():
    trade = parse_row(logical_rows(MODERN_PTR)[0])
    assert trade["ticker"] == "AMAT"
    assert trade["owner"] == "DC"
    assert trade["asset_type"] == "stock"
    assert trade["asset_code"] == "ST"
    assert trade["transaction_type"] == "buy"
    assert trade["trade_date"] == "2026-06-18"
    assert trade["filing_date"] == "2026-06-30"
    assert (trade["value_min"], trade["value_max"]) == (1_001, 15_000)
    assert trade["asset_name"].startswith("Applied Materials")


def test_split_amount_and_trailing_ticker():
    trades = parse_rows(SPLIT_AMOUNT_PTR)
    assert len(trades) == 1
    trade = trades[0]
    assert trade["ticker"] == "NVDA"
    assert trade["transaction_type"] == "sell"
    assert trade["value_range"] == "$15,001 - $50,000"
    assert trade["trade_date"] == "2026-07-21"
    # the equity's own price text ("100 shares") must not become the amount
    assert trade["value_min"] == 15_001


def test_rows_without_ticker_are_still_read():
    trades = parse_rows(NO_TICKER_PTR)
    assert len(trades) == 2
    fund, treasury = trades
    assert fund["ticker"] == ""
    assert fund["asset_type"] == "other"
    assert "Oaktree" in fund["asset_name"]
    assert treasury["asset_type"] == "bond"
    assert "Treasury" in treasury["asset_name"]
    assert treasury["value_max"] == 50_000


def test_option_rows_carry_type_strike_and_expiry():
    trades = parse_rows(OPTION_PTR)
    assert len(trades) == 1
    trade = trades[0]
    assert trade["asset_type"] == "option_call"
    assert trade["asset_code"] == "OP"
    assert (trade["value_min"], trade["value_max"]) == (1_000_001, 5_000_000)
    # description text is kept so strike/expiry extraction can use it
    assert "call options" in trade["asset_name"]

    from congress_quant_tracker.fetchers.congress_invests import parse_option_details

    details = parse_option_details(trade["asset_name"], trade["asset_type"])
    assert details["option_type"] == "call"
    assert details["strike"] == 100.0
    assert details["expiration_date"] == date(2027, 1, 15)


def test_put_description_wins_over_option_code():
    row = (
        "SP Acme Corp P 04/28/2026 04/28/2026 $1,001 - $15,000\n"
        "Common Stock (ACME) [OP]\n"
        "D: 10 puts at $11.80\n"
    )
    trade = parse_row(logical_rows(row)[0])
    assert trade["asset_type"] == "option_put"
    details_trade = trade
    from congress_quant_tracker.fetchers.congress_invests import parse_option_details

    details = parse_option_details(details_trade["asset_name"], trade["asset_type"])
    # "$11.80" is a premium, not the strike: better no strike than a wrong one
    assert details["strike"] is None


def test_scanned_row_uses_grid_side_and_amount():
    trade = parse_row(
        SCANNED_ROW,
        side="sell",
        value_min=1_001,
        value_max=15_000,
        value_range="$1,001 - $15,000",
        amount_column="A",
    )
    assert trade["transaction_type"] == "sell"
    assert trade["ticker"] == ""
    assert trade["owner"] == "DC"
    assert trade["value_range"] == "$1,001 - $15,000"
    assert trade["amount_column"] == "A"
    assert trade["asset_name"] == "AMRIZE LTD CMN"
    assert trade["trade_date"] == "2026-08-07"


def test_text_amount_beats_grid_amount_when_both_exist():
    row = "DC Apple Inc (AAPL) [ST] P 06/10/2026 06/30/2026 $15,001 - $50,000"
    trade = parse_row(row, side="buy", value_min=1_001, value_max=15_000)
    assert (trade["value_min"], trade["value_max"]) == (15_001, 50_000)


def test_dedupe_key_matches_views_of_one_trade():
    text_view = {"ticker": "NVDA", "trade_date": "2026-07-21", "transaction_type": "sell"}
    other_view = {"ticker": "nvda", "trade_date": "2026-07-21", "transaction_type": "sell"}
    assert dedupe_key(text_view) == dedupe_key(other_view)
    tickerless = {"ticker": "", "asset_name": "AMRIZE LTD CMN",
                  "trade_date": "2026-08-07", "transaction_type": "buy"}
    assert dedupe_key(tickerless)[0] == "AMRIZE LTD CMN"
