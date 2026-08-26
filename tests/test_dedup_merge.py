"""Tests for duplicate-trade merging in DataUpdateService (no network)."""

from datetime import date

from congress_quant_tracker.database.models import Trade
from congress_quant_tracker.services.data_updater import DataUpdateService


def _trade(**kwargs) -> Trade:
    base = dict(
        politician_id=1,
        ticker="NVDA",
        asset_name=None,
        asset_type="stock",
        transaction_type="buy",
        trade_date=date(2026, 5, 1),
        filing_date=date(2026, 6, 1),
        value_min=50_000,
        value_max=100_000,
        value_range="$50K-$100K",
        pdf_url="http://x/p.pdf",
        owner="SP",
        sector="Technology",
    )
    base.update(kwargs)
    return Trade(**base)


def _svc() -> DataUpdateService:
    # Skip __init__ (engine/DB setup not needed for the pure merge helper)
    return DataUpdateService.__new__(DataUpdateService)


def test_merge_fills_missing_fields_and_widens_range():
    existing = _trade(
        filing_date=None, pdf_url="", owner="", sector="", value_min=75_000
    )
    changed = _svc()._merge_into_existing(
        existing,
        {
            "filing_date": "2026-06-15",
            "pdf_url": "http://x/new.pdf",
            "owner": "JT",
            "sector": "Tech",
            "amount_min": 10_000,
            "amount_max": 150_000,
        },
    )
    assert changed is True
    assert str(existing.filing_date) == "2026-06-15"
    assert existing.pdf_url == "http://x/new.pdf"
    assert existing.owner == "JT"
    assert existing.sector == "Tech"
    assert existing.value_min == 10_000  # widened down
    assert existing.value_max == 150_000  # widened up


def test_merge_never_shrinks_or_overwrites():
    original = _trade()
    before = (original.value_min, original.value_max, original.pdf_url)
    changed = _svc()._merge_into_existing(
        original,
        {
            "pdf_url": "http://x/other.pdf",
            "amount_min": 90_000,  # higher than current min → ignored
            "amount_max": 20_000,  # lower than current max → ignored
        },
    )
    assert changed is False
    assert (original.value_min, original.value_max, original.pdf_url) == before


def test_merge_reports_noop_for_identical_record():
    existing = _trade()
    changed = _svc()._merge_into_existing(existing, {"owner": ""})
    assert changed is False
