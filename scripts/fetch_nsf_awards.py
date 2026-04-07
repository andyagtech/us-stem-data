#!/usr/bin/env python3
"""Fetch NSF Award Search data for 101 PhD Demographics universities.

Queries the NSF Award Search API for awards dated 2020-01-01 through
2024-12-31 for each university, aggregates by year, and writes
nsf_by_university.json.

API docs: https://www.research.gov/common/webapi/awardapisearch-v1.htm
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict

STEM_DIR = "/Users/andy/usds_china/site/data/stem"
ENTITY_MAP_PATH = "/Users/andy/usds_china/pipeline/entity_map.json"
OUT_DIR = "/Users/andy/usds_china/data/state_funding/nsf_awards"
OUT_PATH = os.path.join(OUT_DIR, "nsf_by_university.json")
RAW_DIR = os.path.join(OUT_DIR, "raw")

API = "https://api.nsf.gov/services/v1/awards.json"
DATE_START = "01/01/2020"
DATE_END = "12/31/2024"
YEARS = ["2020", "2021", "2022", "2023", "2024"]
RPP = 25  # results per page (NSF default/max for this endpoint)
SLEEP_SECS = 1.0
PRINT_FIELDS = "id,date,fundsObligatedAmt,awardeeName,piFirstName,piLastName,title"


def load_keys() -> list[str]:
    keys = []
    for f in sorted(os.listdir(STEM_DIR)):
        if f.endswith(".json") and not f.startswith("_"):
            keys.append(os.path.splitext(f)[0])
    return keys


def build_key_to_canonical() -> dict[str, list[str]]:
    em = json.load(open(ENTITY_MAP_PATH))
    rev: dict[str, list[str]] = {}
    for full, key in em.items():
        rev.setdefault(key, []).append(full)
    return rev


def pick_primary_name(candidates: list[str]) -> str:
    """Pick the best NSF query name.

    Prefer the first non-abbreviated variant that contains 'UNIVERSITY',
    'INSTITUTE', 'COLLEGE', or 'SCHOOL'. Fall back to the first entry.
    """
    # Filter out truncated (ends with space) and very short abbreviations
    cleaned = [c.strip() for c in candidates if c.strip()]
    # Prefer ones with full words
    good_words = ("UNIVERSITY", "INSTITUTE", "COLLEGE", "SCHOOL")
    preferred = [
        c for c in cleaned
        if any(w in c for w in good_words)
        and not c.endswith(" UNIV")
        and not c.endswith(" INST")
    ]
    if preferred:
        # Prefer the longest/most specific that isn't truncated-looking
        preferred.sort(key=lambda c: (-len(c), c))
        # Pick the one with most characters but not oddly abbreviated
        for p in preferred:
            if "UNIV" in p and "UNIVERSITY" not in p:
                continue
            return p
        return preferred[0]
    return cleaned[0]


# Manual overrides for awkward cases.
# These names were verified by probing the NSF Award Search API directly;
# they are the exact awardeeName strings NSF uses.
NAME_OVERRIDES = {
    "mit": "Massachusetts Institute of Technology",
    "caltech": "California Institute of Technology",
    "cmu": "Carnegie Mellon University",
    "columbia": "Columbia University",
    "cornell": "Cornell University",
    "cuny": "CUNY Graduate School University Center",
    "duke": "Duke University",
    "harvard": "Harvard University",
    "mines": "Colorado School of Mines",
    "missouri_st": "Missouri University of Science and Technology",
    "njit": "New Jersey Institute of Technology",
    "binghamton": "SUNY at Binghamton",
    # Previously broken: pick_primary_name was selecting the legal/long name
    # from entity_map.json which NSF does not index under.
    "stanford": "Stanford University",
    "ucberkeley": "University of California-Berkeley",
    "ucla": "University of California-Los Angeles",
    "ucdavis": "University of California-Davis",
    "ucirvine": "University of California-Irvine",
    "ucmerced": "University of California-Merced",
    "ucriverside": "University of California-Riverside",
    "ucsb": "University of California-Santa Barbara",
    "ucsc": "University of California-Santa Cruz",
    "ucsf": "University of California-San Francisco",
    "gatech": "Georgia Tech Research Corporation",
    "penn_state": "Pennsylvania State Univ University Park",
    "purdue": "Purdue University",
    "iowa_state": "Iowa State University",
    "lsu": "Louisiana State University",
    "msu": "Michigan State University",
    "stony_brook": "SUNY at Stony Brook",
    "ubuffalo": "SUNY at Buffalo",
    "syracuse": "Syracuse University",
    "rit": "Rochester Institute of Tech",
    "ttu": "Texas Tech University",
    "uhouston": "University of Houston",
    "uiuc": "University of Illinois at Urbana-Champaign",
    "umissouri": "University of Missouri-Columbia",
    "umt": "University of Montana",
    "utarlington": "University of Texas at Arlington",
    "utdallas": "University of Texas at Dallas",
    "utk": "University of Tennessee Knoxville",
    "uwmadison": "University of Wisconsin-Madison",
    "washu": "Washington University",
}

# Extra state-code disambiguation for cases where the NSF awardeeName is
# not unique across institutions (e.g., "Washington University" matches
# several schools; filter to MO to keep only WashU in St. Louis).
STATE_FILTER = {
    "washu": "MO",
}


def fetch_page(awardee: str, offset: int, state_code: str | None = None) -> list[dict]:
    params = {
        "awardeeName": f'"{awardee}"',
        "dateStart": DATE_START,
        "dateEnd": DATE_END,
        "printFields": PRINT_FIELDS,
        "offset": offset,
        "rpp": RPP,
    }
    if state_code:
        params["awardeeStateCode"] = state_code
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "usds-china-research/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    return data.get("response", {}).get("award", []) or []


def fetch_all_awards(awardee: str, state_code: str | None = None) -> list[dict]:
    all_awards: list[dict] = []
    offset = 1
    while True:
        try:
            page = fetch_page(awardee, offset, state_code)
        except Exception as e:
            print(f"  ERROR page offset={offset}: {e}", file=sys.stderr)
            time.sleep(3)
            try:
                page = fetch_page(awardee, offset, state_code)
            except Exception as e2:
                print(f"  RETRY failed: {e2}", file=sys.stderr)
                break
        if not page:
            break
        all_awards.extend(page)
        if len(page) < RPP:
            break
        offset += RPP
        time.sleep(SLEEP_SECS)
        # safety cap
        if offset > 20000:
            print(f"  WARN: hit offset cap for {awardee}", file=sys.stderr)
            break
    return all_awards


def aggregate(awards: list[dict]) -> dict:
    by_year: dict[str, dict] = {y: {"award_count": 0, "total_obligated": 0} for y in YEARS}
    total_awards = 0
    total_obligated = 0
    for a in awards:
        date = a.get("date", "")  # MM/DD/YYYY
        if not date or len(date) < 10:
            continue
        year = date[-4:]
        if year not in by_year:
            continue
        try:
            amt = float(a.get("fundsObligatedAmt") or 0)
        except (TypeError, ValueError):
            amt = 0.0
        by_year[year]["award_count"] += 1
        by_year[year]["total_obligated"] += amt
        total_awards += 1
        total_obligated += amt
    # cast totals to int (dollars)
    for y in by_year:
        by_year[y]["total_obligated"] = int(round(by_year[y]["total_obligated"]))
    return {
        "by_year": by_year,
        "total_awards": total_awards,
        "total_obligated_5yr": int(round(total_obligated)),
    }


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    keys = load_keys()
    rev = build_key_to_canonical()

    # Load existing progress if present
    if os.path.exists(OUT_PATH):
        results = json.load(open(OUT_PATH))
    else:
        results = {}

    print(f"Processing {len(keys)} universities...")

    for i, key in enumerate(keys, 1):
        if key in results and results[key].get("total_awards") is not None:
            print(f"[{i}/{len(keys)}] {key}: already fetched, skipping")
            continue

        query_name = NAME_OVERRIDES.get(key) or pick_primary_name(rev[key])
        state_code = STATE_FILTER.get(key)
        suffix = f" (state={state_code})" if state_code else ""
        print(f"[{i}/{len(keys)}] {key}: querying '{query_name}'{suffix}")

        awards = fetch_all_awards(query_name, state_code)
        # Also include the "appears_as" names we observed (dedupe on id)
        names_seen = {a.get("awardeeName") for a in awards}

        agg = aggregate(awards)
        results[key] = {
            "name": query_name,
            "appears_as": sorted(n for n in names_seen if n),
            **agg,
        }
        print(
            f"  awards={agg['total_awards']} "
            f"obligated=${agg['total_obligated_5yr']:,}"
        )

        # Save raw per-university for audit
        with open(os.path.join(RAW_DIR, f"{key}.json"), "w") as fh:
            json.dump(awards, fh, indent=2)

        # Incremental save
        with open(OUT_PATH, "w") as fh:
            json.dump(results, fh, indent=2)

        time.sleep(SLEEP_SECS)

    print(f"\nDone. Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
