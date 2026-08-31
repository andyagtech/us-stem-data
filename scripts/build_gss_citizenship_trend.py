#!/usr/bin/env python3
"""Forty-five years of science and engineering graduate enrolment by citizenship.

The IPEDS enrolment series covers all fields and runs from 2010. This one is
restricted to science, engineering and health -- the population the argument
is actually about -- and runs from 1980, which is long enough to show that
the present position is not a recent excursion.

It also carries postdoctoral appointees on the same basis, where the shift
happened earlier and went further.

WHY THIS AND THE DEGREE SERIES ARE BOTH NEEDED. graduate_balance counts
DEGREES CONFERRED in eight core-STEM CIP families from IPEDS. This counts
STUDENTS ENROLLED in science, engineering and health units from the GSS.
Different populations, different field definitions, different collections --
they corroborate each other in direction, and their levels are not
interchangeable.

Usage:
  python3 scripts/build_gss_citizenship_trend.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "nsf_gss" / "tables" / "nsf26307-tab001-007.xlsx"
OUT = ROOT / "site" / "data" / "gss_citizenship_trend.json"

# Columns after the year: graduate total, citizen n, citizen %, visa n,
# visa %, then the same five for postdoctoral appointees.
POPULATIONS = ("graduate_students", "postdocs")


def main() -> int:
    if not SRC.exists():
        print(f"  missing {SRC.relative_to(ROOT)}")
        return 1
    import openpyxl
    ws = openpyxl.load_workbook(SRC).active
    rows = [list(r) for r in ws.iter_rows(values_only=True)]

    series, warns = {}, []
    for r in rows:
        try:
            year = int(r[0])
        except (TypeError, ValueError):
            continue
        if not 1960 <= year <= 2100:
            continue
        nums = [x for x in r[1:] if isinstance(x, (int, float))]
        if len(nums) < 10:
            continue
        rec = {}
        for i, pop in enumerate(POPULATIONS):
            tot, cit_n, cit_p, vis_n, vis_p = nums[i * 5: i * 5 + 5]
            rec[pop] = {"total": int(tot), "citizen_pr": int(cit_n),
                        "temporary_visa": int(vis_n), "share": round(vis_p, 1)}
            # The published parts and percentages must agree with the total.
            if abs((cit_n + vis_n) - tot) > 2:
                warns.append(f"{year} {pop}: {cit_n:,}+{vis_n:,} != {tot:,}")
            if abs(100 * vis_n / tot - vis_p) > 0.15:
                warns.append(f"{year} {pop}: {vis_p}% != {100 * vis_n / tot:.1f}%")
        series[str(year)] = rec

    if len(series) < 20:
        print(f"  only {len(series)} years parsed")
        return 1

    years = sorted(series)
    f, l = years[0], years[-1]
    doc = {
        "_comment": (
            "Citizenship of graduate students and postdoctoral appointees in "
            "SCIENCE, ENGINEERING AND HEALTH, from the NSF Survey of Graduate "
            "Students and Postdoctorates. COUNTS ARE STUDENTS ENROLLED in a "
            "fall term, in S&E&H units -- a different population and a "
            "different field definition from graduate_balance, which counts "
            "DEGREES CONFERRED in eight core-STEM CIP families from IPEDS. "
            "The two corroborate each other in direction; their levels are "
            "NOT interchangeable and must not be quoted as one series. "
            "'Temporary visa holders' is a visa category: permanent residents "
            "are grouped with citizens throughout."),
        "source": "NSF NCSES, Survey of Graduate Students and Postdoctorates, table 1-7",
        "source_file": SRC.name,
        "years": [int(y) for y in years],
        "series": series,
        "shift": {pop: {"first_year": int(f), "last_year": int(l),
                        "first_share": series[f][pop]["share"],
                        "last_share": series[l][pop]["share"],
                        "change_pts": round(series[l][pop]["share"]
                                            - series[f][pop]["share"], 1),
                        "peak_year": int(max(years, key=lambda y: series[y][pop]["share"])),
                        "peak_share": max(series[y][pop]["share"] for y in years),
                        "citizen_change_pct": round(
                            100 * (series[l][pop]["citizen_pr"]
                                   / series[f][pop]["citizen_pr"] - 1), 1),
                        "visa_change_pct": round(
                            100 * (series[l][pop]["temporary_visa"]
                                   / series[f][pop]["temporary_visa"] - 1), 1)}
                  for pop in POPULATIONS},
        "warnings": warns,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {len(years)} years, {f}-{l}  (science, engineering and health)")
    print(f"  {'year':6}{'grad visa %':>13}{'postdoc visa %':>16}{'grad visa n':>13}")
    for y in years:
        if int(y) % 5 == 0 or y in (f, l):
            s = series[y]
            print(f"  {y:6}{s['graduate_students']['share']:>12.1f}%"
                  f"{s['postdocs']['share']:>15.1f}%"
                  f"{s['graduate_students']['temporary_visa']:>13,}")
    for pop in POPULATIONS:
        sh = doc["shift"][pop]
        print(f"  {pop:18} {sh['first_share']}% -> {sh['last_share']}% "
              f"({sh['change_pts']:+.1f} pts), peak {sh['peak_share']}% in "
              f"{sh['peak_year']}; visa {sh['visa_change_pct']:+.0f}%, "
              f"citizen {sh['citizen_change_pct']:+.0f}%")
    for w in warns[:6]:
        print(f"  WARN {w}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
