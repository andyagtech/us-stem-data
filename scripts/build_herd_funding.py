#!/usr/bin/env python3
"""Build data/herd/funding_by_university.json from HERD Table 13 xlsx.

Reads:
  data/herd/herd_fy2024_table13.xlsx (sheet: 'Table 13')
  pipeline/universities.json

Writes:
  data/herd/funding_by_university.json

Behavior:
  - Parses HERD R&D values (in thousands of dollars) for years 2010-2024.
  - Matches institutions to internal university keys via:
      1) explicit HERD_ALIAS map keyed by university key (raw HERD strings,
         including any inline footnote letters)
      2) normalized name match against the display name in
         pipeline/universities.json as a fallback
  - HERD inline footnote letters (e.g. "U. Marylandb",
    "U. Tennessee, Knoxvilleg") are stripped from the *display* name only,
    using the alias map as ground truth.
  - Preserves any existing ipeds_finance_fy2023 / ipeds_finance_series
    blocks already present in funding_by_university.json (so this script
    is safe to re-run without losing IPEDS finance enrichment).
"""
import json
import os
import re
import sys

import openpyxl

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERD_XLSX = os.path.join(BASE_DIR, "data/herd/herd_fy2024_table13.xlsx")
OUT_PATH = os.path.join(BASE_DIR, "data/herd/funding_by_university.json")
UNIVERSITIES_JSON = os.path.join(BASE_DIR, "pipeline/universities.json")

YEARS = list(range(2010, 2025))  # 2010..2024 inclusive


