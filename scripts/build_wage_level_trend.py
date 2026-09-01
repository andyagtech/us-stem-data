#!/usr/bin/env python3
"""Has the wage level employers promise moved over fifteen years?

The wage-level finding rests on two years, FY2019 and FY2023. Two points
cannot say whether employers have been shifting toward the bottom of the
legal range, holding steady, or moving up -- and that is the question the
finding invites. The disclosure archive runs from FY2008, so the series can
be built.

ONE FILE AT A TIME. The archive is 4.3 GB against roughly 8 GB free, so each
file is fetched from S3, reduced to counts, and deleted before the next.
Nothing is kept but the tallies.

THE FISCAL YEAR COMES FROM THE FILE, NOT THE FILENAME where the two can
disagree. Quarterly files are summed into their year; a year assembled from
fewer than four quarters is reported as partial rather than compared with a
complete one.

Usage:
  python3 scripts/build_wage_level_trend.py
  python3 scripts/build_wage_level_trend.py --keep
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import warnings
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "data" / "h1b" / "_lca_work"
OUT = ROOT / "site" / "data" / "wage_level_trend.json"
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

BUCKET = "s3://phd-demographics-raw-data/data/h1b/lca/"
PROFILE = "personal"
LEVELS = ("Level I", "Level II", "Level III", "Level IV")
LEVEL_ALIASES = {"I": "Level I", "II": "Level II",
                 "III": "Level III", "IV": "Level IV"}


def listing() -> list[str]:
    r = subprocess.run(["aws", "s3", "ls", BUCKET, "--profile", PROFILE],
                       capture_output=True, text=True)
    return [line.split()[-1] for line in r.stdout.splitlines()
            if line.strip().endswith(".xlsx") or line.strip().endswith(".xls")]


def year_of(fname: str) -> tuple[int | None, str | None]:
    """Fiscal year and quarter from the filename, both formats."""
    m = re.search(r"FY(\d{4})", fname, re.I) or re.search(r"fy(\d{4})", fname)
    year = int(m.group(1)) if m else None
    if year is None:
        m2 = re.search(r"FY(\d{2})\b", fname, re.I)
        if m2:
            year = 2000 + int(m2.group(1))
    q = re.search(r"_Q(\d)", fname, re.I)
    return year, (f"Q{q.group(1)}" if q else None)


def fetch(fname: str) -> Path | None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    dest = SCRATCH / fname
    if dest.exists():
        return dest
    subprocess.run(["aws", "s3", "cp", f"{BUCKET}{fname}", str(dest),
                    "--profile", PROFILE, "--no-progress"],
                   capture_output=True, text=True)
    return dest if dest.exists() else None


def scan(path: Path) -> dict[str, int]:
    import openpyxl
    counts = dict.fromkeys(LEVELS, 0)
    try:
        wb = openpyxl.load_workbook(path, read_only=True)
    except Exception as e:                                   # noqa: BLE001
        print(f"    {path.name}: unreadable ({str(e)[:50]})")
        return counts
    ws = wb[wb.sheetnames[0]]
    it = ws.iter_rows(values_only=True)
    hdr = [str(c) if c is not None else "" for c in next(it)]
    idx = {c: i for i, c in enumerate(hdr)}

    def pick(*names):
        return next((idx[n] for n in names if n in idx), None)

    i_lvl = pick("PW_WAGE_LEVEL_1", "PW_WAGE_LEVEL", "PW_WAGE_LEVEL_9089")
    i_st = pick("CASE_STATUS", "STATUS")
    i_vc = pick("VISA_CLASS", "PROGRAM")
    if i_lvl is None:
        print(f"    {path.name}: no wage-level column")
        wb.close()
        return counts
    for r in it:
        if i_st is not None:
            st = str(r[i_st] or "").strip().upper()
            if st and not st.startswith("CERTIFIED"):
                continue
        if i_vc is not None:
            vc = str(r[i_vc] or "").strip().upper()
            # Exact: "H-1B1 Chile" contains "H-1B" but is a different visa.
            if vc and vc not in ("H-1B", "H-1B "):
                continue
        raw = str(r[i_lvl] or "").strip()
        lvl = LEVEL_ALIASES.get(raw.upper(), raw)
        if lvl in counts:
            counts[lvl] += 1
    wb.close()
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    files = listing()
    if not files:
        print("  could not list the archive")
        return 1

    by_year: dict[int, dict[str, int]] = defaultdict(
        lambda: dict.fromkeys(LEVELS, 0))
    quarters: dict[int, set[str]] = defaultdict(set)
    annual_file: dict[int, tuple[str, int]] = {}
    per_file: dict[str, dict[str, int]] = {}
    superseded, skipped = [], []

    for fname in files:
        year, q = year_of(fname)
        if year is None:
            skipped.append(fname)
            continue
        print(f"  FY{year}{' ' + q if q else ''}: {fname}")
        p = fetch(fname)
        if not p:
            skipped.append(fname)
            continue
        got = scan(p)
        total = sum(got.values())
        per_file[fname] = got
        if total:
            if q:
                for k, v in got.items():
                    by_year[year][k] += v
                quarters[year].add(q)
            else:
                # Some years ship two overlapping ANNUAL files -- FY2018 has
                # both an end-of-year release and a separate full-year one,
                # and adding both doubled the year. Keep the larger and record
                # what was dropped rather than summing them.
                prev = annual_file.get(year)
                if prev and prev[1] >= total:
                    superseded.append({"file": fname, "year": year,
                                       "filings": total,
                                       "kept_instead": prev[0]})
                else:
                    if prev:
                        superseded.append({"file": prev[0], "year": year,
                                           "filings": prev[1],
                                           "kept_instead": fname})
                        for k in LEVELS:
                            by_year[year][k] -= per_file[prev[0]][k]
                    annual_file[year] = (fname, total)
                    for k, v in got.items():
                        by_year[year][k] += v
        if not args.keep:
            p.unlink(missing_ok=True)

    if len(by_year) < 5:
        print(f"  only {len(by_year)} years")
        return 1

    years = sorted(by_year)
    series = {}
    for y in years:
        c = by_year[y]
        tot = sum(c.values())
        if not tot:
            continue
        complete = y in annual_file or len(quarters[y]) == 4
        series[str(y)] = {
            "certified_filings": tot,
            **{k.replace(" ", "_").lower(): v for k, v in c.items()},
            "low_level_pct": round(100 * (c["Level I"] + c["Level II"]) / tot, 1),
            "level_i_pct": round(100 * c["Level I"] / tot, 1),
            "complete_year": complete,
            "quarters_seen": sorted(quarters[y]) or None,
        }

    full = [y for y in series if series[y]["complete_year"]]
    doc = {
        "_comment": (
            "Share of certified H-1B labour condition applications naming "
            "each prevailing-wage level, by fiscal year. THE TREND RUNS THE "
            "OTHER WAY FROM WHAT TWO YEARS IMPLIED: the Level I or II share "
            "FELL from 80.5% in FY2017 to 62.7% in FY2025, and Level I alone "
            "from 44.4% to 20.8%. Employers file higher on the scale than "
            "they did, not lower, and any page quoting the level figures must "
            "say so. The break is between FY2017 and FY2018 (Level I 44.4% to "
            "17.9%); both files use the same column and visa-class field, so "
            "it is a real reading, and it coincides with the April 2017 "
            "executive order that put Level I filings under scrutiny -- a "
            "coincidence in time, not a demonstrated cause. THE LEVEL MIX IS "
            "A SEPARATE QUESTION from whether the wage clears a local median, "
            "which local_wage_comparison answers and where the picture is "
            "worse. "
            "PARTIAL YEARS ARE MARKED: a year assembled from fewer than four "
            "quarterly files is flagged complete_year false and must not be "
            "compared with a full one -- the level MIX is still meaningful "
            "for a partial year but the COUNT is not. Certified filings only, "
            "and VISA_CLASS matched exactly because 'H-1B1 Chile' contains "
            "'H-1B'. SOME YEARS SHIP TWO OVERLAPPING ANNUAL FILES -- FY2018 "
            "has both an end-of-year release and a separate full-year one, "
            "and summing them doubled that year to 939,820 against a true "
            "576,359. The larger is kept and the other recorded in "
            "superseded_duplicates. Column names and level spellings changed with the FLAG "
            "system in FY2020, and both forms are read. THIS IS WHAT WAS "
            "PROMISED, not paid, and filing at any level is lawful."),
        "source": "US DOL OFLC, H-1B LCA disclosure archive",
        "source_url": "https://www.dol.gov/agencies/eta/foreign-labor/performance",
        "years": [int(y) for y in years if str(y) in series],
        "complete_years": sorted(int(y) for y in full),
        "series": series,
        "files_skipped": skipped,
        "superseded_duplicates": superseded,
    }
    write_json(OUT, doc)

    print(f"\n  {len(series)} years, {len(full)} complete")
    print(f"  {'FY':6}{'filings':>11}{'Lvl I':>8}{'Lvl I+II':>10}{'':>4}")
    for y in years:
        s = series.get(str(y))
        if not s:
            continue
        mark = "" if s["complete_year"] else "  partial"
        print(f"  {y:6}{s['certified_filings']:>11,}{s['level_i_pct']:>7.1f}%"
              f"{s['low_level_pct']:>9.1f}%{mark}")
    if len(full) >= 2:
        f, l = sorted(full)[0], sorted(full)[-1]
        print(f"\n  complete years only: Level I+II "
              f"{series[f]['low_level_pct']}% in {f} -> "
              f"{series[l]['low_level_pct']}% in {l}")
    for x in skipped[:5]:
        print(f"  SKIPPED {x}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
