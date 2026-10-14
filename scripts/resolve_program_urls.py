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
    #: THE 106 UNIVERSITIES THIS SITE PUBLISHES are the universe the
    #: lab search should cover, and 30 of them had no resolved
    #: department at all on 2026-10-14 -- UVA with 5,675 doctorates in
    #: the thesis record, Temple, USF, UC Santa Cruz, UCSF, George
    #: Mason, West Virginia, Syracuse, Oregon, CUNY. Sixteen were
    #: already in this table and had simply never been put in a target
    #: list; these fourteen were missing outright. Each one was checked
    #: with a request before being written down.
    "Boise State University": "boisestate.edu",
    "Brigham Young University": "byu.edu",
    "Montana State University": "montana.edu",
    "Northern Arizona University": "nau.edu",
    "Northern Illinois University": "niu.edu",
    "University of Northern Colorado": "unco.edu",
    "Portland State University": "pdx.edu",
    #: ucsc.edu answers 403 to a bare request. Checked rather than
    #: assumed: cse.ucsc.edu, physics.ucsc.edu and engineering.ucsc.edu
    #: all answer 200, and those are the pages the resolver reads.
    "University of California-Santa Cruz": "ucsc.edu",
    "University of California-San Francisco": "ucsf.edu",
    "The University of Montana": "umt.edu",
    "University of New Hampshire-Main Campus": "unh.edu",
    "University of Oregon": "uoregon.edu",
    "University of South Dakota": "usd.edu",
    "University of Southern Mississippi": "usm.edu",
    #: THESE TWO BLOCK US, and are written down so the attempt is on
    #: the record rather than looking like an oversight. ucmerced.edu
    #: and gc.cuny.edu return 403 to this crawler at the root AND at
    #: engineering.ucmerced.edu and gc.cuny.edu/physics, so the
    #: resolver will record "unresolved" for both and no lab at either
    #: university will be found by this route.
    "University of California-Merced": "ucmerced.edu",
    "CUNY Grad Center": "gc.cuny.edu",
    #: Added when each field widened from 14 institutions to 30.
    "University of Chicago": "uchicago.edu",
    "CUNY City College": "ccny.cuny.edu",
    "Cleveland State University": "csuohio.edu",
    "Georgia State University": "gsu.edu",
    "New Mexico State University-Main Campus": "nmsu.edu",
    "Old Dominion University": "odu.edu",
    "South Dakota State University": "sdstate.edu",
    "The Catholic University of America": "catholic.edu",
    "The University of Texas at San Antonio": "utsa.edu",
    "University at Albany": "albany.edu",
    "University of Alabama at Birmingham": "uab.edu",
    "University of Denver": "du.edu",
    "University of Hawaii at Manoa": "hawaii.edu",
    "University of Maryland Eastern Shore": "umes.edu",
    "University of Massachusetts-Lowell": "uml.edu",
    "University of North Dakota": "und.edu",
    "West Virginia University": "wvu.edu",
    "William & Mary": "wm.edu",
    #: The dissertation record's short house style, mapped straight to a
    #: domain. Simpler than routing each through PROGRAM_NAMES, and it
    #: cannot break when an IPEDS name changes.
    "CO School of Mines": "mines.edu",
    "CUNY Graduate Center": "gc.cuny.edu",
    "Caltech": "caltech.edu",
    "Dartmouth College": "dartmouth.edu",
    "Georgia Tech": "gatech.edu",
    "Indiana University-Bloomington": "indiana.edu",
    "MIT": "mit.edu",
    "Purdue": "purdue.edu",
    "Stanford": "stanford.edu",
    "U Delaware": "udel.edu",
    "U Florida": "ufl.edu",
    "U Houston": "uh.edu",
    "U Kansas": "ku.edu",
    "U Maryland": "umd.edu",
    "U Minnesota": "umn.edu",
    "U Missouri": "missouri.edu",
    "U Penn": "upenn.edu",
    "U South Carolina": "sc.edu",
    "U Virginia": "virginia.edu",
    "UC Irvine": "uci.edu",
    "UC Merced": "ucmerced.edu",
    "UC San Diego": "ucsd.edu",
    "UC Santa Barbara": "ucsb.edu",
    "UMass Amherst": "umass.edu",
    "UT Arlington": "uta.edu",
    "UT Austin": "utexas.edu",
    "UT Dallas": "utdallas.edu",
    "UW Seattle": "washington.edu",
    "University of California-Riverside": "ucr.edu",
    "University of Illinois Chicago": "uic.edu",
    "University of North Carolina at Chapel Hill": "unc.edu",
    "Wayne State": "wayne.edu",
    "West Virginia U": "wvu.edu",
    "Yale": "yale.edu",
    "Air Force Institute of Technology-Graduate School of Engineering & Management": "afit.edu",
    "Rensselaer Polytechnic Institute": "rpi.edu",
    "The University of Texas at Arlington": "uta.edu",
    "Purdue University-Main Campus": "purdue.edu",
    #: Added for the wider STEM search list. Hand-kept, because an
    #: institution's domain cannot be derived from its IPEDS name and a
    #: guess sends the resolver to someone else's website.
    "Binghamton University": "binghamton.edu",
    "Bowling Green State University-Main Campus": "bgsu.edu",
    "Clarkson University": "clarkson.edu",
    "Florida Atlantic University": "fau.edu",
    "Florida Institute of Technology": "fit.edu",
    "Florida International University": "fiu.edu",
    "George Mason University": "gmu.edu",
    "George Washington University": "gwu.edu",
    "Kent State University at Kent": "kent.edu",
    "Lamar University": "lamar.edu",
    "Louisiana Tech University": "latech.edu",
    "Marquette University": "marquette.edu",
    "Michigan State University": "msu.edu",
    "North Dakota State University-Main Campus": "ndsu.edu",
    "Ohio University-Main Campus": "ohio.edu",
    "Rochester Institute of Technology": "rit.edu",
    "Rutgers University-New Brunswick": "rutgers.edu",
    "Southern Illinois University-Carbondale": "siu.edu",
    "Southern Methodist University": "smu.edu",
    "Temple University": "temple.edu",
    "Texas A & M University-College Station": "tamu.edu",
    "The University of Texas at Dallas": "utdallas.edu",
    "Tulane University of Louisiana": "tulane.edu",
    "University at Buffalo": "buffalo.edu",
    "University of Akron Main Campus": "uakron.edu",
    "University of Dayton": "udayton.edu",
    "University of Louisville": "louisville.edu",
    "University of Maine": "maine.edu",
    "University of Memphis": "memphis.edu",
    "University of Miami": "miami.edu",
    "University of Mississippi": "olemiss.edu",
    "University of Nevada-Las Vegas": "unlv.edu",
    "University of North Carolina at Charlotte": "charlotte.edu",
    "University of North Texas": "unt.edu",
    "University of Texas Southwestern Medical Center": "utsouthwestern.edu",
    "University of Toledo": "utoledo.edu",
    "Western Michigan University": "wmich.edu",
    "Wichita State University": "wichita.edu",
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
    "bio": ["https://bioe.{d}", "https://bme.{d}", "https://www.bme.{d}",
            "https://biology.{d}", "https://bio.{d}", "https://biosci.{d}",
            "https://mcb.{d}", "https://biochem.{d}",
            "https://engineering.{d}/biomedical",
            "https://engineering.{d}/bioengineering",
            "https://www.{d}/biomedical-engineering",
            "https://www.{d}/bioengineering", "https://www.{d}/biology",
            "https://{d}/bme", "https://{d}/bioe",
            "https://bioengineering.{d}", "https://biomedical.{d}",
            "https://cbe.{d}", "https://bmes.{d}"],
    #: The wider STEM search list from rank_stem_targets.py. Not one of
    #: the six critical industries -- these say where to look, nothing
    #: more. Subdomain shapes are the common ones across US engineering
    #: and science schools.
    "math": ["https://math.{d}", "https://www.math.{d}",
             "https://mathematics.{d}", "https://stat.{d}",
             "https://statistics.{d}", "https://www.{d}/math",
             "https://www.{d}/mathematics", "https://math.sciences.{d}",
             "https://www.{d}/mathematics-statistics",
             "https://artsci.{d}/mathematics", "https://amath.{d}",
                  "https://{d}/math",
                  "https://www.{d}/artsci/math",
                  "https://www.{d}/college/math"],
    "cs": ["https://cs.{d}", "https://www.cs.{d}", "https://cse.{d}",
           "https://www.cse.{d}", "https://compsci.{d}",
           "https://www.{d}/computer-science", "https://cis.{d}",
           "https://engineering.{d}/computer-science", "https://ics.{d}",
           "https://csd.{d}", "https://www.{d}/cs", "https://eecs.{d}",
                  "https://{d}/cs",
                  "https://{d}/cse",
                  "https://www.{d}/engineering/computer-science"],
    "ee": ["https://ece.{d}", "https://www.ece.{d}", "https://ee.{d}",
           "https://www.ee.{d}", "https://eecs.{d}", "https://www.eecs.{d}",
           "https://engineering.{d}/electrical", "https://elec.{d}",
           "https://www.{d}/electrical-engineering",
           "https://engineering.{d}/ece", "https://www.{d}/ece",
                  "https://{d}/ece",
                  "https://{d}/ee",
                  "https://{d}/eecs",
                  "https://www.{d}/engineering/electrical",
                  "https://www.{d}/engineering/ece"],
    "me": ["https://me.{d}", "https://www.me.{d}", "https://mae.{d}",
           "https://mech.{d}", "https://meche.{d}", "https://mems.{d}",
           "https://engineering.{d}/mechanical",
           "https://www.{d}/mechanical-engineering",
           "https://mechanical.{d}", "https://www.{d}/me",
                  "https://{d}/me",
                  "https://{d}/mae",
                  "https://www.{d}/engineering/mechanical"],
    "chemeng": ["https://cheme.{d}", "https://che.{d}", "https://chbe.{d}",
                "https://chemeng.{d}", "https://engineering.{d}/chemical",
                "https://www.{d}/chemical-engineering", "https://cbe.{d}",
                  "https://{d}/cheme",
                  "https://{d}/chbe",
                  "https://www.{d}/engineering/chemical"],
    "civil": ["https://cee.{d}", "https://civil.{d}", "https://ce.{d}",
              "https://engineering.{d}/civil", "https://cce.{d}",
              "https://www.{d}/civil-engineering", "https://caee.{d}",
                  "https://{d}/cee",
                  "https://{d}/civil",
                  "https://www.{d}/engineering/civil"],
    "industrial": ["https://ise.{d}", "https://ie.{d}", "https://isye.{d}",
                   "https://imse.{d}", "https://engineering.{d}/industrial",
                   "https://www.{d}/industrial-engineering", "https://iems.{d}",
                  "https://www.{d}/engineering/industrial",
                  "https://{d}/ise",
                  "https://www.{d}/ise",
                  "https://engineering.{d}/ise",
                  "https://www.{d}/engineering/industrial-systems"],
    "physics": ["https://physics.{d}", "https://www.physics.{d}",
                "https://phys.{d}", "https://www.{d}/physics",
                "https://physastro.{d}", "https://artsci.{d}/physics",
                "https://www.{d}/physics-astronomy",
                  "https://{d}/physics",
                  "https://www.{d}/artsci/physics"],
    "chemistry": ["https://chemistry.{d}", "https://chem.{d}",
                  "https://www.chem.{d}", "https://www.{d}/chemistry",
                  "https://artsci.{d}/chemistry",
                  "https://{d}/chemistry",
                  "https://www.{d}/artsci/chemistry"],
    "biomed": ["https://bme.{d}", "https://www.bme.{d}", "https://bioe.{d}",
               "https://engineering.{d}/biomedical",
               "https://www.{d}/biomedical-engineering", "https://bioeng.{d}",
                  "https://{d}/bme",
                  "https://www.{d}/engineering/biomedical"],
    "optics": ["https://optics.{d}", "https://creol.{d}",
               "https://www.{d}/optics", "https://photonics.{d}",
                  "https://{d}/optics"],
    "oceanatmos": ["https://eas.{d}", "https://atmos.{d}", "https://ocean.{d}",
                   "https://geosciences.{d}", "https://marine.{d}",
                   "https://www.{d}/earth-atmospheric-sciences",
                   "https://eaps.{d}", "https://geo.{d}",
                  "https://{d}/eas",
                  "https://{d}/geosciences"],
    "nuclear": ["https://nuclear.{d}", "https://www.{d}/nuclear-engineering",
                "https://engineering.{d}/academics/departments/nuclear",
                "https://nuc.{d}", "https://mne.{d}", "https://ne.{d}", "https://npre.{d}",
                "https://ners.engin.{d}", "https://www.{d}/nuclear",
                "https://engineering.{d}/nuclear", "https://nse.{d}",
                  "https://{d}/nuclear"],
    "aerospace": ["https://aerospace.{d}", "https://aero.{d}",
                  "https://www.{d}/aerospace-engineering",
                  "https://engineering.{d}/academics/departments/aerospace",
                  "https://mae.{d}", "https://www.mae.{d}", "https://ae.{d}", "https://aa.{d}",
                  "https://www.aere.{d}", "https://aerospace.{d}",
                  "https://www.{d}/aerospace", "https://engineering.{d}/aerospace",
                  "https://aeroastro.{d}",
                  "https://{d}/aerospace",
                  "https://{d}/ae"],
    "petroleum": ["https://petroleum.{d}", "https://www.{d}/petroleum",
                  "https://engineering.{d}/pete", "https://pete.{d}",
                  "https://www.{d}/engineering/petroleum", "https://pge.{d}",
                  "https://www.{d}/petroleum", "https://engineering.{d}/petroleum",
                  "https://{d}/petroleum",
                  "https://www.{d}/engineering/petroleum"],
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
                "https://engineering.{d}/mse",
                "https://{d}/mse",
                "https://{d}/matse",
                "https://www.{d}/engineering/materials-science",
                "https://mse.engin.{d}",
                "https://matse.engr.{d}",
                "https://www.{d}/materials-science",
                "https://msae.{d}",
                "https://mems.{d}",
                "https://www.{d}/mse",
                "https://smse.{d}",
                "https://engineering.{d}/materials-science-engineering",
                "https://www.{d}/engineering/mse"],
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
    #: A proof term must appear in the page body before a URL is kept.
    #: It is what stops a department subdomain that has been reassigned
    #: -- "ce.example.edu" is Civil at one school and Continuing
    #: Education at another -- from being filed as the wrong department.
    #: bio had no proof terms either, so even a correct URL would have
    #: been discarded.
    "bio": ("biomedical", "bioengineering", "biolog", "biochem",
            "life sciences"),
    "math": ("mathematic", "statistic", "applied math"),
    "cs": ("computer science", "computing", "computer engineering"),
    "ee": ("electrical", "computer engineering", "electronic"),
    "me": ("mechanical", "aerospace engineering", "thermal"),
    "chemeng": ("chemical engineering", "biomolecular", "chemical and bio"),
    "civil": ("civil engineering", "environmental engineering", "structural"),
    "industrial": ("industrial", "systems engineering", "operations research"),
    "physics": ("physics", "astronomy", "astrophys"),
    "chemistry": ("chemistry", "biochemistry", "chemical"),
    "biomed": ("biomedical", "bioengineering", "biomedical engineering"),
    "optics": ("optic", "photonic", "laser"),
    "oceanatmos": ("atmospheric", "oceanograph", "earth science", "geoscience"),
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
FACULTY_PATHS = ["/people/faculty-directory", "/people/faculty-directory/",
                 "/people/faculty", "/faculty", "/faculty/",
                 "/directory/faculty", "/people/faculty/",
                 "/faculty-directory", "/faculty-directory/",
                 "/directory/faculty-staff", "/people/faculty-staff",
                 "/about/faculty", "/faculty-and-staff"]
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