# Internal key -> exact RAW HERD institution string (verified against the
# Table 13 xlsx). Some entries include inline footnote letters - those are
# part of the literal HERD cell value and must be matched verbatim.
HERD_ALIAS = {
    # Top R&D universities the user explicitly called out as missing
    "cornell": "Cornell U.",
    "columbia": "Columbia U. in the City of New York",
    "northwestern": "Northwestern U.",
    "penn_state": "Pennsylvania State U., University Park and Hershey Medical Center",
    "cmu": "Carnegie Mellon U.",
    "msu": "Michigan State U.",
    "rice": "Rice U.",
    "umd": "U. Marylandb",
    "uiuc": "U. Illinois, Urbana-Champaign",
    "uw_seattle": "U. Washington, Seattle",
    "uwmadison": "U. Wisconsin-Madison",
    "utk": "U. Tennessee, Knoxvilleg",
    "uutah": "U. Utah",
    "uf": "U. Florida",
    "uva": "U. Virginia, Charlottesville",
    "ncstate": "North Carolina State U.",
    "gmu": "George Mason U.",
    "temple": "Temple U.",
    "la_tech": "Louisiana Tech U.",
    "uoregon": "U. Oregon",
    "wsu": "Washington State U.",
    # Caltech / SIU - regression guards
    "caltech": "California Institute of Technology",
    "siu": "Southern Illinois U., Carbondale",
    # All other universities tracked by the pipeline
    "mit": "Massachusetts Institute of Technology",
    "ucla": "U. California, Los Angeles",
    "ucsd": "U. California, San Diego",
    "uci": "U. California, Irvine",
    "ucirvine": "U. California, Irvine",
    "ucr": "U. California, Riverside",
    "ucriverside": "U. California, Riverside",
    "ucberkeley": "U. California, Berkeley",
    "ucdavis": "U. California, Davis",
    "ucsb": "U. California, Santa Barbara",
    "ucsc": "U. California, Santa Cruz",
    "ucsf": "U. California, San Francisco",
    "ucmerced": "U. California, Merced",
    "uarizona": "U. Arizona",
    "umass": "U. Massachusetts, Amherst",
    "utdallas": "U. Texas, Dallas",
    "utarlington": "U. Texas, Arlington",
    "utaustin": "U. Texas, Austin",
    "umissouri": "U. Missouri, Columbia",
    "usc_columbia": "U. South Carolina, Columbia",
    "unh": "U. New Hampshire",
    "unm": "U. New Mexico",
    "und": "U. North Dakota",
    "usd": "U. South Dakota",
    "ucf": "U. Central Florida",
    "olemiss": "U. Mississippi",
    "umemphis": "U. Memphis",
    "ulouisville": "U. Louisville",
    "ubuffalo": "SUNY, U. Buffalo",
    "uhouston": "U. Houston",
    "washu": "Washington U., Saint Louis",
    "stony_brook": "SUNY, Stony Brook U.",
    "northern_colorado": "U. Northern Colorado",
    "upenn": "U. Pennsylvania",
    "umn": "U. Minnesota, Twin Cities",
    "unl": "U. Nebraska, Lincoln and Medical Centerd",
    "unlv": "U. Nevada, Las Vegas",
    "unt": "U. North Texas, Denton",
    "wvu": "West Virginia U.",
    "ttu": "Texas Tech U.",
    "mines": "Colorado School of Mines",
    "binghamton": "SUNY, Binghamton U.",
    "umt": "U. Montana, Missoula",
    "udenver": "U. Denver",
    "udel": "U. Delaware",
    "usf": "U. South Floridae",
    "usm": "U. Southern Mississippi",
    "cuny": "CUNY, Graduate Center",
    "utah_state": "Utah State U.",
    "gatech": "Georgia Institute of Technology",
    "kstate": "Kansas State U.",
    "iowa_state": "Iowa State U.",
    "msstate": "Mississippi State U.",
    "lsu": "Louisiana State U., Baton Rouge",
    "sdsu": "San Diego State U.",
    "rpi": "Rensselaer Polytechnic Institute",
    "rit": "Rochester Institute of Technology",
    "njit": "New Jersey Institute of Technology",
    "mtu": "Michigan Technological U.",
    "missouri_st": "Missouri U. of Science and Technology",
    "vt": "Virginia Polytechnic Institute and State U.",
    "clemson": "Clemson U.",
    "duke": "Duke U.",
    "stanford": "Stanford U.",
    "harvard": "Harvard U.",
    "yale": "Yale U.",
    "syracuse": "Syracuse U.",
    "dartmouth": "Dartmouth C. and Dartmouth Hitchcock Medical Center",
    "bu": "Boston U.",
    "wayne_state": "Wayne State U.",
    "ukansas": "U. Kansas",
    "uarkansas": "U. Arkansas, Fayetteville",
    "byu": "Brigham Young U., Provo",
    "smu": "Southern Methodist U.",
    "nau": "Northern Arizona U.",
    "marquette": "Marquette U.",
    "niu": "Northern Illinois U.",
    "boise_state": "Boise State U.",
    "pdx": "Portland State U.",
    "purdue": "Purdue U., West Lafayette",
}


# Known HERD inline footnote letter suffixes (extracted from HERD_ALIAS).
# Used to clean the *display* name only - never used for matching.
def clean_display_name(raw: str) -> str:
    """Strip a HERD inline footnote letter from the end of an institution
    name, but only when we recognize the pattern as a footnote rather than a
    real word ending. The conservative rule: a single trailing lowercase
    letter immediately following a longer place name where the previous
    'word' ends in a consonant typically used as a footnote anchor in HERD.

    Rather than guess, we maintain an explicit set of (raw -> clean) entries
    for the few known cases.
    """
    fixups = {
        "U. Marylandb": "U. Maryland, College Park",
        "U. Tennessee, Knoxvilleg": "U. Tennessee, Knoxville",
        "U. South Floridae": "U. South Florida",
        "U. Nebraska, Lincoln and Medical Centerd": "U. Nebraska, Lincoln and Medical Center",
    }
    return fixups.get(raw, raw)


def normalize(name: str) -> str:
    """Aggressive normalization for fallback fuzzy matching."""
    if not name:
        return ""
    s = name.lower()
    s = s.replace("u.", "university")
    s = s.replace(" c.", " college")
    s = s.replace("inst.", "institute")
    s = s.replace("&", "and")
    s = re.sub(r"[^\w\s]", " ", s)
    tokens = [
        t for t in s.split()
        if t not in {"university", "the", "of", "at", "in", "and", "for"}
    ]
    return " ".join(tokens)


