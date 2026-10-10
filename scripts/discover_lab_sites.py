#!/usr/bin/env python3
"""Find the lab group pages that actually list students.

WHAT THE EVIDENCE SAYS, AFTER TRYING THE OTHER WAY FIRST. Department
directories mostly do not work: Missouri S&T's nuclear "People" page is
faculty and staff with no students on it, Iowa State answers an automated
request with a WAF rejection, NC State times out, Maryland renders nothing
a scraper can read. A probe that looked for the PHRASE "graduate students"
scored several of those as successes, which they were not -- it was
matching a navigation label.

What does work is the research group's own site. The Information
Processing Lab at Washington lists 82 people including every student;
LIGHT lists 27. Those pages exist because a lab advertises itself, and
they are the places a reader can actually see a group.

So this walks the other way round: from a department's faculty list, to
each faculty member's page, to the group site they link, and asks whether
that site names people. It is a discovery pass. It archives nothing and
counts nobody -- harvest_lab_rosters.py does that, against the seeds this
produces.

Usage:
  python3 scripts/discover_lab_sites.py --department "UCLA ECE" \\
      --faculty-url https://www.ee.ucla.edu/faculty/
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

OUT = ROOT / "data" / "labs" / "discovered_sites.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

#: A link that looks like a research group rather than a course or a paper.
GROUP_HINT = re.compile(
    r"(lab|laborator|group|\.github\.io|sites\.google\.com|research)", re.I)
#: and one that plainly is not
NOT_GROUP = re.compile(
    r"(scholar\.google|orcid|linkedin|twitter|x\.com|youtube|doi\.org|"
    r"arxiv|ieee|acm\.org|springer|wiley|\.pdf|mailto:|facebook)", re.I)
#: A page that names people says one of these.
PEOPLE_HINT = re.compile(
    r"(members?|people|our team|group members|lab members|students|alumni)",
    re.I)


def get(url: str, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            return r.status, raw.decode("utf-8", "replace"), r.url
    except urllib.error.HTTPError as e:
        return e.code, "", url
    except Exception:                                          # noqa: BLE001
        return 0, "", url


def links(html: str, base: str) -> list[str]:
    out = []
    for h in re.findall(r'href="([^"#]+)"', html):
        if NOT_GROUP.search(h):
            continue
        out.append(urllib.parse.urljoin(base, h))
    return out


def looks_like_roster(html: str) -> int:
    """How strongly a page reads as a list of people."""
    import harvest_lab_rosters as h
    names = h.candidate_names(html)
    body = re.sub(r"<[^>]+>", " ", html)
    return len(names) if PEOPLE_HINT.search(body) else len(names) // 3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--department", required=True)
    ap.add_argument("--faculty-url", required=True)
    ap.add_argument("--max-faculty", type=int, default=25)
    a = ap.parse_args()

    code, html, _ = get(a.faculty_url, timeout=30)
    if code != 200:
        print(f"  faculty page returned {code}")
        return 1

    #: Faculty pages on the same host are the profiles; anything offsite
    #: that looks like a group is a candidate in its own right.
    host = urllib.parse.urlsplit(a.faculty_url).netloc
    profiles, offsite = [], []
    for u in dict.fromkeys(links(html, a.faculty_url)):
        n = urllib.parse.urlsplit(u).netloc
        if n == host and re.search(r"(faculty|people|profile|/~)", u, re.I):
            profiles.append(u)
        elif n != host and GROUP_HINT.search(u):
            offsite.append(u)

    print(f"  {len(profiles)} profile links, {len(offsite)} offsite group links")

    found = []
    seen = set()
    for u in (offsite + profiles)[:a.max_faculty]:
        if u in seen:
            continue
        seen.add(u)
        c, h2, final = get(u)
        if c != 200 or len(h2) < 1500:
            continue
        score = looks_like_roster(h2)
        if score >= 8:
            found.append({"url": final, "names_detected": score,
                          "via": "offsite" if u in offsite else "profile"})
            print(f"    roster  {final[:66]:68} ~{score} names")
        else:
            #: one hop from a profile to the group it links
            for g in dict.fromkeys(links(h2, final)):
                if urllib.parse.urlsplit(g).netloc == host or not GROUP_HINT.search(g):
                    continue
                if g in seen:
                    continue
                seen.add(g)
                c3, h3, f3 = get(g)
                if c3 != 200 or len(h3) < 1500:
                    continue
                s3 = looks_like_roster(h3)
                if s3 >= 8:
                    found.append({"url": f3, "names_detected": s3,
                                  "via": "profile->group"})
                    print(f"    roster  {f3[:66]:68} ~{s3} names")
                time.sleep(0.5)
                break
        time.sleep(0.6)

    prior = {}
    if OUT.exists():
        try:
            prior = json.loads(OUT.read_text()).get("departments", {})
        except Exception:                                      # noqa: BLE001
            pass
    prior[a.department] = {"faculty_url": a.faculty_url,
                           "candidates": sorted(found,
                                                key=lambda r: -r["names_detected"])}
    write_text(OUT, json.dumps({"note": "Discovery only: nothing archived, "
                                        "nobody counted or classified.",
                                "departments": prior}, indent=2))
    print(f"\n  {len(found)} roster candidates -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
