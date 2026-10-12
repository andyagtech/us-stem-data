#!/usr/bin/env python3
"""Run every hand-written site parser and store what it reads.

The generic extractor handles an ordinary lab page. A university that
publishes a DIRECTORY SYSTEM is worth a parser of its own, because
one parser reaches every programme behind it rather than one page.
"""
from __future__ import annotations

import argparse
import importlib
import pkgutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_name_cache as cache                                # noqa: E402
import lab_store                                              # noqa: E402
import site_parsers                                           # noqa: E402
from follow_lab_links import get                              # noqa: E402
from harvest_lab_rosters import clean_member, composition     # noqa: E402

MIN = 12


def load_parsers() -> list:
    mods = []
    for m in pkgutil.iter_modules(site_parsers.__path__):
        mods.append(importlib.import_module(f"site_parsers.{m.name}"))
    return mods


def harvest(job: tuple) -> dict | None:
    mod, t = job
    html = get(t["url"])
    if not html:
        return None
    raw = mod.parse(t["url"], html)
    if not raw:
        return None
    cache.put(t["url"], raw)
    names = []
    for n in raw:
        c = clean_member(n)
        if c and c not in names:
            names.append(c)
    if len(names) < MIN:
        return None
    return {**t, "status": "roster", "members": len(names),
            "members_detected": len(names),
            "composition": composition(names),
            "found_from": f"parser:{mod.__name__.split('.')[-1]}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    jobs = []
    for mod in load_parsers():
        t = mod.targets()
        print(f"  {mod.__name__.split('.')[-1]}: {len(t)} targets")
        jobs += [(mod, x) for x in t]
    if a.limit:
        jobs = jobs[: a.limit]

    found = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, r in enumerate(ex.map(harvest, jobs), 1):
            if r:
                found.append(r)
                c = r["composition"]
                print(f"  {c['dominance']:>5}% {c['dominant_group'][:9]:<10} "
                      f"{r['members']:>3}m  {r['title'][:46]}")
            if i % 50 == 0:
                print(f"  ... {i}/{len(jobs)}, {len(found)} rosters")
            time.sleep(0.01)

    print(f"\n  {len(found)} rosters of {len(jobs)} targets")
    if found:
        print(" ", lab_store.merge(found, source="site-parsers"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
