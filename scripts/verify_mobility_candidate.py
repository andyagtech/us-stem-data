#!/usr/bin/env python3
"""Hand-verification sheet for one mobility candidate.

THE IDENTIFICATION PROBLEM IS THE WHOLE PROBLEM. Chinese given and
family names draw on a small pool: a handful of surnames cover a large
share of the population, so "Wei Li" in the NSF award database is many
people and no amount of care with the funding figures fixes that. The
name is not an identifier and must never be used as one.

WHAT DISAMBIGUATES. Not the name -- the INSTITUTION AND THE FIELD. A
person's ORCID record names where they worked. The NSF award record
names which institution received each award. Where those overlap, and
the award subject matches what the person publishes on, the
identification is defensible. Where they do not overlap, the name
matched somebody else and the total is meaningless.

So this prints, for one candidate:
  - every NSF award with its awardee institution and title
  - which of those institutions appear in the person's own ORCID record
  - the split between centre awards and personal awards
  - their OpenAlex affiliation history, which is derived from bylines
    and so fails differently from the self-reported ORCID one

It decides nothing. It lays the evidence out so a person can.

Usage:
  python3 scripts/verify_mobility_candidate.py "Huajian Gao"
  python3 scripts/verify_mobility_candidate.py "Fei Yan" --orcid 0000-...
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse

import requests

UA = {"User-Agent": "phd-demographics research (public APIs only)"}

#: An award whose title starts like this funds a centre, not a person.
#: The PI directs it and it is a mark of standing, but the money paid
#: many salaries and quoting it as personal funding overstates it.
CENTRE = re.compile(
    r"^\s*(MRSEC|ERC|STC|NSEC|IUCRC|Center|Centre|Institute|Workshop|"
    r"Conference|REU Site|Training|Collaborative Research Center|"
    r"Materials Research Science)", re.I)


def nsf(name: str) -> list[dict]:
    q = urllib.parse.quote(f'"{name}"')
    url = (f"https://api.nsf.gov/services/v1/awards.json?pdPIName={q}"
           f"&printFields=id,title,awardeeName,fundsObligatedAmt,startDate,"
           f"expDate,piFirstName,piLastName")
    r = requests.get(url, headers=UA, timeout=40)
    if r.status_code != 200:
        return []
    return (r.json().get("response") or {}).get("award") or []


def orcid_employments(oid: str) -> list[dict]:
    r = requests.get(f"https://pub.orcid.org/v3.0/{oid}/employments",
                     headers={**UA, "Accept": "application/json"}, timeout=30)
    if r.status_code != 200:
        return []
    out = []
    for g in r.json().get("affiliation-group") or []:
        for s in g.get("summaries") or []:
            e = s.get("employment-summary") or {}
            org = e.get("organization") or {}
            yr = lambda d: (d or {}).get("year", {}).get("value")     # noqa: E731
            out.append({
                "org": org.get("name", ""),
                "country": (org.get("address") or {}).get("country"),
                "role": e.get("role-title") or "",
                "start": yr(e.get("start-date")),
                "end": yr(e.get("end-date")),
            })
    return out


def orcid_find(name: str) -> list[str]:
    parts = name.split()
    if len(parts) < 2:
        return []
    q = (f'given-names:"{parts[0]}" AND family-name:"{parts[-1]}"')
    r = requests.get("https://pub.orcid.org/v3.0/search/",
                     params={"q": q, "rows": 8},
                     headers={**UA, "Accept": "application/json"}, timeout=30)
    if r.status_code != 200:
        return []
    return [x["orcid-identifier"]["path"] for x in r.json().get("result") or []]


def openalex(name: str) -> list[dict]:
    r = requests.get("https://api.openalex.org/authors",
                     params={"search": name, "per-page": 1},
                     headers=UA, timeout=30)
    if r.status_code != 200:
        return []
    res = r.json().get("results") or []
    if not res:
        return []
    a = res[0]
    out = []
    for af in a.get("affiliations") or []:
        ys = af.get("years") or []
        out.append({"org": af["institution"]["display_name"],
                    "country": af["institution"].get("country_code"),
                    "from": min(ys) if ys else None,
                    "to": max(ys) if ys else None})
    out.sort(key=lambda x: (x["from"] or 0))
    return out


#: Words that appear in hundreds of institution names and identify
#: nothing. "Virginia Polytechnic Institute and STATE University"
#: matched "STATE Key Laboratory" on this list's first version and
#: declared a different person's $529,249 verified. A match has to rest
#: on a distinctive token -- a place or a proper name -- never on one of
#: these.
GENERIC = {
    "university", "universities", "institute", "institutes", "college",
    "school", "schools", "research", "the", "and", "for", "of", "state",
    "national", "international", "key", "laboratory", "laboratories",
    "lab", "labs", "center", "centre", "centers", "science", "sciences",
    "scientific", "technology", "technological", "technical", "academy",
    "academic", "engineering", "advanced", "applied", "studies", "study",
    "graduate", "campus", "main", "system", "department", "faculty",
    "polytechnic", "agricultural", "mechanical", "medical", "medicine",
    "health", "public", "community", "regional", "central", "northern",
    "southern", "eastern", "western", "north", "south", "east", "west",
    "new", "old", "great", "grand", "saint", "county", "city", "area",
    "united", "states", "america", "american", "chinese", "china",
}


def norm(s: str) -> set:
    """Distinctive tokens only."""
    return {w for w in re.sub(r"[^a-z ]", " ", (s or "").lower()).split()
            if len(w) > 3 and w not in GENERIC}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--orcid", help="skip the search and use this iD")
    a = ap.parse_args()

    print(f"\n{'=' * 72}\n  {a.name}\n{'=' * 72}")

    awards = nsf(a.name)
    personal = centre = 0
    insts: dict = {}
    print(f"\nNSF AWARDS AS PRINCIPAL INVESTIGATOR  ({len(awards)} found)")
    for w in sorted(awards, key=lambda x: (x.get("startDate") or "")[-4:]):
        amt = int(w.get("fundsObligatedAmt") or 0)
        inst = w.get("awardeeName") or ""
        title = w.get("title") or ""
        is_c = bool(CENTRE.match(title))
        centre += amt if is_c else 0
        personal += 0 if is_c else amt
        insts[inst] = insts.get(inst, 0) + amt
        print(f"  {(w.get('startDate') or '')[-4:]}  ${amt:>10,}  "
              f"{'CENTRE ' if is_c else '       '}{inst[:28]:30} {title[:40]}")
    print(f"\n  personal awards  ${personal:>12,}")
    print(f"  centre awards    ${centre:>12,}   <- funded a centre, not a person")
    print(f"  total            ${personal + centre:>12,}")

    oid = a.orcid
    if not oid:
        found = orcid_find(a.name)
        print(f"\nORCID RECORDS MATCHING THIS NAME: {len(found)}")
        if len(found) != 1:
            print("  " + (", ".join(found) or "none"))
            print("  MORE THAN ONE, OR NONE. The name does not identify a "
                  "person.\n  Pass --orcid to pick one.")
        oid = found[0] if len(found) == 1 else None

    orc = orcid_employments(oid) if oid else []
    if orc:
        print(f"\nORCID EMPLOYMENT, SELF-REPORTED  ({oid})")
        for e in sorted(orc, key=lambda x: (x["start"] or 0)):
            print(f"  {e['start'] or '?'}-{e['end'] or 'present':<8} "
                  f"{e['country'] or '??'}  {e['org'][:40]:42} {e['role'][:24]}")

    oa = openalex(a.name)
    if oa:
        print("\nOPENALEX AFFILIATIONS, FROM PAPER BYLINES")
        for e in oa[:10]:
            print(f"  {e['from']}-{e['to']:<9} {e['country'] or '??'}  "
                  f"{e['org'][:48]}")

    #: THE TEST THAT MATTERS
    print(f"\n{'-' * 72}\nIDENTIFICATION: do the NSF awardees appear in this "
          f"person's own record?")
    own = set()
    for e in orc:
        own |= norm(e["org"])
    for e in oa:
        own |= norm(e["org"])
    if not own:
        print("  No ORCID or OpenAlex history to check against. "
              "UNVERIFIABLE on these sources.")
    else:
        for inst, amt in sorted(insts.items(), key=lambda kv: -kv[1]):
            hit = bool(norm(inst) & own)
            print(f"  {'MATCH  ' if hit else 'NO MATCH'}  ${amt:>11,}  {inst[:44]}")
        matched = sum(amt for i, amt in insts.items() if norm(i) & own)
        tot = sum(insts.values()) or 1
        pct = matched / tot * 100
        print(f"\n  ${matched:,} of ${tot:,} ({pct:.0f}%) sits "
              f"at an institution this person's own record names.")

        #: SAY THE VERDICT OUT LOUD. A reviewer reading a wall of awards
        #: will take the big number and move on. Most candidates fail
        #: here, and failing is the normal outcome, not an error.
        print(f"\n  VERDICT")
        if pct >= 90 and len(insts) <= 3:
            print("    The funding and the person line up. Now confirm the "
                  "CURRENT post\n    from the institution's own page, and "
                  "archive it. Then it is a case.")
        elif pct >= 60:
            print("    Partly lines up. Some of this money belongs to "
                  "someone else with\n    the same name. Split it before "
                  "quoting any total.")
        else:
            print("    REJECT. The awards sit at institutions this person's "
                  "own record\n    never mentions, so the name matched "
                  "somebody else. This is the\n    normal outcome for a "
                  "common name and it is not a finding.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
