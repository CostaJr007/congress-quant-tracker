from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from congress_quant_tracker.common import (
    find_politician,
    normalize_transaction_type,
    refresh_politician_stats,
    sanitize_ticker,
)
from congress_quant_tracker.database.models import Base, Politician, Trade
from congress_quant_tracker.services.official_pipeline import OfficialHousePipeline
from congress_quant_tracker.services.senate_pipeline import SenatePipeline


def test_normalize_transaction_type():
    assert normalize_transaction_type("P") == "buy"
    assert normalize_transaction_type("purchase") == "buy"
    assert normalize_transaction_type("Buy") == "buy"
    assert normalize_transaction_type("purchase (partial)") == "buy"
    assert normalize_transaction_type("S") == "sell"
    assert normalize_transaction_type("S (partial)") == "sell"
    assert normalize_transaction_type("sale (full)") == "sell"
    assert normalize_transaction_type("sale_full") == "sell"
    assert normalize_transaction_type("sale") == "sell"
    assert normalize_transaction_type("E") == "exchange"
    assert normalize_transaction_type("Exchange") == "exchange"
    assert normalize_transaction_type("") == "buy"
    assert normalize_transaction_type(None) == "buy"


def test_sanitize_ticker():
    assert sanitize_ticker(" nvda ") == "NVDA"
    assert sanitize_ticker("brk.b") == "BRK.B"
    assert sanitize_ticker("--") is None
    assert sanitize_ticker("N/A") is None
    assert sanitize_ticker("UNKNOWN") is None
    assert sanitize_ticker("") is None
    assert sanitize_ticker(None) is None


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_find_politician():
    session = _make_session()
    pol = Politician(name="Nancy Pelosi", chamber="house", party="D", state="CA")
    session.add(pol)
    session.commit()

    assert find_politician(session, "nancy pelosi").id == pol.id
    assert find_politician(session, "Nancy Pelosi", chamber="house").id == pol.id
    assert find_politician(session, "  Nancy   Pelosi  ").id == pol.id
    # chamber mismatch on exact match and on substring fallback
    assert find_politician(session, "Nancy Pelosi", chamber="senate") is None
    assert find_politician(session, "Pelosi", chamber="senate") is None
    # legacy substring fallback
    assert find_politician(session, "Pelosi").id == pol.id
    assert find_politician(session, "Nonexistent Person") is None


def test_refresh_politician_stats():
    session = _make_session()
    pol = Politician(name="Ro Khanna", chamber="house", party="D", state="CA")
    session.add(pol)
    session.flush()
    session.add(
        Trade(
            politician_id=pol.id,
            ticker="AAPL",
            transaction_type="buy",
            trade_date=date(2026, 1, 1),
            score=0,
            tag=None,
        )
    )
    session.add(
        Trade(
            politician_id=pol.id,
            ticker="MSFT",
            transaction_type="sell",
            trade_date=date(2026, 1, 2),
            score=42,
            tag="noteworthy",
        )
    )
    session.commit()

    refresh_politician_stats(session)
    session.refresh(pol)
    assert pol.total_trades == 2
    # average considers only positive scores (zero-score rows are unscored)
    assert pol.avg_score == 42.0


def test_ensure_politician_dedup_by_state_district():
    session = _make_session()
    pipe = OfficialHousePipeline.__new__(OfficialHousePipeline)
    pipe.members = {}

    filing = {"state": "IN", "district": "06"}
    pol, created = pipe._ensure_politician(session, "Gregory Pence", filing=filing)
    assert created and pol.name == "Gregory Pence" and pol.state == "IN"

    # name variant must resolve to the same row (state + district)
    pol2, created2 = pipe._ensure_politician(session, "Greg Pence", filing=filing)
    assert created2 is False and pol2.id == pol.id

    # same exact name wins even if the filing district diverges
    pol3, created3 = pipe._ensure_politician(
        session, "Gregory Pence", filing={"state": "IN", "district": "07"}
    )
    assert created3 is False and pol3.id == pol.id
    assert session.query(Politician).count() == 1


def test_ensure_politician_dedup_by_bioguide():
    session = _make_session()
    pipe = OfficialHousePipeline.__new__(OfficialHousePipeline)
    pipe.members = {
        "gregory pence": {
            "party": "R",
            "state": "IN",
            "district": "06",
            "bioguide_id": "P000607",
        }
    }

    pol, created = pipe._ensure_politician(
        session, "Gregory Pence", filing={"state": "IN", "district": "06"}
    )
    assert created and pol.bioguide_id == "P000607" and pol.party == "R"

    pol2, created2 = pipe._ensure_politician(
        session, "Greg Pence", filing={"state": "IN", "district": "06"}
    )
    assert created2 is False and pol2.id == pol.id
    assert session.query(Politician).count() == 1


def test_ensure_senator():
    session = _make_session()
    pipe = SenatePipeline.__new__(SenatePipeline)
    pipe.members = {
        "chuck schumer": {"party": "D", "state": "NY", "bioguide_id": "S000148"}
    }

    pol, created = pipe._ensure_senator(session, "Chuck Schumer")
    assert created and pol.chamber == "senate" and pol.party == "D"
    assert pol.bioguide_id == "S000148"

    pol2, created2 = pipe._ensure_senator(session, "Chuck Schumer")
    assert created2 is False and pol2.id == pol.id
    assert session.query(Politician).count() == 1
