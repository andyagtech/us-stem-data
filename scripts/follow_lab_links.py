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
sys.path.insert(0, str(ROOT / "scripts"))
import crawl_resume                                            # noqa: E402

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
    #: github.com/team is GitHub's own product page, not a lab's
    r"^https?://(www\.)?github\.com/(team|about|pricing|features)|"
    r"(scholar\.google|orcid|linkedin|twitter|x\.com|facebook|github\.io/?$|"
    r"researchgate|semanticscholar|dblp|acm\.org|ieee\.org|springer|"
    r"elsevier|wiley|arxiv|doi\.org|youtube|instagram|mailto)", re.I)


#: (connect, read). A scalar timeout spends its whole budget on the
#: handshake when a host simply never answers, which cost one crawl
#: 25 minutes against a single unresponsive address.
CONNECT_TIMEOUT = 4

#: WAIT WHEN TOLD TO WAIT. The widened crawl collected 12 http_429
#: rows -- a university asking us to slow down, recorded as if the page
#: had failed. A 429 is the one status worth sleeping on, and Retry-After
#: says how long. Capped, because a server may name an hour.
RETRY_AFTER_CAP = 30


def get(url: str, timeout: int = 20, tries: int = 2) -> str:
    """The page's HTML, or "" -- retrying a transient failure once.

    A connection reset used to return "" and be written down exactly
    like a page that is really gone. One retry separates the two for
    the price of one fetch.
    """
    for attempt in range(max(1, tries)):
        try:
            r = requests.get(url, headers={"User-Agent": UA},
                             timeout=(CONNECT_TIMEOUT, timeout),
                             allow_redirects=True)
            if r.status_code == 429 and attempt + 1 < max(1, tries):
                wait = RETRY_AFTER_CAP
                try:
                    wait = min(RETRY_AFTER_CAP,
                               max(1, int(r.headers.get("Retry-After", 5))))
                except (TypeError, ValueError):
                    wait = 5
                time.sleep(wait)
                continue
            if r.status_code != 200:
                return ""
            if "html" not in r.headers.get("content-type", "").lower():
                return ""
            return r.text[:900_000]
        except requests.Timeout:
            #: A timeout IS the answer: too slow to crawl. Retrying
            #: doubles the cost for the same result.
            return ""
        except Exception:                                     # noqa: BLE001
            if attempt + 1 < max(1, tries):
                time.sleep(1.0)
    return ""


#: Site chrome. A header's "People" link is the DEPARTMENT's people
#: page, not the professor's group, and matching it sent 59 Purdue
#: profiles to one department index and 32 LSU ones to an IT service
#: desk. Strip the chrome before looking for anything.
CHROME = re.compile(
    r"<(nav|header|footer)\b.*?</\1>|"
    r"<(ul|div)\b[^>]*(class|id)=[\"'][^\"']*"
    r"(nav|menu|breadcrumb|site-?header|site-?footer|utility|"
    r"global|masthead|skip)[^\"']*[\"'].*?</\2>",
    re.I | re.S)


def strip_chrome(html: str) -> str:
    return CHROME.sub(" ", html)


def links(html: str, base: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>',
                         html, re.I | re.S):
        #: URLJOIN RAISES TOO, not only urlparse. I guarded the parses
        #: and the walk died in the same place on the next run: a
        #: single href with an unbalanced bracket raises
        #: ValueError("Invalid IPv6 URL") here, before any of the
        #: guards downstream are reached.
        try:
            href = urljoin(base, m.group(1).strip())
        except ValueError:
            continue
        text = re.sub(r"<[^>]+>", " ", m.group(2))
        text = re.sub(r"\s+", " ", text).strip()
        out.append((href, text))
    return out


#: Paths that are the institution's, never one professor's.
INSTITUTIONAL = re.compile(
    #: a bare /people on the department's own host is the DEPARTMENT's
    #: directory. Seven Oregon State professors "linked" to it because
    #: it is in every page's body, and it was counted seven times.
    r"/(people|faculty|directory|staff)/?$|"
    r"/(students?|student-support|academics|admissions|about|news|events|"
    r"give|giving|contact|directory|apply|alumni|undergraduate|"
    r"graduate|programs?|courses?|seminars?|calendar|jobs|"
    r"employment|diversity|resources|services)(/|$)", re.I)


