#!/usr/bin/env python3
"""Find the members page under a lab site we already reached.

683 candidates came back "no_roster_parsed" without being profiles.
Most are a laboratory's FRONT PAGE -- daklab.org, a professor's ~user
directory, a Research/<Name>_Group index -- and the roster is one
subpage away at /people or /members. The crawler never took that step
on these, so they sat unread.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crawl_resume  # noqa: E402
import lab_store  # noqa: E402
from follow_lab_links import MEMBERS, get, links, strip_chrome  # noqa: E402
from harvest_lab_rosters import best_names, composition          # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LABS = ROOT / "data" / "labs" / "discovered_labs.json"
OUT = ROOT / "data" / "labs" / "lab_member_pages.json"

LABISH = re.compile(r"(lab|group|research|~)", re.I)
PROFILE = re.compile(
    r"/(people|faculty|profile|directory|person|staff|bio)/[^/]+/?(\?|$)",
    re.I)
MIN_MEMBERS = 12


def walk(row: dict) -> dict | None:
    site = row["url"]
    html = get(site)
    if not html:
        return None

    #: try the front page itself first, then each members-ish subpage
    tries = [site]
    for href, text in links(strip_chrome(html), site):
        if href.split("/")[2:3] != site.split("/")[2:3]:
            continue
        if MEMBERS.search(text) or MEMBERS.search(href):
            if href not in tries:
                tries.append(href)
    for url in tries[:4]:
        page = html if url == site else get(url)
        if not page:
            continue
        names = best_names(page)
        if len(names) < MIN_MEMBERS:
            continue
        comp = composition(names)
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
        return {
            "url": url, "from_site": site,
            "institution": row.get("institution"),
            "department_field": row.get("department_field"),
            "title": re.sub(r"\s+", " ",
                            re.sub(r"<[^>]+>", "", m.group(1))).strip()
            if m else "",
            "status": "roster",
            "members": len(names), "members_detected": len(names),
            "composition": comp,
        }
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=600)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--restart", action="store_true",
                    help="ignore the resume file and try every site again")
    a = ap.parse_args()

    #: KEYED ON WHAT WAS TRIED, NOT ON WHAT WAS FOUND. There was no
    #: record at all, so `todo` was the first --limit of the pool on
    #: every run and the rest were never reached. A site that has no
    #: /people subpage is a result, and recording it is what lets the
    #: next run get past it.
    resume = crawl_resume.Resume("member_pages", why=(
        "Lab front pages find_lab_member_pages.py has already looked "
        "under for a roster, whether or not it found one."))
    if a.restart:
        resume.reset()

    groups = json.loads(LABS.read_text())["groups"]
    pool = [g for g in groups
            if g.get("status") == "no_roster_parsed"
            and not PROFILE.search(g.get("url", ""))
            and LABISH.search(g.get("url", ""))]
    todo = [g for g in pool if g["url"] not in resume.done][: a.limit]
    print(f"Looking for a members page under {len(todo)} lab sites "
          f"({len(pool) - len(todo)} already tried or past the limit)")

    #: STORE IN BATCHES, MARK AFTER STORING. The whole run used to be
    #: held in memory and written once, and lab_member_pages.json was
    #: REPLACED rather than merged -- so a second run of 10 rosters
    #: erased the first run's 28.
    BATCH = 50
    pending_rows: list = []
    pending_tried: list = []
    total = 0

    def flush() -> None:
        nonlocal pending_rows, pending_tried, total
        if pending_rows:
            prev = []
            if OUT.exists():
                try:
                    prev = json.loads(OUT.read_text()).get("labs", [])
                except ValueError:
                    prev = []
            by = {r["url"]: r for r in prev}
            for r in pending_rows:
                by.setdefault(r["url"], r)
            OUT.write_text(json.dumps(
                {"why": ("Rosters found one subpage under a lab site "
                         "already crawled."),
                 "count": len(by),
                 "labs": sorted(by.values(), key=lambda r: r["url"])},
                indent=2) + "\n")
            summary = lab_store.merge(pending_rows, source="member-pages")
            total = len(by)
            print(f"   stored: +{summary['added']} new, "
                  f"{summary['rosters']} rosters in all", flush=True)
        resume.mark_many(pending_tried)
        pending_rows, pending_tried = [], []

    found = 0
    try:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for i, (row, r) in enumerate(zip(todo, ex.map(walk, todo)), 1):
                pending_tried.append(row["url"])
                if r:
                    pending_rows.append(r)
                    found += 1
                    c = r["composition"]
                    print(f"  {c.get('dominance', 0):>5}% "
                          f"{c.get('dominant_group', ''):<11} "
                          f"{r['members']:>3}m  {r['url'][:56]}", flush=True)
                if len(pending_tried) >= BATCH:
                    flush()
                    print(f"  ... {i}/{len(todo)}, {found} rosters",
                          flush=True)
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n  interrupted; storing what is in hand", flush=True)
    finally:
        flush()
        print(f"\n  {found} rosters this run; {total} in "
              f"{OUT.name}; {len(resume.done)} sites tried in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
