"""Normalize all politician names/parties/bioguide IDs and download missing photo files.

Features:
  - Fast YAML parsing + regex indexing of historical legislators.
  - Robust name normalization and manual mapping for edge-case congressional names.
  - High-performance concurrent photo downloads (ThreadPoolExecutor) with mirror to web_fused.
  - Synchronizes Politician bioguide_id, photo_url, party, state, and chamber in SQLite.
"""

from __future__ import annotations

import concurrent.futures
import re
import urllib.request
from pathlib import Path
import yaml

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import Politician, get_engine, get_session

ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
PHOTO_DIR = ROOT / "data" / "politicians"
PHOTO_DIR.mkdir(parents=True, exist_ok=True)
WEB_PHOTO_DIR = ROOT / "web_fused" / "public" / "politicians"
WEB_PHOTO_DIR.mkdir(parents=True, exist_ok=True)

YAML_PATH = ROOT / "data" / "legislators-current.yaml"
HIST_YAML_PATH = ROOT / "data" / "legislators-historical.yaml"

LEGISLATORS_BASE_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main"


def ensure_yaml(path: Path, url: str) -> None:
    """Download a legislators YAML file on first run (data/ is not versioned)."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(url, str(path))
        print(f"Downloaded {path.name}")
    except Exception as e:
        print(f"Warning downloading {path.name}: {e}")


ensure_yaml(YAML_PATH, f"{LEGISLATORS_BASE_URL}/legislators-current.yaml")
ensure_yaml(HIST_YAML_PATH, f"{LEGISLATORS_BASE_URL}/legislators-historical.yaml")


def normalize_clean_name(raw: str) -> str:
    """Strip prefixes, titles, suffixes, and punctuation for fuzzy matching."""
    cleaned = re.sub(
        r"\b(mr|dr|hon|mrs|ms|jr|sr|ii|iii|iv|sen|rep)\b",
        "",
        raw.lower(),
        flags=re.I,
    )
    cleaned = re.sub(r"[^a-z ]", " ", cleaned).strip()
    return " ".join(cleaned.split())


# Build lookup index
lookup: dict[str, dict] = {}

# 1. Current legislators (small file, load full YAML)
if YAML_PATH.exists():
    try:
        with open(YAML_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or []
            for member in data:
                bio_id = (member.get("id", {}) or {}).get("bioguide")
                if not bio_id:
                    continue
                name_obj = member.get("name", {})
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
                    cleaned = normalize_clean_name(c)
                    if cleaned:
                        lookup[cleaned] = info
                        parts = cleaned.split()
                        if len(parts) >= 2:
                            lookup[f"{parts[0]} {parts[-1]}"] = info
    except Exception as e:
        print(f"Notice loading legislators-current: {e}")

# 2. Historical legislators (large file -> ultra-fast regex extraction)
if HIST_YAML_PATH.exists():
    try:
        with open(HIST_YAML_PATH, "r", encoding="utf-8") as f:
            text = f.read()
        pattern = re.compile(r"bioguide:\s*([A-Z0-9]+).*?name:\s*\n((?:\s+[a-z_]+:\s*[^\n]+\n)+)", re.DOTALL)
        for match in pattern.finditer(text):
            bio_id = match.group(1)
            nb = match.group(2)
            first_m = re.search(r"first:\s*([^\n]+)", nb)
            last_m = re.search(r"last:\s*([^\n]+)", nb)
            official_m = re.search(r"official_full:\s*([^\n]+)", nb)
            first = first_m.group(1).strip("'\" ") if first_m else ""
            last = last_m.group(1).strip("'\" ") if last_m else ""
            official = official_m.group(1).strip("'\" ") if official_m else ""

            info = {
                "bioguide_id": bio_id,
                "name": f"{first} {last}".strip() or official,
                "party": "I",
                "state": "",
                "district": None,
                "chamber": "house",
            }
            for c in [f"{first} {last}", official]:
                cleaned = normalize_clean_name(c)
                if cleaned and cleaned not in lookup:
                    lookup[cleaned] = info
                    parts = cleaned.split()
                    if len(parts) >= 2 and f"{parts[0]} {parts[-1]}" not in lookup:
                        lookup[f"{parts[0]} {parts[-1]}"] = info
    except Exception as e:
        print(f"Notice parsing legislators-historical: {e}")


# Manual overrides for names in Senate/House disclosure systems
MANUAL_MAP = {
    # High-trade Senators & Representatives
    "markwayne mullin": {"bioguide_id": "M001190", "name": "Markwayne Mullin", "party": "R", "state": "OK", "district": None, "chamber": "senate"},
    "thomas h tuberville": {"bioguide_id": "T000278", "name": "Tommy Tuberville", "party": "R", "state": "AL", "district": None, "chamber": "senate"},
    "tommy tuberville": {"bioguide_id": "T000278", "name": "Tommy Tuberville", "party": "R", "state": "AL", "district": None, "chamber": "senate"},
    "angus s king": {"bioguide_id": "K000383", "name": "Angus S. King, Jr.", "party": "I", "state": "ME", "district": None, "chamber": "senate"},
    "angus king": {"bioguide_id": "K000383", "name": "Angus S. King, Jr.", "party": "I", "state": "ME", "district": None, "chamber": "senate"},
    "a mitchell mcconnell": {"bioguide_id": "M000355", "name": "Mitch McConnell", "party": "R", "state": "KY", "district": None, "chamber": "senate"},
    "mitch mcconnell": {"bioguide_id": "M000355", "name": "Mitch McConnell", "party": "R", "state": "KY", "district": None, "chamber": "senate"},
    "jerry moran": {"bioguide_id": "M000934", "name": "Jerry Moran", "party": "R", "state": "KS", "district": None, "chamber": "senate"},
    "lindsey graham": {"bioguide_id": "G000359", "name": "Lindsey Graham", "party": "R", "state": "SC", "district": None, "chamber": "senate"},
    "rafael e cruz": {"bioguide_id": "C001098", "name": "Ted Cruz", "party": "R", "state": "TX", "district": None, "chamber": "senate"},
    "ted cruz": {"bioguide_id": "C001098", "name": "Ted Cruz", "party": "R", "state": "TX", "district": None, "chamber": "senate"},
    "james conley justice": {"bioguide_id": "J000312", "name": "Jim Justice", "party": "R", "state": "WV", "district": None, "chamber": "senate"},
    "jim justice": {"bioguide_id": "J000312", "name": "Jim Justice", "party": "R", "state": "WV", "district": None, "chamber": "senate"},
    "james banks": {"bioguide_id": "B001299", "name": "Jim Banks", "party": "R", "state": "IN", "district": None, "chamber": "senate"},
    "jim banks": {"bioguide_id": "B001299", "name": "Jim Banks", "party": "R", "state": "IN", "district": None, "chamber": "senate"},
    "david h mccormick": {"bioguide_id": "M001243", "name": "Dave McCormick", "party": "R", "state": "PA", "district": None, "chamber": "senate"},
    "dave mccormick": {"bioguide_id": "M001243", "name": "Dave McCormick", "party": "R", "state": "PA", "district": None, "chamber": "senate"},
    "bernie moreno": {"bioguide_id": "M001242", "name": "Bernie Moreno", "party": "R", "state": "OH", "district": None, "chamber": "senate"},
    "adam b schiff": {"bioguide_id": "S001150", "name": "Adam Schiff", "party": "D", "state": "CA", "district": None, "chamber": "senate"},
    "adam schiff": {"bioguide_id": "S001150", "name": "Adam Schiff", "party": "D", "state": "CA", "district": None, "chamber": "senate"},
    "shelley m capito": {"bioguide_id": "C001047", "name": "Shelley Moore Capito", "party": "R", "state": "WV", "district": None, "chamber": "senate"},
    "sheldon whitehouse": {"bioguide_id": "W000802", "name": "Sheldon Whitehouse", "party": "D", "state": "RI", "district": None, "chamber": "senate"},
    "katie britt": {"bioguide_id": "B001319", "name": "Katie Britt", "party": "R", "state": "AL", "district": None, "chamber": "senate"},
    "gary c peters": {"bioguide_id": "P000595", "name": "Gary Peters", "party": "D", "state": "MI", "district": None, "chamber": "senate"},
    "john fetterman": {"bioguide_id": "F000479", "name": "John Fetterman", "party": "D", "state": "PA", "district": None, "chamber": "senate"},
    "john boozman": {"bioguide_id": "B001236", "name": "John Boozman", "party": "R", "state": "AR", "district": None, "chamber": "senate"},
    "ron l wyden": {"bioguide_id": "W000779", "name": "Ron Wyden", "party": "D", "state": "OR", "district": None, "chamber": "senate"},
    "ron wyden": {"bioguide_id": "W000779", "name": "Ron Wyden", "party": "D", "state": "OR", "district": None, "chamber": "senate"},
    "christopher campbell armstrong": {"bioguide_id": "A000383", "name": "Alan Armstrong", "party": "R", "state": "OK", "district": None, "chamber": "senate"},
    "alan armstrong": {"bioguide_id": "A000383", "name": "Alan Armstrong", "party": "R", "state": "OK", "district": None, "chamber": "senate"},
    "paul pelosi": {"bioguide_id": "P000197", "name": "Paul Pelosi", "party": "D", "state": "CA", "district": "11", "chamber": "house"},
    "richard burr": {"bioguide_id": "B001135", "name": "Richard Burr", "party": "R", "state": "NC", "district": None, "chamber": "senate"},
    "dianne feinstein": {"bioguide_id": "F000062", "name": "Dianne Feinstein", "party": "D", "state": "CA", "district": None, "chamber": "senate"},
    "david perdue": {"bioguide_id": "P000612", "name": "David Perdue", "party": "R", "state": "GA", "district": None, "chamber": "senate"},
    "kevin mccarthy": {"bioguide_id": "M001165", "name": "Kevin McCarthy", "party": "R", "state": "CA", "district": "20", "chamber": "house"},
    "marjorie taylor greene": {"bioguide_id": "G000596", "name": "Marjorie Taylor Greene", "party": "R", "state": "GA", "district": "14", "chamber": "house"},
    "linda t sanchez": {"bioguide_id": "S001156", "name": "Linda Sanchez", "party": "D", "state": "CA", "district": "38", "chamber": "house"},
    "william f hagerty": {"bioguide_id": "H000601", "name": "Bill Hagerty", "party": "R", "state": "TN", "district": None, "chamber": "senate"},
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
    "nanette barragan": {"bioguide_id": "B001300", "name": "Nanette Barragan", "party": "D", "state": "CA", "district": "44", "chamber": "house"},
    "cori bush": {"bioguide_id": "B001224", "name": "Cori Bush", "party": "D", "state": "MO", "district": "01", "chamber": "house"},
    "marcus j molinaro": {"bioguide_id": "M001221", "name": "Marcus Molinaro", "party": "R", "state": "NY", "district": "19", "chamber": "house"},
    "c a dutch ruppersberger": {"bioguide_id": "R000576", "name": "Dutch Ruppersberger", "party": "D", "state": "MD", "district": "02", "chamber": "house"},
    "jenniffer gonzalez colon": {"bioguide_id": "G000582", "name": "Jenniffer Gonzalez-Colon", "party": "R", "state": "PR", "district": "00", "chamber": "house"},
    "mark sanford": {"bioguide_id": "S000051", "name": "Mark Sanford", "party": "R", "state": "SC", "district": "01", "chamber": "house"},
    "aumua amata": {"bioguide_id": "R000600", "name": "Aumua Amata Radewagen", "party": "R", "state": "AS", "district": "00", "chamber": "house"},
    "michael a collins": {"bioguide_id": "C001129", "name": "Mike Collins", "party": "R", "state": "GA", "district": "10", "chamber": "house"},
    "ernest anthony tony gonzales": {"bioguide_id": "G000594", "name": "Tony Gonzales", "party": "R", "state": "TX", "district": "23", "chamber": "house"},
}

SPECIAL_PHOTO_URLS = {
    "A000383": "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/55/Alan_S_Armstrong_official_portrait_%28cropped_2%29.jpg/500px-Alan_S_Armstrong_official_portrait_%28cropped_2%29.jpg",
}


def download_photo_if_missing(bio_id: str) -> bool:
    """Download photo for bioguide ID if missing, saving to both backend and frontend."""
    if not bio_id:
        return False
    path = PHOTO_DIR / f"{bio_id}.jpg"
    web_path = WEB_PHOTO_DIR / f"{bio_id}.jpg"

    if path.exists() and path.stat().st_size > 500:
        if not web_path.exists() or web_path.stat().st_size != path.stat().st_size:
            try:
                web_path.write_bytes(path.read_bytes())
            except Exception:
                pass
        return True

    urls = []
    if bio_id in SPECIAL_PHOTO_URLS:
        urls.append(SPECIAL_PHOTO_URLS[bio_id])

    urls.extend([
        f"https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/225x275/{bio_id}.jpg",
        f"https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/450x550/{bio_id}.jpg",
        f"https://theunitedstates.io/images/congress/225x275/{bio_id}.jpg",
        f"https://unitedstates.github.io/images/congress/225x275/{bio_id}.jpg",
        f"https://bioguide.congress.gov/photo/{bio_id}.jpg",
    ])

    for url in urls:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = resp.read()
                if len(data) > 500:
                    path.write_bytes(data)
                    web_path.write_bytes(data)
                    print(f"Downloaded photo for {bio_id} ({len(data)} bytes)")
                    return True
        except Exception:
            continue
    return False


def main() -> None:
    session = get_session(get_engine(settings.DATABASE_URL))
    updated = 0
    pols = session.query(Politician).all()

    bios_to_download: set[str] = set()

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
            if pol.party != info.get("party") and info.get("party") in ("D", "R", "I"):
                pol.party = info["party"]
                updated += 1
            if info.get("state") and pol.state != info["state"]:
                pol.state = info["state"]
                updated += 1
            if info.get("district") and pol.district != info["district"]:
                pol.district = info["district"]
                updated += 1
            if info.get("chamber") and pol.chamber != info["chamber"]:
                pol.chamber = info["chamber"]
                updated += 1
            bios_to_download.add(bio_id)
        else:
            if pol.bioguide_id:
                bios_to_download.add(pol.bioguide_id)

    session.commit()
    session.close()

    print(f"Database metadata synchronized ({updated} fields updated).")
    print(f"Checking photos for {len(bios_to_download)} unique politician bioguides...")

    success_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = pool.map(download_photo_if_missing, sorted(bios_to_download))
        for res in results:
            if res:
                success_count += 1

    print(f"\nCompleted! Active photos verified/downloaded: {success_count}/{len(bios_to_download)}")


if __name__ == "__main__":
    main()
