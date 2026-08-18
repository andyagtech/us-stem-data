#!/usr/bin/env python3
"""Remove duplicate records from harvest CSVs, keyed on the OAI identifier.

Repositories expose the same record through more than one set — Purdue
publishes its dissertations under both `publication:open_access_dissertations`
and `publication:etd` — and until dedup was added to scrape_oai_etds.py those
rows were written twice. The duplicates are byte-identical, so keeping the
first occurrence loses nothing.

Rows with no identifier are always kept; they cannot be compared safely.

Usage:
    python scripts/dedupe_harvest_csv.py --check           # report only
    python scripts/dedupe_harvest_csv.py --repo purdue     # repair one
    python scripts/dedupe_harvest_csv.py --all             # repair all affected
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from pathlib import Path

csv.field_size_limit(1_000_000)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "western_us_dissertations"


def audit(path: Path) -> tuple[int, int, int]:
    """Return (total_rows, distinct_identifiers, excess_rows)."""
    total = 0
    seen: set[str] = set()
    excess = 0
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            total += 1
            ident = row.get("identifier")
            if not ident:
                continue
            if ident in seen:
                excess += 1
            else:
                seen.add(ident)
    return total, len(seen), excess


def dedupe(path: Path, dry_run: bool = False) -> int:
    """Rewrite path keeping the first row per identifier. Returns rows removed."""
    total, _, excess = audit(path)
    if excess == 0:
        print(f"  {path.name}: already clean ({total:,} rows)")
        return 0
    if dry_run:
        print(f"  {path.name}: {excess:,} duplicate rows of {total:,}")
        return excess

    backup = path.with_suffix(path.suffix + ".predupe")
    if not backup.exists():
        shutil.copy2(path, backup)

    tmp = path.with_suffix(path.suffix + ".tmp_dedupe")
    seen: set[str] = set()
    kept = 0
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        with open(tmp, "w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=fields)
            writer.writeheader()
            for row in reader:
                ident = row.get("identifier")
                if ident:
                    if ident in seen:
                        continue
                    seen.add(ident)
                writer.writerow(row)
                kept += 1

    # Refuse to install a result that lost more than the duplicates we counted.
    if kept != total - excess:
        os.unlink(tmp)
        raise SystemExit(
            f"ABORT {path.name}: expected {total - excess:,} rows, produced {kept:,}"
        )

    os.replace(tmp, path)
    print(f"  {path.name}: {total:,} -> {kept:,} rows ({excess:,} removed), backup at {backup.name}")
    return excess


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", help="Single repo key (file <key>_etds.csv)")
    ap.add_argument("--all", action="store_true", help="Repair every affected CSV")
    ap.add_argument("--check", action="store_true", help="Report duplicates, change nothing")
    args = ap.parse_args()

    if args.repo:
        paths = [DATA_DIR / f"{args.repo}_etds.csv"]
    else:
        paths = sorted(DATA_DIR.glob("*_etds.csv"))

    if not paths:
        print("No harvest CSVs found", file=sys.stderr)
        return 1

    total_removed = 0
    for p in paths:
        if not p.exists():
            print(f"  {p.name}: missing", file=sys.stderr)
            continue
        if args.check:
            total, distinct, excess = audit(p)
            if excess:
                print(f"  {p.name}: {excess:,} duplicate rows of {total:,} ({distinct:,} distinct)")
        else:
            total_removed += dedupe(p, dry_run=False)

    if args.check:
        print("Check complete.")
    else:
        print(f"Removed {total_removed:,} duplicate rows in total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
