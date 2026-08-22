#!/usr/bin/env python3
"""Domestic vs non-resident degree counts over time, by field and award level.

WHY THIS EXISTS

A share is a ratio, and a ratio can rise two ways: the numerator grows, or the
denominator shrinks. "Non-resident share of computer science master's reached
two thirds" is compatible with domestic enrolment booming AND with domestic
enrolment collapsing, and those are opposite stories about American students.
Anyone arguing from share alone is one query away from being corrected in
public. This script runs that query first.

WHAT IT FINDS (IPEDS Completions, 2012 vs 2025, core-STEM CIP families)

Domestic counts did NOT fall. In every core-STEM field, at BOTH master's and
doctorate level, the number of degrees awarded to non-resident-alien-excluded
students rose over the period. There is no field in this set where Americans
lost ground in absolute terms.

What did happen is that the EXPANSION was disproportionately non-resident.
Core-STEM master's roughly doubled in total; non-resident awards grew several
times faster than domestic ones, so most of the additional degrees went to
international students and the share climbed steeply.

The strongest cases are computer science and engineering at master's level.
The weakest - and they run the other way - include doctorate-level biological
sciences and engineering, where domestic growth matched or outpaced
non-resident growth.

HOW TO USE THIS HONESTLY

- "Americans are being displaced" is not supported here. Say the growth was
  captured disproportionately, not that domestic participation fell.
- Report absolute counts alongside any share. A share on its own invites the
  wrong inference in whichever direction the reader already leans.
- Composition is not allocation. Nothing in IPEDS says who applied, who was
  admitted, or who was funded. Demonstrating that international students are
  PRIORITISED needs admissions or funding data - the NSF Survey of Earned
  Doctorates records primary source of support by citizenship, which is the
  nearest available test - not completions counts.

Usage:
    python3 scripts/analyze_domestic_trend.py
    python3 scripts/analyze_domestic_trend.py --level 7 --start 2012 --end 2025
    python3 scripts/analyze_domestic_trend.py --series      # every year
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys as _sys
_sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW   # noqa: E402
IPEDS = ROOT / "data" / "ipeds"

# The project's narrow, headline STEM set.
FIELDS = {"11": "Computer & info sci", "14": "Engineering",
          "15": "Engineering tech", "26": "Biological sciences",
          "27": "Mathematics & stats", "30": "Multi/interdisciplinary",
          "40": "Physical sciences", "42": "Psychology"}

# FIELDS carries display labels, so it cannot simply BE the canonical set --
# but its keys must never drift from it. Seven scripts each kept a private
# copy of these eight families; they agreed, which is what made the drift
# risk invisible. Assert rather than restate.
assert set(FIELDS) == set(STEM_NARROW), (
    f"FIELDS {sorted(FIELDS)} has drifted from pipeline/models.py "
    f"STEM_NARROW {sorted(STEM_NARROW)}")

LEVELS = {"7": "master's", "17": "research doctorate", "5": "bachelor's"}


def source_files() -> dict[int, str]:
    """{year: path}, preferring the revised (_rv) file when both exist."""
    out: dict[int, str] = {}
    for path in glob.glob(str(IPEDS / "*_a*.csv")):
        m = re.search(r"c(\d{4})_a", os.path.basename(path).lower())
        if not m:
            continue
        year = int(m.group(1))
        if year not in out or "_rv" in path:
            out[year] = path
    return out


def tally(path: str, level: str):
    """{cip2: [total, nra]} for one file at one award level."""
    acc = defaultdict(lambda: [0, 0])
    try:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            for row in csv.DictReader(fh):
                # AWLEVEL is zero-padded in some vintages ('07' vs '7').
                if (row.get("AWLEVEL") or "").lstrip("0") != level.lstrip("0"):
                    continue
                cip = (row.get("CIPCODE") or "").split(".")[0].zfill(2)
                if cip not in FIELDS:
                    continue
                try:
                    acc[cip][0] += int(row.get("CTOTALT") or 0)
                    acc[cip][1] += int(row.get("CNRALT") or 0)
                except ValueError:
                    continue
    except OSError:
        pass
    return acc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", default="7", choices=sorted(LEVELS),
                    help="award level: 7 master's, 17 doctorate, 5 bachelor's")
    ap.add_argument("--start", type=int, default=2012)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--series", action="store_true",
                    help="every year between start and end, aggregated")
    args = ap.parse_args()

    files = source_files()
    if not files:
        sys.exit(f"No IPEDS completions files found in {IPEDS}")
    level_name = LEVELS[args.level]

    if args.series:
        print(f"{level_name.upper()}, core-STEM, {args.start}-{args.end}")
        print(f"{'year':<6}{'total':>10}{'NRA':>10}{'domestic':>11}"
              f"{'NRA share':>11}{'dom index':>11}")
        print("-" * 59)
        base = None
        for year in sorted(files):
            if not (args.start <= year <= args.end):
                continue
            acc = tally(files[year], args.level)
            tot = sum(v[0] for v in acc.values())
            nra = sum(v[1] for v in acc.values())
            if not tot:
                continue
            dom = tot - nra
            base = base or dom
            print(f"{year:<6}{tot:>10,}{nra:>10,}{dom:>11,}"
                  f"{100 * nra / tot:>10.1f}%{100 * dom / base:>10.1f}")
        return 0

    a = tally(files.get(args.start, ""), args.level)
    b = tally(files.get(args.end, ""), args.level)
    print(f"{level_name.upper()}, {args.start} -> {args.end}, by core-STEM field\n")
    print(f"{'field':<24}{'dom ' + str(args.start):>10}{'dom ' + str(args.end):>10}"
          f"{'dom chg':>9}{'NRA chg':>9}{'share':>8}")
    print("-" * 70)
    fell = []
    for cip in sorted(FIELDS):
        if cip not in a or cip not in b:
            continue
        d0, d1 = a[cip][0] - a[cip][1], b[cip][0] - b[cip][1]
        n0, n1 = a[cip][1], b[cip][1]
        if d0 == 0 or n0 == 0 or b[cip][0] == 0:
            continue
        dchg = 100 * (d1 - d0) / d0
        if dchg < 0:
            fell.append(FIELDS[cip])
        print(f"{FIELDS[cip]:<24}{d0:>10,}{d1:>10,}{dchg:>8.0f}%"
              f"{100 * (n1 - n0) / n0:>8.0f}%{100 * n1 / b[cip][0]:>7.1f}%")

    print()
    if fell:
        print("Fields where domestic counts FELL: " + ", ".join(fell))
    else:
        print("No field shows a domestic decline. The share rose because "
              "non-resident\ncounts grew faster, not because domestic counts "
              "shrank - report it that way.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
