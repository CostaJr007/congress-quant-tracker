"""Unit tests for the 9-signal suspicion scorer (no network)."""

import pytest

from congress_quant_tracker.config import settings
from congress_quant_tracker.scoring.scorer import (
    POINTS_COMMITTEE_MATCH,
    POINTS_DELAY_LATE,
    POINTS_DELAY_NEAR_LIMIT,
    POINTS_LARGE_TRADE_50K,
    POINTS_LARGE_TRADE_100K,
    POINTS_OPTIONS_TRADE,
    POINTS_SPOUSE_DEPENDENT,
    SCORE_HIGH_ALERT,
    SCORE_NOTEWORTHY,
    SCORE_SUSPICIOUS,
    TradeScorer,
    tag_from_score,
)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Keep yfinance-backed signals offline."""
    monkeypatch.setattr(settings, "NO_YF", True)


def test_tag_boundaries():
    assert tag_from_score(0) == "routine"
    assert tag_from_score(SCORE_NOTEWORTHY - 1) == "routine"
    assert tag_from_score(SCORE_NOTEWORTHY) == "noteworthy"
    assert tag_from_score(SCORE_SUSPICIOUS) == "suspicious"
    assert tag_from_score(SCORE_HIGH_ALERT) == "high_alert"


def test_trade_size_bands():
    s = TradeScorer()
    assert s.score_trade_size(30_000)[0] == 0
    assert s.score_trade_size(60_000)[0] == POINTS_LARGE_TRADE_50K
    assert s.score_trade_size(200_000)[0] == POINTS_LARGE_TRADE_100K
    assert s.score_trade_size(2_000_000)[0] == 25


def test_disclosure_delay_bands():
    s = TradeScorer()
    assert s.score_disclosure_delay("2026-01-01", "2026-01-11")[0] == 0
    assert s.score_disclosure_delay("2026-01-01", "2026-02-02")[0] == POINTS_DELAY_LATE
    assert s.score_disclosure_delay("2026-01-01", "2026-02-10")[0] == POINTS_DELAY_NEAR_LIMIT
    assert s.score_disclosure_delay("2026-01-01", "2026-02-20")[0] == 25
    # filed before traded — no penalty
    assert s.score_disclosure_delay("2026-01-10", "2026-01-01")[0] == 0
    assert s.score_disclosure_delay(None, "2026-01-01")[0] == 0


def test_cluster_scores_count_unique_members():
    s = TradeScorer()
    trades = [
        {"ticker": "NVDA", "politician_name": "A"},
        {"ticker": "NVDA", "politician_name": "B"},
        {"ticker": "NVDA", "politician_name": "C"},
        {"ticker": "AAPL", "politician_name": "A"},
        {"ticker": "AAPL", "politician_name": "B"},
        {"ticker": "MSFT", "politician_name": "A"},
        {"ticker": "MSFT", "politician_name": "A"},  # same member twice ≠ cluster
        {"ticker": "", "politician_name": "B"},  # ignored
    ]
    clusters = s.compute_cluster_scores(trades)
    assert clusters["NVDA"][0] == 20
    assert set(clusters["NVDA"][1]) == {"A", "B", "C"}
    assert clusters["AAPL"][0] == 15
    assert "MSFT" not in clusters


def test_owner_points():
    s = TradeScorer()
    assert s.score_owner("SP")[0] == POINTS_SPOUSE_DEPENDENT
    assert s.score_owner("DC")[0] == POINTS_SPOUSE_DEPENDENT
    assert s.score_owner("JT")[0] == 5
    assert s.score_owner("")[0] == 0
    assert s.score_owner("Self")[0] == 0


def test_options_points():
    s = TradeScorer()
    assert s.score_options_trade("option_call")[0] == POINTS_OPTIONS_TRADE
    assert s.score_options_trade("option_put")[0] == POINTS_OPTIONS_TRADE
    assert s.score_options_trade("stock")[0] == 0


def test_committee_match():
    s = TradeScorer()
    pts, reason = s.score_committee_match(["Ways and Means"], "Technology")
    assert pts == 10
    pts, reason = s.score_committee_match(
        ["Energy and Commerce"], "Healthcare"
    )
    assert pts == POINTS_COMMITTEE_MATCH
    assert "Energy" in reason or "Healthcare" in reason
    assert s.score_committee_match([], "Healthcare")[0] == 0
    assert s.score_committee_match(["Agriculture"], "Information Technology")[0] == 0


def test_score_trade_aggregates_and_caps():
    s = TradeScorer()
    result = s.score_trade(
        {
            "ticker": "NVDA",
            "trade_date": "2026-01-01",
            "filing_date": "2026-03-05",
            "transaction_type": "sell",
            "value_max": 2_500_000,
            "asset_type": "option_call",
            "owner": "SP",
        },
        cluster_results={"NVDA": (20, ["Other A", "Other B", "Other C"])},
        sector="Healthcare",
        committees=["Energy and Commerce"],
    )
    # 25 committee + 25 size + 25 delay + 5 options + 10 spouse + 20 cluster = 110 → capped at 100
    assert result["score"] == 100
    assert result["tag"] == "high_alert"
    assert "+" in result["reason"]


def test_score_batch_sorted_desc_and_mutates_rows():
    s = TradeScorer()
    rows = [
        {"id": 1, "value_max": 10_000, "trade_date": "2026-01-01", "filing_date": "2026-01-05"},
        {"id": 2, "value_max": 500_000, "trade_date": "2026-01-01", "filing_date": "2026-03-10"},
    ]
    scored = s.score_batch(rows)
    assert scored[0]["id"] == 2
    assert scored[0]["score"] >= scored[1]["score"]
    # dicts are mutated in place (same objects, new list order)
    by_id = {r["id"]: r for r in rows}
    assert by_id[2]["tag"] == scored[0]["tag"]
    assert by_id[2]["reason"] == scored[0]["reason"]


def test_parse_amount_upper_takes_last_match():
    from congress_quant_tracker.scoring.scorer import _parse_amount_upper

    assert _parse_amount_upper("$1,001 - $15,000") == 15_000
    assert _parse_amount_upper("") == 0
    assert _parse_amount_upper("n/a") == 0


def test_contrarian_disabled_without_yfinance(monkeypatch):
    import congress_quant_tracker.scoring.scorer as scorer_mod

    monkeypatch.setattr(settings, "NO_YF", False)
    monkeypatch.setattr(scorer_mod, "yf", None)
    pts, _ = TradeScorer().score_contrarian("NVDA", "2026-01-01", "buy")
    assert pts == 0
