#!/usr/bin/env python3
"""Graduate enrolment by citizenship, as a check on the degree counts.

The degree series measures what was conferred. This measures who is enrolled,
from a different IPEDS collection, and so is an independent read on the same
shift.

TWO LIMITS THAT DECIDE HOW THIS CAN BE USED. IPEDS reports enrolment by
institution and level but NOT by field, so this is ALL GRADUATE STUDY, not
core STEM, and it is not comparable to the core-STEM degree figures. And the
enrolment files run two years behind the completions files, so this does not
lead the degree series -- it corroborates it.

Usage:
  python3 scripts/build_graduate_enrollment.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "ipeds_enrollment"
OUT = ROOT / "site" / "data" / "graduate_enrollment.json"

# IPEDS EFALEVEL: 12 is all graduate students, 32 full-time graduate and 52
# part-time graduate. 22 and 42 are the UNDERGRADUATE full- and part-time
# codes; using them here put 12 million undergraduates into a graduate series,
# which the full-time-plus-part-time reconciliation below caught. Those two
# now sum to level 12 exactly, in every year.
LEVELS = {12: "all", 32: "full_time", 52: "part_time"}


def rows(path: Path):
    with zipfile.ZipFile(path) as z:
        inner = next(x for x in z.namelist() if x.lower().endswith(".csv"))
        with z.open(inner) as fh:
            yield from csv.DictReader(
                io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace"))


def num(r: dict, key: str) -> int:
    try:
        return int(float(r.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def main() -> int:
    files = sorted(SRC.glob("EF*A.zip"))
    if not files:
        print(f"  no enrolment files in {SRC.relative_to(ROOT)}")
        return 1

    series, warns = {}, []
    for p in files:
        year = int(p.stem[2:6])
        agg = {k: [0, 0] for k in LEVELS.values()}
        insts = set()
        for r in rows(p):
            lv = num(r, "EFALEVEL")
            if lv not in LEVELS:
                continue
            t, n = num(r, "EFTOTLT"), num(r, "EFNRALT")
            if not t:
                continue
            a = agg[LEVELS[lv]]
            a[0] += t
            a[1] += n
            if lv == 12:
                insts.add(r.get("UNITID"))
        if not agg["all"][0]:
            warns.append(f"{year}: no graduate rows")
            continue
        rec = {"institutions": len(insts)}
        for k, (t, n) in agg.items():
            rec[k] = {"total": t, "nra": n, "domestic": t - n,
                      "share": round(100 * n / t, 1)}
        # Full-time plus part-time should account for the whole.
        parts = agg["full_time"][0] + agg["part_time"][0]
        if parts and abs(parts - agg["all"][0]) > 0.01 * agg["all"][0]:
            warns.append(f"{year}: FT+PT {parts:,} != all {agg['all'][0]:,}")
        series[str(year)] = rec

    if len(series) < 5:
        print(f"  only {len(series)} usable years")
        return 1

    years = sorted(series)
    f, l = years[0], years[-1]
    doc = {
        "_comment": (
            "Graduate enrolment by citizenship, IPEDS Fall Enrolment. ALL "
            "FIELDS, NOT CORE STEM -- IPEDS does not publish enrolment by "
            "field, so these figures are NOT comparable with the core-STEM "
            "degree counts in graduate_balance and must never be quoted "
            "beside them as if they were. The files also run about two years "
            "behind completions, so this corroborates the degree series "
            "rather than leading it. NRA is a visa category: permanent "
            "residents are counted under their race and appear as domestic. "
            "COUNTS ARE ENROLMENTS IN A FALL TERM, not people-years."),
        "source": "NCES IPEDS Fall Enrolment (EF), all fields",
        "levels": {"all": "all graduate students (EFALEVEL 12)",
                   "full_time": "full-time graduate (EFALEVEL 32)",
                   "part_time": "part-time graduate (EFALEVEL 52)"},
        "years": [int(y) for y in years],
        "series": series,
        "shift": {k: {"first_share": series[f][k]["share"],
                      "last_share": series[l][k]["share"],
                      "change_pts": round(series[l][k]["share"]
                                          - series[f][k]["share"], 1)}
                  for k in ("all", "full_time", "part_time")},
        "warnings": warns,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {len(years)} years, {f}-{l}  (all fields, not core STEM)")
    print(f"  {'year':6}{'all grad':>11}{'full-time':>12}{'part-time':>12}{'NRA (all)':>12}")
    for y in years:
        s = series[y]
        print(f"  {y:6}{s['all']['share']:>10.1f}%{s['full_time']['share']:>11.1f}%"
              f"{s['part_time']['share']:>11.1f}%{s['all']['nra']:>12,}")
    for k in ("all", "full_time"):
        sh = doc["shift"][k]
        print(f"  {k:10} {sh['first_share']:.1f}% -> {sh['last_share']:.1f}% "
              f"({sh['change_pts']:+.1f} pts)")
    for w in warns:
        print(f"  WARN {w}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
