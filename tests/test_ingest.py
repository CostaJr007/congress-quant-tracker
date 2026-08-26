"""Tests for the unified ingestion path (services/ingest.py)."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from congress_quant_tracker.database.models import (
    Base,
    OptionsTrade,
    Politician,
    Trade,
)
from congress_quant_tracker.services.ingest import (
    looks_like_sample,
    normalize_record,
    store_trade,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _pol(session) -> Politician:
    pol = Politician(name="Test Member", chamber="house", party="D", state="CA")
    session.add(pol)
    session.flush()
    return pol


def test_normalize_record_maps_aliases():
    rec, err = normalize_record(
        {
            "member": "Jane Roe",
            "ticker": " nvda ",
            "asset": "NVIDIA CORP",
            "trade_type": "P",
            "tx_date": "06/10/2026",
            "disclosed": "07/01/2026",
            "amount_min": "1,001",
            "amount_max": "15,000",
            "link": "http://x/p.pdf",
        }
    )
    assert err is None
    assert rec["politician_name"] == "Jane Roe"
    assert rec["ticker"] == "NVDA"
    assert rec["transaction_type"] == "buy"
    assert rec["trade_date"] == date(2026, 6, 10)
    assert rec["filing_date"] == date(2026, 7, 1)
    assert rec["value_min"] == 1001
    assert rec["value_max"] == 15000
    assert rec["pdf_url"] == "http://x/p.pdf"


def test_normalize_record_rejects_sample_payloads():
    payloads = (
        {"member": "X", "ticker": "AAPL", "notes": "Sample trade for X",
         "trade_date": "2026-01-05"},
        {"name": "Sample trade for Y", "ticker": "AAPL", "trade_date": "2026-01-05"},
    )
    for payload in payloads:
        rec, err = normalize_record(payload)
        assert rec is None and err == "sample_data_rejected"


def test_normalize_record_rejects_bad_input():
    assert normalize_record({"ticker": "AAPL"})[1] == "missing_politician"
    assert normalize_record({"member": "X", "ticker": "--"})[1] == "missing_or_bad_ticker"
    assert normalize_record({"member": "X", "ticker": "AAPL"})[1] == "missing_or_invalid_trade_date"


def test_normalize_record_swaps_inverted_range():
    rec, err = normalize_record(
        {
            "member": "J",
            "ticker": "MSFT",
            "transaction_type": "S",
            "trade_date": "2026-03-01",
            "value_min": 50_000,
            "value_max": 10_000,
        }
    )
    assert err is None
    assert rec["value_min"] == 10_000
    assert rec["value_max"] == 50_000


def test_normalize_record_never_keeps_trade_after_filing():
    """Impossible ordering gets repaired by the date sanitizer (filing anchor)."""
    rec, err = normalize_record(
        {
            "member": "J",
            "ticker": "MSFT",
            "transaction_type": "S",
            "trade_date": "2026-06-10",
            "filing_date": "2026-07-20",
            "asset_name": "weird 12/31/2027 expiration text",  # future noise ignored
        }
    )
    assert err is None
    assert rec["trade_date"] <= rec["filing_date"]


def test_store_trade_add_merge_dedupe_cycle(session):
    pol = _pol(session)

    def _rec(**over):
        base = {
            "politician_name": pol.name,
            "ticker": "NVDA",
            "asset_name": "NVIDIA",
            "asset_type": "stock",
            "transaction_type": "buy",
            "trade_date": date(2026, 5, 1),
            "filing_date": date(2026, 6, 1),
            "value_min": 50_000,
            "value_max": 100_000,
            "value_range": "$50K-$100K",
            "pdf_url": "http://x/1.pdf",
            "owner": "",
            "sector": "",
            "boost": 0,
            "source": "unit",
        }
        base.update(over)
        return base

    stats = {}
    assert store_trade(session, _rec(), pol, stats) == "added"
    row = session.query(Trade).one()
    assert row.notes == "unit"  # provenance tag

    # same key with MORE information → merged into the existing row
    status = store_trade(
        session,
        _rec(value_max=250_000, owner="SP", pdf_url=""),
        pol,
        stats,
    )
    assert status == "merged"
    # NOTE: no session.refresh() here — it would discard uncommitted mutations
    assert row.value_max == 250_000
    assert row.owner == "SP"
    assert row.pdf_url == "http://x/1.pdf"  # never overwritten by empty

    # identical record → deduped no-op
    assert store_trade(session, _rec(), pol, stats) == "deduped"
    assert session.query(Trade).count() == 1


def test_store_trade_inserts_option_row(session):
    pol = _pol(session)
    rec = {
        "politician_name": pol.name,
        "ticker": "TSLA",
        "asset_name": "Call $140 03/13/2026",
        "asset_type": "option_call",
        "transaction_type": "sell",
        "trade_date": date(2026, 2, 2),
        "filing_date": date(2026, 3, 1),
        "value_min": 5_000,
        "value_max": 25_000,
        "value_range": "",
        "pdf_url": "",
        "owner": "",
        "sector": "",
        "boost": 0,
        "source": "unit",
    }
    assert store_trade(session, rec, pol) == "added"
    opt = session.query(OptionsTrade).one()
    assert opt.option_type == "call"
    assert opt.strike == 140.0


def test_looks_like_sample():
    assert looks_like_sample({"member": "Sample trade for Nancy Pelosi"})
    assert not looks_like_sample({"member": "Nancy Pelosi"})
