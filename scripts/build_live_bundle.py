#!/usr/bin/env python3
"""Build the compact data bundle the live voice dashboard runs on.

The dashboard has to feel instant, so it holds NO network dependency once
loaded. Every series a voice command can summon is already in the browser;
a tool call only re-renders. That constrains the bundle to something small
enough to ship with the page -- target under 200 KB uncompressed.

Contents, all derived from files already in this repo:

  degrees   IPEDS Completions by award level (master's 7, doctorate 17),
            core-STEM CIP family, and year: total and non-resident counts.
            This is the series behind the expansion finding.
  f1        State Department F-1 visa issuance by fiscal year, with China
            and India broken out.
  national  The national non-resident share of research doctorates.

Usage:
    python3 scripts/build_live_bundle.py
    python3 scripts/build_live_bundle.py --out site/data/live_bundle.json
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from atomic_write import write_text

ROOT = Path(__file__).resolve().parent.parent
import sys as _sys
_sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW   # noqa: E402
IPEDS = ROOT / "data" / "ipeds"
DEFAULT_OUT = ROOT / "site" / "data" / "live_bundle.json"

FIELDS = {"11": "Computer science", "14": "Engineering",
          "15": "Engineering tech", "26": "Biological sciences",
          "27": "Math & statistics", "30": "Interdisciplinary",
          "40": "Physical sciences", "42": "Psychology"}

# FIELDS carries display labels, so it cannot simply BE the canonical set --
# but its keys must never drift from it. Seven scripts each kept a private
# copy of these eight families; they agreed, which is what made the drift
# risk invisible. Assert rather than restate.
assert set(FIELDS) == set(STEM_NARROW), (
    f"FIELDS {sorted(FIELDS)} has drifted from pipeline/models.py "
    f"STEM_NARROW {sorted(STEM_NARROW)}")

# Award level 9 is the pre-2010 research-doctorate coding; 17 replaced it.
# Omitting 9 left the doctorate series empty before 2008 and understated 2008
# by 79% and 2009 by 57%, which drew a fabricated five-fold ramp into 2010 on
# the live dashboard. Institutions migrated one at a time across 2008-09 and
# each reported exactly one coding, so summing both cannot double-count -- the
# same rule pipeline.models.bases_for() applies everywhere else.
# First-professional degrees were AWLEVEL 10, not 9, so this does not sweep
# MDs and JDs into the doctorate counts.
LEVELS = {"7": "masters", "9": "doctorate", "17": "doctorate"}
# 2008, not earlier: CTOTALT/CNRALT below first appear in the 2008 file. The
# 1995-2007 files carry residency as sex-split race columns (CRACE01/02 against
# CRACE15/16), so those years parsed to zero and were dropped -- START_YEAR was
# 2005 but the bundle has always begun at 2008. scripts/build_long_series.py
# reads the legacy columns and covers 1995-2025 if a longer series is wanted.
START_YEAR = 2008


def source_files() -> dict[int, str]:
    out: dict[int, str] = {}
    for path in glob.glob(str(IPEDS / "*_a*.csv")):
        m = re.search(r"c(\d{4})_a", os.path.basename(path).lower())
        if not m:
            continue
        year = int(m.group(1))
        if year not in out or "_rv" in path:
            out[year] = path
    return out


def build_degrees():
    """{level: {cip: {year: [total, nra]}}}"""
    acc = {lv: defaultdict(dict) for lv in LEVELS.values()}
    files = source_files()
    for year in sorted(files):
        if year < START_YEAR:
            continue
        per = {lv: defaultdict(lambda: [0, 0]) for lv in LEVELS.values()}
        try:
            with open(files[year], newline="", encoding="utf-8-sig",
                      errors="replace") as fh:
                for row in csv.DictReader(fh):
                    lv = LEVELS.get((row.get("AWLEVEL") or "").lstrip("0"))
                    if not lv:
                        continue
                    cip = (row.get("CIPCODE") or "").split(".")[0].zfill(2)
                    if cip not in FIELDS:
                        continue
                    try:
                        per[lv][cip][0] += int(row.get("CTOTALT") or 0)
                        per[lv][cip][1] += int(row.get("CNRALT") or 0)
                    except ValueError:
                        continue
        except OSError:
            continue
        for lv, by_cip in per.items():
            for cip, (t, n) in by_cip.items():
                if t:
                    acc[lv][cip][year] = [t, n]
    return {lv: dict(v) for lv, v in acc.items()}


def build_f1():
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from build_f1_series import build as build_series
        return build_series()
    except Exception as e:                       # noqa: BLE001
        print(f"  warning: F-1 series unavailable ({e})", file=sys.stderr)
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    degrees = build_degrees()
    f1 = build_f1()

    bundle = {
        "meta": {
            "fields": FIELDS,
            "levels": list(LEVELS.values()),
            "basis": ("IPEDS Completions, CIP families "
                      + ", ".join(sorted(FIELDS)) + "; CTOTALT and CNRALT"),
            "note": ("Domestic is derived as total minus non-resident. "
                     "Counts are degrees conferred, not enrolment."),
        },
        "degrees": degrees,
        "f1": f1,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(bundle, separators=(",", ":"))
    write_text(out, text)

    n_years = {lv: len({y for cip in v.values() for y in cip})
               for lv, v in degrees.items()}
    print(f"  wrote {out}  ({len(text) / 1024:.0f} KB)")
    print(f"  degrees: {', '.join(f'{lv} {n} years' for lv, n in n_years.items())}")
    print(f"  f1: {len(f1)} fiscal years")
    return 0


if __name__ == "__main__":
    sys.exit(main())