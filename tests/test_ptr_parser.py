"""Tests for House PTR text parsing (regex path) and Groq output coercion."""

from congress_quant_tracker.parsers.house_ptr_parser import (
    _coerce_groq_trade,
    _parse_amount,
    extract_member_name,
    merge_trades,
    parse_trades_regex,
)

PTR_TEXT = """Periodic Transaction Report
Name: Hon. Nancy Pelosi
State: CA  District: 11
SP Apple Inc (AAPL) Purchase 06/10/2026 07/01/2026 $1,001 - $15,000
Microsoft Corporation (MSFT) S 06/15/2026 07/01/2026 $100,001 - $250,000
NVIDIA Corp (NVDA) [P] P 06/20/2026 07/02/2026 $15,001 - $50,000
"""


def test_extract_member_name():
    assert extract_member_name(PTR_TEXT) == "Hon. Nancy Pelosi".replace("Hon. ", "")


def test_parse_trades_regex_extracts_core_rows():
    trades = parse_trades_regex(PTR_TEXT)
    by_ticker = {t["ticker"]: t for t in trades}

    aapl = by_ticker.get("AAPL")
    assert aapl, "AAPL row missing"
    assert aapl["transaction_type"] == "buy"
    assert aapl["trade_date"] == "2026-06-10"
    assert aapl["filing_date"] == "2026-07-01"
    assert aapl["value_min"] == 1_001
    assert aapl["value_max"] == 15_000
    assert aapl["owner"] == "SP"

    msft = by_ticker.get("MSFT")
    assert msft and msft["transaction_type"] == "sell"

    # dedup: no repeated keys
    keys = {(t["ticker"], t["trade_date"], t["transaction_type"]) for t in trades}
    assert len(keys) == len(trades)


def test_parse_amount_range_and_single():
    lo, hi, rng = _parse_amount("$1,001 - $15,000")
    assert (lo, hi) == (1_001, 15_000)
    assert "$1,001" in rng
    assert _parse_amount("$5,000")[0] == 5_000
    assert _parse_amount("") == (0, 0, "")


def test_merge_trades_prefers_primary_and_fills_gaps():
    primary = [
        {"ticker": "AAPL", "trade_date": "2026-06-10", "transaction_type": "buy",
         "value_max": 15000, "asset_name": "", "owner": "SP"}
    ]
    secondary = [
        {"ticker": "AAPL", "trade_date": "2026-06-10", "transaction_type": "buy",
         "value_max": 15000, "asset_name": "Apple Inc", "owner": None},
        {"ticker": "MSFT", "trade_date": "2026-06-15", "transaction_type": "sell",
         "value_max": 250000},
    ]
    merged = merge_trades(primary, secondary)
    assert len(merged) == 2
    aapl = next(t for t in merged if t["ticker"] == "AAPL")
    assert aapl["owner"] == "SP"          # primary kept
    assert aapl["asset_name"] == "Apple Inc"  # gap filled from secondary


def test_coerce_groq_trade_validates_everything():
    good = _coerce_groq_trade(
        {
            "ticker": "nvda",
            "asset_name": "NVIDIA  Corp",
            "asset_type": "OPTION_CALL",
            "transaction_type": "purchase",
            "trade_date": "2026-06-10",
            "filing_date": "07/01/2026",
            "value_min": 2000,
            "value_max": 1000,
            "owner": "sp",
        }
    )
    assert good is not None
    assert good["ticker"] == "NVDA"
    assert good["transaction_type"] == "buy"
    assert good["asset_type"] == "option_call"
    assert (good["value_min"], good["value_max"]) == (1000, 2000)  # swapped
    assert good["owner"] == "SP"

    bad_rows = [
        {"ticker": "TOOLONGTICKER", "trade_date": "2026-06-10"},
        {"ticker": "AAPL"},  # no date
        {"ticker": "AAPL", "trade_date": "not-a-date"},
        {"ticker": "", "trade_date": "2026-06-10"},
    ]
    for row in bad_rows:
        assert _coerce_groq_trade(row) is None
