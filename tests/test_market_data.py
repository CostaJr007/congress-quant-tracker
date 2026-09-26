"""Unit tests for market_data helpers (offline, mocked yfinance/providers)."""

from datetime import date

import pytest

from congress_quant_tracker.config import settings
from congress_quant_tracker.enrichers import market_data as md


@pytest.fixture(autouse=True)
def _enable_market(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_ENABLED", True)
    monkeypatch.setattr(settings, "NO_YF", False)
    md._mem_hist.clear()
    md._mem_quote.clear()
    md._last_source.clear()
    yield
    md._mem_hist.clear()
    md._mem_quote.clear()


def _bars(start_iso="2026-05-01", closes=(100.0, 102.0, 110.0)):
    from datetime import date as _d, timedelta
    base = _d.fromisoformat(start_iso)
    return [
        {
            "date": (base + timedelta(days=i)).isoformat(),
            "close": c, "open": c, "high": c, "low": c, "volume": 1000,
        }
        for i, c in enumerate(closes)
    ]


def test_mid_value_and_estimate_shares():
    assert md.mid_value(1000, 15000) == 8000.0
    assert md.mid_value(0, 15000) == 15000.0
    assert md.mid_value(None, None) is None
    assert md.estimate_shares(None, None, 100) is None
    assert md.estimate_shares(1000, 2000, 0) is None
    s = md.estimate_shares(1000, 2000, 100.0)
    assert s["shares_est"] == pytest.approx(15.0)
    assert s["value_mid"] == 1500.0


def test_get_price_on_or_after(monkeypatch):
    bars = _bars("2026-06-10", (100.0, 101.0))
    monkeypatch.setattr(md, "get_history", lambda *a, **k: bars)
    assert md.get_price_on_or_after("NVDA", date(2026, 6, 10)) == {"date": "2026-06-10", "price": 100.0}
    assert md.get_price_on_or_after("NVDA", date(2026, 6, 9))["price"] == 100.0
    monkeypatch.setattr(md, "get_history", lambda *a, **k: [])
    assert md.get_price_on_or_after("NVDA", date(2026, 6, 10)) is None


def test_trade_performance_buy_and_sell(monkeypatch):
    bars = _bars("2026-06-10", (100.0, 110.0))
    monkeypatch.setattr(md, "get_history", lambda *a, **k: bars)
    md._last_source["NVDA"] = "yfinance"
    perf = md.trade_performance("nvda", "2026-06-10", value_min=1000, value_max=2000,
                                transaction_type="buy", chart_points=0)
    assert perf["price_at_trade"] == 100.0
    assert perf["price_now"] == 110.0
    assert perf["change_pct"] == pytest.approx(10.0)
    assert perf["direction"] == "up"
    assert perf["pnl_mid_est"] == pytest.approx(150.0)  # 15 shares * +10
    assert perf["source"] == "yfinance"

    perf_s = md.trade_performance("NVDA", "2026-06-10", value_min=1000, value_max=2000,
                                  transaction_type="sell", chart_points=0)
    assert perf_s["pnl_mid_est"] == pytest.approx(-150.0)


def test_trade_performance_errors():
    assert md.trade_performance("NVDA", "not-a-date")["error"] == "bad_trade_date"
    assert md.trade_performance("--", "2026-06-10")["error"] == "no_price_data"


def test_trade_performance_disabled(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_ENABLED", False)
    out = md.trade_performance("NVDA", "2026-06-10")
    assert out["error"] == "market_data_disabled"


def test_enrich_trades_batch_limits_tickers(monkeypatch):
    calls = []

    def fake_perf(ticker, td, **kw):
        calls.append(ticker)
        return {"price_now": 10.0, "change_pct": 1.0,
                "shares": {"shares_est": 5.0}, "pnl_mid_est": 50.0}

    monkeypatch.setattr(md, "trade_performance", fake_perf)
    trades = [
        {"ticker": "AAPL", "trade_date": "2026-06-10", "transaction_type": "buy"},
        {"ticker": "MSFT", "trade_date": "2026-06-10", "transaction_type": "buy"},
        {"ticker": "NVDA", "trade_date": "2026-06-10", "transaction_type": "buy"},
    ]
    out = md.enrich_trades_batch(trades, max_unique_tickers=2)
    assert out[0]["market"] is not None
    assert out[1]["market"] is not None
    assert out[2]["market"] is None  # over the cap
    assert calls == ["AAPL", "MSFT"]


def test_fetch_history_uses_stooq_fallback(monkeypatch):
    # yfinance leg empty -> fallback providers supply bars
    monkeypatch.setattr(md, "_fetch_yf_history", lambda t, s, e: [])
    fake_bars = _bars("2026-06-10", (50.0, 51.0))
    monkeypatch.setattr(
        "congress_quant_tracker.enrichers.market_providers.fetch_history_with_fallback",
        lambda *a, **k: (fake_bars, "stooq"),
    )
    bars = md._fetch_history("NVDA", date(2026, 6, 10), date(2026, 6, 12))
    assert bars == fake_bars
    assert md._last_source["NVDA"] == "stooq"


def test_fetch_history_yf_primary_wins(monkeypatch):
    primary = _bars("2026-06-10", (9.0,))
    monkeypatch.setattr(md, "_fetch_yf_history", lambda t, s, e: primary)

    def _boom(*a, **k):
        raise AssertionError("fallback must not be called")

    monkeypatch.setattr(
        "congress_quant_tracker.enrichers.market_providers.fetch_history_with_fallback",
        _boom,
    )
    assert md._fetch_history("AAPL", date(2026, 6, 10), date(2026, 6, 11)) == primary
