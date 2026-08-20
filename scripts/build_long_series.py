#!/usr/bin/env python3
"""The full 1995-2025 series, with the award-level transition handled correctly.

WHY A SEPARATE BUILDER

Most of this project works in the post-2010 window because IPEDS recoded
doctorate award levels in 2010 and a figure from either side of that line is not
comparable with one from the other. But a thirty-year view is more persuasive
than a fifteen-year one, and it lets the argument own the recent decline rather
than be ambushed by it.

THE TRANSITION, AND A CORRECTION

Award level 9 became 17 (research doctorate) and 18 (professional practice) in
2010, but institutions migrated one at a time across 2008 and 2009. This project
previously documented that summing both codings in those years would
double-count, and computed them on a single basis.

That was backwards. Verified against the index: in 2008, 495 institutions report
aw09 and 122 report aw17; in 2009 it is 350 and 242. **Zero institutions report
both, in either year.** So the two bases must be SUMMED to get a complete year,
and taking one alone silently drops whoever was on the other scheme --
understating 2008 and 2009 by roughly twenty percent and putting a false trough
in the middle of the series.

    2007  aw09 28,794                     = 28,794
    2008  aw09 23,296 + aw17  6,202       = 29,498     (single basis: 23,296)
    2009  aw09 16,829 + aw17 12,432       = 29,261     (single basis: 16,829)
    2010              aw17 28,741         = 28,741

Summed, the transition is invisible. Taken singly, it looks like a collapse and
a recovery that never happened.

WHAT THE SERIES SHOWS

The non-resident share of core-STEM doctorates rose from about 30% in the late
1990s to roughly 39% by 2006, held near there, climbed again to a peak just over
40% in 2021-22, and has fallen since. Domestic counts rose throughout and are
rising fastest at the end.

Both facts are real and the honest presentation carries both.

Usage:
    python3 scripts/build_long_series.py
    python3 scripts/build_long_series.py --out site/data/long_series.json
    python3 scripts/build_long_series.py --by-field
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "ipeds" / "nra_index.csv.gz"
DEFAULT_OUT = ROOT / "site" / "data" / "long_series.json"

sys.path.insert(0, str(ROOT))
try:
    from pipeline.models import STEM_NARROW, bases_for, TRANSITION_YEARS
except Exception:                                            # noqa: BLE001
    STEM_NARROW = ("11", "14", "15", "26", "27", "30", "40", "42")
    TRANSITION_YEARS = (2008, 2009)

    def bases_for(year):
        if year in TRANSITION_YEARS:
            return ("aw09", "aw17")
        return ("aw17",) if year >= 2010 else ("aw09",)

FIELDS = {"11": "Computer science", "14": "Engineering", "15": "Engineering tech",
          "26": "Biological sciences", "27": "Math & statistics",
          "30": "Interdisciplinary", "40": "Physical sciences",
          "42": "Psychology"}


def build(by_field: bool = False):
    if not INDEX.exists():
        sys.exit(f"Missing {INDEX}. Run scripts/build_nra_index.py first.")
    tot = defaultdict(int)
    nra = defaultdict(int)
    ftot = defaultdict(lambda: defaultdict(int))
    fnra = defaultdict(lambda: defaultdict(int))

    with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            year = int(row["year"])
            if row["basis"] not in bases_for(year):
                continue
            cip = row["cipcode"].split(".")[0].zfill(2)
            if cip not in STEM_NARROW:
                continue
            t, n = int(row["total"]), int(row["nra"])
            tot[year] += t
            nra[year] += n
            if by_field:
                ftot[cip][year] += t
                fnra[cip][year] += n

    series = {}
    for year in sorted(tot):
        t, n = tot[year], nra[year]
        if not t:
            continue
        series[year] = {"total": t, "nra": n, "domestic": t - n,
                        "share": round(100 * n / t, 1),
                        "transition": year in TRANSITION_YEARS}
    fields = {}
    if by_field:
        for cip, ys in ftot.items():
            fields[FIELDS.get(cip, cip)] = {
                y: round(100 * fnra[cip][y] / ys[y], 1) for y in sorted(ys) if ys[y]}
    return series, fields


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--by-field", action="store_true")
    args = ap.parse_args()

    series, fields = build(by_field=True)
    years = sorted(series)
    peak = max(years, key=lambda y: series[y]["share"])
    trough = min(years, key=lambda y: series[y]["share"])
    last = years[-1]

    payload = {
        "basis": {
            "cip_families": list(STEM_NARROW),
            "award_levels": "9 before 2010, 17 from 2010; 2008-09 sum both",
            "note": ("Institutions migrated from award level 9 to 17 one at a "
                     "time across 2008-09, each reporting exactly one. Both "
                     "bases are summed in those two years; zero institutions "
                     "report both, so this cannot double-count."),
        },
        "peak": {"year": peak, "share": series[peak]["share"]},
        "trough": {"year": trough, "share": series[trough]["share"]},
        "latest": {"year": last, "share": series[last]["share"]},
        "series": {str(y): series[y] for y in years},
        "fields": fields,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")))

    print(f"Core-STEM doctorates, {years[0]}-{years[-1]}\n")
    print(f"{'year':<6}{'total':>9}{'NRA':>9}{'domestic':>10}{'share':>8}")
    print("-" * 43)
    base = series[years[0]]["domestic"]
    for y in years:
        d = series[y]
        flag = "  (transition: both bases summed)" if d["transition"] else ""
        print(f"{y:<6}{d['total']:>9,}{d['nra']:>9,}{d['domestic']:>10,}"
              f"{d['share']:>7.1f}%{flag}")
    print(f"\ntrough {series[trough]['share']}% in {trough} · "
          f"peak {series[peak]['share']}% in {peak} · "
          f"latest {series[last]['share']}% in {last}")
    print(f"domestic {series[years[0]]['domestic']:,} -> "
          f"{series[last]['domestic']:,} "
          f"({100 * (series[last]['domestic'] - base) / base:+.0f}%)")
    print(f"\nwrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
