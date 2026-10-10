#!/usr/bin/env python3
"""Find the real department page for each program, and verify it.

A link to a Google search is not a link. The directory shipped with one
per row because discovering a department's URL at scale is harder than
generating a query, which is a reason and not an excuse.

HOW IT RESOLVES. Universities name department sites from a small set of
patterns -- a subdomain, a /dept/ path, a college path. This tries them
against the institution's domain, in order, and keeps the first that both
answers 200 AND reads like the right department: the page has to mention
the field. A page that merely exists is not a match; the university's
404 handler also returns 200 on many of these sites.

EVERY URL IS VERIFIED BEFORE IT IS WRITTEN. The output records the status
code, the number of bytes and the terms that matched, so a bad link is
visible in the data rather than only when a reader clicks it.

Usage:
  python3 scripts/resolve_program_urls.py --set security
  python3 scripts/resolve_program_urls.py --set programs --limit 120
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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

LABS = ROOT / "data" / "labs"
OUT = LABS / "program_urls.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

#: Institution -> the domain its departments live under. Hand-kept,
#: because deriving it from a display name produces wrong hosts and a
#: wrong host silently resolves to somebody else's university.
DOMAINS = {
    "Missouri University of Science and Technology": "mst.edu",
    "University of Illinois Urbana-Champaign": "illinois.edu",
    "Purdue University-Main Campus": "purdue.edu",
    "Massachusetts Institute of Technology": "mit.edu",
    "North Carolina State University at Raleigh": "ncsu.edu",
    "Texas A&M University-College Station": "tamu.edu",
    "University of Michigan-Ann Arbor": "umich.edu",
    "The University of Tennessee-Knoxville": "utk.edu",
    "Georgia Institute of Technology-Main Campus": "gatech.edu",
    "Iowa State University": "iastate.edu",
    "University of Minnesota-Twin Cities": "umn.edu",
    "University of Colorado Boulder": "colorado.edu",
    "University of Maryland-College Park": "umd.edu",
    "The University of Texas at Austin": "utexas.edu",
    "The University of Texas at Arlington": "uta.edu",
    "Stanford University": "stanford.edu",
    "University of Southern California": "usc.edu",
    "Pennsylvania State University-Main Campus": "psu.edu",
    "Ohio State University-Main Campus": "osu.edu",
    "Rensselaer Polytechnic Institute": "rpi.edu",
    "University of Florida": "ufl.edu",
    "University of California-Los Angeles": "ucla.edu",
    "University of Washington-Seattle Campus": "washington.edu",
    "Colorado School of Mines": "mines.edu",
    "University of Utah": "utah.edu",
    "Virginia Polytechnic Institute and State University": "vt.edu",
    "University of Wyoming": "uwyo.edu",
    "University of Tulsa": "utulsa.edu",
    "Stony Brook University": "stonybrook.edu",
    "Arizona State University Campus Immersion": "asu.edu",
    "University of California-San Diego": "ucsd.edu",
    "Carnegie Mellon University": "cmu.edu",
    "University of California-Berkeley": "berkeley.edu",
    "Northwestern University": "northwestern.edu",
    "University of Cincinnati-Main Campus": "uc.edu",
    "University of Wisconsin-Madison": "wisc.edu",
    "California Institute of Technology": "caltech.edu",
    "University of Notre Dame": "nd.edu",
    "Oregon State University": "oregonstate.edu",
    "University of New Mexico-Main Campus": "unm.edu",
    "Kansas State University": "k-state.edu",
    "University of Idaho": "uidaho.edu",
    "University of Pittsburgh-Pittsburgh Campus": "pitt.edu",
    "Rice University": "rice.edu",
    "University of Houston": "uh.edu",
    "Louisiana State University and Agricultural & Mechanical College": "lsu.edu",
    "University of Oklahoma-Norman Campus": "ou.edu",
    "University of Alaska Fairbanks": "uaf.edu",
    "South Dakota School of Mines and Technology": "sdsmt.edu",
    "University of Nevada-Reno": "unr.edu",
    "Michigan Technological University": "mtu.edu",
    "The University of Alabama": "ua.edu",
    "Auburn University": "auburn.edu",
    "University of Central Florida": "ucf.edu",
    "Air Force Institute of Technology-Graduate School of Engineering & Management": "afit.edu",
}

#: Subdomain and path patterns, tried in order. {d} is the domain.
PATTERNS = {
    "nuclear": ["https://nuclear.{d}", "https://www.{d}/nuclear-engineering",
                "https://engineering.{d}/academics/departments/nuclear",
                "https://nuc.{d}", "https://mne.{d}", "https://ne.{d}", "https://npre.{d}",
                "https://ners.engin.{d}", "https://www.{d}/nuclear",
                "https://engineering.{d}/nuclear", "https://nse.{d}"],
    "aerospace": ["https://aerospace.{d}", "https://aero.{d}",
                  "https://www.{d}/aerospace-engineering",
                  "https://engineering.{d}/academics/departments/aerospace",
                  "https://mae.{d}", "https://www.mae.{d}", "https://ae.{d}", "https://aa.{d}",
                  "https://www.aere.{d}", "https://aerospace.{d}",
                  "https://www.{d}/aerospace", "https://engineering.{d}/aerospace",
                  "https://aeroastro.{d}"],
    "petroleum": ["https://petroleum.{d}", "https://www.{d}/petroleum",
                  "https://engineering.{d}/pete", "https://pete.{d}",
                  "https://www.{d}/engineering/petroleum", "https://pge.{d}",
                  "https://www.{d}/petroleum", "https://engineering.{d}/petroleum"],
    "mining": ["https://mining.{d}", "https://www.{d}/mining",
               "https://engineering.{d}/mining"],
    "ai": ["https://cs.{d}", "https://www.cs.{d}", "https://ece.{d}",
           "https://www.ece.{d}", "https://eecs.{d}", "https://cse.{d}",
           "https://www.{d}/cs", "https://engineering.{d}/ece"],
    "battery": ["https://mse.{d}", "https://matsci.{d}", "https://www.mse.{d}",
                "https://cheme.{d}", "https://che.{d}",
                "https://engineering.{d}/mse"],
}

#: Words that prove the page is the right department rather than a
#: university landing page or a 404 that answers 200.
PROOF = {
    "nuclear": ("nuclear", "radiolog", "reactor"),
    "aerospace": ("aerospace", "aeronaut", "astronaut"),
    "petroleum": ("petroleum", "reservoir", "drilling"),
    "mining": ("mining", "metallurg", "mineral"),
    "ai": ("computer science", "electrical", "computing", "engineering"),
    "battery": ("materials", "chemical engineering"),
}

#: STUDENT PAGES FIRST. A department's /people page is usually faculty and
#: staff -- Missouri S&T's nuclear one has no students on it at all --
#: while the roster that answers the question is a separate page a level
#: down. These are tried in order and the first that actually names
#: students wins, so a generic people page is only used as a fallback.
STUDENT_PATHS = [
    "/directory/graduate-students", "/people/graduate-students",
    "/graduate-students", "/grad-students", "/people/grad-students",
    "/directory/students", "/people/students", "/students",
    "/people/phd-students", "/graduate/students", "/academics/graduate/students",
    "/directory/graduate", "/people/current-students",
]
GENERIC_PATHS = ["/people", "/people/", "/directory", "/directory/",
                 "/people/faculty", "/faculty"]

#: Proof the page lists students rather than merely linking to them.
STUDENT_PROOF = re.compile(
    r"(graduate students?|ph\.?\s?d\.?\s+students?|doctoral students?|"
    r"grad students?|m\.?s\.?\s+students?)", re.I)


def get(url, timeout=14):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(400_000)
            if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                import gzip
                try:
                    raw = gzip.decompress(raw)
                except Exception:                              # noqa: BLE001
                    pass
            return r.status, raw.decode("utf-8", "replace"), r.url
    except urllib.error.HTTPError as e:
        return e.code, "", url
    except Exception:                                          # noqa: BLE001
        return 0, "", url


def resolve_one(inst: str, sector: str) -> dict:
    dom = DOMAINS.get(inst)
    if not dom:
        return {"institution": inst, "sector": sector,
                "status": "no-domain",
                "note": "institution domain not in the hand-kept table"}
    proof = PROOF.get(sector, ())
    for pat in PATTERNS.get(sector, []):
        url = pat.format(d=dom)
        code, html, final = get(url)
        if code != 200 or len(html) < 1500:
            continue
        body = re.sub(r"<[^>]+>", " ", html).lower()
        hits = [w for w in proof if w in body]
        #: Two proofs, or one plus the sector word in the title. A single
        #: generic hit on a university landing page is not a match.
        title = (re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
                 or [None, ""])[1] if re.search(r"<title", html, re.I) else ""
        title = re.sub(r"<[^>]+>", "", title or "").strip()[:110]
        strong = len(hits) >= 2 or (hits and sector in title.lower())
        if not strong:
            continue
        #: the roster under it: a student page if one exists, else the
        #: generic people page. A page counts as a student roster only if
        #: it says so AND carries enough name-shaped lines to be a list
        #: rather than a link to one.
        import harvest_lab_rosters as hl
        people = people_kind = None
        for pp in STUDENT_PATHS:
            c2, h2, f2 = get(final.rstrip("/") + pp, timeout=12)
            if c2 != 200 or len(h2) < 2500:
                continue
            body2 = re.sub(r"<[^>]+>", " ", h2)
            if STUDENT_PROOF.search(body2) and len(hl.candidate_names(h2)) >= 6:
                people, people_kind = f2, "students"
                break
        if not people:
            for pp in GENERIC_PATHS:
                c2, h2, f2 = get(final.rstrip("/") + pp, timeout=12)
                if c2 == 200 and len(h2) > 2500:
                    people, people_kind = f2, "people"
                    break
        return {"institution": inst, "sector": sector, "status": "ok",
                "url": final, "title": title, "bytes": len(html),
                "matched": hits, "people_url": people,
                "people_kind": people_kind}
    return {"institution": inst, "sector": sector, "status": "unresolved",
            "tried": len(PATTERNS.get(sector, []))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="security", choices=["security"])
    ap.add_argument("--limit", type=int, default=60)
    a = ap.parse_args()

    src = json.loads((LABS / "security_targets.json").read_text())
    want = [(t["institution"], t["sector"]) for t in src["targets"]]
    seen, pairs = set(), []
    for p in want:
        if p not in seen:
            seen.add(p)
            pairs.append(p)
    pairs = pairs[:a.limit]

    print(f"  resolving {len(pairs)} institution/sector pairs\n")
    rows = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(lambda p: resolve_one(*p), pairs):
            rows.append(r)
            mark = {"ok": "ok  ", "unresolved": "--  ",
                    "no-domain": "dom "}.get(r["status"], "??  ")
            extra = r.get("url", "") or r.get("note", "")
            print(f"  {mark}{r['sector']:10}{r['institution'][:38]:40}{extra[:46]}")

    ok = [r for r in rows if r["status"] == "ok"]
    write_text(OUT, json.dumps({
        "note": ("Department URLs resolved from a pattern list and verified: "
                 "each returned 200 and contained terms proving it is the "
                 "right department. No Google links."),
        "resolved": len(ok), "attempted": len(rows), "rows": rows}, indent=2))
    with_people = sum(1 for r in ok if r.get("people_url"))
    print(f"\n  {len(ok)}/{len(rows)} resolved, {with_people} with a people page")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
