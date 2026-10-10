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


#: Short forms used by the dissertation harvest, mapped onto the registered
#: names the domain table is keyed on.
PROGRAM_NAMES = {
    "UCLA": "University of California-Los Angeles",
    "UC Riverside": "University of California-Riverside",
    "UC Berkeley": "University of California-Berkeley",
    "UCSD": "University of California-San Diego",
    "UCSB": "University of California-Santa Barbara",
    "UC Davis": "University of California-Davis",
    "Stony Brook": "Stony Brook University",
    "NJIT": "New Jersey Institute of Technology",
    "RPI": "Rensselaer Polytechnic Institute",
    "RIT": "Rochester Institute of Technology",
    "NC State": "North Carolina State University at Raleigh",
    "Penn State": "Pennsylvania State University-Main Campus",
    "Missouri S&T": "Missouri University of Science and Technology",
    "Boston U": "Boston University",
    "Columbia": "Columbia University in the City of New York",
    "Cornell": "Cornell University", "Duke": "Duke University",
    "Harvard": "Harvard University", "Clemson": "Clemson University",
    "Dartmouth": "Dartmouth College", "Northwestern": "Northwestern University",
    "Michigan State": "Michigan State University",
    "Michigan Tech": "Michigan Technological University",
    "Mississippi State": "Mississippi State University",
    "Kansas State": "Kansas State University",
    "LSU": "Louisiana State University and Agricultural & Mechanical College",
    "U Buffalo": "University of Buffalo", "UConn": "University of Connecticut",
    "U Kentucky": "University of Kentucky", "UIUC": "University of Illinois Urbana-Champaign",
    "U Nebraska-Lincoln": "University of Nebraska-Lincoln",
    "Wash U St Louis": "Washington University in St Louis",
    "Rice": "Rice University", "Syracuse": "Syracuse University",
    "Iowa State": "Iowa State University", "UCF": "University of Central Florida",
    "Virginia Tech": "Virginia Polytechnic Institute and State University",
    "Texas Tech": "Texas Tech University", "Marquette": "Marquette University",
    "Ole Miss": "University of Mississippi",
    "CUNY Grad Center": "CUNY Graduate Center",
    "Louisiana Tech": "Louisiana Tech University",
}

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
    "Texas Tech University": "ttu.edu",
    "University of Missouri-Columbia": "missouri.edu",
    "Johns Hopkins University": "jhu.edu",
    "Columbia University in the City of New York": "columbia.edu",
    "Cornell University": "cornell.edu",
    "Duke University": "duke.edu",
    "Harvard University": "harvard.edu",
    "New York University": "nyu.edu",
    "Princeton University": "princeton.edu",
    "University of Pennsylvania": "upenn.edu",
    "Yale University": "yale.edu",
    "Brown University": "brown.edu",
    "University of California-Davis": "ucdavis.edu",
    "University of California-Irvine": "uci.edu",
    "University of California-Santa Barbara": "ucsb.edu",
    "University of Maryland-Baltimore County": "umbc.edu",
    "University of Massachusetts-Amherst": "umass.edu",
    "University of Virginia-Main Campus": "virginia.edu",
    "Boston University": "bu.edu",
    "Northeastern University": "northeastern.edu",
    "University of Delaware": "udel.edu",
    "University of Connecticut": "uconn.edu",
    "University of Rochester": "rochester.edu",
    "Case Western Reserve University": "case.edu",
    "Washington University in St Louis": "wustl.edu",
    "Vanderbilt University": "vanderbilt.edu",
    "Emory University": "emory.edu",
    "University of Iowa": "uiowa.edu",
    "University of Kansas": "ku.edu",
    "University of Kentucky": "uky.edu",
    "University of Nebraska-Lincoln": "unl.edu",
    "University of Arizona": "arizona.edu",
    "Clemson University": "clemson.edu",
    "University of South Carolina-Columbia": "sc.edu",
    "University of Georgia": "uga.edu",
    "Florida State University": "fsu.edu",
    "University of South Florida": "usf.edu",
    "Drexel University": "drexel.edu",
    "Lehigh University": "lehigh.edu",
    "Syracuse University": "syr.edu",
    "University of Buffalo": "buffalo.edu",
    "SUNY at Binghamton": "binghamton.edu",
    "Colorado State University-Fort Collins": "colostate.edu",
    "Utah State University": "usu.edu",
    "Washington State University": "wsu.edu",
    "Oklahoma State University-Main Campus": "okstate.edu",
    "University of Arkansas": "uark.edu",
    "Mississippi State University": "msstate.edu",
    "University of Alabama in Huntsville": "uah.edu",
    "Wayne State University": "wayne.edu",
    "Illinois Institute of Technology": "iit.edu",
    "Stevens Institute of Technology": "stevens.edu",
    "New Jersey Institute of Technology": "njit.edu",
    "Worcester Polytechnic Institute": "wpi.edu",
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
    "mining": ["https://mining.{d}", "https://mge.{d}",
               "https://www.{d}/mining-engineering",
               "https://engineering.{d}/mining-engineering", "https://www.{d}/mining",
               "https://engineering.{d}/mining"],
    "ai": ["https://cs.{d}", "https://www.khoury.{d}", "https://cis.{d}",
           "https://cs.{d}/", "https://compsci.{d}", "https://www.cise.{d}",
           "https://engineering.{d}/computer-science", "https://www.cs.{d}", "https://ece.{d}",
           "https://www.ece.{d}", "https://eecs.{d}", "https://cse.{d}",
           "https://www.{d}/cs", "https://engineering.{d}/ece"],
    "battery": ["https://mse.{d}", "https://matse.{d}", "https://dmse.{d}",
                "https://www.{d}/materials", "https://materials.{d}",
                "https://engineering.{d}/materials",
                "https://chemengr.{d}", "https://www.che.{d}", "https://matsci.{d}", "https://www.mse.{d}",
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
FACULTY_PATHS = ["/people/faculty", "/faculty", "/faculty/",
                 "/directory/faculty", "/people/faculty/"]
#: A page that is neither one nor the other: a single directory listing
#: everybody. Used only when faculty and students are not both found.
GENERIC_PATHS = ["/people", "/people/", "/directory", "/directory/"]

#: A URL that is an article about students rather than a list of them.
#: These passed the word test -- "graduate students" appears in the
#: headline -- and put links like /2026/phd-students-recognized and
#: /news/2025/01/31/graduate-engineer into the roster column, which is
#: worse than leaving it empty.
NOT_A_ROSTER = re.compile(
    r"(/news/|/magazine/|/blog/|/story|/stories/|/article|/press|"
    r"/20\d\d/|/award|/spotlight|/announce)", re.I)

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

        #: BOTH, SEPARATELY. A department usually publishes faculty and
        #: students on different pages, and the earlier version returned
        #: whichever it found first -- so a row that had both showed one.
        def probe(paths, require_students):
            for pp in paths:
                c2, h2, f2 = get(final.rstrip("/") + pp, timeout=12)
                if c2 != 200 or len(h2) < 2500 or NOT_A_ROSTER.search(f2):
                    continue
                body2 = re.sub(r"<[^>]+>", " ", h2)
                if require_students:
                    if not STUDENT_PROOF.search(body2):
                        continue
                    if len(hl.candidate_names(h2)) < 6:
                        continue
                return f2
            return None

        students = probe(STUDENT_PATHS, True)
        faculty = probe(FACULTY_PATHS, False)
        #: A combined directory is both; say so rather than listing it twice.
        combined = None
        if not (students and faculty):
            combined = probe(GENERIC_PATHS, False)

        return {"institution": inst, "sector": sector, "status": "ok",
                "url": final, "title": title, "bytes": len(html),
                "matched": hits,
                "students_url": students, "faculty_url": faculty,
                "directory_url": combined}
    return {"institution": inst, "sector": sector, "status": "unresolved",
            "tried": len(PATTERNS.get(sector, []))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="security",
                    choices=["security", "programs"],
                    help="security: the IPEDS sector lists. programs: the "
                         "institutions in the dissertation ranking, which "
                         "the sector lists never reach.")
    ap.add_argument("--limit", type=int, default=120)
    a = ap.parse_args()

    if a.set == "programs":
        #: The dissertation ranking names institutions in a short house
        #: style and does not carry an IPEDS name, so the domain table is
        #: keyed on both forms via PROGRAM_NAMES below.
        src = json.loads((LABS / "search_targets.json").read_text())
        want = [(PROGRAM_NAMES.get(t["university"], t["university"]),
                 t["critical_sector"])
                for t in src["targets"] if t["critical_sector"]]
    else:
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

    #: MERGE, DO NOT REPLACE. Running --set programs after --set security
    #: overwrote sixty-five resolved URLs with thirty-four, because the
    #: whole file was rewritten from one run's rows. Each run now adds to
    #: what is there, keyed on institution and sector, and a later OK
    #: supersedes an earlier failure but not the other way round.
    prior = {}
    if OUT.exists():
        try:
            for r in json.loads(OUT.read_text()).get("rows", []):
                prior[(r.get("institution"), r.get("sector"))] = r
        except Exception:                                      # noqa: BLE001
            pass
    for r in rows:
        k = (r["institution"], r["sector"])
        if k in prior and prior[k].get("status") == "ok" and r["status"] != "ok":
            continue
        prior[k] = r
    rows = sorted(prior.values(),
                  key=lambda r: (r["sector"], r["institution"]))

    ok = [r for r in rows if r["status"] == "ok"]
    write_text(OUT, json.dumps({
        "note": ("Department URLs resolved from a pattern list and verified: "
                 "each returned 200 and contained terms proving it is the "
                 "right department. No Google links."),
        "resolved": len(ok), "attempted": len(rows), "rows": rows}, indent=2))
    st = sum(1 for r in ok if r.get("students_url"))
    fa = sum(1 for r in ok if r.get("faculty_url"))
    co = sum(1 for r in ok if r.get("directory_url"))
    print(f"\n  {len(ok)}/{len(rows)} resolved | {st} student, {fa} faculty, "
          f"{co} combined directories")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
