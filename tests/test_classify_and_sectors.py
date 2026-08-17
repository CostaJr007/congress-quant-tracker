from congress_quant_tracker.enrichers.sectors import resolve_sector, scorer_sector
from congress_quant_tracker.fetchers.congress_invests import classify_asset, parse_option_details
from congress_quant_tracker.scoring.scorer import TradeScorer, tag_from_score


def test_classify_options_and_stock():
    assert classify_asset("NVIDIA Call Option $140 strike", "NVDA") == "option_call"
    assert classify_asset("Put option on AAPL", "AAPL") == "option_put"
    assert classify_asset("Apple Inc Common Stock", "AAPL") == "stock"
    assert classify_asset("SPDR S&P 500 ETF", "SPY") == "etf"


def test_parse_option_details():
    opt = parse_option_details("Call $140 03/13/2026", "option_call")
    assert opt is not None
    assert opt["option_type"] == "call"
    assert opt["strike"] == 140.0
    assert opt["expiration_date"].isoformat() == "2026-03-13"


def test_resolve_sector_static_map():
    assert resolve_sector("NVDA") == "Technology"
    assert resolve_sector("XOM") == "Energy"
    assert resolve_sector("JPM") == "Financials"
    assert resolve_sector("UNKN") is None
    assert resolve_sector("UNKN", trade_sector="Healthcare") == "Healthcare"


def test_scorer_sector_alias():
    assert scorer_sector("Technology") == "Information Technology"
    assert scorer_sector("Financials") == "Financial Services"


def test_score_delay_and_size():
    scorer = TradeScorer()
    result = scorer.score_trade(
        {
            "ticker": "TEST",
            "trade_date": "2026-01-01",
            "filing_date": "2026-03-01",
            "transaction_type": "buy",
            "value_max": 250_000,
            "asset_type": "stock",
            "owner": "SP",
        },
        sector="",
        committees=[],
    )
    assert result["score"] >= 25
    assert result["tag"] in ("noteworthy", "suspicious", "high_alert")
    assert tag_from_score(80) == "high_alert"
    assert tag_from_score(10) == "routine"
