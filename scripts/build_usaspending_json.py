#!/usr/bin/env python3
"""
Build per-university USAspending federal awards JSON from the
top_university_grants.csv export.

Output: data/usaspending/usaspending_by_university.json
Format: {key: {total_grants: float, rank: int, source_name: str}}

The source CSV uses legal-entity names (e.g., "REGENTS OF THE UNIVERSITY
OF MICHIGAN"). Manual mapping below covers our 101 university keys.
"""
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "usaspending" / "top_university_grants.csv"
OUT_PATH = ROOT / "data" / "usaspending" / "usaspending_by_university.json"

# Map USAspending legal entity name → our university key.
# Names are uppercased, no other normalization. We compare case-insensitively
# below. Only entries that map to one of our 101 universities are included.
LEGAL_NAME_TO_KEY = {
    "REGENTS OF THE UNIVERSITY OF MICHIGAN": "umich",
    "THE JOHNS HOPKINS UNIVERSITY": "jhu",
    "REGENTS OF THE UNIVERSITY OF CALIFORNIA, SAN FRANCISCO, THE": "ucsf",
    "TRUSTEES OF THE UNIVERSITY OF PENNSYLVANIA, THE": "upenn",
    "WASHINGTON UNIVERSITY, THE": "washu",
    "REGENTS OF THE UNIVERSITY OF MINNESOTA": "umn",
    "UNIVERSITY OF FLORIDA": "uf",
    "NORTHWESTERN UNIVERSITY": "northwestern",
    "OREGON HEALTH & SCIENCE UNIVERSITY": "ohsu",  # not in our 101 → drop
    "UNIVERSITY OF UTAH": "uutah",
    "UNIVERSITY OF MARYLAND, COLLEGE PARK": "umd",
    "RECTOR & VISITORS OF THE UNIVERSITY OF VIRGINIA": "uva",
    "CORNELL UNIVERSITY": "cornell",
    "MICHIGAN STATE UNIVERSITY": "msu",
    "PURDUE UNIVERSITY": "purdue",
    "THE LELAND STANFORD JUNIOR UNIVERSITY": "stanford",
    "DUKE UNIVERSITY": "duke",
    "THE TRUSTEES OF COLUMBIA UNIVERSITY IN THE CITY OF NEW YORK": "columbia",
    "PENNSYLVANIA STATE UNIVERSITY, THE": "penn_state",
    "UNIVERSITY OF WASHINGTON": "uw_seattle",
    "UNIVERSITY OF CALIFORNIA, SAN DIEGO": "ucsd",
    "UNIVERSITY OF PITTSBURGH - OF THE COMMONWEALTH SYSTEM OF HIGHER EDUCATION": "pitt",
    "UNIVERSITY OF WISCONSIN SYSTEM": "uwmadison",
    "UNIVERSITY OF NORTH CAROLINA AT CHAPEL HILL": "unc",
    "UNIVERSITY OF CALIFORNIA, LOS ANGELES": "ucla",
    "EMORY UNIVERSITY": "emory",
    "UNIVERSITY OF SOUTHERN CALIFORNIA": "usc_la",
    "UNIVERSITY OF TEXAS AT AUSTIN": "utaustin",
    "NEW YORK UNIVERSITY": "nyu",
    "REGENTS OF THE UNIVERSITY OF CALIFORNIA, BERKELEY, THE": "ucberkeley",
    "REGENTS OF THE UNIVERSITY OF CALIFORNIA, DAVIS, THE": "ucdavis",
    "REGENTS OF THE UNIVERSITY OF CALIFORNIA, IRVINE, THE": "ucirvine",
    "REGENTS OF THE UNIVERSITY OF CALIFORNIA, RIVERSIDE, THE": "ucriverside",
    "REGENTS OF THE UNIVERSITY OF CALIFORNIA, SANTA BARBARA, THE": "ucsb",
    "REGENTS OF THE UNIVERSITY OF CALIFORNIA, SANTA CRUZ, THE": "ucsc",
    "REGENTS OF THE UNIVERSITY OF CALIFORNIA, MERCED, THE": "ucmerced",
    "MASSACHUSETTS INSTITUTE OF TECHNOLOGY": "mit",
    "PRESIDENT AND FELLOWS OF HARVARD COLLEGE": "harvard",
    "YALE UNIVERSITY": "yale",
    "TRUSTEES OF DARTMOUTH COLLEGE, THE": "dartmouth",
    "TRUSTEES OF PRINCETON UNIVERSITY, THE": "princeton",
    "BROWN UNIVERSITY IN PROVIDENCE IN THE STATE OF RHODE ISLAND AND PROVIDENCE PLANTATIONS": "brown",
    "WILLIAM MARSH RICE UNIVERSITY": "rice",
    "VANDERBILT UNIVERSITY": "vanderbilt",
    "BAYLOR COLLEGE OF MEDICINE": "baylor_med",
    "GEORGIA TECH RESEARCH CORPORATION": "gatech",
    "GEORGIA INSTITUTE OF TECHNOLOGY": "gatech",
    "CARNEGIE MELLON UNIVERSITY": "cmu",
    "BOSTON UNIVERSITY": "bu",
    "BOSTON COLLEGE": "bc",
    "NORTH CAROLINA STATE UNIVERSITY": "ncstate",
    "RUTGERS, THE STATE UNIVERSITY OF NEW JERSEY": "rutgers",
    "OHIO STATE UNIVERSITY, THE": "osu",
    "UNIVERSITY OF ILLINOIS": "uiuc",
    "BOARD OF TRUSTEES OF THE UNIVERSITY OF ILLINOIS, THE": "uiuc",
    "UNIVERSITY OF ARIZONA": "uarizona",
    "ARIZONA BOARD OF REGENTS": "uarizona",
    "TEXAS A&M UNIVERSITY": "tamu",
    "TEXAS A&M ENGINEERING EXPERIMENT STATION": "tamu",
    "BAYLOR UNIVERSITY": "baylor",
    "UNIVERSITY OF SOUTH FLORIDA": "usf",
    "UNIVERSITY OF MIAMI": "umiami",
    "UNIVERSITY OF KANSAS": "ukansas",
    "UNIVERSITY OF KANSAS CENTER FOR RESEARCH, INC": "ukansas",
    "UNIVERSITY OF MASSACHUSETTS": "umass",
    "GEORGE WASHINGTON UNIVERSITY, THE": "gwu",
    "GEORGETOWN UNIVERSITY": "georgetown",
    "TUFTS UNIVERSITY": "tufts",
    "CASE WESTERN RESERVE UNIVERSITY": "case_western",
    "UNIVERSITY OF NOTRE DAME DU LAC": "notre_dame",
    "UNIVERSITY OF IOWA, THE": "uiowa",
    "IOWA STATE UNIVERSITY OF SCIENCE AND TECHNOLOGY": "iowa_state",
    "UNIVERSITY OF NEBRASKA": "unl",
    "UNIVERSITY OF CONNECTICUT": "uconn",
    "UNIVERSITY OF NEW MEXICO, THE": "unm",
    "VIRGINIA POLYTECHNIC INSTITUTE AND STATE UNIVERSITY": "vt",
    "OREGON STATE UNIVERSITY": "ou_oregon",  # not in 101
    "UNIVERSITY OF OREGON": "uoregon",
    "UNIVERSITY OF KENTUCKY": "uky",
    "UNIVERSITY OF DELAWARE": "udel",
    "WAYNE STATE UNIVERSITY": "wayne_state",
    "UNIVERSITY OF NEW HAMPSHIRE": "unh",
    "WEST VIRGINIA UNIVERSITY": "wvu",
    "UNIVERSITY OF SOUTH CAROLINA - COLUMBIA": "usc_columbia",
    "UNIVERSITY OF VERMONT AND STATE AGRICULTURAL COLLEGE": "uvm",
    "STATE UNIVERSITY OF NEW YORK AT STONY BROOK": "stony_brook",
    "STATE UNIVERSITY OF NEW YORK AT BUFFALO": "ubuffalo",
    "BINGHAMTON UNIVERSITY": "binghamton",
    "RUTGERS UNIVERSITY": "rutgers",
    "TEMPLE UNIVERSITY OF THE COMMONWEALTH SYSTEM OF HIGHER EDUCATION": "temple",
    "DREXEL UNIVERSITY": "drexel",
    "UNIVERSITY OF ROCHESTER": "u_rochester",
    "INDIANA UNIVERSITY": "indiana",
    "INDIANA UNIVERSITY BLOOMINGTON": "indiana",
}


