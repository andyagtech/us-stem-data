#!/usr/bin/env python3
"""Core-STEM graduate degrees by IPEDS race/citizenship category, per year.

IPEDS reports completions in ONE field with nine mutually exclusive values.
Non-resident sits alongside the race categories rather than above them: a
permanent resident is counted under their race, and a foreign national on a
student visa is counted as non-resident regardless of race. There is no
citizen-versus-foreign split in the data, and no way to separate citizens
from permanent residents.

That matters for any comparison against national population shares, so both
denominators are published here:

  share_all        of every degree conferred, non-residents included
  share_domestic   of degrees to residents only, non-residents removed

A group's share of all degrees falls when non-resident numbers rise even if
that group's own count is flat, which makes share_all the wrong figure to
put beside a census population share. share_domestic is the comparable one.

The modern columns (CWHITT, CNRALT, ...) exist from 2010. Earlier files use
a race-by-sex scheme that is not carried here.

Usage:
  python3 scripts/build_completions_by_race.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IPEDS = ROOT / "data" / "ipeds"
OUT = ROOT / "site" / "data" / "completions_by_race.json"

# The one definition of the narrow eight lives in pipeline.models; restating
# it here would be a second place for it to drift.
try:
    sys.path.insert(0, str(ROOT))
    from pipeline.models import STEM_NARROW as FAMILIES
except ImportError:  # pragma: no cover - only if run outside the repo
    FAMILIES = {"11", "14", "15", "26", "27", "30", "40", "42"}
LEVELS = {"masters": 7, "doctorate": 17}
FIRST_MODERN_YEAR = 2010

CATS = [
    ("CNRALT", "nonresident", "Non-resident (temporary visa)"),
    ("CWHITT", "white", "White"),
    ("CASIAT", "asian", "Asian"),
    ("CHISPT", "hispanic", "Hispanic or Latino"),
    ("CBKAAT", "black", "Black or African American"),
    ("C2MORT", "two_or_more", "Two or more races"),
    ("CUNKNT", "unknown", "Race/ethnicity unknown"),
    ("CAIANT", "native_american", "American Indian or Alaska Native"),
    ("CNHPIT", "pacific_islander", "Native Hawaiian or Other Pacific Islander"),
]


def rows_for(year: int):
    """Yield the completions rows for a year, from CSV or the zip it ships in."""
    for name in (f"c{year}_a.csv", f"C{year}_a.csv", f"C{year}_A.csv"):
        p = IPEDS / name
        if p.exists():
            with open(p, newline="", encoding="latin-1") as fh:
                yield from csv.DictReader(fh)
            return
    for name in (f"C{year}_A.zip", f"c{year}_a.zip"):
        p = IPEDS / name
        if p.exists():
            with zipfile.ZipFile(p) as z:
                inner = next(n for n in z.namelist() if n.lower().endswith(".csv"))
                with z.open(inner) as fh:
                    yield from csv.DictReader(io.TextIOWrapper(fh, encoding="latin-1"))
            return


def tally(year: int) -> dict | None:
    out = {lvl: {key: 0 for _c, key, _l in CATS} | {"total": 0} for lvl in LEVELS}
    seen = False
    for r in rows_for(year):
        cip = (r.get("CIPCODE") or "").strip()
        if cip[:2] not in FAMILIES or cip.startswith("99"):
            continue
        try:
            level = int(r.get("AWLEVEL") or 0)
            # MAJORNUM 2 is a second major on the same degree; counting it
            # would double-count the student.
            if int(r.get("MAJORNUM") or 1) != 1:
                continue
        except ValueError:
            continue
        for lvl, code in LEVELS.items():
            if level != code:
                continue
            if "CNRALT" not in r:
                return None       # pre-2010 layout
            seen = True
            out[lvl]["total"] += int(r.get("CTOTALT") or 0)
            for col, key, _label in CATS:
                out[lvl][key] += int(r.get(col) or 0)
    return out if seen else None


def main() -> int:
    years = sorted({int(n[1:5]) for n in
                    (p.name for p in IPEDS.iterdir())
                    if len(n) > 5 and n[0] in "cC" and n[1:5].isdigit()
                    and int(n[1:5]) >= FIRST_MODERN_YEAR})
    series: dict[str, dict] = {lvl: {} for lvl in LEVELS}
    for y in years:
        got = tally(y)
        if not got:
            print(f"  {y}: skipped (no modern race columns)")
            continue
        for lvl in LEVELS:
            t = got[lvl]
            if not t["total"]:
                continue
            # The nine categories partition the total, so they must sum to it.
            # In 2010 they do not: institutions were mid-migration between the
            # old race-by-sex scheme and the current one, so the new columns
            # are only partly filled. That year's White count is 23,030 against
            # 52,017 in 2011 -- not a collapse, an artefact. CNRALT survived
            # both schemes, which is why the non-resident figure looks fine and
            # the breakdown does not.
            parts = sum(t[k] for _c, k, _l in CATS)
            if abs(parts - t["total"]) > 0.01 * t["total"]:
                print(f"  {y} {lvl}: categories sum to {parts:,} against a total of "
                      f"{t['total']:,}; dropping this year's breakdown")
                continue
            dom = t["total"] - t["nonresident"]
            series[lvl][str(y)] = {
                "total": t["total"],
                "domestic_total": dom,
                "counts": {k: t[k] for _c, k, _l in CATS},
                "share_all": {k: round(100 * t[k] / t["total"], 2) for _c, k, _l in CATS},
                "share_domestic": {
                    k: (round(100 * t[k] / dom, 2) if dom else 0.0)
                    for _c, k, _l in CATS if k != "nonresident"},
            }
        m = series["masters"].get(str(y), {})
        print(f"  {y}: master's {m.get('total', 0):>7,}  "
              f"non-res {m.get('share_all', {}).get('nonresident', 0):5.1f}%  "
              f"white {m.get('share_all', {}).get('white', 0):5.1f}% of all, "
              f"{m.get('share_domestic', {}).get('white', 0):5.1f}% of domestic")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "_comment": ("Core-STEM graduate completions by IPEDS race/citizenship "
                     "category. share_all includes non-residents in the "
                     "denominator; share_domestic excludes them. Use "
                     "share_domestic when comparing against national population "
                     "shares -- a group's share_all falls when non-resident "
                     "numbers rise even if its own count is unchanged."),
        "source": "NCES IPEDS Completions",
        "basis": {"cip_families": sorted(FAMILIES),
                  "award_levels": {"masters": 7, "doctorate": 17},
                  "note": "First majors only (MAJORNUM 1)."},
        "categories": {k: label for _c, k, label in CATS},
        "levels": series,
    }, indent=1) + "\n")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
