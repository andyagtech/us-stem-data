#!/usr/bin/env python3
"""Fetch NSF Survey of Earned Doctorates data-table releases.

WHY
    SED is the strongest long-run series available for this work: a census of
    every research doctorate awarded in the US, reporting citizenship, and
    reaching back to 1979 -- twenty-six years further than IPEDS Completions,
    which carries no citizenship breakdown before 1995.

    The catch is granularity. In any single release:
        table 1-1  annual totals, 1958 onward, NO citizenship
        table 1-6  citizenship, but only at FIVE-YEAR intervals
        table 1-7  citizenship annually, but only a rolling ~10-year window
    So an ANNUAL citizenship series longer than a decade has to be assembled
    by chaining table 1-7 across successive releases, each contributing the
    years the next one has already dropped.

RULES
    * Never overwrite and never delete. Each release lands in its own
      directory under data/nsf_sed/releases/<pubid>/, so the existing
      data/nsf_sed/tables/ (the 2024 release) is untouched.
    * Download to .partial and rename only after the zip opens cleanly.

USAGE
    python3 scripts/download_sed_archive.py --list
    python3 scripts/download_sed_archive.py
    python3 scripts/download_sed_archive.py --only nsf22300
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "nsf_sed" / "releases"
BASE = "https://ncses.nsf.gov/pubs"

# pubid -> the data year the release reports. Verified reachable 2026-08-22 by
# HEAD on the excels zip; NCSES pub ids do not follow a computable pattern, so
# they are listed rather than generated. Re-check the survey page for new ones:
#   https://ncses.nsf.gov/surveys/earned-doctorates
RELEASES: dict[str, int] = {
    "nsf20301": 2018,
    "nsf21308": 2019,
    "nsf22300": 2020,
    "nsf23300": 2021,
    "nsf24300": 2022,
    "nsf24336": 2023,
    "nsf25349": 2024,   # already unpacked under data/nsf_sed/tables/
}


def zip_url(pubid: str) -> str:
    return f"{BASE}/{pubid}/assets/data-tables/{pubid}-data-tables-tables-excels.zip"


def fetch(pubid: str, year: int, timeout: int = 600) -> bool:
    dest = OUT / pubid
    if dest.exists() and any(dest.glob("*.xlsx")):
        print(f"  {pubid} ({year}): already unpacked, {len(list(dest.glob('*.xlsx')))} tables")
        return True
    dest.mkdir(parents=True, exist_ok=True)
    tmp = OUT / f"{pubid}.zip.partial"
    print(f"  {pubid} ({year}): fetching", flush=True)
    try:
        with requests.get(zip_url(pubid), stream=True, timeout=timeout) as r:
            r.raise_for_status()
            expect = int(r.headers.get("content-length") or 0)
            got = 0
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
                    got += len(chunk)
        if expect and got != expect:
            raise OSError(f"short read: {got} of {expect}")
        with zipfile.ZipFile(tmp) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".xlsx")]
            if not names:
                raise OSError("zip holds no .xlsx")
            for n in names:
                # Flatten: releases nest tables under a directory that differs
                # between years, and the basename already carries the pub id.
                data = zf.read(n)
                (dest / Path(n).name).write_bytes(data)
        os.replace(tmp, OUT / f"{pubid}.zip")
        print(f"    ok  {len(names)} tables, {got/1048576:.1f} MB")
        return True
    except Exception as e:                                    # noqa: BLE001
        print(f"    FAILED: {e}")
        if tmp.exists():
            tmp.unlink()
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()

    items = ({args.only: RELEASES[args.only]} if args.only else RELEASES)
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"  releases dir: {OUT}")
    for pid, yr in sorted(items.items(), key=lambda kv: kv[1]):
        have = (OUT / pid).exists() and any((OUT / pid).glob("*.xlsx"))
        print(f"    {'have' if have else 'MISSING':>7}  {pid}  SED {yr}")
    if args.list:
        return 0
    print()
    failed = [p for p, y in sorted(items.items(), key=lambda kv: kv[1])
              if not fetch(p, y)]
    print(f"\n  {len(items)-len(failed)} of {len(items)} releases available")
    if failed:
        print(f"  failed: {', '.join(failed)}")
        return 1
    print("  Nothing existing was modified. Next:")
    print("    python3 scripts/build_sed_annual_series.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