#: The fields a research university is worth searching for a group in.
#: Taken from PATTERNS below, so a field with no URL pattern is not
#: asked for.
SECTORS_FOR_UNIVERSITIES = (
    "ai", "cs", "ee", "me", "civil", "chemeng", "chemistry", "physics",
    "math", "bio", "biomed", "aerospace", "industrial", "battery",
    "nuclear", "oceanatmos", "optics",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="security",
                    choices=["security", "programs", "stem", "universities"],
                    help="security: the IPEDS sector lists. programs: the "
                         "institutions in the dissertation ranking, which "
                         "the sector lists never reach. universities: every "
                         "university this site publishes, crossed with "
                         "every STEM field -- the universe, rather than "
                         "whichever list a target file happened to hold.")
    ap.add_argument("--limit", type=int, default=120)
    #: WHY A SKIP AND NOT A BIGGER LIMIT. `pairs[:limit]` takes the first
    #: N of the declared order, so reaching an untried pair meant raising
    #: the limit past every pair already resolved -- and refetching up to
    #: fifteen URL patterns at each of them against the university's own
    #: servers. 230 of the 580 declared pairs had never been attempted
    #: on 2026-10-14 for exactly this reason.
    ap.add_argument("--skip-resolved", action="store_true",
                    help="leave out pairs already resolved ok, so --limit "
                         "spends itself on ground not yet covered")
    a = ap.parse_args()

    if a.set == "universities":
        #: THE SITE'S OWN UNIVERSE, not a list assembled for another
        #: purpose. The three target files were built for the sector
        #: work and between them left 30 of the 106 published
        #: universities with no department resolved at all, so they
        #: were never searched for a research group.
        import institution_keys
        cat = json.loads(
            (ROOT / "pipeline" / "universities.json").read_text())
        names = [institution_keys.official_name(k) for k in cat]
        want = [(n, f) for n in names if n for f in SECTORS_FOR_UNIVERSITIES]
    elif a.set == "stem":
        #: The wider STEM search list. Keyed on field, not sector, but
        #: the resolver treats the two the same -- both are "a subject
        #: at an institution".
        src = json.loads((LABS / "stem_targets.json").read_text())
        want = [(t["institution"], t["field"]) for t in src["targets"]]
    elif a.set == "programs":
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
    if a.skip_resolved and OUT.exists():
        #: Only an OK is skipped. An "unresolved" row is retried, because
        #: the pattern list grows and a miss is not a verdict.
        done = {(r.get("institution"), r.get("sector"))
                for r in json.loads(OUT.read_text()).get("rows", [])
                if r.get("status") == "ok"}
        before = len(pairs)
        pairs = [p for p in pairs if p not in done]
        print(f"  skipping {before - len(pairs)} pairs already resolved")
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

    #: LAST, so a crawl cannot overwrite a link a person checked.
    from program_url_overrides import apply_to
    forced = apply_to(rows)
    if forced:
        print(f"  {forced} hand-supplied URL(s) reapplied")

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
