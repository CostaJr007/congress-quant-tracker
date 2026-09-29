"""Merge duplicate politician rows that are the same person.

The pre-OCR pipeline registered whoever the filing text or the Clerk index
named, so one member could end up as several rows ("Ro Khanna" / "Rohit Khanna",
"Dan Crenshaw" / "Daniel Crenshaw", "Diana Harshbarger" / "Drana Harshbarger").

Merging is driven by the legislature directory and refuses to guess:

  * rows already carrying the same bioguide ID are one person, always
  * rows whose name resolves to a bioguide are grouped only when the chamber,
    state and surname all agree — two different people can share a surname
  * anything else is reported for a human, never merged

The surviving row keeps its trades and takes the name spelling the directory
recognises.

Usage:
    python scripts/merge_duplicate_politicians.py            # report only
    python scripts/merge_duplicate_politicians.py --apply    # write changes
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

from congress_quant_tracker.common import refresh_politician_stats  # noqa: E402
from congress_quant_tracker.config import settings  # noqa: E402
from congress_quant_tracker.database.models import (  # noqa: E402
    Politician,
    Trade,
    get_engine,
    get_session,
)
from congress_quant_tracker.fetchers.congress_invests import _load_members_db  # noqa: E402

logger = logging.getLogger("merge_duplicate_politicians")

_TITLES = r"\b(mr|dr|hon|mrs|ms|jr|sr|ii|iii|iv)\b"


def _name_words(name: str) -> list[str]:
    key = re.sub(_TITLES, "", (name or "").lower(), flags=re.I)
    return [w for w in re.split(r"[^a-z]+", key) if w]


def _candidate_keys(name: str) -> list[tuple[str, int]]:
    """(lookup key, specificity) pairs for a name, most specific first.

    Specificity 0 = the full name, 1 = first + last, 2 = the bare surname. A
    full-name hit is better evidence than a surname hit, which the merge uses to
    pick which spelling to keep.
    """
    words = _name_words(name)
    if not words:
        return []
    keys = [(" ".join(words), 0)]
    if len(words) > 2:
        keys.append((f"{words[0]} {words[-1]}", 1))
    if len(words) > 1:
        keys.append((words[-1], 2))
    return keys


def surname(pol: Politician) -> str:
    words = _name_words(pol.name)
    return words[-1] if words else ""


def initial(pol: Politician) -> str:
    words = _name_words(pol.name)
    return words[0][0] if words else ""


def _same_person_names(rows: list[Politician]) -> bool:
    """True when the names plausibly describe one person.

    Same surname plus the same first initial, or a first name that prefixes the
    other ("Ro"/"Rohit"). "A. Mitchell" vs "Mitch", or "Ashley" vs "James",
    fail this and go to a human instead.
    """
    surnames = {surname(pol) for pol in rows}
    if len(surnames) > 1:
        return False
    words = [_name_words(pol.name) for pol in rows]
    firsts = [w[0] for w in words if w]
    if len({f[0] for f in firsts}) == 1:
        return True
    return any(a.startswith(b) or b.startswith(a) for a in firsts for b in firsts if a != b)


def directory_match(pol: Politician, members: dict) -> tuple[str, int]:
    """(bioguide, specificity) from the directory for a row's name, or ("", -1).

    The row's own bioguide is ignored here: this asks what the directory says
    about the *name*, which is how a mis-assigned ID gets noticed. A hit counts
    only when the chamber, state and district agree with the row.
    """
    for key, rank in _candidate_keys(pol.name):
        info = members.get(key) or {}
        bio_id = info.get("bioguide_id")
        if not bio_id:
            continue
        if pol.state and info.get("state") and info["state"] != pol.state:
            continue
        if info.get("chamber") and info["chamber"] != pol.chamber:
            continue
        if pol.district and info.get("district") is not None:
            if str(info["district"]) != str(pol.district):
                continue
        return str(bio_id), rank
    return "", -1


def resolve_bioguide(pol: Politician, members: dict) -> tuple[str, str]:
    """(bioguide, source) for a politician row: its own, else the directory."""
    if pol.bioguide_id:
        return str(pol.bioguide_id), "row"
    bioguide, rank = directory_match(pol, members)
    if bioguide:
        return bioguide, ["full", "first-last", "surname"][rank]
    return "", ""


def build_groups(politicians: list[Politician], members: dict):
    """(mergeable groups, groups needing a human) keyed by bioguide/identity."""
    groups: dict[str, list[Politician]] = defaultdict(list)
    unresolved: dict[tuple, list[Politician]] = defaultdict(list)
    mismatched: list[str] = []
    for pol in politicians:
        bioguide, _key = resolve_bioguide(pol, members)
        named, _rank = directory_match(pol, members)
        if pol.bioguide_id and named and named != pol.bioguide_id:
            mismatched.append(
                f"{pol.name} (id={pol.id}): row says {pol.bioguide_id}, name says {named}"
            )
        if bioguide:
            groups[bioguide].append(pol)
        else:
            unresolved[(surname(pol), pol.chamber, pol.state)].append(pol)

    mergeable: list[list[Politician]] = []
    needs_review: list[list[Politician]] = []
    for rows in groups.values():
        if len(rows) < 2:
            continue
        existing = {pol.bioguide_id for pol in rows if pol.bioguide_id}
        # Two different bioguides on one key is a conflict, never a merge; and
        # the names must still plausibly be the same person.
        if len(existing) > 1 or not _same_person_names(rows):
            needs_review.append(rows)
        else:
            mergeable.append(rows)
    for rows in unresolved.values():
        if len(rows) > 1:
            needs_review.append(rows)
    return mergeable, needs_review, mismatched


def merge_group(session, rows: list[Politician], members: dict) -> dict:
    """Fold every row of one person into the row that has the most trades."""
    def trade_count(pol: Politician) -> int:
        return session.query(Trade).filter(Trade.politician_id == pol.id).count()

    ordered = sorted(rows, key=lambda p: (-trade_count(p), p.id))
    target, extras = ordered[0], ordered[1:]

    # Name to keep: whichever spelling the directory recognises most precisely.
    preferred_name = ""
    best_rank = 99
    for pol in rows:
        _bioguide, rank = directory_match(pol, members)
        if _bioguide and rank < best_rank:
            preferred_name, best_rank = pol.name, rank

    moved = 0
    for extra in extras:
        for trade in session.query(Trade).filter(Trade.politician_id == extra.id).all():
            trade.politician_id = target.id
            moved += 1
        # keep the richer metadata on the surviving row
        if not target.bioguide_id and extra.bioguide_id:
            target.bioguide_id = extra.bioguide_id
        if not target.photo_url and extra.photo_url:
            target.photo_url = extra.photo_url
        if not target.committees and extra.committees:
            target.committees = extra.committees
        if (target.party in ("I", None)) and extra.party in ("D", "R"):
            target.party = extra.party
        if not target.state and extra.state:
            target.state = extra.state
        if not target.district and extra.district:
            target.district = extra.district
        session.delete(extra)

    if not target.bioguide_id:
        target.bioguide_id, _rank = directory_match(rows[0], members)
    if target.bioguide_id:
        target.photo_url = target.photo_url or f"/politicians/{target.bioguide_id}.jpg"
    # Delete the extras first: renaming the survivor to a name an extra still
    # holds would trip uq_politician (name, state, district).
    session.flush()
    if preferred_name:
        target.name = preferred_name
    session.flush()
    return {
        "kept": target.name,
        "kept_id": target.id,
        "bioguide": target.bioguide_id,
        "merged": [p.name for p in extras],
        "trades_moved": moved,
    }


def _label(rows: list[Politician]) -> str:
    return ", ".join(f"{pol.name} (id={pol.id})" for pol in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the merges")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    members = _load_members_db()
    engine = get_engine(settings.DATABASE_URL)
    session = get_session(engine)

    try:
        mergeable, needs_review, mismatched = build_groups(
            session.query(Politician).all(), members
        )
        print(f"mergeable duplicate groups: {len(mergeable)}")
        results = []
        for rows in mergeable:
            if args.apply:
                result = merge_group(session, rows, members)
                results.append(result)
                print(
                    f"  merged [{_label(rows)}] -> {result['kept']} "
                    f"(id={result['kept_id']}, {result['trades_moved']} trades moved)"
                )
            else:
                print(f"  would merge [{_label(rows)}]")

        if mismatched:
            print(f"\nbioguide/name mismatches (left alone): {len(mismatched)}")
            for line in mismatched[:20]:
                print(f"  {line}")

        if needs_review:
            print(f"\nneeds a human eye, not merged: {len(needs_review)}")
            for rows in needs_review[:20]:
                print(f"  {_label(rows)}")

        if args.apply:
            session.commit()
            refresh_politician_stats(session)
            print(f"\n[merge] {len(results)} groups merged")
        else:
            print("\n[merge] dry run — re-run with --apply to write")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
