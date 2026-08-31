#!/usr/bin/env python3
"""How the citizenship balance shifted across thirty years of graduate STEM.

The doctorate series already runs 1995-2025, but the doctorate is the small
end of graduate education: master's degrees outnumber it several times over,
and they are the larger route into the workforce and, through it, into
permanent residence. A shift shown only at doctorate level understates both
the scale and the timing.

This builds the same measure at master's level, at doctorate level, and for
the two combined, on one basis, for every year IPEDS supports.

TWO SCHEMA CHANGES, BOTH HANDLED

Residency columns were renamed in 2008: legacy CRACE01/CRACE02 are
non-resident men/women and CRACE15/CRACE16 are grand totals by sex; from 2008
CNRALT and CTOTALT carry the same quantities. Rows are read under whichever
scheme the file presents.

Doctorate award level 9 became 17 in 2010, and institutions migrated one at a
time across 2008 and 2009 -- no institution reports both in the same year, so
those two years must SUM the codings or the series shows a collapse and
recovery that never happened. Master's level 7 is stable throughout and needs
no such handling.

FIRST MAJORS ONLY, so a double-major is not counted twice, and CIPCODE 99
rollups are excluded so degrees are not counted under both a programme and a
summary row.

Usage:
  python3 scripts/build_graduate_balance.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IPEDS = ROOT / "data" / "ipeds"
OUT = ROOT / "site" / "data" / "graduate_balance.json"

sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW, TRANSITION_YEARS       # noqa: E402
from atomic_write import write_json                             # noqa: E402

MASTERS = 7
DOCTORATE_BY_YEAR = {}          # filled per year: which award codes count


def doctorate_levels(year: int) -> set[int]:
    """Award codes carrying research doctorates in a given year."""
    if year in TRANSITION_YEARS:
        return {9, 17}
    return {17} if year >= 2010 else {9}


def upper(reader):
    """Column names are lowercase before 2008 and uppercase after."""
    for row in reader:
        yield {k.upper(): v for k, v in row.items() if k}


def rows(year: int):
    """Yield completion rows for a year, preferring the revised file."""
    stems = [f"c{year}_a_rv", f"C{year}_A_RV", f"c{year}_a", f"C{year}_A"]
    if year < 2000:                        # 1995-96 is filed as c9596_a
        yy = year % 100
        stems = [f"c{yy:02d}{(yy + 1) % 100:02d}_a"] + stems
    for stem in stems:
        p = IPEDS / f"{stem}.csv"
        if p.exists():
            with open(p, newline="", encoding="utf-8-sig", errors="replace") as fh:
                yield from upper(csv.DictReader(fh))
            return p.name
        z = IPEDS / f"{stem}.zip"
        if z.exists():
            with zipfile.ZipFile(z) as zf:
                inner = next(x for x in zf.namelist() if x.lower().endswith(".csv"))
                with zf.open(inner) as fh:
                    yield from upper(csv.DictReader(
                        io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")))
            return z.name
    return None


def num(r: dict, key: str) -> int:
    try:
        return int(float(r.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def tally(year: int) -> dict | None:
    fam = set(STEM_NARROW)
    doc = doctorate_levels(year)
    agg = {"masters": [0, 0], "doctorate": [0, 0]}
    modern = None
    seen = 0

    for r in rows(year):
        if modern is None:
            modern = "CNRALT" in r and "CTOTALT" in r
        cip = (r.get("CIPCODE") or "").strip()
        if cip.split(".")[0].zfill(2) not in fam or cip.startswith("99"):
            continue
        lvl = num(r, "AWLEVEL")
        if lvl == MASTERS:
            key = "masters"
        elif lvl in doc:
            key = "doctorate"
        else:
            continue
        # MAJORNUM is absent from the oldest files; those carry first majors
        # only, so a missing column is treated as first-major.
        if "MAJORNUM" in r and num(r, "MAJORNUM") not in (0, 1):
            continue
        if modern:
            tot, nra = num(r, "CTOTALT"), num(r, "CNRALT")
        else:
            tot = num(r, "CRACE15") + num(r, "CRACE16")
            nra = num(r, "CRACE01") + num(r, "CRACE02")
        if not tot:
            continue
        seen += 1
        agg[key][0] += tot
        agg[key][1] += nra

    if not seen or not agg["masters"][0] or not agg["doctorate"][0]:
        return None

    out = {}
    for key, (tot, nra) in agg.items():
        out[key] = {"total": tot, "nra": nra, "domestic": tot - nra,
                    "share": round(100 * nra / tot, 1)}
    gt = agg["masters"][0] + agg["doctorate"][0]
    gn = agg["masters"][1] + agg["doctorate"][1]
    out["graduate"] = {"total": gt, "nra": gn, "domestic": gt - gn,
                       "share": round(100 * gn / gt, 1)}
    out["transition"] = year in TRANSITION_YEARS
    return out


def main() -> int:
    series, missing = {}, []
    for year in range(1995, 2026):
        got = tally(year)
        if got:
            series[str(year)] = got
        else:
            missing.append(year)

    if len(series) < 15:
        print(f"  only {len(series)} usable years; not enough for a series")
        return 1

    years = sorted(series)
    f, l = years[0], years[-1]
    levels = ("masters", "doctorate", "graduate")

    doc = {
        "_comment": (
            "Non-resident share of core-STEM degrees at MASTER'S and DOCTORATE "
            "level and for the two combined, 1995-2025. NRA is the IPEDS "
            "'Nonresident alien' reporting category -- a visa holder, not an "
            "immigrant; permanent residents are counted under their race and "
            "so fall in DOMESTIC here. First majors only, CIPCODE 99 rollups "
            "excluded. Residency columns were renamed in 2008 and doctorate "
            "award level 9 became 17 in 2010 with institutions migrating "
            "across 2008-09, so those two years sum both codings; master's "
            "level 7 is stable throughout. COUNTS ARE DEGREES, NOT PEOPLE."),
        "source": "NCES IPEDS Completions, eight core-STEM CIP families",
        "cip_families": list(STEM_NARROW),
        "years": [int(y) for y in years],
        "series": series,
        "shift": {lv: {"first_year": int(f), "last_year": int(l),
                       "first_share": series[f][lv]["share"],
                       "last_share": series[l][lv]["share"],
                       "change_pts": round(series[l][lv]["share"]
                                           - series[f][lv]["share"], 1),
                       "peak_year": int(max(years, key=lambda y: series[y][lv]["share"])),
                       "peak_share": max(series[y][lv]["share"] for y in years),
                       "domestic_change_pct": round(
                           100 * (series[l][lv]["domestic"]
                                  / series[f][lv]["domestic"] - 1), 1),
                       "nra_change_pct": round(
                           100 * (series[l][lv]["nra"] / series[f][lv]["nra"] - 1), 1)}
                  for lv in levels},
        "missing_years": missing,
    }
    write_json(OUT, doc)

    print(f"  {len(years)} years, {f}-{l}" + (f"  (missing {missing})" if missing else ""))
    print(f"  {'year':6}{'MA share':>10}{'PhD share':>11}{'grad share':>12}"
          f"{'grad NRA':>11}{'grad dom':>10}")
    for y in years:
        if int(y) % 5 == 0 or y in (f, l):
            s = series[y]
            print(f"  {y:6}{s['masters']['share']:>9.1f}%{s['doctorate']['share']:>10.1f}%"
                  f"{s['graduate']['share']:>11.1f}%{s['graduate']['nra']:>11,}"
                  f"{s['graduate']['domestic']:>10,}")
    for lv in levels:
        sh = doc["shift"][lv]
        print(f"  {lv:10} {sh['first_share']:.1f}% -> {sh['last_share']:.1f}% "
              f"({sh['change_pts']:+.1f} pts), peak {sh['peak_share']:.1f}% in "
              f"{sh['peak_year']}; NRA {sh['nra_change_pct']:+.1f}%, "
              f"domestic {sh['domestic_change_pct']:+.1f}%")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
