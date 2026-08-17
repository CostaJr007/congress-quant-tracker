"""Legacy Streamlit desk — optional. Prefer CI://TERMINAL or web_fused."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd
import streamlit as st
from sqlalchemy import func

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import Politician, Trade, get_engine, get_session

st.set_page_config(page_title="CongressInvests", layout="wide")
st.title("CongressInvests — Streamlit (legacy)")
st.caption("Use http://localhost:8000/terminal/ or web_fused :3000 for the full desk.")


@st.cache_data(ttl=60)
def load_summary():
    session = get_session(get_engine(settings.DATABASE_URL))
    try:
        trades = session.query(func.count(Trade.id)).scalar() or 0
        pols = session.query(func.count(Politician.id)).scalar() or 0
        rows = (
            session.query(
                Politician.name,
                Politician.party,
                Politician.chamber,
                func.count(Trade.id),
                func.avg(Trade.score),
            )
            .join(Trade, Trade.politician_id == Politician.id)
            .group_by(Politician.id)
            .order_by(func.count(Trade.id).desc())
            .limit(25)
            .all()
        )
        df = pd.DataFrame(rows, columns=["name", "party", "chamber", "trades", "avg_score"])
        return trades, pols, df
    finally:
        session.close()


n_trades, n_pols, top = load_summary()
c1, c2 = st.columns(2)
c1.metric("Trades", f"{n_trades:,}")
c2.metric("Politicians", f"{n_pols:,}")
st.subheader("Most active members")
st.dataframe(top, use_container_width=True, hide_index=True)
