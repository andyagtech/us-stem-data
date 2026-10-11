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
    a = ap.parse_args()

    labs = json.loads(FOLLOWED.read_text())["labs"]
    print(f"Reading {len(labs)} group sites")

    out = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(harvest, labs):
            out.append(r)
            if r.get("status") == "roster":
                c = r["composition"]
                print(f"  {r['members']:>3} members  "
                      f"{c.get('share_chinese_markers', 0):>5}%  "
                      f"{r['url'][:62]}")
            time.sleep(0.01)

    rosters = [r for r in out if r.get("status") == "roster"]
    print(f"\n  {len(rosters)} rosters of {len(labs)} sites")

    #: merge into the file the ranker reads, never replacing a row
    doc = json.loads(LABS.read_text())
    by = {g["url"]: g for g in doc["groups"]}
    added = 0
    for r in out:
        cur = by.get(r["url"])
        if cur is None:
            by[r["url"]] = r
            added += 1
        elif r.get("composition") and not cur.get("composition"):
            cur.update(r)
    doc["groups"] = sorted(by.values(), key=lambda g: g["url"])
    doc["candidate_urls"] = len(doc["groups"])
    doc["groups_found"] = sum(1 for g in doc["groups"]
                              if g.get("status") == "roster")
    LABS.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"  {added} new rows; {doc['groups_found']} rosters in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
