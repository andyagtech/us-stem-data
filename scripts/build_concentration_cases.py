#!/usr/bin/env python3
"""Departments that are sustainedly majority non-resident, with taxpayer context.

WHAT THIS IS FOR

The site's landing page needs to state its finding in the first screen, to a
reader who will not scroll. This builds that finding's evidence: individual
institution-and-field cells where non-resident students take the large majority
of research doctorates, year after year, on cohorts big enough to mean
something.

WHAT COUNTS AS A CASE -- and why each threshold is here

  cohort >= 80 doctorates over 2015-2022   A 100% share on a cohort of three is
                                           noise. Eighty over eight years is a
                                           real program.
  >= 8 doctorates in a year to count it    Same reason, applied per year.
  >= 70% non-resident in >= 6 of 8 years   Sustained, not a single unusual
                                           cohort. Six of eight cannot be a blip.

These are deliberately conservative. Loosening any of them produces a longer
list that is easier to attack, which is the opposite of useful.

WHAT THIS DOES AND DOES NOT SHOW

It shows composition: who received the degrees. Taxpayer money funds these
programs, so the public has a straightforward interest in who the output goes
to, and that interest does not depend on any claim about displacement.

It does NOT show displacement, and the data actively argues against that
reading. Across core STEM between 2012 and 2025, total research doctorates rose
about a third and DOMESTIC research doctorates rose about a third alongside
them -- they moved together. Master's more than doubled. The number of seats
was not fixed and domestic participation did not fall. Anyone presenting these
cases as Americans being pushed out will be corrected by four columns of the
same public file this script reads.

The honest and stronger claim is about public investment and its return: these
particular programs, funded by federal research dollars, produce doctorates
that go overwhelmingly to non-residents, and have done so consistently for
most of a decade.

Usage:
    python3 scripts/build_concentration_cases.py
    python3 scripts/build_concentration_cases.py --out site/data/concentration_cases.json
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "ipeds" / "nra_index.csv.gz"
REGISTRY = ROOT / "pipeline" / "universities.json"
CIP_TITLES = ROOT / "data" / "ipeds" / "cip_titles.csv"
DEFAULT_OUT = ROOT / "site" / "data" / "concentration_cases.json"

YEAR_LO, YEAR_HI = 2015, 2022
MIN_COHORT = 80         # doctorates across the whole window
MIN_YEAR_N = 8          # doctorates in a year for that year to count
HIGH_MARK = 70.0        # "majority non-resident" threshold, in percent
MIN_HIGH_YEARS = 6      # of the eight


def institution_names() -> dict[str, str]:
    """UNITID -> name, from the newest IPEDS directory file available."""
    names: dict[str, str] = {}
    files = sorted(glob.glob(str(ROOT / "data" / "ipeds" / "hd*.csv")))
    if not files:
        return names
    with open(files[-1], newline="", encoding="utf-8-sig", errors="replace") as fh:
        for row in csv.DictReader(fh):
            uid = (row.get("UNITID") or "").strip()
            if uid:
                names[uid] = (row.get("INSTNM") or "").strip()
    return names


def cip_titles() -> dict[str, str]:
    titles: dict[str, str] = {}
    if not CIP_TITLES.exists():
        return titles
    with open(CIP_TITLES, newline="", encoding="utf-8-sig", errors="replace") as fh:
        for row in csv.DictReader(fh):
            code = (row.get("cipcode") or row.get("CIPCODE") or "").strip()
            title = (row.get("title") or row.get("TITLE") or "").strip()
            if code and title:
                titles.setdefault(code.split(".")[0].zfill(2), title)
    return titles


def national_context():
    """Total and domestic core-STEM awards, first and last year, both levels.

    Carried in the output so the page cannot show the cases without the
    context that stops them being misread.
    """
    narrow = {"11", "14", "15", "26", "27", "30", "40", "42"}
    files: dict[int, str] = {}
    for path in glob.glob(str(ROOT / "data" / "ipeds" / "*_a*.csv")):
        m = re.search(r"c(\d{4})_a", os.path.basename(path).lower())
        if not m:
            continue
        year = int(m.group(1))
        if year not in files or "_rv" in path:
            files[year] = path

    out: dict[str, dict] = {}
    for level, name in (("17", "doctorate"), ("7", "masters")):
        series = {}
        for year in sorted(files):
            if year < 2012:
                continue
            tot = nra = 0
            try:
                with open(files[year], newline="", encoding="utf-8-sig",
                          errors="replace") as fh:
                    for row in csv.DictReader(fh):
                        if (row.get("AWLEVEL") or "").lstrip("0") != level:
                            continue
                        cip = (row.get("CIPCODE") or "").split(".")[0].zfill(2)
                        if cip not in narrow:
                            continue
                        tot += int(row.get("CTOTALT") or 0)
                        nra += int(row.get("CNRALT") or 0)
                except_ = None
            except (OSError, ValueError):
                continue
            if tot:
                series[year] = {"total": tot, "nra": nra, "domestic": tot - nra}
        if series:
            years = sorted(series)
            first, last = series[years[0]], series[years[-1]]
            out[name] = {
                "first_year": years[0], "last_year": years[-1],
                "total_change_pct": round(100 * (last["total"] - first["total"])
                                          / first["total"], 1),
                "domestic_change_pct": round(100 * (last["domestic"] - first["domestic"])
                                             / first["domestic"], 1),
                "series": series,
            }
    return out


def build():
    if not INDEX.exists():
        sys.exit(f"Missing {INDEX}. Run scripts/build_nra_index.py first.")

    agg = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            year = int(row["year"])
            if not (YEAR_LO <= year <= YEAR_HI) or row["basis"] != "aw17":
                continue
            cip = row["cipcode"].split(".")[0].zfill(2)
            cell = agg[(row["unitid"], cip)][year]
            cell[0] += int(row["total"])
            cell[1] += int(row["nra"])

    names, titles = institution_names(), cip_titles()
    cases = []
    for (uid, cip), by_year in agg.items():
        total = sum(v[0] for v in by_year.values())
        nra = sum(v[1] for v in by_year.values())
        if total < MIN_COHORT:
            continue
        counted = {y: v for y, v in by_year.items() if v[0] >= MIN_YEAR_N}
        if len(counted) < MIN_HIGH_YEARS:
            continue
        high = [y for y, v in counted.items() if 100 * v[1] / v[0] >= HIGH_MARK]
        if len(high) < MIN_HIGH_YEARS:
            continue
        cases.append({
            "unitid": uid,
            "institution": names.get(uid, f"UNITID {uid}"),
            "cip2": cip,
            "field": titles.get(cip, f"CIP {cip}"),
            "doctorates": total,
            "nra": nra,
            "share": round(100 * nra / total, 1),
            "years_at_or_above_mark": len(high),
            "years_counted": len(counted),
            "by_year": {str(y): {"total": v[0], "nra": v[1]}
                        for y, v in sorted(by_year.items())},
        })
    cases.sort(key=lambda c: -c["share"])
    return cases


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--top", type=int, default=25, help="how many to print")
    args = ap.parse_args()

    cases = build()
    ctx = national_context()

    payload = {
        "criteria": {
            "years": [YEAR_LO, YEAR_HI],
            "award_level": 17,
            "min_cohort": MIN_COHORT,
            "min_year_n": MIN_YEAR_N,
            "high_mark_pct": HIGH_MARK,
            "min_high_years": MIN_HIGH_YEARS,
            "description": (f"Institution-and-field cells with at least {MIN_COHORT} "
                            f"research doctorates over {YEAR_LO}-{YEAR_HI}, at or "
                            f"above {HIGH_MARK:.0f}% non-resident in at least "
                            f"{MIN_HIGH_YEARS} separate years."),
        },
        "context": ctx,
        "honest_reading": (
            "These cases show composition -- who received the degrees -- in "
            "programs supported by federal research funding. They do not show "
            "displacement. Over the same period total core-STEM doctorates and "
            "DOMESTIC core-STEM doctorates both rose by roughly a third, and "
            "master's awards more than doubled. Seats were not fixed and "
            "domestic participation did not fall."),
        "count": len(cases),
        "cases": cases,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")))

    print(payload["criteria"]["description"])
    print(f"\n{len(cases)} departments qualify.\n")
    print(f"{'share':>7}{'doctorates':>12}{'yrs':>5}  institution / field")
    print("-" * 84)
    for c in cases[:args.top]:
        print(f"{c['share']:>6.1f}%{c['doctorates']:>12,}"
              f"{c['years_at_or_above_mark']:>5}  "
              f"{c['institution'][:38]:<38} {c['field'][:26]}")
    for level, d in ctx.items():
        print(f"\n{level}, {d['first_year']}-{d['last_year']}: "
              f"total {d['total_change_pct']:+.0f}%, "
              f"domestic {d['domestic_change_pct']:+.0f}%")
    print(f"\nwrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
