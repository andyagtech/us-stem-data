#!/usr/bin/env python3
"""Read again the pages that gave nothing the first time.

765 URLs came back "no roster parsed" and 219 failed to fetch. Most
are real lab pages: the extractor tested a name's SHAPE before
stripping what the roster had hung off it, so "Chandika Kiriella
(Spring 2024 - )" was not a name and a whole group vanished.

Nothing here crawls. These URLs are already found and sitting in the
file; this only reads them again with the current extractor.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_name_cache as cache                                # noqa: E402
import lab_store                                              # noqa: E402
from harvest_lab_rosters import (                             # noqa: E402
    best_names, clean_member, composition, fetch,
)

MIN = 8


def redo(g: dict) -> dict | None:
    url = g["url"]
    try:
        code, html = fetch(url)
    except Exception as exc:                                  # noqa: BLE001
        return {"url": url, "status": f"http_{getattr(exc, 'code', 0) or 0}"}
    if code != 200 or not html:
        return {"url": url, "status": f"http_{code}"}
    raw = best_names(html)
    cache.put(url, raw)
    names = []
    for n in raw:
        c = clean_member(n)
        if c and c not in names:
            names.append(c)
    if len(names) < MIN:
        return {"url": url, "status": "no_roster_parsed",
                "members_detected": len(names)}
    return {**g, "url": url, "status": "roster", "members": len(names),
            "members_detected": len(names), "composition": composition(names)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1200)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()

    doc = lab_store.load()
    todo = [g for g in doc["groups"]
            if g.get("status") in ("no_roster_parsed", "http_0", None)][: a.limit]
    print(f"Re-reading {len(todo)} pages that gave nothing before")

    out, won = [], 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, r in enumerate(ex.map(redo, todo), 1):
            if r:
                out.append(r)
                if r.get("status") == "roster":
                    won += 1
                    c = r["composition"]
                    print(f"  {c['dominance']:>5}% {c['dominant_group'][:9]:<10}"
                          f" {r['members']:>3}m  {r['url'][:56]}")
            if i % 200 == 0:
                print(f"  ... {i}/{len(todo)}, {won} rosters recovered")
            time.sleep(0.01)

    keep = [r for r in out if r.get("status") == "roster"]
    print(f"\n  {won} rosters recovered from {len(todo)} dead pages")
    print(" ", lab_store.merge(keep, source="retry"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
