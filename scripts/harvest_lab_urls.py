#!/usr/bin/env python3
"""Harvest rosters from lab URLs supplied directly.

WHY THIS EXISTS. Crawling departments finds department pages. The
pages that answer the author's question are individual laboratory
rosters, and those are scattered across hosts a department never
links to -- zhulab.engr.tamu.edu, kim.mse.ufl.edu, metalab.gatech.edu.
Search finds them in one step where three hops of crawling did not.

Reads URLs from a file (one per line, '#' comments ignored) or stdin,
harvests each, and merges into the file the ranker reads. Append-only.
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
import lab_store  # noqa: E402
from follow_lab_links import MEMBERS, get, links, strip_chrome  # noqa: E402
from harvest_lab_rosters import best_names, composition          # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LABS = ROOT / "data" / "labs" / "discovered_labs.json"
#: 8, matching the ranker and the other harvesters. THREE OF THE SIX
#: STORED A ROSTER ONLY AT 12+ while three stored at 8, so the 8-11 band
#: was a biased sample of whichever crawler happened to find the page.
MIN_MEMBERS = 8


def institution_of(url: str, html: str) -> str:
    """Name the university from the host, then the page."""
    host = urlparse(url).netloc.lower()
    known = {
        "tamu.edu": "Texas A & M University-College Station",
        "ttu.edu": "Texas Tech University",
        "utexas.edu": "The University of Texas at Austin",
        "ufl.edu": "University of Florida",
        "illinois.edu": "University of Illinois Urbana-Champaign",
        "asu.edu": "Arizona State University-Tempe",
        "arizona.edu": "University of Arizona",
        "nau.edu": "Northern Arizona University",
        "ua.edu": "The University of Alabama",
        "gatech.edu": "Georgia Institute of Technology-Main Campus",
        "uri.edu": "University of Rhode Island",
        "ncsu.edu": "North Carolina State University at Raleigh",
        "osu.edu": "Ohio State University-Main Campus",
        "umich.edu": "University of Michigan-Ann Arbor",
        "wisc.edu": "University of Wisconsin-Madison",
        "umn.edu": "University of Minnesota-Twin Cities",
        "psu.edu": "Pennsylvania State University-Main Campus",
        "ucsd.edu": "University of California-San Diego",
        "ucdavis.edu": "University of California-Davis",
        "uci.edu": "University of California-Irvine",
        "usc.edu": "University of Southern California",
        "colostate.edu": "Colorado State University-Fort Collins",
        "utah.edu": "University of Utah",
        "ou.edu": "University of Oklahoma-Norman Campus",
        "lsu.edu": "Louisiana State University and Agricultural & "
                   "Mechanical College",
        "utk.edu": "The University of Tennessee-Knoxville",
        "vt.edu": "Virginia Polytechnic Institute and State University",
        "rice.edu": "Rice University",
        "uh.edu": "University of Houston",
        "msu.edu": "Michigan State University",
        "iastate.edu": "Iowa State University",
        "purdue.edu": "Purdue University-Main Campus",
        "unm.edu": "University of New Mexico-Main Campus",
        "nmsu.edu": "New Mexico State University-Main Campus",
        "ufl.edu ": "University of Florida",
        "fsu.edu": "Florida State University",
        "ucf.edu": "University of Central Florida",
        "fiu.edu": "Florida International University",
        "miami.edu": "University of Miami",
        "clemson.edu": "Clemson University",
        "sc.edu": "University of South Carolina-Columbia",
        "uky.edu": "University of Kentucky",
        "missouri.edu": "University of Missouri-Columbia",
        "ku.edu": "University of Kansas",
        "unl.edu": "University of Nebraska-Lincoln",
        "oregonstate.edu": "Oregon State University",
        "washington.edu": "University of Washington-Seattle Campus",
        "colorado.edu": "University of Colorado Boulder",
        "harvard.edu": "Harvard University",
        "mines.edu": "Colorado School of Mines",
        "njit.edu": "New Jersey Institute of Technology",
        "uab.edu": "University of Alabama at Birmingham",
        "umbc.edu": "University of Maryland-Baltimore County",
        "northeastern.edu": "Northeastern University",
        "stanford.edu": "Stanford University",
        "sdstate.edu": "South Dakota State University",
        "albany.edu": "SUNY at Albany",
        "mit.edu": "Massachusetts Institute of Technology",
        "columbia.edu": "Columbia University in the City of New York",
        "cornell.edu": "Cornell University",
        "brown.edu": "Brown University",
        "duke.edu": "Duke University",
        "unc.edu": "University of North Carolina at Chapel Hill",
        "ucsb.edu": "University of California-Santa Barbara",
        "ucla.edu": "University of California-Los Angeles",
        "berkeley.edu": "University of California-Berkeley",
        "lehigh.edu": "Lehigh University",
        "mtu.edu": "Michigan Technological University",
        "stonybrook.edu": "Stony Brook University",
    }
    for suffix, name in known.items():
        if host.endswith(suffix.strip()) or f".{suffix.strip()}" in host:
            return name
    return ""


def field_of(url: str) -> str:
    """The site's field key, from the host or path."""
    s = url.lower()
    table = [
        ("mse", "materials"), ("matse", "materials"),
        ("materials", "materials"),
        ("che", "chemeng"), ("chbe", "chemeng"), ("chemeng", "chemeng"),
        ("cbe", "chemeng"),
        ("bme", "biomed"), ("biomed", "biomed"), ("biomems", "biomed"),
        ("mae", "mecheng"), ("ame", "mecheng"), ("mech", "mecheng"),
        ("me.", "mecheng"),
        ("ece", "ee"), ("ee.", "ee"), ("electrical", "ee"),
        ("cs.", "ai"), ("cse", "ai"), ("compute", "ai"),
        ("phys", "physics"), ("chem", "chemistry"),
        ("math", "math"), ("stat", "stats"),
        ("civil", "civileng"), ("cee", "civileng"),
        ("aero", "aerospace"), ("nuclear", "nuclear"),
        ("bio", "biology"),
    ]
    for key, val in table:
        if key in s:
            return val
    return ""


