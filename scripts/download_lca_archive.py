#!/usr/bin/env python3
"""Fetch DOL LCA disclosure files we do not already hold.

WHY
    The archive began at FY2013 and skipped FY2014 entirely, so the published
    filing series had a hole at calendar 2014 (1,348 filings against ~7,000
    either side) that looked like a collapse and was really an absent file.
    DOL in fact publishes back to FY2008.

RULES
    * Never overwrite. A file already on disk is left exactly as it is; this
      script only ever adds. Deduplication happens later on the case number,
      so a redundant file costs nothing and a deleted one may be
      unrecoverable -- see data/h1b/LCA_ARCHIVE.md.
    * Download to a .partial and rename only once the bytes are complete and
      the file actually opens as a workbook. A truncated xlsx that lands under
      the real name would be read as a short year.

USAGE
    python3 scripts/download_lca_archive.py --list
    python3 scripts/download_lca_archive.py            # fetch what is missing
    python3 scripts/download_lca_archive.py --only H-1B_FY14_Q4
"""
from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LCA_DIR = ROOT / "data" / "h1b" / "lca"
BASE = "https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs"

# Remote stem -> local filename. Local names keep the `lca_` prefix convention
# the existing archive uses, so the corpus sorts together.
ARCHIVE: dict[str, str] = {
    "H-1B_Case_Data_FY2008":     "lca_H-1B_Case_Data_FY2008.xlsx",
    "H-1B_Case_Data_FY2009":     "lca_H-1B_Case_Data_FY2009.xlsx",
    "H-1B_FY2010":               "lca_H-1B_FY2010.xlsx",
    "H-1B_iCert_LCA_FY2011_Q4":  "lca_H-1B_iCert_LCA_FY2011_Q4.xlsx",
    "LCA_FY2012_Q4":             "lca_LCA_FY2012_Q4.xlsx",
    "H-1B_FY14_Q4":              "lca_H-1B_FY14_Q4.xlsx",
}


def already_have(local: str) -> bool:
    """True if this file, or an obvious equivalent, is already on disk."""
    if (LCA_DIR / local).exists():
        return True
    # The existing corpus names FY2013 `lca_LCA_FY2013.xlsx`; tolerate any file
    # whose name carries the same fiscal-year token.
    token = local.lower().replace("lca_", "").replace(".xlsx", "")
    for p in LCA_DIR.glob("*.xlsx"):
        if p.stem.lower().endswith(token):
            return True
    return False


def fetch(stem: str, local: str, timeout: int = 600) -> bool:
    url = f"{BASE}/{stem}.xlsx"
    dest = LCA_DIR / local
    tmp = dest.with_suffix(".xlsx.partial")
    print(f"  {stem} -> {local}", flush=True)
    try:
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            expect = int(r.headers.get("content-length") or 0)
            got = 0
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
                    got += len(chunk)
                    if expect:
                        pct = 100 * got / expect
                        print(f"\r    {got/1048576:7.1f} / {expect/1048576:.1f} MB"
                              f"  {pct:5.1f}%", end="", flush=True)
            print()
        if expect and got != expect:
            raise OSError(f"short read: {got} of {expect} bytes")
        # An xlsx is a zip. If it will not open, it is not a workbook.
        with zipfile.ZipFile(tmp) as zf:
            if not any(n.startswith("xl/") for n in zf.namelist()):
                raise OSError("no xl/ members; not a workbook")
        os.replace(tmp, dest)
        print(f"    ok  {dest.stat().st_size/1048576:.1f} MB")
        return True
    except Exception as e:                                   # noqa: BLE001
        print(f"    FAILED: {e}")
        if tmp.exists():
            tmp.unlink()
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="show status, download nothing")
    ap.add_argument("--only", help="fetch just this remote stem")
    args = ap.parse_args()

    LCA_DIR.mkdir(parents=True, exist_ok=True)
    items = ({args.only: ARCHIVE[args.only]} if args.only else ARCHIVE)

    missing = {s: l for s, l in items.items() if not already_have(l)}
    print(f"  archive dir: {LCA_DIR}")
    print(f"  known historical files: {len(items)}   already held: "
          f"{len(items) - len(missing)}   to fetch: {len(missing)}\n")
    for stem, local in items.items():
        print(f"    {'have' if stem not in missing else 'MISSING':>7}  {stem}")
    if args.list or not missing:
        return 0

    print()
    failed = [s for s, l in missing.items() if not fetch(s, l)]
    print(f"\n  fetched {len(missing) - len(failed)} of {len(missing)}")
    if failed:
        print(f"  failed: {', '.join(failed)}")
        return 1
    print("  Nothing was overwritten. Re-run the LCA aggregation to pick these up:")
    print("    scripts/aws_lca_rebuild.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
