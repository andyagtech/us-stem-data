#!/usr/bin/env python3
"""Re-read every stored roster under the dominance metric.

Compositions are totals; the names behind them are deliberately not
kept, so changing how a roster is scored means fetching it again.
Append-only: a page that no longer answers keeps the figures it had.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_name_cache as cache                                  # noqa: E402
import lab_store                                                # noqa: E402
from harvest_lab_rosters import (                               # noqa: E402
    best_names, clean_member, composition, fetch,
)

ROOT = Path(__file__).resolve().parents[1]
LABS = ROOT / "data" / "labs" / "discovered_labs.json"


def redo(g: dict, refresh: bool = False) -> dict:
    #: the cached read, unless asked for a fresh one
    names = None if refresh else cache.get(g["url"])
    if names is None:
        try:
            code, html = fetch(g["url"])
        except Exception as exc:                              # noqa: BLE001
            code, html = getattr(exc, "code", 0) or 0, ""
        if code != 200 or not html:
            return g
        names = best_names(html)
        cache.put(g["url"], names)
    #: RE-CLEAN WHAT THE CACHE HOLDS. The cache stores what the
    #: extractor accepted at the time, so a change to clean_member had
    #: no effect on any page already read -- and the point of this
    #: script is to re-score under a changed rule. Without this, adding
    #: "a paper title is not a person" would have left every stored
    #: roster carrying its paper titles.
    cleaned = []
    for n in names:
        c = clean_member(n)
        if c and c not in cleaned:
            cleaned.append(c)
    if cleaned != names:
        #: THE CACHE HOLDS WHAT THE EXTRACTOR ACCEPTED, so it is
        #: rewritten too. Without this the next pass re-scores the
        #: old list and the correction never sticks: the member
        #: count moved but 'IEEE CNS' was still sitting in the
        #: cache as a name.
        cache.put(g["url"], cleaned)
    names = cleaned
    if len(names) < 8:
        return g
    comp = composition(names)
    return {**g, "members": len(names), "members_detected": len(names),
            "composition": comp}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--refresh", action="store_true",
                    help="re-fetch every page instead of using the "
                         "local name cache")
    a = ap.parse_args()
    doc = json.loads(LABS.read_text())
    todo = [g for g in doc["groups"] if g.get("status") == "roster"]
    print(f"Re-scoring {len(todo)} rosters "
          f"({cache.count()} cached, "
          f"{'refreshing' if a.refresh else 'cache first'})")
    done = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for g in ex.map(lambda x: redo(x, a.refresh), todo):
            done.append(g)
            c = g.get("composition") or {}
            if c.get("dominance"):
                print(f"  {c['dominance']:>5}%  {c.get('dominant_group',''):<11}"
                      f" {g.get('members', 0):>3}m  {g['url'][:54]}")
            time.sleep(0.01)
    #: THROUGH THE LOCK. This used to write LABS directly from a
    #: document read at the start of the run, so anything another pass
    #: merged in the meantime was silently discarded -- 1,400 rows of
    #: page labels went that way. A re-score is a correction and not an
    #: append, so it names the fields it is allowed to overwrite.
    scored = [g for g in done if (g.get("composition") or {}).get("dominance")]
    s = lab_store.merge(
        scored, source="recompute",
        correct=("members", "members_detected", "composition"))
    print(f"  re-scored {len(scored)} rosters; "
          f"{s['rosters']} rosters of {s['total']} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
