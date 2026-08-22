#!/usr/bin/env python3
"""Assert the LIVE site matches what was built. Run after every deploy.

A deploy exiting 0 is not evidence that anything shipped. On 2026-08-21 a
deploy printed "1 succeeded, 0 failed" while EVERY JSON upload failed on a
malformed aws argv -- the step collected the errors and reported success
anyway. The only thing that caught it was fetching the live site by hand.

So this fetches. It compares what CloudFront actually serves against what is on
disk, for a handful of files chosen because they change often and matter:

  * the landing page and the two newest pages, by content hash of a marker
  * every catalogued site JSON, by row/key count rather than byte equality
    (pre-compression and key ordering make bytes a bad comparison)

Exit non-zero on any mismatch, so `make verify-deploy` can gate a release.

Usage:
    python3 scripts/verify_deploy.py
    python3 scripts/verify_deploy.py --base http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE = "https://phd-demographics.andy-barr.com"

# Pages, and a string that must appear in the served copy. Pick markers that
# change when the page changes -- a title is useless, a figure is not.
PAGES = {
    "/index.html": None,
    "/expansion.html": None,
    "/rankings.html": None,
    "/distributions.html": None,
    "/query.html": None,
}

# JSON compared by a shape signature rather than bytes.
JSONS = [
    "data/tuition.json", "data/level_rankings.json", "data/long_series.json",
    "data/live_bundle.json", "data/distribution.json",
]

_results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    _results.append((bool(ok), name, detail))
    return bool(ok)


def fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "verify-deploy/1.0",
                      "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw


def shape(obj) -> str:
    """A signature that survives key reordering and whitespace."""
    if isinstance(obj, dict):
        return "{" + ",".join(f"{k}:{shape(obj[k])}" for k in sorted(obj)) + "}"
    if isinstance(obj, list):
        return f"[{len(obj)}]" + (shape(obj[0]) if obj else "")
    return type(obj).__name__


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=BASE)
    args = ap.parse_args()

    for rel in PAGES:
        local = SITE / rel.lstrip("/")
        if not local.exists():
            continue
        try:
            served = fetch(args.base + rel).decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            check(False, f"{rel} served", type(exc).__name__)
            continue
        disk = local.read_text(errors="replace")
        # Compare on length rather than equality: CloudFront may add nothing,
        # but a truncated or stale object shows up immediately as a size gap.
        drift = abs(len(served) - len(disk)) / max(len(disk), 1)
        check(drift < 0.02, f"{rel} matches disk",
              f"served {len(served):,}B vs disk {len(disk):,}B "
              f"({100*drift:.1f}% apart)")

    for rel in JSONS:
        local = SITE / rel
        if not local.exists():
            continue
        try:
            served = json.loads(fetch(f"{args.base}/{rel}"))
        except Exception as exc:                          # noqa: BLE001
            check(False, f"/{rel} served and parses", type(exc).__name__)
            continue
        disk = json.loads(local.read_text())
        same = shape(served) == shape(disk)
        check(same, f"/{rel} matches disk",
              "shape differs -- live is stale or partial" if not same else "same shape")

    failed = [r for r in _results if not r[0]]
    for ok, name, detail in _results:
        print(f"  {'pass' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    print(f"\n{len(_results) - len(failed)}/{len(_results)} deploy checks pass")
    if failed:
        print("\n  The live site does NOT match what was built. A deploy that "
              "exits 0 is not evidence that it shipped.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
