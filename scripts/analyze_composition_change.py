#!/usr/bin/env python3
"""Which institutions and fields changed most in non-resident composition.

WHY THIS NEEDS A GUARD

The obvious query -- compare an early window with a late one and sort by the
difference -- produces a ranking dominated by an artifact. Before 2008, IPEDS
carried residency as sex-split race columns, and an institution that reported
only its grand total lands in the index with zero non-residents. A hard zero at
a research university is far more likely to be an unreported breakdown than a
true absence of international students.

The rate is not small: 12.7% of institutions with 20+ STEM doctorates report
zero non-residents in 2000, against 5.6% in 2025. That halving is itself
evidence that reporting improved rather than composition changing.

Left unguarded, the ranking led with Duke (1 non-resident doctorate out of 134
in 2000, versus 117 of 299 in 2022) and the University of Hawaii (a hard zero
for six consecutive years). Both would have been published as spectacular
increases. Neither is measurable from this data.

THE GUARD

An institution qualifies only if, in the EARLY window, it reports a non-zero
non-resident count in most years. That keeps institutions whose early share was
genuinely low and drops those whose early share is unknown. It is deliberately
blunt: a real zero at a small program is excluded too, which costs a little
coverage and buys a ranking that survives being checked.

Usage:
    python3 scripts/analyze_composition_change.py
    python3 scripts/analyze_composition_change.py --fields
    python3 scripts/analyze_composition_change.py --out site/data/composition_change.json
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "ipeds" / "nra_index.csv.gz"
DEFAULT_OUT = ROOT / "site" / "data" / "composition_change.json"

sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW, bases_for          # noqa: E402

EARLY = (2000, 2004)
LATE = (2021, 2025)
MIN_COHORT = 150          # doctorates in EACH window
MIN_REPORTING_YEARS = 3   # early years with a non-zero NRA count, of 5

FIELDS = {"11": "Computer science", "14": "Engineering", "15": "Engineering tech",
          "26": "Biological sciences", "27": "Math & statistics",
          "30": "Interdisciplinary", "40": "Physical sciences",
          "42": "Psychology"}


def institution_names() -> dict[str, str]:
    files = sorted(glob.glob(str(ROOT / "data" / "ipeds" / "hd*.csv")))
    if not files:
        return {}
    out = {}
    with open(files[-1], newline="", encoding="utf-8-sig", errors="replace") as fh:
        for row in csv.DictReader(fh):
            uid = (row.get("UNITID") or "").strip()
            if uid:
                out[uid] = (row.get("INSTNM") or "").strip()
    return out


def load():
    """(per-institution windows, per-field-per-year totals)."""
    inst = defaultdict(lambda: {"e": [0, 0], "l": [0, 0], "e_years": defaultdict(int)})
    fields = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            year = int(row["year"])
            if row["basis"] not in bases_for(year):
                continue
            cip = row["cipcode"].split(".")[0].zfill(2)
            if cip not in STEM_NARROW:
                continue
            t, n = int(row["total"]), int(row["nra"])
            f = fields[cip][year]
            f[0] += t
            f[1] += n
            slot = ("e" if EARLY[0] <= year <= EARLY[1]
                    else "l" if LATE[0] <= year <= LATE[1] else None)
            if not slot:
                continue
            rec = inst[row["unitid"]]
            rec[slot][0] += t
            rec[slot][1] += n
            if slot == "e":
                rec["e_years"][year] += n
    return inst, fields


def rank_institutions(inst, names):
    rows, dropped = [], []
    for uid, rec in inst.items():
        et, en = rec["e"]
        lt, ln = rec["l"]
        if et < MIN_COHORT or lt < MIN_COHORT:
            continue
        reporting = sum(1 for _y, n in rec["e_years"].items() if n > 0)
        entry = {
            "unitid": uid, "institution": names.get(uid, uid),
            "early_share": round(100 * en / et, 1),
            "late_share": round(100 * ln / lt, 1),
            "change": round(100 * ln / lt - 100 * en / et, 1),
            "early_n": et, "late_n": lt,
            "early_reporting_years": reporting,
        }
        if reporting < MIN_REPORTING_YEARS:
            dropped.append(entry)
        else:
            rows.append(entry)
    rows.sort(key=lambda r: -r["change"])
    dropped.sort(key=lambda r: -r["change"])
    return rows, dropped


def rank_fields(fields):
    out = []
    for cip, years in fields.items():
        ys = sorted(years)
        if not ys:
            continue
        def window(a, b):
            t = sum(years[y][0] for y in ys if a <= y <= b)
            n = sum(years[y][1] for y in ys if a <= y <= b)
            return (100 * n / t) if t else None
        early, late = window(*EARLY), window(*LATE)
        latest_year = ys[-1]
        lt, ln = years[latest_year]
        out.append({
            "cip2": cip, "field": FIELDS.get(cip, cip),
            "latest_year": latest_year,
            "latest_share": round(100 * ln / lt, 1) if lt else None,
            "early_share": round(early, 1) if early is not None else None,
            "late_share": round(late, 1) if late is not None else None,
            "change": round(late - early, 1) if (early is not None and late is not None) else None,
            "series": {str(y): round(100 * years[y][1] / years[y][0], 1)
                       for y in ys if years[y][0]},
        })
    out.sort(key=lambda r: -(r["latest_share"] or 0))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--fields", action="store_true", help="fields only")
    args = ap.parse_args()

    inst, fields = load()
    names = institution_names()
    rows, dropped = rank_institutions(inst, names)
    fld = rank_fields(fields)

    if not args.fields:
        print(f"BIGGEST INCREASE IN NON-RESIDENT SHARE OF STEM DOCTORATES")
        print(f"{EARLY[0]}-{EARLY[1]} vs {LATE[0]}-{LATE[1]} · {MIN_COHORT}+ doctorates "
              f"in each window · early residency reported in {MIN_REPORTING_YEARS}+ of 5 years\n")
        print(f"{'change':>8}{'then':>7}{'now':>7}{'n then':>8}{'n now':>8}  institution")
        print("-" * 74)
        for r in rows[:args.top]:
            print(f"{r['change']:>+8.1f}{r['early_share']:>7.1f}{r['late_share']:>7.1f}"
                  f"{r['early_n']:>8,}{r['late_n']:>8,}  {r['institution'][:36]}")
        print(f"\nBIGGEST DECREASE")
        print("-" * 74)
        for r in rows[-6:]:
            print(f"{r['change']:>+8.1f}{r['early_share']:>7.1f}{r['late_share']:>7.1f}"
                  f"{r['early_n']:>8,}{r['late_n']:>8,}  {r['institution'][:36]}")
        print(f"\n{len(rows)} institutions qualify. {len(dropped)} excluded for "
              f"unreliable early reporting:")
        for r in dropped[:6]:
            print(f"    {r['institution'][:34]:<34} would have shown "
                  f"{r['change']:+.1f} ({r['early_share']}% -> {r['late_share']}%), "
                  f"but reported residency in only {r['early_reporting_years']} of 5 early years")

    print(f"\n\nFIELDS BY NON-RESIDENT SHARE ({fld[0]['latest_year']})")
    print(f"{'now':>7}{'2000-04':>10}{'2021-25':>10}{'change':>9}  field")
    print("-" * 60)
    for f in fld:
        ch = f"{f['change']:+.1f}" if f["change"] is not None else "  n/a"
        print(f"{f['latest_share']:>6.1f}%{f['early_share']:>9.1f}%"
              f"{f['late_share']:>9.1f}%{ch:>9}  {f['field']}")

    payload = {
        "windows": {"early": list(EARLY), "late": list(LATE)},
        "criteria": {"min_cohort_each_window": MIN_COHORT,
                     "min_early_reporting_years": MIN_REPORTING_YEARS,
                     "note": ("Pre-2008 IPEDS carried residency as sex-split race "
                              "columns; an institution reporting only its grand "
                              "total appears as zero non-residents. Institutions "
                              "without a non-zero early count in most years are "
                              "excluded, because their early share is unknown "
                              "rather than low.")},
        "institutions": rows,
        "excluded_unreliable_early": dropped,
        "fields": fld,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"\nwrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
