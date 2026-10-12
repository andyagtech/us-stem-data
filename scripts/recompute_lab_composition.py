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
from harvest_lab_rosters import best_names, composition, fetch  # noqa: E402

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
    by = {g["url"]: g for g in done}
    doc["groups"] = [by.get(g["url"], g) for g in doc["groups"]]
    LABS.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"  wrote {LABS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
