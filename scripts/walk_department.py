#!/usr/bin/env python3
"""Walk a department's faculty list to every lab roster under it.

THE AUTHOR'S OWN PROCESS, automated. He described it exactly:

  open the department's people page
    -> click a professor
      -> follow "Research Website"
        -> click "Team Members"

  engineering.oregonstate.edu/EECS/About/People
    -> /about/people/tejasvi-anand
      -> web.engr.oregonstate.edu/~anandt/
        -> ~anandt/team.html

He expected this to need a scraper per lab, because every lab page
looks different. It does not: the LINKS are predictable even when the
pages are not. What differs is the roster markup, and one extractor
with the annotations stripped handles most of it.

Takes department URLs, one per line. Everything it finds goes through
the locked store, so this can run beside other crawlers.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_name_cache as cache                                # noqa: E402
import lab_store                                              # noqa: E402
from follow_lab_links import (                                # noqa: E402
    PROFILE, get, group_site_for, links, members_page, strip_chrome,
)
from harvest_lab_rosters import (                             # noqa: E402
    best_names, clean_member, composition,
)

MIN = 8
#: A PROFILE PATH ENDS IN A PERSON'S NAME. Matching any slug under
#: /directory/ pulled in "/about/directory/administration" and
#: "/directory/school-leadership-staff", and Illinois' engineering
#: directory offered 729 of those alongside its real faculty.
PROFILE_PATH = re.compile(
    r"/(about/)?(people|faculty|profile|directory|person|staff|bio)/"
    r"([a-z]{2,}-[a-z]{2,}(-[a-z]{2,})?|[a-z]{3,12})/?$", re.I)

#: slugs that are a section, not a person
NOT_A_PERSON_SLUG = re.compile(
    r"^(administration|staff|faculty|people|directory|leadership|"
    r"school-leadership-staff|emeritus|adjunct|affiliate|"
    r"postdocs?|students?|graduate-students|alumni|all|index|"
    r"research-faculty|teaching-faculty|by-name|by-area|a-z|"
    r"advisory-board|committees?|contact|overview|list)$", re.I)


def _host(url: str) -> str:
    """The host, or "" for a URL urlparse refuses.

    A page with an unbalanced bracket in an href made urlparse raise
    ValueError("Invalid IPv6 URL"), which ended a walk of 505
    departments at 260. One bad anchor should cost one link.
    """
    try:
        return urlparse(url).netloc
    except ValueError:
        return ""


def _path(url: str) -> str:
    try:
        return urlparse(url).path
    except ValueError:
        return ""


def faculty_of(dept_url: str) -> list[str]:
    html = get(dept_url)
    if not html:
        return []
    out = []
    home = _host(dept_url)
    for href, _text in links(strip_chrome(html), dept_url):
        if not _host(href) or _host(href) != home:
            continue
        path = _path(href)
        if not PROFILE_PATH.search(path):
            continue
        slug = [x for x in path.split("/") if x][-1]
        if NOT_A_PERSON_SLUG.match(slug):
            continue
        clean = href.split("?")[0]
        if clean not in out:
            out.append(clean)
    return out


def roster_under(profile_url: str, institution: str, field: str) -> dict | None:
    html = get(profile_url)
    if not html:
        return None
    site = group_site_for(profile_url, html)
    if not site:
        return None
    shtml = get(site)
    if not shtml:
        return None
    page = members_page(site, shtml)
    phtml = shtml if page == site else get(page)
    if not phtml:
        return None
    raw = best_names(phtml)
    cache.put(page, raw)
    names = []
    for n in raw:
        c = clean_member(n)
        if c and c not in names:
            names.append(c)
    if len(names) < MIN:
        return None
    m = re.search(r"<title[^>]*>(.*?)</title>", phtml, re.I | re.S)
    return {
        "url": page, "group_site": site, "from_profile": profile_url,
        "institution": institution, "department_field": field,
        "title": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
        if m else "",
        "status": "roster", "members": len(names),
        "members_detected": len(names), "composition": composition(names),
        "found_from": "department-walk",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True,
                    help="lines of: <department url> | <institution> | <field>")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--max-faculty", type=int, default=80)
    a = ap.parse_args()

    jobs = []
    for line in Path(a.file).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split("|")]
        jobs.append((parts[0], parts[1] if len(parts) > 1 else "",
                     parts[2] if len(parts) > 2 else ""))

    found = []
    for dept, inst, field in jobs:
        profs = faculty_of(dept)[: a.max_faculty]
        print(f"\n{dept[:62]}\n  {len(profs)} faculty profiles")
        hits = 0
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for r in ex.map(lambda u: roster_under(u, inst, field), profs):
                if r:
                    found.append(r)
                    hits += 1
                    c = r["composition"]
                    print(f"    {c['dominance']:>5}% "
                          f"{c['dominant_group'][:9]:<10} {r['members']:>3}m  "
                          f"{r['url'][:54]}")
                time.sleep(0.01)
        print(f"  {hits} rosters")

    if found:
        print("\n ", lab_store.merge(found, source="department-walk"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
