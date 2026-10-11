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
    a = ap.parse_args()

    groups = json.loads(LABS.read_text())["groups"]
    todo = [g for g in groups
            if g.get("status") == "no_roster_parsed"
            and not PROFILE.search(g.get("url", ""))
            and LABISH.search(g.get("url", ""))][: a.limit]
    print(f"Looking for a members page under {len(todo)} lab sites")

    found = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, r in enumerate(ex.map(walk, todo), 1):
            if r:
                found.append(r)
                c = r["composition"]
                print(f"  {c.get('dominance', 0):>5}% "
                      f"{c.get('dominant_group', ''):<11} "
                      f"{r['members']:>3}m  {r['url'][:56]}")
            if i % 100 == 0:
                print(f"  ... {i}/{len(todo)}, {len(found)} rosters")
            time.sleep(0.01)

    OUT.write_text(json.dumps(
        {"why": "Rosters found one subpage under a lab site already crawled.",
         "count": len(found), "labs": found}, indent=2) + "\n")

    #: merge, never replacing a row that already has a composition
    doc = json.loads(LABS.read_text())
    by = {g["url"]: g for g in doc["groups"]}
    added = 0
    for r in found:
        if r["url"] not in by:
            by[r["url"]] = r
            added += 1
        elif not (by[r["url"]].get("composition") or {}).get("dominance"):
            by[r["url"]].update(r)
    doc["groups"] = sorted(by.values(), key=lambda g: g["url"])
    doc["candidate_urls"] = len(doc["groups"])
    doc["groups_found"] = sum(1 for g in doc["groups"]
                              if g.get("status") == "roster")
    LABS.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"\n  {len(found)} rosters, {added} new; "
          f"{doc['groups_found']} rosters in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