def parse_herd():
    """Return list of (raw_name, rank, {year: value_thousands}) for every
    HERD institution row."""
    wb = openpyxl.load_workbook(HERD_XLSX, data_only=True)
    ws = wb["Table 13"]
    # Header at row 4. Year columns are 3,5,7,...,31 -> 2010..2024
    year_cols = list(range(3, 3 + 2 * len(YEARS), 2))
    out = []
    for r in range(5, ws.max_row + 1):
        raw_name = ws.cell(row=r, column=1).value
        if not raw_name:
            continue
        name = raw_name.strip()
        if name.lower().startswith("all institutions"):
            continue
        rank_val = ws.cell(row=r, column=2).value
        try:
            rank = int(rank_val) if rank_val not in (None, "-", "") else None
        except (TypeError, ValueError):
            rank = None
        rd = {}
        for y, col in zip(YEARS, year_cols):
            v = ws.cell(row=r, column=col).value
            if v is None or v == "":
                continue
            try:
                rd[str(y)] = int(round(float(v)))
            except (TypeError, ValueError):
                continue
        out.append((name, rank, rd))
    return out


def main():
    if not os.path.exists(HERD_XLSX):
        print(f"ERROR: HERD xlsx not found: {HERD_XLSX}", file=sys.stderr)
        sys.exit(1)

    universities = json.load(open(UNIVERSITIES_JSON))
    herd_rows = parse_herd()
    print(f"Parsed {len(herd_rows)} HERD institutions")

    # Build lookups (raw exact, normalized fallback)
    by_raw = {raw: i for i, (raw, _r, _rd) in enumerate(herd_rows)}
    by_norm = {}
    for i, (raw, _r, _rd) in enumerate(herd_rows):
        by_norm.setdefault(normalize(raw), i)

    # Sanity-check the alias map: any aliases that don't match a HERD row?
    bad_aliases = [
        (k, v) for k, v in HERD_ALIAS.items() if v not in by_raw
    ]
    if bad_aliases:
        print("WARN: alias map contains entries not found in HERD xlsx:")
        for k, v in bad_aliases:
            print(f"  {k} -> {v!r}")

    # Load existing JSON to preserve IPEDS finance blocks
    existing = {}
    if os.path.exists(OUT_PATH):
        existing = json.load(open(OUT_PATH))

    out = {}
    matched = 0
    matched_via_alias = 0
    matched_via_norm = 0
    unmatched = []
    for key, info in universities.items():
        display = info.get("name") if isinstance(info, dict) else info

        idx = None
        # 1) alias map
        alias = HERD_ALIAS.get(key)
        if alias and alias in by_raw:
            idx = by_raw[alias]
            matched_via_alias += 1
        # 2) normalized fallback against display name from universities.json
        if idx is None and display:
            norm_d = normalize(display)
            if norm_d in by_norm:
                idx = by_norm[norm_d]
                matched_via_norm += 1

        if idx is None:
            unmatched.append((key, display))
            if key in existing:
                out[key] = existing[key]
            continue

        raw, rank, rd = herd_rows[idx]
        record = {
            "name": clean_display_name(raw),
            "rank": rank,
            "yearly_rd_thousands": rd,
        }
        prior = existing.get(key, {})
        for k in ("ipeds_finance_fy2023", "ipeds_finance_series"):
            if k in prior:
                record[k] = prior[k]
        out[key] = record
        matched += 1

    # Stable sort: by rank then by key
    def sort_key(item):
        rk = item[1].get("rank")
        return (rk if rk is not None else 10**9, item[0])
    out_sorted = dict(sorted(out.items(), key=sort_key))

    with open(OUT_PATH, "w") as f:
        json.dump(out_sorted, f, indent=2)

    print(f"Matched {matched}/{len(universities)} universities "
          f"(alias={matched_via_alias}, normalized={matched_via_norm})")
    print(f"Wrote {OUT_PATH} with {len(out_sorted)} entries")
    if unmatched:
        print(f"\nUNMATCHED ({len(unmatched)}):")
        for k, n in unmatched:
            print(f"  {k}\t{n}")


if __name__ == "__main__":
    main()
