"""Unit tests for market_providers fallback chain (offline, mocked HTTP)."""

from datetime import date

from congress_quant_tracker.enrichers import market_providers as mp


class _Resp:
    def __init__(self, text="", status=200, payload=None):
        self.text = text
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


def test_to_stooq_symbol():
    assert mp.to_stooq_symbol("NVDA") == "nvda.us"
    assert mp.to_stooq_symbol("aapl") == "aapl.us"
    assert mp.to_stooq_symbol("^GSPC") == "^spx"
    assert mp.to_stooq_symbol("GC=F") == "xauusd"
    assert mp.to_stooq_symbol("BRK.B") == "brk.b"
    assert mp.to_stooq_symbol("") == ""


def test_fetch_stooq_history_parses_csv(monkeypatch):
    csv_text = (
        "Date,Open,High,Low,Close,Volume\n"
        "2026-06-10,100,101,99,100.5,1000\n"
        "2026-06-11,101,102,100,N/A,1100\n"
        "2026-06-12,102,103,101,105,1200\n"
    )
    monkeypatch.setattr(mp, "requests", type("R", (), {
        "get": staticmethod(lambda *a, **k: _Resp(text=csv_text)),
    }))
    bars = mp.fetch_stooq_history("NVDA", date(2026, 6, 10), date(2026, 6, 12))
    assert [b["date"] for b in bars] == ["2026-06-10", "2026-06-12"]
    assert bars[0]["close"] == 100.5


def test_fetch_stooq_history_bad_status(monkeypatch):
    monkeypatch.setattr(mp, "requests", type("R", (), {
        "get": staticmethod(lambda *a, **k: _Resp(text="Exceeded daily limit", status=200)),
    }))
    assert mp.fetch_stooq_history("NVDA", date(2026, 6, 10), date(2026, 6, 12)) == []


def test_fetch_yahoo_direct_parses_chart(monkeypatch):
    payload = {
        "chart": {"result": [{
            "timestamp": [1717977600, 1718064000],  # 2024-06-10/11 UTC
            "indicators": {
                "quote": [{"open": [100.0, 101.0], "high": [101.0, 102.0],
                           "low": [99.0, 100.0], "close": [100.5, 101.5],
                           "volume": [1000, 1100]}],
                "adjclose": [{"adjclose": [100.5, 101.5]}],
            },
        }], "error": None}
    }
    monkeypatch.setattr(mp, "requests", type("R", (), {
        "get": staticmethod(lambda *a, **k: _Resp(text="{}", payload=payload)),
    }))
    bars = mp.fetch_yahoo_direct_history("NVDA", date(2024, 6, 10), date(2024, 6, 11))
    assert len(bars) == 2
    assert bars[0]["close"] == 100.5
    assert bars[0]["volume"] == 1000


def test_fetch_history_with_fallback_order(monkeypatch):
    yf_bars = [{"date": "2026-06-10", "close": 1.0, "open": 1.0,
                "high": 1.0, "low": 1.0, "volume": 1}]
    bars, src = mp.fetch_history_with_fallback(
        "NVDA", date(2026, 6, 10), date(2026, 6, 11),
        yf_fetcher=lambda t, s, e: yf_bars,
    )
    assert (bars, src) == (yf_bars, "yfinance")

    monkeypatch.setattr(mp, "fetch_yahoo_direct_history",
                        lambda *a, **k: yf_bars)
    monkeypatch.setattr(mp, "fetch_stooq_history", lambda *a, **k: [])
    bars, src = mp.fetch_history_with_fallback(
        "NVDA", date(2026, 6, 10), date(2026, 6, 11), yf_fetcher=lambda *a, **k: [])
    assert src == "yahoo_direct"

    monkeypatch.setattr(mp, "fetch_yahoo_direct_history", lambda *a, **k: [])
    monkeypatch.setattr(mp, "fetch_stooq_history", lambda *a, **k: yf_bars)
    bars, src = mp.fetch_history_with_fallback(
        "NVDA", date(2026, 6, 10), date(2026, 6, 11), yf_fetcher=lambda *a, **k: [])
    assert src == "stooq"

    monkeypatch.setattr(mp, "fetch_stooq_history", lambda *a, **k: [])
    bars, src = mp.fetch_history_with_fallback(
        "NVDA", date(2026, 6, 10), date(2026, 6, 11), yf_fetcher=lambda *a, **k: [])
    assert (bars, src) == ([], "empty")