def surname_of(profile_url: str, html: str) -> str:
    """The professor's surname, for matching their own group link."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = re.sub(r"<[^>]+>", " ", m.group(1)) if m else ""
    title = re.split(r"[|\u2013\u2014<>]", title)[0]
    words = [w for w in re.findall(r"[A-Za-z][a-z]{2,}", title)]
    return words[-1].lower() if words else ""


def _safe_parse(url: str):
    """urlparse that returns a blank host rather than raising."""
    try:
        return urlparse(url)
    except ValueError:
        return urlparse("")


def group_site_for(profile_url: str, html: str) -> str:
    """The link on a profile that points at the person's own group.

    Ranked, because the first match was usually the wrong one. A link
    carrying the professor's own surname or sitting on its own host
    is theirs; a link saying "People" in the site header belongs to
    the department.
    """
    body = strip_chrome(html)
    home = urlparse(profile_url).netloc
    last = surname_of(profile_url, html)
    best, best_score = "", 0

    for href, text in links(body, profile_url):
        if JUNK_HOST.search(href):
            continue
        parsed = _safe_parse(href)
        host, path = parsed.netloc, parsed.path
        if not host or href.rstrip("/") == profile_url.rstrip("/"):
            continue
        if INSTITUTIONAL.search(path) and host == home:
            continue

        score = 0
        if GROUP_TEXT.search(text):
            score += 2
        #: the professor's name in the host or the path is the
        #: strongest evidence a page is theirs
        if last and len(last) > 3:
            if last in host.lower():
                score += 5
            elif last in path.lower():
                score += 3
        if host != home:
            score += 2
        if re.search(r"/~", path):
            score += 2
        if re.search(r"\b(lab|group)\b", host.lower()):
            score += 3
        if score > best_score:
            best, best_score = href, score

    #: a bare "lab" word with nothing else behind it is the department
    #: navigation again, so require more than one signal
    return best if best_score >= 3 else ""


def members_page(site: str, html: str) -> str:
    """A members page under a group site, or the site itself."""
    for href, text in links(html, site):
        if _safe_parse(href).netloc != _safe_parse(site).netloc:
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
    ap.add_argument("--restart", action="store_true",
                    help="ignore the resume file and follow every profile")
    a = ap.parse_args()

    #: KEYED ON WHAT WAS TRIED, NOT ON WHAT WAS FOUND. The skip set was
    #: read from this script's own output, which only holds the profiles
    #: that led somewhere -- so the 304 profiles that led nowhere were
    #: followed again on every run, for ever, and the limit kept being
    #: spent on them. A profile with no outbound group link is a result.
    resume = crawl_resume.Resume("follow_profiles", why=(
        "Faculty profiles follow_lab_links.py has already followed, "
        "whether or not a group site was found behind them."))
    if a.restart:
        resume.reset()
    else:
        #: seeded from the profiles this script is known to have walked
        seeded = resume.seed(
            l.get("from_profile") for l in
            (json.loads(OUT.read_text()).get("labs", [])
             if OUT.exists() else []))
        if seeded:
            print(f"  resume file seeded with {seeded} profiles that "
                  f"produced a group site")

    groups = json.loads(SRC.read_text())["groups"]
    pool = [r for r in groups
            if r.get("status") == "no_roster_parsed"
            and PROFILE.search(r.get("url", ""))]
    todo = [r for r in pool if r.get("url") not in resume.done][: a.limit]
    print(f"Following {len(todo)} faculty profiles to their group sites "
          f"({len(pool) - len(todo)} already followed or past the limit)")

    #: STORE IN BATCHES, MARK AFTER STORING. The run used to be held in
    #: memory and written once at the end, so an interrupted run of
    #: four hundred profiles lost all of them.
    BATCH = 40
    pending_rows: list[dict] = []
    pending_tried: list[str] = []
    found = 0

    def flush() -> None:
        nonlocal pending_rows, pending_tried
        if pending_rows:
            prev = {}
            if OUT.exists():
                try:
                    prev = {r["url"]: r for r in
                            json.loads(OUT.read_text())["labs"]}
                except (ValueError, KeyError):
                    prev = {}
            for r in pending_rows:
                prev.setdefault(r["url"], r)
            OUT.write_text(json.dumps({
                "why": ("Group sites reached by following a faculty "
                        "profile's own outbound link. The department crawl "
                        "stops at the profile; the laboratory is one hop "
                        "further out, usually on a different host."),
                "profiles_followed": len(resume.done) + len(pending_tried),
                "count": len(prev),
                "labs": sorted(prev.values(), key=lambda r: r["url"]),
            }, indent=2) + "\n")
            print(f"   stored: {len(prev)} group sites in all", flush=True)
        resume.mark_many(pending_tried)
        pending_rows, pending_tried = [], []

    try:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for i, (row, res) in enumerate(zip(todo, ex.map(walk, todo)), 1):
                pending_tried.append(row["url"])
                if res:
                    pending_rows.append(res)
                    found += 1
                    print(f"  {res['institution'][:26]:28} "
                          f"{res['url'][:66]}", flush=True)
                if len(pending_tried) >= BATCH:
                    flush()
                    print(f"  ... {i}/{len(todo)}, {found} group sites",
                          flush=True)
                time.sleep(0.02)
    except KeyboardInterrupt:
        print("\n  interrupted; storing what is in hand", flush=True)
    finally:
        flush()
        print(f"\n  {found} group sites from {len(todo)} profiles")
        print(f"  {len(resume.done)} profiles followed in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
