"""Tests for the duplicate-politician merge tool (it moves real trades)."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from congress_quant_tracker.database.models import Base, Politician, Trade
from scripts.merge_duplicate_politicians import (
    build_groups,
    merge_group,
    resolve_bioguide,
    surname,
)

MEMBERS = {
    "ro khanna": {"party": "D", "state": "CA", "district": "17", "chamber": "house",
                  "bioguide_id": "K000389"},
    "khanna": {"party": "D", "state": "CA", "district": "17", "chamber": "house",
               "bioguide_id": "K000389"},
    "diana harshbarger": {"party": "R", "state": "TN", "district": "01", "chamber": "house",
                          "bioguide_id": "H001086"},
    "harshbarger": {"party": "R", "state": "TN", "district": "01", "chamber": "house",
                    "bioguide_id": "H001086"},
    "nancy pelosi": {"party": "D", "state": "CA", "district": "11", "chamber": "house",
                     "bioguide_id": "P000197"},
}


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _pol(session, name, **over):
    pol = Politician(name=name, chamber=over.pop("chamber", "house"),
                     party=over.pop("party", "D"), state=over.pop("state", "CA"), **over)
    session.add(pol)
    session.flush()
    return pol


def _trade(session, pol, ticker="AAPL", day=1):
    session.add(
        Trade(politician_id=pol.id, ticker=ticker, transaction_type="buy",
              trade_date=date(2026, 1, day), score=0, tag=None)
    )
    session.flush()


def test_resolve_bioguide_matches_full_name_and_refuses_other_chambers(session):
    pol = _pol(session, "Rohit Khanna", state="CA", chamber="house")
    bioguide, source = resolve_bioguide(pol, MEMBERS)
    assert bioguide == "K000389" and source == "surname"

    senator = _pol(session, "Ro Khanna", chamber="senate", state="CA")
    assert resolve_bioguide(senator, MEMBERS)[0] == ""


def test_resolve_bioguide_rejects_mismatched_state(session):
    pol = _pol(session, "Rohit Khanna", state="TX", chamber="house")
    assert resolve_bioguide(pol, MEMBERS)[0] == ""


def test_variant_names_of_one_member_are_mergeable(session):
    ro = _pol(session, "Ro Khanna", state="CA", bioguide_id="K000389")
    rohit = _pol(session, "Rohit Khanna", state="CA")
    _trade(session, rohit, "NVDA")
    mergeable, review, _mismatched = build_groups([ro, rohit], MEMBERS)
    assert len(mergeable) == 1 and not review


def test_different_people_with_the_same_surname_are_not_merged(session):
    harshbarger = _pol(session, "Diana Harshbarger", state="TN", bioguide_id="H001086")
    stray = _pol(session, "Drana Harshbarger", state="TN")
    other = _pol(session, "Ashley Banks", state="IL", bioguide_id="H001086")
    mergeable, review, _mismatched = build_groups([harshbarger, stray, other], MEMBERS)
    assert not mergeable
    assert any(other in group for group in review)


def test_row_bioguide_that_contradicts_the_name_is_reported(session):
    a = _pol(session, "Ro Khanna", state="CA", bioguide_id="K000389")
    b = _pol(session, "Rohit Khanna", state="CA", bioguide_id="X999999")
    mergeable, review, mismatched = build_groups([a, b], MEMBERS)
    assert not mergeable and not review
    assert any("Rohit Khanna" in line and "X999999" in line for line in mismatched)


def test_unresolvable_same_surname_rows_go_to_review(session):
    lee_one = _pol(session, "Daniel Lee", state="")
    lee_two = _pol(session, "Erica Lee", state="")
    mergeable, review, _mismatched = build_groups([lee_one, lee_two], MEMBERS)
    assert not mergeable and len(review) == 1


def test_merge_group_moves_trades_and_keeps_the_directory_name(session):
    ro = _pol(session, "Ro Khanna", state="CA", bioguide_id="K000389")
    rohit = _pol(session, "Rohit Khanna", state="CA")
    _trade(session, rohit, "NVDA", day=1)
    _trade(session, rohit, "MSFT", day=2)

    result = merge_group(session, [ro, rohit], MEMBERS)
    session.commit()
    # trades stay put: the row that already has them survives
    assert result["trades_moved"] == 0
    assert session.query(Politician).count() == 1
    survivor = session.query(Politician).one()
    assert survivor.name == "Ro Khanna"
    assert survivor.bioguide_id == "K000389"
    assert session.query(Trade).filter(Trade.politician_id == survivor.id).count() == 2


def test_surname_helper_ignores_titles():
    pol = Politician(name="A. Mitchell McConnell, Jr.", chamber="senate", party="R", state="KY")
    assert surname(pol) == "mcconnell"
