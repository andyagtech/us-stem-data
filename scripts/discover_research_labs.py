#!/usr/bin/env python3
"""Find research-group member pages from the departments already resolved.

THE SEARCH IS THE PROBLEM, NOT THE TEST. Two labs given by name can be
tested on their own. A LIST assembled by scanning cannot: test a
hundred groups against their department's rate and about five clear
p < 0.05 by chance, so a page of "unusual" groups found that way is
partly a page of noise. This script therefore records HOW MANY groups
it examined, which is the number the correction needs, and
rank_research_labs.py applies Benjamini-Hochberg to the whole set
rather than letting each group be judged alone.

HOW IT LOOKS. A department's people page links to faculty; a faculty
page links to a group; a group page has a members list. Rather than
walk all three hops for 398 departments, this looks for the shape
directly -- a link whose text or address says lab, group, or members --
and keeps the ones that turn out to carry a roster.

Usage:
  python3 scripts/discover_research_labs.py --limit 120
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402
import harvest_lab_rosters as hl                               # noqa: E402

URLS = ROOT / "data" / "labs" / "program_urls.json"
OUT = ROOT / "data" / "labs" / "discovered_labs.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}

#: A link that leads to a research group.
LAB_LINK = re.compile(
    r"\b(lab|laboratory|group|research group|team|our team|members|"
    r"people|the group|research team)\b", re.I)
#: and its address usually says so too
LAB_URL = re.compile(
    r"(lab|group|team|research|people|members|~)", re.I)
#: pages that are definitely not a group roster
NOT_LAB = re.compile(
    r"(/news|/event|/calendar|/apply|/admission|/course|/syllab|"
    r"/seminar|/giving|/alumni|/contact|/about$|/jobs|\.pdf$)", re.I)
#: "Lab" also means a room with equipment in it. These titles are
#: facility booking and safety pages, and the first wide crawl
#: returned several: "Lab Equipment Items (Fee For Service)".
NOT_A_RESEARCH_GROUP = re.compile(
    r"(equipment|checkout|fee for service|safety|booking|reserve|"
    r"inventory|machine shop|cleanroom access|instrument|core facility|"
    r"policy|handbook|training and access|rates?\b)", re.I)
#: a members page says so
MEMBERS = re.compile(
    r"\b(members|our team|the team|group members|lab members|people|"
    r"students|researchers|current members)\b", re.I)


def get(url: str, timeout: int = 15):
    try:
        r = requests.get(url, headers=UA, timeout=timeout,
                         allow_redirects=True)
        return r.status_code, r.text, r.url
    except requests.RequestException:
        return 0, "", url


def links(html: str, base: str):
    for m in re.finditer(
            r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html, re.S | re.I):
        href = urljoin(base, m.group(1))
        text = " ".join(re.sub(r"<[^>]+>", " ", m.group(2)).split())
        if text and len(text) < 90:
            yield text, href


def roster_of(url: str) -> dict | None:
    """If this page lists a group's members, the counts."""
    code, html, final = get(url, 18)
    if code != 200 or len(html) < 1200 or NOT_LAB.search(final):
        return None
    #: A RESEARCH GROUP, NOT A DEPARTMENT ROSTER. The first pass
    #: returned "Current Graduate Students | Aeronautics" nine times:
    #: a departmental list, which the other pipeline already covers.
    #: A group names itself a lab or a group, on the page or in the
    #: address.
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if title_m and NOT_A_RESEARCH_GROUP.search(title_m.group(1)):
        return None
    head = (html[:4000] + " " + final).lower()
    if not re.search(r"\b(lab|laborator|research group|our group|"
                     r"the group|research team)\b", head):
        return None
    names = hl.best_names(html)
    #: A GROUP, not a department. Four is a group; ninety is a
    #: directory and belongs to the department pipeline, not this one.
    if not 4 <= len(names) <= 60:
        return None
    comp = hl.composition(names)
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return {
        "url": final,
        "title": " ".join(title.group(1).split())[:110] if title else "",
        "members": comp.get("members_detected") or 0,
        "composition": comp,
    }


