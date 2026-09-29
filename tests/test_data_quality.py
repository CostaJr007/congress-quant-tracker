"""Data-quality guards: absurd dates, unknown amounts, option evidence."""

from datetime import date, timedelta

from congress_quant_tracker.fetchers.congress_invests import (
    _page_older_than,
    classify_asset,
    parse_option_details,
)
from congress_quant_tracker.parsers.ptr_rows import parse_ptr_date, parse_row
from congress_quant_tracker.services.ingest import normalize_record
from congress_quant_tracker.services.screener import resolve_since_days


def test_parse_ptr_date_rejects_absurd_years():
    assert parse_ptr_date("07/14/2608") is None
    assert parse_ptr_date("07/14/1999") is None
    assert parse_ptr_date("08/07/26") == date(2026, 8, 7)


def test_future_trade_is_rejected_not_stored():
    rec, reason = normalize_record(
        {
            "politician_name": "Test Member",
            "ticker": "AAPL",
            "asset_name": "Apple Inc.",
            "transaction_type": "buy",
            "trade_date": "2608-07-14",
            "filing_date": "2608-07-14",
        }
    )
    assert rec is None and reason == "bad_date"


def test_future_filing_is_nulled_not_trusted():
    rec, reason = normalize_record(
        {
            "politician_name": "Test Member",
            "ticker": "AAPL",
            "asset_name": "Apple Inc.",
            "transaction_type": "buy",
            "trade_date": "2026-07-14",
            "filing_date": "2608-07-14",
        }
    )
    assert reason is None
    assert rec["filing_date"] is None


def test_unknown_amount_is_null_not_zero():
    rec, _ = normalize_record(
        {
            "politician_name": "Test Member",
            "ticker": "AAPL",
            "asset_name": "Apple Inc.",
            "transaction_type": "buy",
            "trade_date": "2026-07-14",
        }
    )
    assert rec["value_min"] is None and rec["value_max"] is None


def test_op_code_without_keywords_is_not_an_option():
    trade = parse_row(
        "DC CrowdStrike Holdings Inc Class A Common Stock (CRWD) [OP] "
        "P 07/15/2026 07/20/2026 $1,001 - $15,000"
    )
    assert trade is not None
    assert not trade["asset_type"].startswith("option")


def test_muni_shorthand_is_bond_but_marvell_is_stock():
    assert classify_asset("HamsCtyTXCulturalSrARVBE/R/", "") == "bond"
    assert classify_asset("EnergyNorthwest WAElec RV BE/R/", "") == "bond"
    assert classify_asset("MARVELL TECHNOLOGY INC CMN", "") == "stock"
    assert classify_asset("CrowdStrike Holdings Inc Class A Common Stock", "") == "stock"
    assert classify_asset("FLEXLTDCMN", "") == "stock"
    assert classify_asset("CALL/MSFT FLEX EURO PM485 EXP 08/07/2026", "") == "option_call"


def test_flex_option_strike_and_glued_expiry():
    details = parse_option_details(
        "CALL/MSFT FLEX EURO PM485 EXP 08/07/2026", "option_call"
    )
    assert details["strike"] == 485.0
    details = parse_option_details("PUT/XSP @710EXP10/16/2026", "option_put")
    assert details["strike"] == 710.0
    assert details["expiration_date"] == date(2026, 10, 16)


def test_page_older_than_stops_pager():
    since = date(2026, 1, 1)
    assert _page_older_than(
        [{"filing_date": "2025-01-01", "trade_date": "2024-12-01"}], since
    )
    assert not _page_older_than(
        [{"filing_date": "2026-06-01", "trade_date": "2024-12-01"}], since
    )
    assert not _page_older_than([{"member": "x"}], since)


def test_screener_modes(session=None):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from congress_quant_tracker.database.models import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sess = sessionmaker(bind=engine)()

    days, mode = resolve_since_days(sess, None, "house_last_run", "house_last_filing")
    assert mode == "first-run" and days == 730

    days, mode = resolve_since_days(sess, 5000, "house_last_run", "house_last_filing")
    assert mode == "explicit" and days == 730

    from congress_quant_tracker.database.models import set_pipeline_state

    set_pipeline_state(sess, "house_last_filing", "2026-09-01")
    sess.commit()
    days, mode = resolve_since_days(sess, None, "house_last_run", "house_last_filing")
    assert mode == "incremental"
    expected = (date.today() - (date(2026, 9, 1) - timedelta(days=7))).days
    assert days == expected
