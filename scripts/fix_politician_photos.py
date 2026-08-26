"""Normalize all politician names/parties/bioguide IDs and download any missing photo files."""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path
import yaml

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import Politician, Trade, get_engine, get_session

ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
PHOTO_DIR = ROOT / "data" / "politicians"
PHOTO_DIR.mkdir(parents=True, exist_ok=True)
WEB_PHOTO_DIR = ROOT / "web_fused" / "public" / "politicians"
WEB_PHOTO_DIR.mkdir(parents=True, exist_ok=True)

YAML_PATH = ROOT / "data" / "legislators-current.yaml"
if not YAML_PATH.exists():
    url = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml"
    try:
        urllib.request.urlretrieve(url, str(YAML_PATH))
    except Exception as e:
        print(f"Warning downloading legislators-current: {e}")

HIST_YAML_PATH = ROOT / "data" / "legislators-historical.yaml"
if not HIST_YAML_PATH.exists():
    url_hist = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-historical.yaml"
    try:
        urllib.request.urlretrieve(url_hist, str(HIST_YAML_PATH))
    except Exception as e:
        print(f"Warning downloading legislators-historical: {e}")

try:
    from yaml import CSafeLoader as Loader
except ImportError:
    from yaml import SafeLoader as Loader

legislators = []
if YAML_PATH.exists():
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=Loader)
        if data:
            legislators.extend(data)

if HIST_YAML_PATH.exists():
    with open(HIST_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=Loader)
        if data:
            legislators.extend(data)

# Build comprehensive lookup table
lookup: dict[str, dict] = {}
for member in legislators:
    name_obj = member.get("name", {})
    bio_id = (member.get("id", {}) or {}).get("bioguide")
    if not bio_id:
        continue
    first = (name_obj.get("first") or "").strip()
    last = (name_obj.get("last") or "").strip()
    middle = (name_obj.get("middle") or "").strip()
    nickname = (name_obj.get("nickname") or "").strip()
    official = (name_obj.get("official_full") or "").strip()
    terms = member.get("terms") or []
    last_term = terms[-1] if terms else {}
    party_raw = (last_term.get("party") or "").lower()
    party = "D" if "democrat" in party_raw else ("R" if "republican" in party_raw else "I")

    info = {
        "bioguide_id": bio_id,
        "name": f"{first} {last}".strip(),
        "party": party,
        "state": last_term.get("state") or "",
        "district": str(last_term.get("district") or "") if last_term.get("district") is not None else None,
        "chamber": "house" if last_term.get("type") == "rep" else "senate",
    }

    candidates = [
        f"{first} {last}",
        official,
        f"{first} {middle} {last}" if middle else "",
        f"{nickname} {last}" if nickname else "",
    ]
    for c in candidates:
        if not c:
            continue
        cleaned = re.sub(r"[^a-z ]", "", c.lower()).strip()
        cleaned = " ".join(cleaned.split())
        lookup[cleaned] = info
        # first + last
        parts = cleaned.split()
        if len(parts) >= 2:
            lookup[f"{parts[0]} {parts[-1]}"] = info


def normalize_clean_name(raw: str) -> str:
    cleaned = re.sub(r"\b(mr|dr|hon|mrs|ms|jr|sr|ii|iii|iv)\b", "", raw.lower(), flags=re.I)
    cleaned = re.sub(r"[^a-z ]", "", cleaned).strip()
    return " ".join(cleaned.split())