def from_department(row: dict) -> list[dict]:
    """Group rosters reachable from one department page."""
    base = row.get("faculty_url") or row.get("url")
    if not base:
        return []
    code, html, final = get(base, 18)
    if code != 200:
        return []
    host = urlparse(final).netloc

    #: THREE HOPS, BECAUSE THAT IS WHERE LABS LIVE. A department page
    #: lists faculty; a faculty profile links to that person's group;
    #: the group has a members page. Stopping at hop one found a single
    #: lab under sixteen departments, because departments rarely link
    #: to groups directly.
    profiles = []
    for text, href in links(html, final):
        if re.search(r"(/people/|/faculty/|/profile|/directory/|/~)", href) \
                and not NOT_LAB.search(href):
            profiles.append(href)
    seen: set = set()
    for prof in profiles[:14]:
        c2, h2, f2 = get(prof, 12)
        if c2 != 200:
            continue
        for text, href in links(h2, f2):
            if LAB_LINK.search(text) or re.search(r"(lab|group)", href, re.I):
                if not NOT_LAB.search(href):
                    seen.add(href)
        time.sleep(0.25)

    out = []
    for text, href in links(html, final):
        if not (LAB_LINK.search(text) or LAB_URL.search(href)):
            continue
        if NOT_LAB.search(href) or href in seen:
            continue
        #: stay on the university; a lab on sites.google.com is common
        #: and allowed, anything else is someone else's site
        h = urlparse(href).netloc
        if not (h == host or h.endswith(".edu") or "sites.google" in h
                or "github.io" in h):
            continue
        seen.add(href)
        if len(seen) > 40:
            break

    #: KEEP EVERY CANDIDATE, not only the ones that parse. A lab page
    #: whose roster this crawler cannot read is still a lab page, and
    #: the address is the expensive part to find -- re-deriving it
    #: later means crawling three hops again. Rows carry a status so a
    #: later pass can pick up where this one stopped.
    for href in list(seen):
        code, html, final = get(href, 15)
        if code != 200:
            out.append({"url": href, "status": f"http_{code}",
                        "institution": row["institution"],
                        "department_field": row["sector"],
                        "found_from": base})
            continue
        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        target = final
        for text, link in links(html, final):
            if MEMBERS.search(text) and not NOT_LAB.search(link):
                target = link
                break
        r = roster_of(target)
        if r:
            r.update({"status": "roster", "institution": row["institution"],
                      "department_field": row["sector"], "found_from": base})
            out.append(r)
        else:
            out.append({
                "url": final,
                "members_page_tried": target if target != final else "",
                "title": " ".join(title.group(1).split())[:110]
                         if title else "",
                "status": "no_roster_parsed",
                "institution": row["institution"],
                "department_field": row["sector"], "found_from": base})
        time.sleep(0.4)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=80)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--fields", help="comma-separated field keys to crawl")
    ap.add_argument("--exclude", help="field keys to skip")
    a = ap.parse_args()

    rows = [r for r in json.loads(URLS.read_text())["rows"]
            if r.get("status") == "ok" and (r.get("faculty_url") or r.get("url"))]
    #: spread across institutions and fields rather than taking the
    #: first N, which would be one field in alphabetical order
    if a.fields:
        want = {x.strip() for x in a.fields.split(",")}
        rows = [r for r in rows if r["sector"] in want]
    if a.exclude:
        skip = {x.strip() for x in a.exclude.split(",")}
        rows = [r for r in rows if r["sector"] not in skip]

    by: dict = {}
    for r in rows:
        by.setdefault((r["institution"], r["sector"]), r)
    #: ROUND-ROBIN ACROSS FIELDS. Taking the first N of a dict gave 77
    #: computing groups, 8 aerospace and 4 materials, because the
    #: computing departments come first and there are more of them.
    #: The author asked for all of STEM, so each field contributes in
    #: turn until the limit is reached.
    pools: dict = {}
    for r in by.values():
        pools.setdefault(r["sector"], []).append(r)
    picks, order = [], [k for k in pools if pools[k]]
    while order and len(picks) < a.limit:
        for k in list(order):
            if not pools[k]:
                order.remove(k)
                continue
            picks.append(pools[k].pop(0))
            if len(picks) >= a.limit:
                break
    print(f"Looking for research groups under {len(picks)} departments")

    found: list = []
    seen_urls: set = set()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for got in ex.map(from_department, picks):
            for g in got:
                #: one page, one row -- several departments link to the
                #: same group and the first pass listed it once each
                if g["url"] in seen_urls:
                    continue
                seen_urls.add(g["url"])
                found.append(g)
                if g.get("status") == "roster":
                    print(f"  {g['members']:>3} members  "
                          f"{g['composition'].get('share_chinese_markers', 0):>5}%  "
                          f"{g['institution'][:24]:26} {g.get('title','')[:40]}")

    #: merge with whatever a previous run found rather than replacing
    prior = []
    if OUT.exists():
        prior = json.loads(OUT.read_text()).get("groups", [])
    have = {g.get("url") for g in found}
    found = found + [g for g in prior if g.get("url") not in have]

    write_text(OUT, json.dumps({
        "why": ("Research groups found by crawling departments already "
                "resolved. The COUNT EXAMINED is the number that matters "
                "for the correction: a list assembled by scanning needs "
                "Benjamini-Hochberg over the whole set, not a p-value per "
                "group."),
        "departments_examined": len(picks),
        "groups_found": sum(1 for g in found if g.get("status") == "roster"),
        "candidate_urls": len(found),
        "note_on_candidates": (
            "Rows with status 'roster' carry counts. The rest are lab "
            "pages whose member list this crawler could not read, kept "
            "because the ADDRESS is the expensive part: finding it took "
            "three hops from a department page."),
        "groups": found}, indent=2))
    rosters = sum(1 for g in found if g.get("status") == "roster")
    print(f"\n  {len(found)} lab URLs kept, {rosters} with a readable roster")
    print(f"  from {len(picks)} departments")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
