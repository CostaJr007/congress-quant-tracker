"""API endpoint tests against an isolated temp SQLite database (no network).

Covers the core read endpoints of server/routers/*: health, dashboard,
trades (+months, signals), politicians (+detail, leaderboard), stocks,
search, meta and terminal congress months.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import (
    Company,
    Politician,
    Trade,
    get_engine,
    init_db,
)


def _d(iso: str):
    from datetime import date

    return date.fromisoformat(iso)


NANCY_TRADES = [
    # (ticker, trade_date, filing_date, tx, value_min, value_max, score, tag)
    ("NVDA", "2026-05-01", "2026-06-01", "buy", 50_000, 100_000, 40, "noteworthy"),
    ("NVDA", "2026-06-10", "2026-07-01", "sell", 100_000, 250_000, 55, "suspicious"),
    ("AAPL", "2026-06-20", "2026-07-05", "buy", 15_000, 50_000, 20, "routine"),
    ("MSFT", "2026-07-10", "2026-08-01", "buy", 250_000, 500_000, 80, "high_alert"),
]


def _seed(db_url: str) -> None:
    engine = create_engine(db_url)
    session_factory = sessionmaker(bind=engine)
    s = session_factory()
    pol = Politician(
        name="Nancy Pelosi",
        chamber="house",
        party="D",
        state="CA",
        district="11",
        bioguide_id="P000197",
    )
    s.add(pol)
    s.flush()
    for ticker, td, fd, tx, vmin, vmax, score, tag in NANCY_TRADES:
        s.add(
            Trade(
                politician_id=pol.id,
                ticker=ticker,
                asset_name=f"{ticker} Corp",
                asset_type="stock",
                transaction_type=tx,
                trade_date=_d(td),
                filing_date=_d(fd),
                value_min=vmin,
                value_max=vmax,
                value_range=f"${vmin // 1000}K-${vmax // 1000}K",
                score=score,
                tag=tag,
                reason="unit test",
            )
        )
    s.add(Company(ticker="NVDA", name="NVIDIA Corporation", sector="Technology"))
    s.commit()
    s.close()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"

    monkeypatch.setattr(settings, "DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "AUTO_SYNC_ON_STARTUP", False)

    init_db(db_url)
    _seed(db_url)

    import server.deps as deps

    monkeypatch.setattr(deps, "engine", get_engine(db_url))

    from server.api_server import app

    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["total_trades"] == len(NANCY_TRADES)
    assert body["version"]


def test_dashboard(client):
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["total_trades"] == 4
    assert body["total_politicians"] == 1
    assert len(body["activity_by_month"]) == 12
    assert body["signal_distribution"]["high_alert"] == 1
    tickers = {t["ticker"]: t for t in body["top_tickers"]}
    assert tickers["NVDA"]["name"] == "NVIDIA Corporation"
    assert len(body["recent_trades"]) == 4


def test_trades_list_and_filters(client):
    r = client.get("/api/trades")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4

    r = client.get("/api/trades", params={"tag": "suspicious"})
    assert r.json()["total"] == 1

    r = client.get("/api/trades", params={"month": "2026-07", "date_field": "filing"})
    assert r.json()["total"] == 2  # filings on 2026-07-01 and 2026-07-05

    r = client.get("/api/trades", params={"sort_by": "score"})
    scores = [t["score"] for t in r.json()["trades"]]
    assert scores == sorted(scores, reverse=True)


def test_trade_months(client):
    r = client.get("/api/trades/months")
    assert r.status_code == 200
    months = {m["month"]: m for m in r.json()["months"]}
    assert months["2026-08"]["count"] == 1
    assert months["2026-07"]["count"] == 2  # by filing date
    assert months["2026-06"]["count"] == 1


def test_politicians_and_detail(client):
    r = client.get("/api/politicians")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    pol = body["politicians"][0]
    assert pol["name"] == "Nancy Pelosi"
    assert pol["total_trades"] == 4
    assert pol["photo_url"].endswith("P000197.jpg")

    r = client.get("/api/politicians/nancy-pelosi")
    assert r.status_code == 200
    detail = r.json()
    assert detail["buys"] == 3
    assert detail["sells"] == 1
    assert len(detail["recent_trades"]) == 4
    assert any(a["ticker"] == "NVDA" for a in detail["top_assets"])

    r = client.get("/api/politicians/nobody-here")
    assert r.status_code == 404


def test_leaderboard_requires_three_trades(client):
    r = client.get("/api/leaderboard", params={"metric": "score"})
    assert r.status_code == 200
    board = r.json()["leaderboard"]
    assert len(board) == 1
    assert board[0]["rank"] == 1
    assert board[0]["trades"] >= 3


def test_signals(client):
    r = client.get("/api/signals", params={"min_score": 51})
    body = r.json()
    assert body["total"] == 2
    tags = {s["tag"] for s in body["signals"]}
    assert tags <= {"suspicious", "high_alert"}


def test_search(client):
    r = client.get("/api/search", params={"q": "pelos"})
    assert r.status_code == 200
    assert any(p["name"] == "Nancy Pelosi" for p in r.json()["politicians"])

    r = client.get("/api/search", params={"q": "NVDA"})
    assert any(t["ticker"] == "NVDA" for t in r.json()["tickers"])


def test_meta(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    body = r.json()
    assert "CA" in body["states"]
    assert "D" in body["parties"]
    assert "House" in body["chambers"]
    assert body["data_age_days"] is not None and body["data_age_days"] >= 0


def test_stocks_aggregate(client):
    r = client.get("/api/stocks")
    assert r.status_code == 200
    nvda = next(s for s in r.json()["stocks"] if s["ticker"] == "NVDA")
    assert nvda["name"] == "NVIDIA Corporation"
    assert nvda["sector"] == "Technology"
    assert nvda["unique_politicians"] == 1

    r = client.get("/api/stocks/NVDA")
    body = r.json()
    assert body["total_trades"] == 2
    assert body["buy_count"] == 1
    assert body["sell_count"] == 1

    assert client.get("/api/stocks/ZZZZ").status_code == 404


def test_terminal_congress_months(client):
    r = client.get("/api/terminal/congress/months")
    assert r.status_code == 200


def test_terminal_chat_models(client):
    r = client.get("/api/terminal/chat/models")
    assert r.status_code == 200
    providers = {p["id"] for p in r.json()["providers"]}
    assert {"groq", "openai", "local"} <= providers


def test_terminal_dataset_alias_rejects_reserved(client):
    r = client.get("/api/terminal/congress")
    assert r.status_code == 404


def test_root_redirects_to_terminal(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (301, 302, 307)
    assert "/terminal/" in r.headers["location"]
