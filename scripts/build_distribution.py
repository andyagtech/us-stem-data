#!/usr/bin/env python3
"""The distribution of departments by non-resident share, then and now.

WHY A HISTOGRAM

The argument is that a flat national average hides a moving distribution. A
line chart of the average cannot show that; a histogram can. Put 2010 beside
2025 and the whole shape shifts right, with a thickening tail above 70% -- which
is the claim, drawn rather than asserted.

WHAT COUNTS AS A DEPARTMENT

One institution, one 2-digit CIP family, in one year, with at least 20 research
doctorates awarded. The floor matters: a department of three can sit at 100% by
accident, and letting those in would fatten the top bin with noise.

THE REPORTING CAVEAT

Institutions that report a grand total but leave the residency breakdown blank
land at zero non-residents. That was 12.7% of qualifying departments in 2000
against 5.6% in 2025, so the LEFT tail of an early histogram is partly an
artifact. This builder therefore starts at 2010, where the rate has already
fallen, and reports the zero-share count for each year so the reader can see how
much of the bottom bin might be non-reporting.

Usage:
    python3 scripts/build_distribution.py
    python3 scripts/build_distribution.py --years 2010 2025
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
DEFAULT_OUT = ROOT / "site" / "data" / "distribution.json"

sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW, bases_for          # noqa: E402
from atomic_write import write_json

MIN_COHORT = 20
#: 4-digit CIP, matching the unit the headline claims use. A "department" is one
#: programme at one school -- Electrical Engineering at Purdue, not all of
#: Engineering at Purdue. At 2-digit grain the whole distribution is coarser and
#: the counts do not line up with anything else on the site.
CIP_GRAIN = 4
BINS = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 50),
        (50, 60), (60, 70), (70, 80), (80, 90), (90, 101)]


def departments(year: int):
    """[(share, total)] for every qualifying department in `year`."""
    acc = defaultdict(lambda: [0, 0])
    with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            y = int(row["year"])
            if y != year or row["basis"] not in bases_for(y):
                continue
            family = row["cipcode"].split(".")[0].zfill(2)
            if family not in STEM_NARROW:
                continue
            key = row["cipcode"] if CIP_GRAIN == 4 else family
            slot = acc[(row["unitid"], key)]
            slot[0] += int(row["total"])
            slot[1] += int(row["nra"])
    return [(100 * n / t, t) for t, n in acc.values() if t >= MIN_COHORT]


def histogram(year: int):
    rows = departments(year)
    counts = [0] * len(BINS)
    for share, _t in rows:
        for i, (lo, hi) in enumerate(BINS):
            if lo <= share < hi:
                counts[i] += 1
                break
    total = len(rows)
    return {
        "year": year,
        "departments": total,
        "counts": counts,
        "pct": [round(100 * c / total, 1) if total else 0 for c in counts],
        "at_or_above_50": sum(1 for s, _ in rows if s > 50),
        "doctorates_in_majority": sum(t for s, t in rows if s > 50),
        "doctorates_total": sum(t for _s, t in rows),
        "at_or_above_70": sum(1 for s, _ in rows if s >= 70),
        "zero_share": sum(1 for s, _ in rows if s == 0),
        "median": round(sorted(s for s, _ in rows)[total // 2], 1) if total else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--years", nargs="+", type=int, default=[2010, 2015, 2020, 2025])
    args = ap.parse_args()

    hists = [histogram(y) for y in args.years]
    payload = {
        "bins": [{"lo": lo, "hi": hi, "label": f"{lo}–{hi if hi <= 100 else 100}%"}
                 for lo, hi in BINS],
        "min_cohort": MIN_COHORT,
        "cip_grain": CIP_GRAIN,
        "caveat": ("A department is one institution and one 2-digit CIP family in "
                   "one year, with 20+ research doctorates. Institutions that "
                   "report a total but leave the residency breakdown blank appear "
                   "at zero, so the lowest bin includes some non-reporting; the "
                   "zero_share count is given per year so that is visible."),
        "histograms": hists,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, payload, separators=(",", ":"))

    width = 34
    peak = max(max(h["counts"]) for h in hists) or 1
    for h in hists:
        print(f"\n{h['year']}  ·  {h['departments']} departments  ·  "
              f"median {h['median']}%  ·  {h['at_or_above_50']} at 50%+  ·  "
              f"{h['at_or_above_70']} at 70%+  ·  {h['zero_share']} at zero")
        for (lo, hi), c in zip(BINS, h["counts"]):
            bar = "█" * round(width * c / peak)
            print(f"  {lo:>3}–{min(hi,100):<3} {c:>4}  {bar}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
