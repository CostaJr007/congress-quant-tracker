"""Incremental screener checkpoints — pipelines only fetch what's new.

Every pipeline run records two checkpoints in `pipeline_state`:
  <name>_last_run     — UTC stamp of the last *completed* run
  <name>_last_filing  — max filing_date covered by that run (House only)

A run with since_days=None resumes from the checkpoint minus
SCREENER_OVERLAP_DAYS (late/amended filings surface days late) and never
looks further back than DATA_WINDOW_DAYS (2 years). Storage is idempotent
(merge on uq_trade), so the overlap only re-reads a handful of rows.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import (
    get_pipeline_state,
    set_pipeline_state,
)


def collection_cutoff() -> date:
    """Nothing older than this is ever fetched or kept."""
    return date.today() - timedelta(days=settings.DATA_WINDOW_DAYS)


def resolve_since_days(
    session,
    requested: int | None,
    run_key: str,
    filing_key: str | None = None,
) -> tuple[int, str]:
    """Effective lookback in days + a human-readable mode label.

    Explicit `requested` always wins (clamped to the collection window).
    Otherwise resume from the checkpoint, or take the whole window on the
    first run.
    """
    window = settings.DATA_WINDOW_DAYS
    if requested is not None:
        return min(max(1, requested), window), "explicit"

    watermark = None
    if filing_key:
        raw = get_pipeline_state(session, filing_key)
        if raw:
            try:
                watermark = date.fromisoformat(raw[:10])
            except ValueError:
                watermark = None
    if watermark is None:
        raw_run = get_pipeline_state(session, run_key)
        if raw_run:
            try:
                watermark = datetime.fromisoformat(raw_run[:19]).date()
            except ValueError:
                watermark = None

    if watermark is None:
        return window, "first-run"
    start = min(watermark - timedelta(days=settings.SCREENER_OVERLAP_DAYS),
                date.today())
    start = max(start, collection_cutoff())
    return max(1, (date.today() - start).days), "incremental"


def save_checkpoint(
    session,
    run_key: str,
    filing_key: str | None = None,
    last_filing: date | None = None,
) -> None:
    set_pipeline_state(session, run_key, datetime.utcnow().isoformat())
    if filing_key and last_filing:
        set_pipeline_state(session, filing_key, last_filing.isoformat())
    session.commit()


__all__ = ["collection_cutoff", "resolve_since_days", "save_checkpoint"]
