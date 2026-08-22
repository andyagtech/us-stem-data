#!/usr/bin/env python3
"""Do the study pipeline's stages move together? F-1, master's, OPT, H-1B.

The claim this tests is that the F-1 -> master's -> OPT -> H-1B route behaves
like a pipeline rather than four unrelated programmes. Four national-ish series,
each from a different federal collection:

    f1_issuance    State Dept, Nonimmigrant Visa Issuances by class, FY1997-2024
    nra_masters    IPEDS Completions, core-STEM award level 7, 2008-2025
    opt_auth       SEVP top-school OPT authorisations, 2017-2024   *** SAMPLE ***
    lca_filings    DOL LCA disclosure rows, FY2013-2026

WHAT EACH SERIES IS NOT, because these are easy to overstate:

  * f1_issuance counts DOCUMENTS ISSUED at consulates, at every level of study
    from language school upward. It is not enrolment, and a person can appear
    in more than one year.
  * opt_auth is NOT national. It is the sum over whichever schools appear in
    that year's SEVP top-100/200 list, and the roster changes annually (48
    schools in 2017, 52 in 2024). Year-over-year movement therefore mixes real
    change with roster churn. It is the weakest series here and is labelled so
    everywhere it is published.
  * lca_filings counts Labor Condition Applications, which are the employer's
    pre-petition filing. One certified LCA can cover several workers, and an
    LCA is not a granted visa. DOL quarterly files are CUMULATIVE within a
    fiscal year, so the latest quarter present IS the annual total -- summing
    the quarters would double count badly.
  * Correlation across four collections with different units, different
    populations and n < 20 is descriptive. It is not evidence that one stage
    causes another, and the series share a common driver (overall foreign
    student volume) that guarantees some association.

Usage:
    python3 scripts/build_pipeline_correlation.py --report
    python3 scripts/build_pipeline_correlation.py          # writes site/data/pipeline_correlation.json
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_write import write_json                       # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data" / "pipeline_correlation.json"


def f1_series() -> dict[int, int]:
    d = json.loads((ROOT / "site" / "data" / "live_bundle.json").read_text())
    return {int(y): v["total"] for y, v in d["f1"].items()}


def masters_series() -> dict[int, int]:
    d = json.loads((ROOT / "site" / "data" / "live_bundle.json").read_text())
    out: collections.Counter = collections.Counter()
    for fam in d["degrees"]["masters"].values():
        for y, pair in fam.items():
            out[int(y)] += pair[1]          # non-resident count
    return dict(out)


def opt_series() -> tuple[dict[int, int], dict[int, int]]:
    """(authorisations, schools_in_that_year's_list). Sample, not a census."""
    p = ROOT / "data" / "h1b" / "opt_by_university.json"
    auth: collections.Counter = collections.Counter()
    schools: collections.Counter = collections.Counter()
    for uni, years in json.loads(p.read_text()).items():
        for y, v in years.items():
            if not isinstance(v, dict) or "opt" not in v:
                continue
            n = v["opt"].get("authorizations") or 0
            if n:
                auth[int(y)] += n
                schools[int(y)] += 1
    return dict(auth), dict(schools)


def lca_series() -> dict[int, int]:
    """Rows in the LATEST quarter file per fiscal year -- files are cumulative."""
    try:
        import openpyxl
    except ModuleNotFoundError:
        sys.exit("openpyxl required -- see requirements.txt")
    latest: dict[int, tuple[int, str]] = {}
    for path in glob.glob(str(ROOT / "data" / "h1b" / "lca" / "*.xlsx")):
        base = os.path.basename(path)
        m = re.search(r"(?:FY|fy)(\d{4})", base)
        if not m:
            m2 = re.search(r"FY(\d{2})\b", base)
            if not m2:
                continue
            year = 2000 + int(m2.group(1))
        else:
            year = int(m.group(1))
        q = re.search(r"_Q(\d)", base, re.I)
        qn = int(q.group(1)) if q else 9        # EOY/annual files sort last
        if year not in latest or qn > latest[year][0]:
            latest[year] = (qn, path)
    out = {}
    for year, (_q, path) in sorted(latest.items()):
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb[wb.sheetnames[0]]
        out[year] = max(0, (ws.max_row or 1) - 1)     # minus header
        wb.close()
        print(f"    LCA FY{year}: {out[year]:>9,} rows  ({os.path.basename(path)})",
              flush=True)
    return out


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return round(num / (dx * dy), 3) if dx and dy else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    print("  reading LCA row counts (cumulative files: latest quarter per FY)...")
    series = {
        "f1_issuance": f1_series(),
        "nra_masters": masters_series(),
        "lca_filings": lca_series(),
    }
    opt_auth, opt_schools = opt_series()
    series["opt_authorisations"] = opt_auth

    names = list(series)
    corr = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = sorted(set(series[a]) & set(series[b]))
            if len(shared) < 3:
                continue
            r = pearson([series[a][y] for y in shared],
                        [series[b][y] for y in shared])
            corr[f"{a}~{b}"] = {"r": r, "years": [shared[0], shared[-1]],
                                "n": len(shared)}

    payload = {
        "series": {k: {str(y): v for y, v in sorted(s.items())}
                   for k, s in series.items()},
        "opt_schools_in_sample": {str(y): n for y, n in sorted(opt_schools.items())},
        "correlations": corr,
        "caveats": {
            "opt": ("NOT NATIONAL. Sum over whichever schools appear in that "
                    "year's SEVP top-100/200 list; the roster changes annually "
                    "(48 schools in 2017, 52 in 2024), so year-over-year change "
                    "mixes real movement with roster churn."),
            "f1": ("Documents issued at consulates, every level of study. Not "
                   "enrolment; one person can appear in more than one year."),
            "lca": ("Labor Condition Applications, the employer's pre-petition "
                    "filing. One LCA can cover several workers and is not a "
                    "granted visa. DOL quarterly files are cumulative within a "
                    "fiscal year, so the latest quarter IS the annual total."),
            "correlation": ("Descriptive only. Four collections, different units "
                            "and populations, n under 20, and a shared driver "
                            "(overall foreign student volume) that guarantees "
                            "some association. This does not show that one stage "
                            "causes another."),
        },
    }

    print("\n  series coverage")
    for k, s in series.items():
        ys = sorted(s)
        print(f"    {k:<20} {ys[0]}-{ys[-1]}  ({len(ys)} years)")
    print("\n  pairwise correlation (Pearson r on overlapping years)")
    for k, v in sorted(corr.items(), key=lambda x: -(abs(x[1]["r"] or 0))):
        print(f"    {k:<38} r={v['r']:>6}  n={v['n']:>2}  {v['years'][0]}-{v['years'][1]}")

    if not args.report:
        write_json(OUT, payload, indent=1)
        print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
