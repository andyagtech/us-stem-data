#!/usr/bin/env python3
"""Match Build Fellowship employers to their own H-1B filings.

A fellow holds a cap-exempt petition through the nonprofit while working for
a private company. That company is named in the fellow's bio and nowhere in
any government file. Matching those names to the USCIS H-1B Employer Data Hub
shows whether the same firms also petition directly -- and in particular
whether they file CONCURRENT petitions, the mechanism that lets one worker
hold two H-1Bs at once.

WHAT A MATCH MEANS. That a firm of this name filed H-1B petitions. It does
NOT show that any Build fellow is among them: no published source links a
named worker to a petition. Concurrent approvals at these employers are
consistent with the arrangement and are not evidence of it.

Names come from prose, so matching is conservative: exact on a normalised
name, or a single unambiguous containment. A name matching several employers
is left unmatched rather than assigned to the largest.

Usage:
  python3 scripts/join_fellowship_employers.py
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "data" / "buildfellowship" / "projects.json"
HUB = ROOT / "data" / "h1b"
OUT = ROOT / "data" / "buildfellowship" / "employer_h1b.json"

YEARS = (2023, 2024, 2025, 2026)
LEGACY = {"name": 1, "naics": 6, "state": 8, "new": 2, "cont": 4, "min": 9}
MODERN = {"name": 2, "naics": 4, "state": 6, "new": 8, "cont": 10,
          "concurrent": 14, "min": 15}

# "THE" is NOT stripped. Removing it made "Citadel" an exact match for "THE
# CITADEL" -- the military college in South Carolina, NAICS 61 Educational
# Services -- and put a trading firm's fellow at a state military academy.
NOISE = re.compile(r"\b(INC|LLC|LTD|CORP|CORPORATION|CO|COMPANY|LP|LLP|PLC|"
                   r"HOLDINGS|GROUP|TECHNOLOGIES|TECHNOLOGY|LABS)\b")


def norm(s: str) -> str:
    s = s.upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = NOISE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def hub_rows(path: Path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text, delim, L = raw.decode("utf-16", "replace"), "\t", MODERN
    else:
        text, delim, L = raw.decode("latin-1", "replace"), ",", LEGACY
    r = csv.reader(io.StringIO(text), delimiter=delim)
    next(r, None)
    for row in r:
        if len(row) >= L["min"]:
            yield row, L


def num(x: str) -> int:
    x = (x or "").replace(",", "").strip()
    return int(x) if x.isdigit() else 0


def main() -> int:
    if not PROJECTS.exists():
        print("  no projects.json; run the scraper first")
        return 1
    doc = json.loads(PROJECTS.read_text())
    employers = [e["name"] for e in doc["employers"]]
    counts = {e["name"]: e["projects"] for e in doc["employers"]}

    # Index the hub by normalised employer name.
    hub: dict[str, dict] = defaultdict(
        lambda: {"new": 0, "cont": 0, "concurrent": 0, "years": set(),
                 "naics": None, "state": None, "spellings": set()})
    for year in YEARS:
        p = HUB / f"h1b_datahub_fy{year}.csv"
        if not p.exists():
            continue
        for row, L in hub_rows(p):
            name = row[L["name"]].strip().strip('"')
            if not name:
                continue
            k = norm(name)
            if not k:
                continue
            rec = hub[k]
            rec["new"] += num(row[L["new"]])
            rec["cont"] += num(row[L["cont"]])
            if "concurrent" in L:
                rec["concurrent"] += num(row[L["concurrent"]])
            rec["years"].add(year)
            rec["naics"] = rec["naics"] or (row[L["naics"]] or "").strip().strip('"')
            rec["state"] = rec["state"] or row[L["state"]]
            rec["spellings"].add(name)

    matched, unmatched, ambiguous = [], [], []
    keys = list(hub)
    for emp in employers:
        k = norm(emp)
        if not k:
            unmatched.append(emp)
            continue
        # A single word is too generic to match on: "Citadel", "Lob",
        # "Everlaw" alone could be any number of filers. Require two tokens
        # unless the exact normalised string is present in the hub.
        if k in hub:
            hits = [k]
        elif len(k.split()) < 2:
            unmatched.append(emp)
            continue
        else:
            # One unambiguous containment, or nothing. Assigning a name that
            # matches several employers to the biggest would be a guess.
            hits = [h for h in keys if h.startswith(k + " ") or k.startswith(h + " ")]
        if len(hits) != 1:
            (ambiguous if len(hits) > 1 else unmatched).append(emp)
            continue
        r = hub[hits[0]]
        matched.append({
            "employer": emp,
            "fellowship_projects": counts.get(emp, 0),
            "hub_name": sorted(r["spellings"])[0],
            "state": r["state"], "naics": r["naics"],
            "new_employment": r["new"], "continuation": r["cont"],
            "concurrent": r["concurrent"],
            "approvals": r["new"] + r["cont"],
            "years_present": sorted(r["years"]),
        })
    # Two bio spellings can resolve to one hub employer ("Dream Venture Labs"
    # and "Dream Venture Lab"). Merge them, or the same approvals are counted
    # twice in any total.
    merged: dict[str, dict] = {}
    for m in matched:
        key = m["hub_name"]
        if key in merged:
            merged[key]["employer"] += f" / {m['employer']}"
            merged[key]["fellowship_projects"] += m["fellowship_projects"]
        else:
            merged[key] = m
    matched = sorted(merged.values(), key=lambda m: -m["approvals"])

    # A rate means nothing without a base rate. 76% of these firms filing
    # concurrent petitions sounds damning until you know what share of all
    # employers do. Computed over the same years and the same size band, so
    # the comparison is like for like.
    CONC_YEARS = [y for y in YEARS if y >= 2024]   # the column exists from FY2024
    allf: dict[str, dict] = defaultdict(lambda: {"appr": 0, "conc": 0})
    for year in CONC_YEARS:
        p2 = HUB / f"h1b_datahub_fy{year}.csv"
        if not p2.exists():
            continue
        for row, L in hub_rows(p2):
            if "concurrent" not in L:
                continue
            k = norm(row[L["name"]])
            if not k:
                continue
            a = allf[k]
            a["appr"] += num(row[L["new"]]) + num(row[L["cont"]])
            a["conc"] += num(row[L["concurrent"]])
    mine_keys = {norm(m["hub_name"]) for m in matched}
    mine = [allf[k] for k in mine_keys if k in allf]
    mine_c = [v for v in mine if v["conc"]]
    baseline = None
    if mine:
        lo = min(v["appr"] for v in mine)
        hi = max(v["appr"] for v in mine)
        band = [v for v in allf.values() if lo <= v["appr"] <= hi]
        band_c = [v for v in band if v["conc"]]
        baseline = {
            "years": CONC_YEARS,
            "approval_band": [lo, hi],
            "fellowship_employers": len(mine),
            "fellowship_with_concurrent": len(mine_c),
            "fellowship_rate_pct": round(100 * len(mine_c) / len(mine), 1),
            "all_employers_in_band": len(band),
            "all_with_concurrent": len(band_c),
            "all_rate_pct": round(100 * len(band_c) / len(band), 2),
            "ratio": round((len(mine_c) / len(mine)) / (len(band_c) / len(band)), 1),
            "caveat": ("These firms were identified BECAUSE they host fellows, "
                       "so some association is expected. The gap is far larger "
                       "than selection alone would produce, but this is an "
                       "association: no source links a named worker to a "
                       "petition, and a concurrent approval at one of these "
                       "employers is not evidence that a fellow holds it."),
        }

    OUT.write_text(json.dumps({
        "_comment": ("Build Fellowship employers matched to the USCIS H-1B "
                     "Employer Data Hub. A match means a firm of that name "
                     "filed H-1B petitions; it does NOT show that any fellow "
                     "is among them, and no published source links a named "
                     "worker to a petition. Employer names come from bio "
                     "prose, so matching is exact on a normalised name or a "
                     "single unambiguous containment; anything matching "
                     "several employers is left unmatched."),
        "hub_years": list(YEARS),
        "employers_named": len(employers),
        "matched": len(matched),
        "ambiguous": ambiguous,
        "unmatched": unmatched,
        "concurrent_baseline": baseline,
        "employers": matched,
    }, indent=1) + "\n")

    tot = sum(m["approvals"] for m in matched)
    conc = sum(m["concurrent"] for m in matched)
    print(f"  {len(employers)} employers named in bios")
    print(f"  matched to the hub: {len(matched)}   ambiguous: {len(ambiguous)}   "
          f"unmatched: {len(unmatched)}")
    print(f"  their H-1B approvals FY{YEARS[0]}-FY{YEARS[-1]}: {tot:,}"
          f"   of which concurrent: {conc:,}")
    print(f"  {'employer':34}{'proj':>5}{'approvals':>11}{'concurrent':>12}  state")
    for m in matched[:16]:
        print(f"  {m['employer'][:34]:34}{m['fellowship_projects']:>5}"
              f"{m['approvals']:>11,}{m['concurrent']:>12,}  {m['state']}")
    if baseline:
        b = baseline
        print(f"  concurrent-employment petitions, FY{b['years'][0]}-FY{b['years'][-1]}:")
        print(f"   fellowship employers: {b['fellowship_with_concurrent']} of "
              f"{b['fellowship_employers']} ({b['fellowship_rate_pct']}%)")
        print(f"   all employers, {b['approval_band'][0]}-{b['approval_band'][1]} "
              f"approvals: {b['all_with_concurrent']:,} of {b['all_employers_in_band']:,} "
              f"({b['all_rate_pct']}%)")
        print(f"   ratio: {b['ratio']}x")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