def download_photo_if_missing(bio_id: str) -> bool:
    if not bio_id:
        return False
    path = PHOTO_DIR / f"{bio_id}.jpg"
    web_path = WEB_PHOTO_DIR / f"{bio_id}.jpg"
    
    if path.exists() and path.stat().st_size > 500:
        if not web_path.exists() or web_path.stat().st_size != path.stat().st_size:
            web_path.write_bytes(path.read_bytes())
        return True

    urls = [
        f"https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/225x275/{bio_id}.jpg",
        f"https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/450x550/{bio_id}.jpg",
        f"https://bioguide.congress.gov/photo/{bio_id}.jpg",
        f"https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/original/{bio_id}.jpg",
        f"https://unitedstates.github.io/images/congress/225x275/{bio_id}.jpg",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                if len(data) > 500:
                    path.write_bytes(data)
                    web_path.write_bytes(data)
                    print(f"Downloaded photo for {bio_id} ({len(data)} bytes) from {url}")
                    return True
        except Exception:
            continue
    return False


MANUAL_MAP = {
    "paul pelosi": {"bioguide_id": "P000197", "name": "Paul Pelosi", "party": "D", "state": "CA", "district": "11", "chamber": "house"},
    "richard burr": {"bioguide_id": "B001135", "name": "Richard Burr", "party": "R", "state": "NC", "district": None, "chamber": "senate"},
    "dianne feinstein": {"bioguide_id": "F000062", "name": "Dianne Feinstein", "party": "D", "state": "CA", "district": None, "chamber": "senate"},
    "david perdue": {"bioguide_id": "P000612", "name": "David Perdue", "party": "R", "state": "GA", "district": None, "chamber": "senate"},
    "kevin mccarthy": {"bioguide_id": "M001165", "name": "Kevin McCarthy", "party": "R", "state": "CA", "district": "20", "chamber": "house"},
    "marjorie taylor greene": {"bioguide_id": "G000596", "name": "Marjorie Taylor Greene", "party": "R", "state": "GA", "district": "14", "chamber": "house"},
    "linda t sanchez": {"bioguide_id": "S001156", "name": "Linda Sanchez", "party": "D", "state": "CA", "district": "38", "chamber": "house"},
    "a mitchell mcconnell": {"bioguide_id": "M000355", "name": "Mitch McConnell", "party": "R", "state": "KY", "district": None, "chamber": "senate"},
    "lindsey graham": {"bioguide_id": "G000359", "name": "Lindsey Graham", "party": "R", "state": "SC", "district": None, "chamber": "senate"},
    "william f hagerty": {"bioguide_id": "H000601", "name": "Bill Hagerty", "party": "R", "state": "TN", "district": None, "chamber": "senate"},
    "thomas h tuberville": {"bioguide_id": "T000278", "name": "Tommy Tuberville", "party": "R", "state": "AL", "district": None, "chamber": "senate"},
    "rafael e cruz": {"bioguide_id": "C001098", "name": "Ted Cruz", "party": "R", "state": "TX", "district": None, "chamber": "senate"},
    "matthew robert van epps": {"bioguide_id": "V000137", "name": "Matt Van Epps", "party": "R", "state": "TN", "district": "07", "chamber": "house"},
    "richard dean dr mccormick": {"bioguide_id": "M001218", "name": "Rich McCormick", "party": "R", "state": "GA", "district": "06", "chamber": "house"},
    "richard mccormick": {"bioguide_id": "M001218", "name": "Rich McCormick", "party": "R", "state": "GA", "district": "06", "chamber": "house"},
    "richard w allen": {"bioguide_id": "A000372", "name": "Rick W. Allen", "party": "R", "state": "GA", "district": "12", "chamber": "house"},
    "rick allen": {"bioguide_id": "A000372", "name": "Rick W. Allen", "party": "R", "state": "GA", "district": "12", "chamber": "house"},
    "daniel crenshaw": {"bioguide_id": "C001120", "name": "Dan Crenshaw", "party": "R", "state": "TX", "district": "02", "chamber": "house"},
    "dan crenshaw": {"bioguide_id": "C001120", "name": "Dan Crenshaw", "party": "R", "state": "TX", "district": "02", "chamber": "house"},
    "christian d menefee": {"bioguide_id": "M001245", "name": "Christian Menefee", "party": "D", "state": "TX", "district": "18", "chamber": "house"},
    "christian menefee": {"bioguide_id": "M001245", "name": "Christian Menefee", "party": "D", "state": "TX", "district": "18", "chamber": "house"},
    "april mcclain delaney": {"bioguide_id": "M001232", "name": "April McClain Delaney", "party": "D", "state": "MD", "district": "06", "chamber": "house"},
    "david j taylor": {"bioguide_id": "T000490", "name": "David J. Taylor", "party": "R", "state": "OH", "district": "02", "chamber": "house"},
    "john j mr mcguire iii": {"bioguide_id": "M001239", "name": "John McGuire", "party": "R", "state": "VA", "district": "05", "chamber": "house"},
    "derek tran": {"bioguide_id": "T000491", "name": "Derek Tran", "party": "D", "state": "CA", "district": "45", "chamber": "house"},
    "julie johnson": {"bioguide_id": "J000310", "name": "Julie Johnson", "party": "D", "state": "TX", "district": "32", "chamber": "house"},
    "kelly louise morrison": {"bioguide_id": "M001234", "name": "Kelly Morrison", "party": "D", "state": "MN", "district": "03", "chamber": "house"},
    "tim moore": {"bioguide_id": "M001236", "name": "Tim Moore", "party": "R", "state": "NC", "district": "14", "chamber": "house"},
}


def main():
    session = get_session(get_engine(settings.DATABASE_URL))
    updated = 0
    pols = session.query(Politician).all()
    for pol in pols:
        clean = normalize_clean_name(pol.name)
        info = MANUAL_MAP.get(clean) or lookup.get(clean)
        if not info and " " in clean:
            parts = clean.split()
            info = MANUAL_MAP.get(f"{parts[0]} {parts[-1]}") or lookup.get(f"{parts[0]} {parts[-1]}")
            if not info and len(parts) >= 3:
                info = MANUAL_MAP.get(f"{parts[1]} {parts[-1]}") or lookup.get(f"{parts[1]} {parts[-1]}")

        if info:
            bio_id = info["bioguide_id"]
            if pol.bioguide_id != bio_id:
                pol.bioguide_id = bio_id
                updated += 1
            if bio_id and pol.photo_url != f"/politicians/{bio_id}.jpg":
                pol.photo_url = f"/politicians/{bio_id}.jpg"
                updated += 1
            if pol.party != info["party"] and info["party"] in ("D", "R", "I"):
                pol.party = info["party"]
                updated += 1
            if info["state"] and pol.state != info["state"]:
                pol.state = info["state"]
                updated += 1
            if info["district"] and pol.district != info["district"]:
                pol.district = info["district"]
                updated += 1
            download_photo_if_missing(bio_id)
            print(f"OK: {pol.name} -> {info['name']} ({bio_id}, {info['party']}-{info['state']})")
        else:
            if pol.bioguide_id:
                download_photo_if_missing(pol.bioguide_id)
            print(f"NO MATCH: {pol.name} (bioguide: {pol.bioguide_id})")

    session.commit()
    print(f"\nCompleted: {updated} records updated in database.")
    session.close()


if __name__ == "__main__":
    main()
