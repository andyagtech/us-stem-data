#!/usr/bin/env python3
"""Does the domestic STEM pipeline leak, and where?

The intuitive version of "the pipeline is broken" -- that America is not
producing STEM graduates -- is not what the data shows. Domestic core-STEM
completions rose at every level between 2011 and 2025: bachelor's +56%,
master's +82%, research doctorates +35%. Stating it the intuitive way
invites a one-line rebuttal.

The defensible question is CONVERSION. A growing bachelor's pool that
produces a shrinking proportion of doctorates is a pipeline problem even
while every absolute number rises, and that is measurable here.

COHORT LAG. A bachelor's graduate does not appear in doctorate statistics
the same year. Conversion is therefore computed against a lagged cohort --
six years to the doctorate, two to the master's -- so a 2011 bachelor's
cohort is compared with 2017 doctorates. The lag is a modelling choice, is
stated in the output, and the raw counts are published so anyone can apply
their own.

WHAT THIS CANNOT SHOW. IPEDS counts degrees conferred, not individuals. No
published source follows a person from a bachelor's to a doctorate, so this
is a ratio between two populations, not a tracked cohort. It cannot say
whether someone chose industry, was not admitted, or was not funded.

Usage:
  python3 scripts/build_domestic_pipeline.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW  # noqa: E402

IPEDS = ROOT / "data" / "ipeds"
OUT = ROOT / "site" / "data" / "domestic_pipeline.json"

LEVELS = {"bachelors": 5, "masters": 7, "doctorate": 17}
LAG = {"masters": 2, "doctorate": 6}
FIRST, LAST = 2011, 2025


def rows(year: int):
    for n in (f"c{year}_a.csv", f"C{year}_a.csv", f"C{year}_A.csv"):
        p = IPEDS / n
        if p.exists():
            with open(p, newline="", encoding="utf-8-sig", errors="replace") as fh:
                yield from csv.DictReader(fh)
            return
    for n in (f"C{year}_A.zip", f"c{year}_a.zip"):
        p = IPEDS / n
        if p.exists():
            with zipfile.ZipFile(p) as z:
                inner = next(x for x in z.namelist() if x.lower().endswith(".csv"))
                with z.open(inner) as fh:
                    yield from csv.DictReader(
                        io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace"))
            return


def tally(year: int) -> dict | None:
    fam = set(STEM_NARROW)
    agg = {k: [0, 0] for k in LEVELS}
    inv = {v: k for k, v in LEVELS.items()}
    seen = False
    for r in rows(year):
        cip = (r.get("CIPCODE") or "").strip()
        if cip.split(".")[0].zfill(2) not in fam or cip.startswith("99"):
            continue
        try:
            lvl = int(r.get("AWLEVEL") or 0)
            if lvl not in inv or int(r.get("MAJORNUM") or 1) != 1:
                continue
            tot, nra = int(r.get("CTOTALT") or 0), int(r.get("CNRALT") or 0)
        except ValueError:
            continue
        seen = True
        a = agg[inv[lvl]]
        a[0] += tot
        a[1] += nra
    if not seen:
        return None
    return {k: {"total": v[0], "nra": v[1], "domestic": v[0] - v[1]}
            for k, v in agg.items()}


def main() -> int:
    series = {}
    for y in range(FIRST, LAST + 1):
        got = tally(y)
        if got:
            series[str(y)] = got
    if not series:
        print("  no completions data found")
        return 1

    years = sorted(int(y) for y in series)
    conversion = {}
    for level, lag in LAG.items():
        rowset = []
        for by in years:
            gy = by + lag
            if str(gy) not in series:
                continue
            b = series[str(by)]["bachelors"]["domestic"]
            g = series[str(gy)][level]["domestic"]
            if b:
                rowset.append({"bachelors_year": by, "graduate_year": gy,
                               "domestic_bachelors": b, "domestic_graduate": g,
                               "rate": round(100 * g / b, 2)})
        conversion[level] = rowset

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "_comment": ("Domestic core-STEM completions by level, and the rate at "
                     "which a bachelor's cohort is followed by graduate degrees. "
                     "Absolute domestic production ROSE at every level over this "
                     "window -- the pipeline claim that survives scrutiny is "
                     "about conversion, not output. IPEDS counts degrees, not "
                     "people: this is a ratio between two populations, not a "
                     "tracked cohort, and it cannot say whether someone chose "
                     "industry, was not admitted, or was not funded."),
        "source": "NCES IPEDS Completions, eight core-STEM CIP families",
        "lag_years": LAG,
        "lag_note": ("A modelling choice, not a measurement. Raw counts are "
                     "published so another lag can be applied."),
        "series": series,
        "conversion": conversion,
    }, indent=1) + "\n")

    f, l = series[str(years[0])], series[str(years[-1])]
    print(f"  domestic core-STEM completions, {years[0]}-{years[-1]}")
    for k in LEVELS:
        a, b = f[k]["domestic"], l[k]["domestic"]
        print(f"   {k:11} {a:>9,} -> {b:>9,}   ({100*(b/a-1):+.0f}%)")
    print()
    for level, rowset in conversion.items():
        if not rowset:
            continue
        a, b = rowset[0], rowset[-1]
        print(f"  domestic bachelor's -> {level} (lag {LAG[level]}y)")
        print(f"   {a['bachelors_year']}->{a['graduate_year']}: {a['rate']}%"
              f"    {b['bachelors_year']}->{b['graduate_year']}: {b['rate']}%"
              f"   ({b['rate'] - a['rate']:+.2f} pts)")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
