#!/usr/bin/env python3
"""Vendor the GeoNames US postal file, so geocoding never needs a network call.

WHY THIS FILE AND NOT A GEOCODING SERVICE
    Mapping the immigration firms needs coordinates for a few hundred
    addresses. Every hosted option was rejected:

      * Google / Mapbox / HERE geocoding  -- metered, and this would be a
        recurring cost for a static answer that never changes.
      * Nominatim, self-hosted            -- full OSM rooftop accuracy, but a
        PostGIS stack and ~100 GB. Wildly disproportionate.
      * pgeocode                          -- wraps this same GeoNames data,
        but downloads it at first use, so a build silently depends on the
        network. Vendoring the file removes that.
      * libpostal                         -- parses and normalises addresses;
        it does not return coordinates at all.

    The addresses on file resolve to a postcode (179 of 262 attorneys) or to a
    city and state (75 more). Both are answerable from ONE 0.6 MB table, and
    postcode-centroid precision is the right resolution for "where are these
    firms" -- rooftop accuracy would be false precision on an address that is
    often just an office suite.

LICENCE
    GeoNames postal data is Creative Commons Attribution 4.0. Attribution is
    written into the header of the vendored file and belongs on any published
    map.

USAGE
    python3 scripts/download_geonames.py          # fetch if missing
    python3 scripts/download_geonames.py --force  # refetch
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
DEST = ROOT / "data" / "geo" / "US_postal.txt"
URL = "https://download.geonames.org/export/zip/US.zip"

HEADER = (
    "# GeoNames US postal codes. Source: https://download.geonames.org/export/zip/US.zip\n"
    "# Licence: Creative Commons Attribution 4.0. Attribute GeoNames on any published map.\n"
    "# Tab-separated, no quoting. Columns:\n"
    "#   0 country  1 postal_code  2 place_name  3 admin1_name  4 admin1_code\n"
    "#   5 admin2_name  6 admin2_code  7 admin3_name  8 admin3_code\n"
    "#   9 latitude  10 longitude  11 accuracy\n"
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if DEST.exists() and not args.force:
        n = sum(1 for _ in DEST.open()) - HEADER.count("\n")
        print(f"  already vendored: {DEST} ({n:,} rows). --force to refetch.")
        return 0

    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"  fetching {URL}")
    r = requests.get(URL, timeout=180)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        raw = zf.read("US.txt").decode("utf-8")
    rows = [l for l in raw.splitlines() if l.strip()]
    if len(rows) < 30_000:
        print(f"  ABORT: only {len(rows)} rows, expected ~41,000")
        return 1

    tmp = DEST.with_suffix(".txt.partial")
    tmp.write_text(HEADER + "\n".join(rows) + "\n")
    os.replace(tmp, DEST)
    print(f"  wrote {DEST}  ({len(rows):,} rows, "
          f"{DEST.stat().st_size/1048576:.2f} MB)")
    print("  No network call is needed again. Geocoding is offline from here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
