#!/usr/bin/env python3
"""Sanity-check the published LCA aggregate before anyone reads a number off it.

The guards inside pipeline/step3_parse_federal.py all watch the INPUT: a
missing library, an unrecognised column, a file that parses to zero rows, a
fiscal year absent from the archive. They run only when the parse runs.

This watches the OUTPUT, and runs on every `make check`. It is the check that
would have caught FY2014 collapsing to 1,348 filings -- a year whose total
fell off a cliff while the pipeline reported success, and which was noticed
by reading it off a chart weeks later.

Checks:

  span        the years in the aggregate are continuous -- no year missing
              from the middle, which is what a lost source file looks like
              once it reaches the output
  swings      no year moves implausibly against its neighbours. Boundary
              years are exempt: the first and last are partial by nature and
              always look like a cliff.
  archive     the aggregate's span matches what the source archive holds, so
              a parse run against half an archive cannot quietly ship
  totals      the national total and university count are within the band the
              site's published figures assume

Usage:
  python3 scripts/check_lca_sanity.py
  python3 scripts/check_lca_sanity.py --verbose
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGG = ROOT / "data" / "h1b" / "lca_by_university.json"
MANIFEST = ROOT / "data" / "h1b" / "lca_archive_manifest.json"
LCA_DIR = ROOT / "data" / "h1b" / "lca"

# A year may move a lot -- 2020 really did fall, and 2022 really did jump --
# but not by an order of magnitude against BOTH neighbours at once. That is
# the shape of a missing file, not of the world changing.
SWING_FLOOR = 0.35      # a year below 35% of both neighbours
SWING_CEILING = 3.0     # or above 3x both neighbours

_results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    _results.append((bool(ok), name, detail))
    return bool(ok)


def national_by_year(agg: dict) -> dict[int, int]:
    """Sum every university's per-year counts into one national series."""
    tot: dict[int, int] = {}
    for uni in agg.values():
        for year, n in (uni.get("yearly") or {}).items():
            try:
                y = int(year)
            except (TypeError, ValueError):
                continue
            if isinstance(n, dict):
                n = n.get("count", 0)
            if isinstance(n, (int, float)):
                tot[y] = tot.get(y, 0) + int(n)
    return dict(sorted(tot.items()))


def archive_years() -> tuple[set[int], str]:
    """Fiscal years the source archive holds, from disk or the manifest."""
    names: list[str] = []
    where = ""
    if LCA_DIR.is_dir():
        names = [f.name for f in LCA_DIR.glob("*.xlsx")]
        where = "local archive"
    if not names and MANIFEST.exists():
        doc = json.loads(MANIFEST.read_text())
        names = [f["name"] for f in doc.get("files", [])]
        where = f"manifest ({doc.get('archived_at', 'archived')})"
    years = set()
    for name in names:
        for m in re.finditer(r"FY_?(\d{2,4})", name, re.I):
            v = int(m.group(1))
            years.add(v if v > 1000 else 2000 + v)
    return years, where


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not AGG.exists():
        print(f"  {AGG.relative_to(ROOT)} not found — run parse_federal")
        return 2
    agg = json.loads(AGG.read_text())
    series = national_by_year(agg)

    check(bool(series), "aggregate has a year series",
          f"{len(series)} years, {sum(series.values()):,} filings")
    if not series:
        return _report(args)

    years = sorted(series)
    lo, hi = years[0], years[-1]

    # 1. No hole in the middle.
    gaps = [y for y in range(lo, hi + 1) if y not in series]
    check(not gaps, "no year missing from the series",
          f"{lo}-{hi} continuous" if not gaps
          else f"nothing for {', '.join(map(str, gaps))} — a lost source file "
               f"looks exactly like this")

    # 2. No implausible swing. Interior years only: the first and last are
    #    partial by construction and always look like a cliff.
    interior = years[1:-1]
    swings = []
    for y in interior:
        prev, nxt = series.get(y - 1), series.get(y + 1)
        if not prev or not nxt:
            continue
        cur = series[y]
        if cur < SWING_FLOOR * prev and cur < SWING_FLOOR * nxt:
            swings.append(f"{y}: {cur:,} against {prev:,} and {nxt:,} (collapse)")
        elif cur > SWING_CEILING * prev and cur > SWING_CEILING * nxt:
            swings.append(f"{y}: {cur:,} against {prev:,} and {nxt:,} (spike)")
    check(not swings, "no year swings against both neighbours",
          f"{len(interior)} interior years checked" if not swings
          else "; ".join(swings[:3]))

    # 3. The output covers what the archive holds.
    arch, where = archive_years()
    if arch:
        # The aggregate is keyed on DECISION_DATE year, which spills one year
        # either side of the fiscal-year filenames, so compare the span rather
        # than demanding an exact set.
        missing = [y for y in sorted(arch) if not (lo <= y <= hi)]
        check(not missing, "output span covers the archive",
              f"archive FY{min(arch)}-FY{max(arch)} within output {lo}-{hi} "
              f"[{where}]" if not missing
              else f"archive has {', '.join(f'FY{y}' for y in missing)} but "
                   f"the output stops at {lo}-{hi}")
    else:
        check(True, "archive not readable here",
              "no local files and no manifest; span not cross-checked")

    # 4. The year series has to reconcile with the headline total, because
    #    both are published: the total is stated in prose and the series is
    #    what a reader sums off the chart. Filings whose decision date is
    #    missing or unparseable land in total_lcas and in no year at all, so
    #    the two legitimately differ -- but only by a little. A widening gap
    #    means dates stopped parsing, and the chart quietly stops matching
    #    the sentence next to it.
    headline = sum(v.get("total_lcas", 0) for v in agg.values())
    dated = sum(series.values())
    orphan = headline - dated
    share = 100 * orphan / headline if headline else 0
    check(share <= 10, "year series reconciles with the headline total",
          f"{dated:,} of {headline:,} carry a year; {orphan:,} undated ({share:.1f}%)"
          if share <= 10 else
          f"{orphan:,} of {headline:,} filings ({share:.1f}%) have no usable "
          f"year, so the chart sums to {dated:,} while the total reads "
          f"{headline:,}")

    # 5. Published figures. These are the numbers the site states, so a
    #    silent halving should stop a deploy rather than reach a reader.
    total = sum(series.values())
    check(total > 100_000, "national total is plausible", f"{total:,} filings")
    check(len(agg) > 80, "university count is plausible", f"{len(agg)} universities")

    if args.verbose:
        for y in years:
            print(f"      {y}: {series[y]:,}")

    return _report(args)


def _report(args) -> int:
    failed = [r for r in _results if not r[0]]
    print()
    for ok, name, detail in _results:
        print(f"  [{'ok  ' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))
    print()
    if failed:
        print(f"  {len(failed)} of {len(_results)} LCA sanity checks FAILED")
        return 1
    print(f"  all {len(_results)} LCA sanity checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
