#!/usr/bin/env python3
"""Publish the SED citizenship series for the site.

WHY IT IS SEPARATE FROM long_series.json
    That file is IPEDS Completions: annual, per-institution, 1995-2025, and
    the basis for every per-university figure. This one is the NSF Survey of
    Earned Doctorates: a CENSUS of every research doctorate awarded in the US,
    reaching back to 1979 -- sixteen years further than IPEDS carries any
    citizenship breakdown at all.

    They are not interchangeable and are deliberately not merged. IPEDS counts
    core-STEM doctorates at named institutions; SED counts all fields
    nationally. Drawing them as one line would imply a continuity the sources
    do not have.

COVERAGE
    Five-yearly 1979-2004, annual from 2009, because that is how NCSES
    publishes it -- no single release carries a long annual citizenship
    series. The output marks which points are which so the chart can draw the
    sparse era differently from the dense one.

USAGE
    python3 scripts/build_sed_site_series.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "nsf_sed" / "parsed" / "sed_citizenship_annual.json"
OUT = ROOT / "site" / "data" / "sed_series.json"


def main() -> int:
    if not SRC.exists():
        print(f"  {SRC} missing. Run scripts/build_sed_annual_series.py")
        return 1
    d = json.loads(SRC.read_text())
    annual, five = d["annual"], d["five_year"]

    series = {}
    for y, r in five.items():
        series[y] = {"temp": r["temp"], "us": r["us"], "all": r["all"],
                     "share": r["temp_share"], "cadence": "five_year"}
    for y, r in annual.items():          # annual wins where both exist
        series[y] = {"temp": r["temp"], "us": r["us"], "all": r["all"],
                     "share": r["temp_share"], "cadence": "annual"}

    yrs = sorted(series, key=int)
    first, last = series[yrs[0]], series[yrs[-1]]
    peak = max(yrs, key=lambda y: series[y]["share"])
    payload = {
        "source": ("NSF NCSES Survey of Earned Doctorates, a census of every "
                   "research doctorate awarded by a US institution"),
        "basis": ("All fields, by citizenship status at the time of the "
                  "award. Not restricted to STEM, and not comparable "
                  "line-for-line with the IPEDS core-STEM series."),
        "coverage": ("Five-yearly to 2004, annual from 2009. NCSES publishes "
                     "no single long annual citizenship series; these are "
                     "chained across seven releases."),
        "span": f"{yrs[0]}-{yrs[-1]}",
        "first": {"year": int(yrs[0]), **first},
        "latest": {"year": int(yrs[-1]), **last},
        "peak": {"year": int(peak), "share": series[peak]["share"]},
        "multiple": round(last["temp"] / first["temp"], 2),
        "series": series,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.partial")
    tmp.write_text(json.dumps(payload, indent=1, sort_keys=True))
    os.replace(tmp, OUT)
    print(f"  {yrs[0]}-{yrs[-1]}: temp-visa share {first['share']}% -> "
          f"{last['share']}%, peak {payload['peak']['share']}% "
          f"({payload['peak']['year']})")
    print(f"  counts {first['temp']:,} -> {last['temp']:,} "
          f"({payload['multiple']}x)")
    print(f"  wrote {OUT} ({OUT.stat().st_size/1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