def harvest(url: str) -> dict | None:
    html = get(url)
    if not html:
        return None
    tries = [url]
    for href, text in links(strip_chrome(html), url):
        if urlparse(href).netloc != urlparse(url).netloc:
            continue
        if MEMBERS.search(text) or MEMBERS.search(urlparse(href).path):
            if href not in tries:
                tries.append(href)
    for u in tries[:5]:
        page = html if u == url else get(u)
        if not page:
            continue
        names = best_names(page)
        if len(names) < MIN_MEMBERS:
            continue
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
        return {
            "url": u,
            "institution": institution_of(u, page),
            "department_field": field_of(u),
            "title": re.sub(r"\s+", " ",
                            re.sub(r"<[^>]+>", "", m.group(1))).strip()
            if m else "",
            "status": "roster",
            "members": len(names),
            "members_detected": len(names),
            "composition": composition(names),
            "found_from": "search",
        }
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="file of URLs, one per line")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    raw = (Path(a.file).read_text() if a.file else sys.stdin.read())
    urls = [l.strip() for l in raw.splitlines()
            if l.strip() and not l.startswith("#")]
    print(f"Harvesting {len(urls)} supplied lab URLs")

    found = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(harvest, urls):
            if r:
                found.append(r)
                c = r["composition"]
                print(f"  {c.get('dominance', 0):>5}% "
                      f"{c.get('dominant_group', '-'):<11} "
                      f"{r['members']:>3}m  "
                      f"{(r['institution'] or '?')[:22]:24} {r['url'][:48]}")
            time.sleep(0.01)

    summary = lab_store.merge(found if 'found' in dir() else out, source="search")
    print(f"\n  {len(found)} rosters of {len(urls)}; "
          f"{summary['added']} new, {summary['improved']} improved; "
          f"{summary['rosters']} rosters in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
