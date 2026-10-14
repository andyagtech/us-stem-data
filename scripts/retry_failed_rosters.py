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
import crawl_resume                                           # noqa: E402
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
    #: A RE-READ IS WORTH REPEATING, A RESUME FILE IS NOT A VERDICT.
    #: This script exists because the extractor improves: a page that
    #: gave nothing last month gives a roster today. So the resume file
    #: is OFF by default here -- unlike the crawlers, where a repeat
    #: costs forty fetches at someone else's expense. --resume uses it
    #: when the point is to get through a long backlog once.
    ap.add_argument("--resume", action="store_true",
                    help="skip pages re-read since the last --restart, so a "
                         "long backlog can be worked through in sittings")
    ap.add_argument("--restart", action="store_true",
                    help="clear the resume file")
    a = ap.parse_args()

    resume = crawl_resume.Resume("retry_rosters", why=(
        "Pages retry_failed_rosters.py has re-read. Re-reading is worth "
        "repeating whenever the extractor changes, so this is only "
        "consulted with --resume."))
    if a.restart:
        resume.reset()

    doc = lab_store.load()
    pool = [g for g in doc["groups"]
            if g.get("status") in ("no_roster_parsed", "http_0", None)]
    todo = [g for g in pool
            if not (a.resume and g["url"] in resume.done)][: a.limit]
    print(f"Re-reading {len(todo)} pages that gave nothing before "
          f"(pool of {len(pool)})")

    #: STORE IN BATCHES, MARK AFTER STORING. A run of 1,200 pages used
    #: to merge once at the very end.
    BATCH = 100
    pending_rows: list = []
    pending_tried: list = []
    won = 0

    def flush() -> None:
        nonlocal pending_rows, pending_tried
        keep = [r for r in pending_rows if r.get("status") == "roster"]
        if keep:
            summary = lab_store.merge(keep, source="retry")
            print(f"   stored: +{summary['added']} new, "
                  f"{summary['improved']} improved, "
                  f"{summary['rosters']} rosters in all", flush=True)
        resume.mark_many(pending_tried)
        pending_rows, pending_tried = [], []

    try:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for i, (row, r) in enumerate(zip(todo, ex.map(redo, todo)), 1):
                pending_tried.append(row["url"])
                if r:
                    pending_rows.append(r)
                    if r.get("status") == "roster":
                        won += 1
                        c = r["composition"]
                        print(f"  {c['dominance']:>5}% "
                              f"{c['dominant_group'][:9]:<10}"
                              f" {r['members']:>3}m  {r['url'][:56]}",
                              flush=True)
                if len(pending_tried) >= BATCH:
                    flush()
                    print(f"  ... {i}/{len(todo)}, {won} rosters recovered",
                          flush=True)
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n  interrupted; storing what is in hand", flush=True)
    finally:
        flush()
        print(f"\n  {won} rosters recovered from {len(todo)} dead pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
