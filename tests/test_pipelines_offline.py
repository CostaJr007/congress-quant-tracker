"""Offline pipeline tests: House/Senate/DataUpdateService store paths (no network)."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import Base, Politician, Trade


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _no_yf(monkeypatch):
    monkeypatch.setattr(settings, "NO_YF", True)
    monkeypatch.setattr(settings, "MARKET_DATA_ENABLED", False)


def _filing():
    return {"filing_date": date(2026, 7, 1), "pdf_url": "http://x/f.pdf",
            "state": "CA", "district": "11"}


def test_house_pipeline_store_trade_offline(session, monkeypatch):
    from congress_quant_tracker.services.official_pipeline import OfficialHousePipeline

    pipe = OfficialHousePipeline.__new__(OfficialHousePipeline)
    pipe.members = {}
    monkeypatch.setattr(
        "congress_quant_tracker.services.official_pipeline.download_photo_if_missing",
        lambda *a, **k: False,
    )
    stats: dict = {}
    trade = {
        "ticker": "NVDA", "asset_name": "NVIDIA",
        "transaction_type": "buy", "trade_date": "2026-06-10",
        "filing_date": "2026-07-01", "value_min": 1000, "value_max": 15000,
    }
    assert pipe._store_trade(session, trade, "Nancy Pelosi",
                             filing=_filing(), pol_info={}, stats=stats) is True
    # duplicate same-day/same-side merges, not a new row (widen range -> merged)
    wider = dict(trade, value_max=25000)
    assert pipe._store_trade(session, wider, "Nancy Pelosi",
                             filing=_filing(), pol_info={}, stats=stats) is False
    assert session.query(Trade).count() == 1
    assert stats.get("trades_merged") == 1
    row = session.query(Trade).one()
    assert row.notes == "house_official"


def test_house_pipeline_rejects_sample(session):
    from congress_quant_tracker.services.official_pipeline import OfficialHousePipeline

    pipe = OfficialHousePipeline.__new__(OfficialHousePipeline)
    pipe.members = {}
    stats: dict = {}
    bad = {"ticker": "AAPL", "trade_date": "2026-06-10",
           "politician_name": "Sample trade for X"}
    assert pipe._store_trade(session, bad, "Sample trade for X",
                             filing=_filing(), pol_info={}, stats=stats) is False
    assert stats.get("samples_rejected") == 1
    assert session.query(Trade).count() == 0


def test_senate_pipeline_store_offline(session):
    from congress_quant_tracker.services.senate_pipeline import SenatePipeline

    pipe = SenatePipeline.__new__(SenatePipeline)
    pipe.members = {}
    stats: dict = {}
    trade = {"politician_name": "Chuck Schumer", "ticker": "MSFT",
             "transaction_type": "sell", "trade_date": date(2026, 6, 15),
             "filing_date": date(2026, 7, 1), "value_min": 5000,
             "value_max": 25000, "source": "senate"}
    assert pipe._store(session, trade, stats) is True
    assert pipe._store(session, trade, stats) is False  # deduped
    pol = session.query(Politician).one()
    assert pol.chamber == "senate"


def test_data_update_service_store_and_score(session):
    from congress_quant_tracker.services.data_updater import DataUpdateService

    svc = DataUpdateService.__new__(DataUpdateService)
    stats: dict = {}
    svc._store_trade(session, {
        "member": "Ro Khanna", "ticker": "AAPL",
        "trade_date": "2026-01-01", "filing_date": "2026-03-10",
        "transaction_type": "buy", "amount_min": 1000, "amount_max": 500_000,
        "chamber": "house", "party": "D", "state": "CA",
    }, stats)
    assert stats["trades_added"] == 1
    # duplicate widens into merged, never a second row
    svc._store_trade(session, {
        "member": "Ro Khanna", "ticker": "AAPL",
        "trade_date": "2026-01-01", "filing_date": "2026-03-10",
        "transaction_type": "buy", "amount_min": 1000, "amount_max": 500_000,
    }, stats)
    assert session.query(Trade).count() == 1

    svc._score_all_trades(session, stats)
    row = session.query(Trade).one()
    assert row.tag in ("routine", "noteworthy", "suspicious", "high_alert")
    assert row.score >= 0
    svc._update_politician_stats(session)
    assert session.query(Politician).one().total_trades == 1


def test_scorer_contrarian_uses_market_fallback(monkeypatch):
    from congress_quant_tracker.scoring.scorer import TradeScorer

    monkeypatch.setattr(settings, "NO_YF", False)
    bars = [
        {"date": "2026-05-01", "close": 100.0},
        {"date": "2026-05-02", "close": 95.0},
        {"date": "2026-05-03", "close": 90.0},
        {"date": "2026-05-04", "close": 85.0},
        {"date": "2026-05-05", "close": 80.0},  # -20% drop
    ]
    monkeypatch.setattr(
        "congress_quant_tracker.enrichers.market_data.get_history",
        lambda *a, **k: bars,
    )
    pts, reason = TradeScorer().score_contrarian("NVDA", "2026-06-10", "buy")
    assert pts == 10
    assert "Contrarian" in reason


def test_terminal_market_quote_and_state():
    from congress_quant_tracker.enrichers.terminal_market import (
        _market_state, _quote_from_bars,
    )
    q = _quote_from_bars([
        {"date": "2026-06-10", "close": 100.0, "open": 99.0,
         "high": 101.0, "low": 98.0, "volume": 10},
        {"date": "2026-06-11", "close": 110.0, "open": 109.0,
         "high": 111.0, "low": 108.0, "volume": 12},
    ])
    assert q["chgPct"] == 10.0
    assert _quote_from_bars([]) is None
    assert _market_state("America/New_York") in (
        "OPEN", "CLOSED", "PRE", "UNKNOWN")


def test_senate_auto_skips_efd_when_blocked(monkeypatch, tmp_path):
    """Akamai 403 -> auto goes straight to CongressInvests, no browser."""
    from congress_quant_tracker.services.senate_pipeline import SenatePipeline

    db_url = f"sqlite:///{(tmp_path / 'sen.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)

    monkeypatch.setattr(
        "congress_quant_tracker.services.senate_pipeline.probe_efd_access",
        lambda *a, **k: {"reachable": False, "blocked_by_akamai": True, "status_code": 403},
    )
    fake = [{
        "politician_name": "Jane Senate", "ticker": "MSFT",
        "transaction_type": "sell", "trade_date": date(2026, 6, 15),
        "filing_date": date(2026, 7, 1), "value_min": 1, "value_max": 2,
    }]
    monkeypatch.setattr(
        "congress_quant_tracker.services.senate_pipeline.fetch_senate_via_congressinvests_sync",
        lambda *a, **k: fake,
    )
    stats = SenatePipeline().run(strategy="auto", max_pages=1)
    assert stats["strategy_used"] == "congressinvests"
    assert stats["trades_added"] == 1
    assert stats["trades_fetched"] == 1


def test_senate_congressinvests_outage_does_not_crash(monkeypatch, tmp_path):
    """Total API outage -> run completes with 0 added and error counted."""
    from congress_quant_tracker.services.senate_pipeline import SenatePipeline

    db_url = f"sqlite:///{(tmp_path / 'sen2.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(
        "congress_quant_tracker.services.senate_pipeline.probe_efd_access",
        lambda *a, **k: {"reachable": False, "blocked_by_akamai": True},
    )

    def _boom(*a, **k):
        raise RuntimeError("API down")

    monkeypatch.setattr(
        "congress_quant_tracker.services.senate_pipeline.fetch_senate_via_congressinvests_sync",
        _boom,
    )
    stats = SenatePipeline().run(strategy="congressinvests", max_pages=1)
    assert stats["strategy_used"] == "congressinvests"
    assert stats["trades_added"] == 0
    assert stats.get("errors", 0) >= 1


def test_fetch_senate_retries_page_then_continues(monkeypatch):
    """Transient 429 on page 1 -> retry succeeds; empty page 2 stops."""
    import asyncio

    import congress_quant_tracker.fetchers.senate_official as sen
    import congress_quant_tracker.fetchers.congress_invests as ci

    calls = {"n": 0}
    good = {
        "member": "Jane Senate", "trade_type": "S", "ticker": "MSFT",
        "asset": "Microsoft", "tx_date": "2026-06-15", "disclosed": "2026-07-01",
        "amount": "$1-$2", "link": "", "owner": "", "chamber": "senate",
    }

    async def fake_fetch_trades(chamber="senate", limit=200, offset=0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("429 throttled")
        if offset == 0:
            return [good]
        return []

    monkeypatch.setattr(ci, "fetch_trades", fake_fetch_trades)
    monkeypatch.setattr(ci, "_load_members_db", lambda: {})
    trades = asyncio.run(sen.fetch_senate_via_congressinvests(max_pages=2))
    assert len(trades) == 1
    assert trades[0]["ticker"] == "MSFT"
    assert calls["n"] >= 2
