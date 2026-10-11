#!/usr/bin/env python3
"""Candidates for the faculty-mobility page, ranked by federal dollars.

WHAT THIS IS FOR. The question is not "how many professors left", which
no public source can answer. It is "who took a large amount of federal
research money and now holds a post abroad". The funding half of that is
a hard federal fact with an award number on it. The leaving half is
soft, and this script does not pretend otherwise -- it produces
CANDIDATES for a person to verify by hand, never rows for a page.

WHY A COUNT IS IMPOSSIBLE, stated here so nobody is tempted. ORCID marks
an affiliation "current" when no end date was typed into it. Nothing
else. Querying eight leading Chinese institutions as current against
eight US ones as past returns on the order of a thousand apparent moves
-- and the same institution set with BOTH marked current returns several
hundred people holding simultaneous appointments. The boundary between
those two groups is an artefact of record-keeping, not of anyone's
career. Any aggregate built on it measures data entry.

So the output is ordered by NSF dollars, which is checkable, and the
mobility signal is only ever a reason to go and look.

THREE THINGS THAT WILL PRODUCE A FALSE POSITIVE, in order of how often:

  1. A simultaneous appointment that reads as a move because the US
     entry has no end date. The commonest case by far.
  2. Name collision against the NSF award database. "Wei Chen" is not
     one person. The script reports how many distinct awardee
     institutions a name matched, which is the tell.
  3. An ordinary career with an ordinary explanation. A family
     situation, a spouse's job, a parent's illness, a retirement.
     Nothing in a database distinguishes those from anything else, and
     a page that forgets it is not evidence, it is innuendo.

Usage:
  python3 scripts/find_mobility_candidates.py --limit 40
  python3 scripts/find_mobility_candidates.py --min-awarded 1000000
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

OUT = ROOT / "data" / "labs" / "mobility_candidates.json"

ORCID = "https://pub.orcid.org/v3.0/csv-search/"
NSF = "https://api.nsf.gov/services/v1/awards.json"

#: Where they are now. Chosen because each is large enough that a US-
#: trained researcher moving there is unremarkable in itself -- the
#: point is the funding, not the destination.
CURRENT = [
    "Tsinghua University", "Peking University",
    "Shanghai Jiao Tong University", "Zhejiang University",
    "Fudan University", "University of Science and Technology of China",
    "Chinese Academy of Sciences", "Nanjing University",
    "Harbin Institute of Technology", "Beihang University",
    "Southern University of Science and Technology",
    "Hong Kong University of Science and Technology",
]

#: Where they were. The US institutions that hold the most federal
#: research money, so a past post at one is most likely to come with
#: an award record.
PAST = [
    "Stanford University", "Massachusetts Institute of Technology",
    "Harvard University", "University of Michigan",
    "University of Illinois", "Purdue University",
    "Georgia Institute of Technology", "University of California",
    "Carnegie Mellon University", "Johns Hopkins University",
    "Texas A&M University", "Pennsylvania State University",
    "Ohio State University", "University of Wisconsin",
    "University of Minnesota", "Columbia University",
]

UA = {"User-Agent": "phd-demographics research (public APIs only)"}


def orcid_pairs(current: str, past: str, rows: int = 200) -> list[dict]:
    q = (f'current-institution-affiliation-name:"{current}" AND '
         f'past-institution-affiliation-name:"{past}"')
    url = f"{ORCID}?q={urllib.parse.quote(q)}&rows={rows}"
    try:
        r = requests.get(url, headers={**UA, "Accept": "text/csv"}, timeout=40)
        if r.status_code != 200:
            return []
        out = []
        for row in csv.DictReader(io.StringIO(r.text)):
            given = (row.get("given-names") or "").strip()
            family = (row.get("family-name") or "").strip()
            if not (given and family):
                continue
            out.append({
                "orcid": row.get("orcid"),
                "name": f"{given} {family}",
                "current": current, "past": past,
                "current_all": row.get("current-institution-affiliation-name"),
                "past_all": row.get("past-institution-affiliation-name"),
            })
        return out
    except requests.RequestException:
        return []


def nsf_awards(name: str) -> dict:
    """Total obligated to this PI name, and the signals that it is not
    one person."""
    q = urllib.parse.quote(f'"{name}"')
    url = (f"{NSF}?pdPIName={q}&printFields=id,title,awardeeName,"
           f"fundsObligatedAmt,startDate,piFirstName,piLastName")
    try:
        r = requests.get(url, headers=UA, timeout=40)
        if r.status_code != 200:
            return {"awards": 0, "obligated": 0}
        aw = (r.json().get("response") or {}).get("award") or []
    except (requests.RequestException, ValueError):
        return {"awards": 0, "obligated": 0}

    total = 0
    insts, years = set(), []
    for a in aw:
        try:
            total += int(a.get("fundsObligatedAmt") or 0)
        except (TypeError, ValueError):
            pass
        if a.get("awardeeName"):
            insts.add(a["awardeeName"])
        if a.get("startDate"):
            years.append(a["startDate"][-4:])
    return {
        "awards": len(aw),
        "obligated": total,
        #: MORE THAN A FEW INSTITUTIONS MEANS MORE THAN ONE PERSON. A
        #: real career spans two or three awardees; eight means the name
        #: is shared and the total is meaningless.
        "awardee_institutions": len(insts),
        "institutions": sorted(insts)[:6],
        "first_award": min(years) if years else None,
        "last_award": max(years) if years else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40,
                    help="candidates to check against NSF")
    ap.add_argument("--min-awarded", type=int, default=500_000)
    ap.add_argument("--pairs", type=int, default=24,
                    help="institution pairs to query")
    a = ap.parse_args()

    print("Collecting candidates from ORCID")
    seen, people = set(), []
    pairs = [(c, p) for c in CURRENT for p in PAST][: a.pairs]
    for cur, past in pairs:
        for rec in orcid_pairs(cur, past):
            if rec["orcid"] in seen:
                continue
            seen.add(rec["orcid"])
            people.append(rec)
        time.sleep(0.2)
    print(f"  {len(people)} distinct ORCID records across {len(pairs)} pairs")

    #: Check the most promising first: a person whose record names a
    #: single current Chinese institution is a cleaner candidate than
    #: one listing five things.
    people.sort(key=lambda r: len((r.get("current_all") or "").split(",")))
    check = people[: a.limit]
    print(f"\nChecking {len(check)} against the NSF award database")

    rows = []
    for i, rec in enumerate(check, 1):
        nsf = nsf_awards(rec["name"])
        rec.update(nsf)
        #: THE BIGGEST NUMBERS ARE THE LEAST TRUSTWORTHY. "Wei Li"
        #: returned $10.8M across 25 awards at ELEVEN awardee
        #: institutions on the first run. That is not a career, it is a
        #: common name. Sorting on dollars alone would have put the two
        #: worst artefacts at the top of the page.
        rec["likely_name_collision"] = nsf.get("awardee_institutions", 0) > 3
        if nsf["obligated"] >= a.min_awarded:
            rows.append(rec)
            flag = ("  <-- SHARED NAME, not one person"
                    if rec["likely_name_collision"] else "")
            print(f"  {nsf['obligated']:>12,}  {nsf['awards']:>2} awards  "
                  f"{rec['name'][:24]:26} {rec['current'][:24]:26} "
                  f"{nsf['awardee_institutions']} inst{flag}")
        time.sleep(0.25)

    #: Clean candidates first, then by dollars. A reviewer should not
    #: have to scroll past two artefacts to reach the first real one.
    rows.sort(key=lambda r: (r["likely_name_collision"], -r["obligated"]))
    payload = {
        "built_by": "scripts/find_mobility_candidates.py",
        "sources": ["ORCID public API (csv-search)",
                    "NSF Award Search API"],
        "what_this_is": (
            "CANDIDATES FOR HAND VERIFICATION, not findings. Ordered by "
            "federal dollars, which is a checkable fact with an award "
            "number on it. The mobility signal is not: ORCID marks an "
            "affiliation current when no end date was typed into it, so "
            "a simultaneous appointment and a departure look identical "
            "here."),
        "two_traps_found_on_the_first_real_candidate": [
            "A CENTER GRANT IS NOT PERSONAL FUNDING. The top candidate's "
            "$15.25M includes a $10.4M MRSEC center award, which funded a "
            "multi-investigator centre and its students, not one person. "
            "Quoting the total as money that went to an individual "
            "overstates it by a factor of three. Read the award titles "
            "before quoting a sum.",
            "ORCID AND OPENALEX DISAGREED ABOUT WHERE HE IS NOW. ORCID "
            "gave a Chinese university as current; OpenAlex's byline-"
            "derived affiliations pointed at Singapore. Neither is "
            "authoritative -- one is self-reported, the other is scraped "
            "from paper bylines including visits and collaborations. The "
            "disagreement is the signal: it says go and find the "
            "institution's own page.",
        ],
        "before_publishing_any_row": [
            "Confirm the person is one person: check awardee_institutions, "
            "then read the award titles.",
            "Confirm the current post from the institution's own page, "
            "and archive it.",
            "Confirm the US post ended, from something other than a "
            "missing end date.",
            "State that changing institutions is ordinary and that "
            "nothing here alleges wrongdoing.",
        ],
        "min_awarded": a.min_awarded,
        "checked": len(check),
        "count": len(rows),
        "clean": sum(1 for r in rows if not r["likely_name_collision"]),
        "likely_collisions": sum(1 for r in rows
                                 if r["likely_name_collision"]),
        "candidates": rows,
    }
    write_text(OUT, json.dumps(payload, indent=1))
    print(f"\n  {len(rows)} of {len(check)} clear ${a.min_awarded:,}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
