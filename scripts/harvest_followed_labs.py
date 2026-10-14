#!/usr/bin/env python3
"""Read the member lists on group sites found by follow_lab_links.

Uses the same extractor as every other roster on the site, and writes
rows in the shape discovered_labs.json already holds, so the ranker
tests these beside the ones the department crawl found.

Append-only: a URL already carrying a composition keeps it.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crawl_resume  # noqa: E402
import lab_store  # noqa: E402
from harvest_lab_rosters import (                            # noqa: E402
    best_names, composition, fetch,
)

ROOT = Path(__file__).resolve().parents[1]
FOLLOWED = ROOT / "data" / "labs" / "followed_labs.json"
LABS = ROOT / "data" / "labs" / "discovered_labs.json"

#: A page with fewer than this is a contact card, not a roster.
MIN_MEMBERS = 8


def title_of(html: str) -> str:
    import re
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() \
        if m else ""


def harvest(lab: dict) -> dict:
    url = lab["url"]
    #: fetch() raises on a 4xx rather than returning the code, and a
    #: dead group site is an ordinary outcome here, not a crash
    try:
        code, html = fetch(url)
    except Exception as exc:                                  # noqa: BLE001
        code = getattr(exc, "code", 0) or 0
        html = ""
    if code != 200 or not html:
        return {**lab, "status": f"http_{code}"}
    names = best_names(html)
    if len(names) < MIN_MEMBERS:
        return {**lab, "status": "no_roster_parsed",
                "members_detected": len(names)}
    comp = composition(names)
    return {
        **lab,
        "title": title_of(html),
        "status": "roster",
        "members": len(names),
        "members_detected": len(names),
        "composition": comp,
        "harvested": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0,
                    help="0 for every site not yet read")
    ap.add_argument("--restart", action="store_true",
                    help="ignore the resume file and read every site again")
    a = ap.parse_args()

    #: Re-reading a page is worth repeating when the extractor changes,
    #: as in retry_failed_rosters -- but this stage reads thousands of
    #: sites found by follow_lab_links, so it resumes by default and
    #: --restart is the way to redo them all.
    resume = crawl_resume.Resume("harvest_followed", why=(
        "Group sites harvest_followed_labs.py has read, whether or not a "
        "roster came off them."))
    if a.restart:
        resume.reset()

    labs = json.loads(FOLLOWED.read_text())["labs"]
    todo = [l for l in labs if l["url"] not in resume.done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"Reading {len(todo)} group sites "
          f"({len(labs) - len(todo)} already read or past the limit)")

    #: STORE IN BATCHES, MARK AFTER STORING. The whole run used to be
    #: held in memory and merged once at the end.
    BATCH = 40
    pending_rows: list = []
    pending_tried: list = []
    rosters = 0

    def flush() -> None:
        nonlocal pending_rows, pending_tried
        if pending_rows:
            summary = lab_store.merge(pending_rows, source="followed")
            print(f"   stored: +{summary['added']} new, "
                  f"{summary['improved']} improved, "
                  f"{summary['rosters']} rosters in all", flush=True)
        resume.mark_many(pending_tried)
        pending_rows, pending_tried = [], []

    try:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for i, (lab, r) in enumerate(zip(todo, ex.map(harvest, todo)), 1):
                pending_tried.append(lab["url"])
                if r:
                    pending_rows.append(r)
                    if r.get("status") == "roster":
                        rosters += 1
                        c = r["composition"]
                        print(f"  {r['members']:>3} members  "
                              f"{c.get('share_chinese_markers', 0):>5}%  "
                              f"{r['url'][:62]}", flush=True)
                if len(pending_tried) >= BATCH:
                    flush()
                    print(f"  ... {i}/{len(todo)}, {rosters} rosters",
                          flush=True)
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n  interrupted; storing what is in hand", flush=True)
    finally:
        flush()
        print(f"\n  {rosters} rosters of {len(todo)} sites read this run; "
              f"{len(resume.done)} sites read in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
