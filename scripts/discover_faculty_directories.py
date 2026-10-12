#!/usr/bin/env python3
"""Find each university's faculty directories, to walk them.

walk_department turns a faculty list into lab rosters and works well.
What it lacked was a supply of faculty lists: coverage ran to 168
rosters at Penn State and a handful at most other universities,
because the lists came from whatever an earlier crawl happened to
resolve.

A department's faculty page sits at a small number of predictable
addresses under a small number of predictable hosts. This tries them,
keeps the ones that answer with real profiles, and writes a walk list.
Nothing is guessed: a URL is kept only if it returns faculty profiles
the walker can use.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_department import faculty_of                        # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "labs" / "faculty_directories.json"

#: host prefix -> the field key the site uses
DEPT_HOSTS = {
    "cs": "ai", "cse": "ai", "eecs": "ai", "compsci": "ai",
    "ece": "ee", "ee": "ee", "elec": "ee",
    "me": "mecheng", "mae": "mecheng", "mech": "mecheng",
    "aero": "aerospace", "ae": "aerospace",
    "cee": "civileng", "civil": "civileng", "ce": "civileng",
    "cbe": "chemeng", "che": "chemeng", "chbe": "chemeng",
    "mse": "materials", "matse": "materials",
    "bme": "biomed", "chem": "chemistry", "chemistry": "chemistry",
    "physics": "physics", "phys": "physics",
    "math": "math", "stat": "stats", "statistics": "stats",
    "ise": "industrial", "ie": "industrial", "isye": "industrial",
    "nuclear": "nuclear", "ne": "nuclear",
    "bio": "biology", "biology": "biology",
    # second pass: hosts the first probe did not try
    "engineering": "", "eng": "", "grainger": "", "seas": "",
    "cems": "", "mems": "", "aerospace": "aerospace",
    "chemeng": "chemeng", "cheme": "chemeng", "chbme": "chemeng",
    "matsci": "materials", "materials": "materials",
    "biomed": "biomed", "bioe": "biomed", "beam": "biomed",
    "civileng": "civileng", "cive": "civileng", "cvl": "civileng",
    "mecheng": "mecheng", "mem": "mecheng", "mie": "mecheng",
    "nuceng": "nuclear", "nucl": "nuclear",
    "isen": "industrial", "iems": "industrial", "iem": "industrial",
    "orie": "industrial", "ieor": "industrial",
    "astro": "physics", "astronomy": "physics",
    "geology": "geoscience", "geo": "geoscience", "ess": "geoscience",
    "earth": "geoscience", "atmos": "geoscience",
    "petroleum": "petroleum", "pge": "petroleum",
    "mining": "mining", "mne": "mining",
    "ams": "math", "apam": "math", "acm": "math", "amath": "math",
    "biostat": "stats", "stats": "stats",
    "informatics": "ai", "ischool": "ai", "cics": "ai", "khoury": "ai",
}
PATHS = ("/people/faculty", "/faculty", "/people", "/directory/faculty",
         "/about/people/faculty", "/faculty-directory",
         "/people/faculty-directory", "/faculty-staff",
         "/directory/people", "/people/all-faculty", "/our-faculty",
         "/people/professors", "/about/faculty", "/faculty/index.html",
         "/people/index.html", "/directory")

#: university -> its domain, for the hosts above
UNIVERSITIES = {
    "Massachusetts Institute of Technology": "mit.edu",
    "Stanford University": "stanford.edu",
    "University of California-Berkeley": "berkeley.edu",
    "University of California-Los Angeles": "ucla.edu",
    "University of California-San Diego": "ucsd.edu",
    "University of Michigan-Ann Arbor": "umich.edu",
    "Carnegie Mellon University": "cmu.edu",
    "Cornell University": "cornell.edu",
    "Columbia University in the City of New York": "columbia.edu",
    "Princeton University": "princeton.edu",
    "University of Texas at Austin": "utexas.edu",
    "University of Wisconsin-Madison": "wisc.edu",
    "University of Minnesota-Twin Cities": "umn.edu",
    "Ohio State University-Main Campus": "osu.edu",
    "University of Maryland-College Park": "umd.edu",
    "North Carolina State University at Raleigh": "ncsu.edu",
    "University of Florida": "ufl.edu",
    "Arizona State University-Tempe": "asu.edu",
    "University of Arizona": "arizona.edu",
    "University of Colorado Boulder": "colorado.edu",
    "University of Utah": "utah.edu",
    "Michigan State University": "msu.edu",
    "Iowa State University": "iastate.edu",
    "Purdue University-Main Campus": "purdue.edu",
    "Rice University": "rice.edu",
    "University of Houston": "uh.edu",
    "Texas A & M University-College Station": "tamu.edu",
    "Virginia Polytechnic Institute and State University": "vt.edu",
    "University of Virginia-Main Campus": "virginia.edu",
    "Boston University": "bu.edu",
    "Northeastern University": "northeastern.edu",
    "New York University": "nyu.edu",
    "University of Southern California": "usc.edu",
    "Northwestern University": "northwestern.edu",
    "University of Chicago": "uchicago.edu",
    "Washington University in St Louis": "wustl.edu",
    "Vanderbilt University": "vanderbilt.edu",
    "Rutgers University-New Brunswick": "rutgers.edu",
    "University of Pittsburgh-Pittsburgh Campus": "pitt.edu",
    "University of Massachusetts-Amherst": "umass.edu",
    "University of Delaware": "udel.edu",
    "Stony Brook University": "stonybrook.edu",
    "University of Washington-Seattle Campus": "washington.edu",
    "Oregon State University": "oregonstate.edu",
    "Colorado School of Mines": "mines.edu",
    "Missouri University of Science and Technology": "mst.edu",
    "University of Oklahoma-Norman Campus": "ou.edu",
    "University of Kansas": "ku.edu",
    "University of Nebraska-Lincoln": "unl.edu",
    "Louisiana State University and Agricultural & Mechanical College":
        "lsu.edu",
    "University of Alabama": "ua.edu",
    "Auburn University": "auburn.edu",
    "University of Tennessee-Knoxville": "utk.edu",
    "University of Kentucky": "uky.edu",
    "Clemson University": "clemson.edu",
    "University of South Carolina-Columbia": "sc.edu",
    "University of Central Florida": "ucf.edu",
    "Florida State University": "fsu.edu",
    "University of Miami": "miami.edu",
    "Lehigh University": "lehigh.edu",
    "Stevens Institute of Technology": "stevens.edu",
    "Rensselaer Polytechnic Institute": "rpi.edu",
    "Case Western Reserve University": "case.edu",
    "University of Notre Dame": "nd.edu",
    "Johns Hopkins University": "jhu.edu",
    "Dartmouth College": "dartmouth.edu",
    "Brown University": "brown.edu",
    "Duke University": "duke.edu",
    "Emory University": "emory.edu",
    "Wayne State University": "wayne.edu",
    "Illinois Institute of Technology": "iit.edu",
    "University of Illinois Chicago": "uic.edu",
    "Temple University": "temple.edu",
    "Drexel University": "drexel.edu",
    "Syracuse University": "syr.edu",
    "University of Connecticut": "uconn.edu",
    "Binghamton University": "binghamton.edu",
    "University at Buffalo": "buffalo.edu",
    "Michigan Technological University": "mtu.edu",
    "New Jersey Institute of Technology": "njit.edu",
    "Worcester Polytechnic Institute": "wpi.edu",
    "University of New Mexico-Main Campus": "unm.edu",
    "New Mexico State University-Main Campus": "nmsu.edu",
    "Texas Tech University": "ttu.edu",
    "University of Texas at Dallas": "utdallas.edu",
    "University of Texas at Arlington": "uta.edu",
    "Wichita State University": "wichita.edu",
    "University of Cincinnati-Main Campus": "uc.edu",
    "University of Iowa": "uiowa.edu",
    "Kansas State University": "k-state.edu",
    "Mississippi State University": "msstate.edu",
}


def probe(job: tuple) -> dict | None:
    url, inst, field = job
    try:
        profs = faculty_of(url)
    except Exception:                                         # noqa: BLE001
        return None
    #: a real faculty list offers several profiles, not one stray link
    if len(profs) < 5:
        return None
    return {"url": url, "institution": inst, "field": field,
            "profiles": len(profs)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    jobs = []
    for inst, domain in UNIVERSITIES.items():
        for host, field in DEPT_HOSTS.items():
            for path in PATHS:
                jobs.append((f"https://{host}.{domain}{path}", inst, field))
    if a.limit:
        jobs = jobs[: a.limit]
    print(f"Probing {len(jobs)} candidate faculty directories")

    found = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, r in enumerate(ex.map(probe, jobs), 1):
            if r:
                found.append(r)
                print(f"  {r['profiles']:>4} profiles  {r['url'][:62]}")
            if i % 500 == 0:
                print(f"  ... {i}/{len(jobs)}, {len(found)} directories")
            time.sleep(0.005)

    OUT.write_text(json.dumps(
        {"why": "Faculty directories that answered with real profiles.",
         "count": len(found), "directories": found}, indent=2) + "\n")
    print(f"\n  {len(found)} live faculty directories")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
