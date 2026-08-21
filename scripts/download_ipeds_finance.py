#!/usr/bin/env python3
"""Fetch IPEDS tuition RATES (IC*_AY) and private-institution finance (F*_F2).

Two mirrors serve IPEDS complete data files and NEITHER is a superset:

    complete-data-files   the current path; has 2015-16 onward, 404s on older
    datacenter/data       the frozen mirror; has the older years, 404s on new

scripts/ipeds_config.py notes that the new path is a superset, which holds for
the completions files it was written about but NOT for IC*_AY -- IC2014_AY is
404 there and 200 on the mirror. So every fetch here tries both.

Why these two collections:
  IC*_AY   published tuition and required fees by level. TUITION3/TUITION4 are
           graduate in-state/out-of-state. Needed because the finance files
           give total tuition revenue with no breakdown by level or residency.
  F*_F2    tuition revenue for private not-for-profit (FASB) institutions.
           F*_F1A covers public (GASB) institutions only and is already local
           for 2014-15 onward; without F2 the series omits the privates.

Resumable: a file already on disk is skipped. Safe to re-run.

Usage:
    python3 scripts/download_ipeds_finance.py --kind ic   --start 2014 --end 2023
    python3 scripts/download_ipeds_finance.py --kind f2   --start 2014 --end 2023
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = {"ic": ROOT / "data" / "ipeds_tuition",
       "f2": ROOT / "data" / "ipeds_finance"}

BASES = ("https://nces.ed.gov/ipeds/complete-data-files",
         "https://nces.ed.gov/ipeds/datacenter/data")

UA = {"User-Agent": "Mozilla/5.0 (research; contact via site)"}


def stem(kind: str, year: int) -> str:
    if kind == "ic":
        return f"IC{year}_AY"
    return f"F{str(year)[2:]}{str(year + 1)[2:]}_F2"


def fetch(name: str, dest: Path, timeout: int = 90) -> str:
    """Download and extract one stem. Returns a status word."""
    got = sorted(dest.glob(f"{name.lower()}*")) + sorted(dest.glob(f"{name}*"))
    if any(p.suffix.lower() == ".csv" for p in got):
        return "have"
    last = ""
    for base in BASES:
        url = f"{base}/{name}.zip"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                blob = r.read()
        except urllib.error.HTTPError as e:
            last = f"{e.code}"
            continue
        except Exception as e:                      # noqa: BLE001
            last = type(e).__name__
            continue
        if len(blob) < 500:
            last = "tiny"
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                z.extractall(dest)
        except zipfile.BadZipFile:
            last = "badzip"
            continue
        return "ok"
    return f"MISS({last})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", choices=("ic", "f2"), required=True)
    ap.add_argument("--start", type=int, default=2014)
    ap.add_argument("--end", type=int, default=2023)
    args = ap.parse_args()

    dest = OUT[args.kind]
    dest.mkdir(parents=True, exist_ok=True)
    ok = miss = have = 0
    for year in range(args.start, args.end + 1):
        name = stem(args.kind, year)
        st = fetch(name, dest)
        print(f"  {name:<14} {st}", flush=True)
        ok += st == "ok"
        have += st == "have"
        miss += st.startswith("MISS")
    print(f"\n  {ok} downloaded, {have} already present, {miss} unavailable -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
