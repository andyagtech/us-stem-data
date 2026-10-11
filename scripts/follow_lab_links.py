#!/usr/bin/env python3
"""Follow a faculty profile to the group site it links out to.

THE HOP THE CRAWLER WAS MISSING. discover_research_labs reaches a
department, then a faculty profile, and stops. But a profile is rarely
a roster -- it is one person's page, and the laboratory lives
somewhere else entirely:

  people.ece.uw.edu/hwang/      -> sites.google.com/uw.edu/light/members
  cs.stonybrook.edu/.../twang   -> alps-lab.github.io
  cs.unc.edu/person/...         -> lavi-lab.github.io

1,054 candidates came back "no_roster_parsed" and 388 of them are
profile pages. The roster was one link away on every one.

This reads each profile, finds the link that looks like the person's
own group site, fetches it, and looks for a members page under it.
Append-only: a URL already known keeps whatever it had.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "labs" / "discovered_labs.json"
OUT = ROOT / "data" / "labs" / "followed_labs.json"

UA = ("Mozilla/5.0 (compatible; phd-demographics/1.0; research; "
      "+https://phd-demographics.andy-barr.com)")

#: A profile page: one person, under a people/faculty index.
PROFILE = re.compile(
    r"/(people|faculty|profile|directory|person|staff|bio)/[^/]+/?(\?|$)",
    re.I)

#: Link text or href that promises a group rather than a paper.
GROUP_TEXT = re.compile(
    r"\b(lab|laboratory|group|research group|my group|team|"
    r"research team|homepage|web ?site|group ?page|our group)\b", re.I)
GROUP_HREF = re.compile(
    r"(lab|group|team|research)[-._/]?|/~", re.I)

#: Once on a group site, this is the page that lists who is in it.
MEMBERS = re.compile(
    r"\b(members?|people|team|students?|group|lab ?members|"
    r"current ?members|who ?we ?are|alumni)\b", re.I)

#: Hosts that are never somebody's lab.
JUNK_HOST = re.compile(
    r"(scholar\.google|orcid|linkedin|twitter|x\.com|facebook|github\.io/?$|"
    r"researchgate|semanticscholar|dblp|acm\.org|ieee\.org|springer|"
    r"elsevier|wiley|arxiv|doi\.org|youtube|instagram|mailto)", re.I)


def get(url: str, timeout: int = 20) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout,
                         allow_redirects=True)
        if r.status_code != 200:
            return ""
        if "html" not in r.headers.get("content-type", "").lower():
            return ""
        return r.text[:900_000]
    except Exception:                                         # noqa: BLE001
        return ""


def links(html: str, base: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>',
                         html, re.I | re.S):
        href = urljoin(base, m.group(1).strip())
        text = re.sub(r"<[^>]+>", " ", m.group(2))
        text = re.sub(r"\s+", " ", text).strip()
        out.append((href, text))
    return out


def group_site_for(profile_url: str, html: str) -> str:
    """The link on a profile that points at the person's own group."""
    home = urlparse(profile_url).netloc
    best = ""
    for href, text in links(html, profile_url):
        if JUNK_HOST.search(href):
            continue
        host = urlparse(href).netloc
        if not host:
            continue
        named = bool(GROUP_TEXT.search(text))
        #: an off-site link whose text says "lab" or "group" is the
        #: strongest signal there is
        if host != home and named:
            return href
        #: a same-site /~user/ or /lab/ path is the next best
        if named and GROUP_HREF.search(href) and not best:
            best = href
    return best


def members_page(site: str, html: str) -> str:
    """A members page under a group site, or the site itself."""
    for href, text in links(html, site):
        if urlparse(href).netloc != urlparse(site).netloc:
            continue
        if MEMBERS.search(text) or MEMBERS.search(urlparse(href).path):
            return href
    return site


def walk(row: dict) -> dict | None:
    url = row["url"]
    html = get(url)
    if not html:
        return None
    site = group_site_for(url, html)
    if not site:
        return None
    shtml = get(site)
    if not shtml:
        return None
    page = members_page(site, shtml)
    return {
        "from_profile": url,
        "institution": row.get("institution"),
        #: the crawler records the field as department_field;
        #: reading row["sector"] returned None on all 69 and
        #: every followed lab rendered an empty field chip
        "sector": row.get("department_field") or row.get("sector"),
        "department_field": row.get("department_field"),
        "group_site": site,
        "url": page,
        "found": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    groups = json.loads(SRC.read_text())["groups"]
    #: skip profiles a previous run already walked, or --limit keeps
    #: handing back the same first N and the rest are never reached
    done = set()
    if OUT.exists():
        done = {l.get("from_profile") for l in
                json.loads(OUT.read_text())["labs"]}
    todo = [r for r in groups
            if r.get("status") == "no_roster_parsed"
            and PROFILE.search(r.get("url", ""))
            and r.get("url") not in done][: a.limit]
    print(f"Following {len(todo)} faculty profiles to their group sites")

    found: list[dict] = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, res in enumerate(ex.map(walk, todo), 1):
            if res:
                found.append(res)
                print(f"  {res['institution'][:26]:28} {res['url'][:66]}")
            if i % 50 == 0:
                print(f"  ... {i}/{len(todo)}, {len(found)} group sites")
            time.sleep(0.02)

    #: append-only: keep anything a previous run found
    prev = {}
    if OUT.exists():
        prev = {r["url"]: r for r in json.loads(OUT.read_text())["labs"]}
    for r in found:
        prev.setdefault(r["url"], r)

    OUT.write_text(json.dumps({
        "why": ("Group sites reached by following a faculty profile's own "
                "outbound link. The department crawl stops at the profile; "
                "the laboratory is one hop further out, usually on a "
                "different host."),
        "profiles_followed": len(todo),
        "count": len(prev),
        "labs": sorted(prev.values(), key=lambda r: r["url"]),
    }, indent=2) + "\n")
    print(f"\n  {len(found)} group sites from {len(todo)} profiles")
    print(f"  wrote {OUT.relative_to(ROOT)} ({len(prev)} total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