def main():
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found")
        return 1

    raw = []
    with open(CSV_PATH) as f:
        for r in csv.DictReader(f):
            try:
                raw.append((r["name"].strip(), float(r["total_grants"])))
            except Exception:
                continue

    # Dedupe by name (CSV has duplicates) — keep max
    by_name = {}
    for name, total in raw:
        if name not in by_name or by_name[name] < total:
            by_name[name] = total

    # Load known university keys
    keys_path = ROOT / "site" / "data" / "stem"
    if not keys_path.is_dir():
        print(f"ERROR: {keys_path} not found")
        return 1
    valid_keys = set()
    for fp in keys_path.glob("*.json"):
        if fp.name.startswith("_"):
            continue
        try:
            d = json.loads(fp.read_text())
            if isinstance(d, dict) and "key" in d:
                valid_keys.add(d["key"])
        except Exception:
            pass

    # Map USAspending entries to our keys
    out = {}
    sorted_records = sorted(by_name.items(), key=lambda x: -x[1])
    rank_within_top = 0
    for name, total in sorted_records:
        rank_within_top += 1
        key = LEGAL_NAME_TO_KEY.get(name)
        if not key:
            continue
        if key not in valid_keys:
            continue
        if key not in out:
            out[key] = {
                "total_grants": total,
                "rank": rank_within_top,
                "source_name": name,
            }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2))

    matched_keys = set(out.keys())
    print(f"USAspending raw entries: {len(raw)}")
    print(f"Unique entities: {len(by_name)}")
    print(f"Mapped to our universities: {len(out)} of 101")
    unmapped_top = [
        (n, t) for n, t in sorted_records[:30]
        if LEGAL_NAME_TO_KEY.get(n) not in valid_keys
    ]
    if unmapped_top:
        print()
        print("Top unmapped (could add to LEGAL_NAME_TO_KEY if matters):")
        for n, t in unmapped_top[:10]:
            print(f"  ${t/1e9:.2f}B  {n}")
    print()
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
