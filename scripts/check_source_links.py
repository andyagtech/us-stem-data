#!/usr/bin/env python3
"""Verify every source URL in the catalogue still resolves.

A methodology page whose links rot is worse than no methodology page: it
looks authoritative and sends a reader nowhere. This walks every source_url
and reports what it finds.

BLOCKED IS NOT BROKEN. Several federal sites refuse automated requests --
travel.state.gov returns 403 to a real browser from this network, and dol.gov
returns 403 to curl but 200 to a browser. A checker that treated those as
dead links would send someone chasing a URL that works fine for a person.
They are reported separately.

Usage:
  python3 scripts/check_source_links.py
  python3 scripts/check_source_links.py --strict   # fail on any dead link
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.datasets import CATALOG  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
# Hosts known to refuse automated requests while serving people normally.
BLOCKS_ROBOTS = ("travel.state.gov", "dol.gov", "h1bgrader.com")


def probe(url: str) -> tuple[str, int | str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return "ok", r.status
    except urllib.error.HTTPError as e:
        host = url.split("/")[2]
        if e.code in (401, 403) and any(h in host for h in BLOCKS_ROBOTS):
            return "blocked", e.code
        return "dead", e.code
    except Exception as e:
        return "dead", type(e).__name__


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    seen, results = {}, []
    for d in sorted(CATALOG, key=lambda x: x.key):
        if not d.source_url:
            continue
        if d.source_url not in seen:
            seen[d.source_url] = probe(d.source_url)
        state, code = seen[d.source_url]
        results.append((state, code, d.key, d.source_url))

    dead = [r for r in results if r[0] == "dead"]
    blocked = {r[3] for r in results if r[0] == "blocked"}
    print(f"  {len(seen)} distinct URLs across {len(results)} datasets")
    print(f"  reachable {sum(1 for v in seen.values() if v[0]=='ok')}, "
          f"blocking automated checks {len(blocked)}, dead {len(dead)}")
    for u in sorted(blocked):
        print(f"    blocked (serves people, refuses bots): {u}")
    for state, code, key, url in dead:
        print(f"    DEAD {code}  {key}: {url}")
    if dead and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
