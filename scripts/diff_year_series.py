#!/usr/bin/env python3
"""What the date correction does to a university's published year series.

The DSpace re-harvest replaces an accession date with the real award date.
On mines, 82.4% of records were misdated by a median of 28 years. That moves
the year histogram on every affected university page, so it should be looked at
before it is deployed rather than after.

Compares the CURRENT harvest CSV against its `.csv.prev` — the generation the
merge kept before promoting — and reports the year distribution both ways.

Usage:
    python3 scripts/diff_year_series.py --repo mines
    python3 scripts/diff_year_series.py --all
"""
from __future__ import annotations

import argparse
import collections
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "western_us_dissertations"


def year(v: str | None) -> int | None:
    m = re.search(r"(19|20)\d{2}", v or "")
    return int(m.group(0)) if m else None


def series(path: Path, field: str) -> collections.Counter:
    out: collections.Counter = collections.Counter()
    if not path.exists():
        return out
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            y = year(r.get(field))
            if y and 1900 <= y <= 2030:
                out[y] += 1
    return out


def report(key: str) -> bool:
    cur = CORPUS / f"{key}_etds.csv"
    prev = CORPUS / f"{key}_etds.csv.prev"
    if not cur.exists():
        print(f"  {key}: no CSV"); return False
    if not prev.exists():
        print(f"  {key}: no .csv.prev — not yet re-harvested through the merge")
        return False

    before = series(prev, "date")            # what the site publishes today
    after = series(cur, "date_issued") or series(cur, "date")
    if not after:
        print(f"  {key}: no usable dates after"); return False

    ys = sorted(set(before) | set(after))
    tb, ta = sum(before.values()), sum(after.values())
    print(f"\n  === {key}   {tb:,} dated before -> {ta:,} after")

    # decade rollup: the shape a reader actually sees
    db: collections.Counter = collections.Counter()
    da: collections.Counter = collections.Counter()
    for y in ys:
        db[(y // 10) * 10] += before.get(y, 0)
        da[(y // 10) * 10] += after.get(y, 0)
    print(f"  {'decade':<10}{'before':>9}{'after':>9}{'change':>10}")
    for d in sorted(set(db) | set(da)):
        b, a = db.get(d, 0), da.get(d, 0)
        if b == 0 and a == 0:
            continue
        arrow = "" if b == a else ("  <-- moves" if abs(a - b) > max(20, 0.1 * max(b, 1)) else "")
        print(f"  {str(d)+'s':<10}{b:>9,}{a:>9,}{a-b:>+10,}{arrow}")

    # How far individual records move, BEFORE -> AFTER.
    #
    # This used to compare two columns of the CURRENT file, `date` against
    # `date_issued`. That measures how far a repository's ingest stamp sits
    # from its award date -- a real quantity, but not this one, and it was
    # printed under a label claiming records had moved. A record whose
    # published year is unchanged by the re-harvest still counted.
    #
    # Match records across the two files instead, on the same stable key the
    # merge itself uses: the repository-local record path, which survives a
    # repository changing its identifier prefix.
    def rec_key(r: dict) -> str:
        ident = (r.get("identifier") or "").strip()
        if ident.startswith("oai:") and ident.count(":") >= 2:
            return ident.split(":", 2)[2]
        return ident or (r.get("url") or "").strip()

    def year_by_key(path: Path, field: str, fallback: str = "") -> dict:
        out = {}
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            for r in csv.DictReader(fh):
                y = year(r.get(field)) or (year(r.get(fallback)) if fallback else None)
                k = rec_key(r)
                if k and y and 1900 <= y <= 2030:
                    out[k] = y
        return out

    yb = year_by_key(prev, "date")
    ya = year_by_key(cur, "date_issued", "date")
    common = yb.keys() & ya.keys()
    shifts = [ya[k] - yb[k] for k in common if ya[k] != yb[k]]
    print(f"  records matched across both files: {len(common):,} "
          f"(prev {len(yb):,}, cur {len(ya):,})")
    if shifts:
        shifts.sort()
        med = shifts[len(shifts) // 2]
        print(f"  records whose published year changes: {len(shifts):,}  "
              f"median {med:+d} years, range {min(shifts):+d}..{max(shifts):+d}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.repo:
        report(a.repo)
    elif a.all:
        keys = sorted(p.name.replace("_etds.csv.prev", "")
                      for p in CORPUS.glob("*_etds.csv.prev"))
        print(f"  {len(keys)} repo(s) have a .prev to compare against")
        for k in keys:
            report(k)
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
