#!/usr/bin/env python3
"""Rank discovered groups, with the correction a scan requires.

WHY A PLAIN P-VALUE WOULD BE WRONG HERE. Two labs named by the author
can each be tested on their own. A list assembled by CRAWLING cannot:
examine two hundred groups and about ten clear p < 0.05 with nothing
unusual happening, so the ten most striking rows of an uncorrected
table are partly an artefact of having looked two hundred times.

Benjamini-Hochberg controls the false discovery rate across the whole
set. At q = 0.05 it means: of the groups this page calls unusual, about
one in twenty is expected to be ordinary. That is a statement a reader
can check and a reviewer can accept. An uncorrected list is not.

THE COMPARISON IS THE DEPARTMENT the group sits in -- same admissions,
same funding, same applicant pool -- taken from this site's own thesis
record. Where that is too thin to be a baseline the group is reported
without a test rather than against a national figure that means
something else.

The output says how unusual a composition is. It does not say why, and
this site does not offer a why.

Usage:
  python3 scripts/rank_research_labs.py --q 0.05
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from math import comb
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

LABS = ROOT / "data" / "labs" / "discovered_labs.json"
PARQUET = ROOT / "site" / "data" / "exports" / "stem_records.parquet"
OUT = ROOT / "data" / "labs" / "lab_outliers.json"

#: field -> words that find the matching department in the thesis record
FIELD_WORDS = {
    "ai": ("computer", "computing"), "cs": ("computer science",),
    "ee": ("electrical",), "me": ("mechanical",),
    "aerospace": ("aerospace", "aeronaut"), "civil": ("civil",),
    "chemeng": ("chemical eng",), "chemistry": ("chemistry",),
    "physics": ("physics",), "math": ("mathematic", "statistic"),
    "bio": ("biolog", "biomedical"), "biomed": ("biomedical",),
    "battery": ("material",), "nuclear": ("nuclear",),
    "petroleum": ("petroleum",), "mining": ("mining",),
    "industrial": ("industrial", "systems eng"),
    "oceanatmos": ("geoscience", "atmospher", "earth"),
    "optics": ("optic", "photonic"),
}

#: institution name -> thesis-record key, via the index's own names
#:
#: THE LOOSE VERSION MATCHED THE WRONG UNIVERSITY. Taking any word of
#: four letters or more and looking for it inside a key sent "North
#: Carolina State University at Raleigh" to "northwestern", because
#: "north" is in it. A false baseline is worse than no baseline: it
#: tests a group against a department it has nothing to do with and
#: the number looks just as real.
#:
#: department_index.json carries each key's display name, which is the
#: authority. Match on the full name, then on a distinctive word, and
#: refuse anything ambiguous.
_NAMES: dict = {}


def _load_names() -> dict:
    global _NAMES
    if not _NAMES:
        f = ROOT / "data" / "labs" / "department_index.json"
        if f.exists():
            _NAMES = json.loads(f.read_text()).get("names") or {}
    return _NAMES


_GENERIC = {"university", "the", "of", "at", "college", "institute",
            "technology", "state", "main", "campus", "and", "school",
            "north", "south", "east", "west", "new", "a", "m"}


def _tokens(name: str) -> set:
    n = re.sub(r"[^a-z ]", " ", (name or "").lower())
    return {w for w in n.split() if len(w) > 3 and w not in _GENERIC}


#: Abbreviations the thesis record uses as display names. "MIT" and
#: "UIUC" are three and four characters, so a length filter drops them
#: and the university matches nothing at all.
_ABBREV = {
    "mit": "massachusetts institute of technology",
    "uiuc": "university of illinois urbana champaign",
    "ucla": "university of california los angeles",
    "ucsd": "university of california san diego",
    "ucsb": "university of california santa barbara",
    "cmu": "carnegie mellon university",
    "byu": "brigham young university",
    "nyu": "new york university",
    "usc": "university of southern california",
    "rpi": "rensselaer polytechnic institute",
    "rit": "rochester institute of technology",
    "njit": "new jersey institute of technology",
    "ncsu": "north carolina state university",
    "umd": "university of maryland",
    "gatech": "georgia institute of technology",
    "caltech": "california institute of technology",
    "penn_state": "pennsylvania state university",
    "uw_seattle": "university of washington",
}


def uni_key(name: str, keys: set) -> str:
    want_raw = re.sub(r"[^a-z ]", " ", (name or "").lower())
    for key, full in _ABBREV.items():
        if key not in keys:
            continue
        ft = _tokens(full)
        if ft and ft <= set(want_raw.split()):
            return key
    names = _load_names()
    want = _tokens(name)
    if not want:
        return ""
    best, score = "", 0
    for key, display in names.items():
        if key not in keys:
            continue
        have = _tokens(display) | _tokens(key.replace("_", " "))
        overlap = len(want & have)
        if not overlap:
            continue
        #: require the match to cover most of the shorter name, so
        #: "carolina state" does not land on "northwestern"
        cover = overlap / min(len(want), len(have) or 1)
        if cover >= 0.6 and overlap > score:
            best, score = key, overlap
    return best


def upper_tail(k: int, n: int, p: float) -> float:
    if not 0 < p < 1 or n <= 0:
        return 1.0
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i)
               for i in range(k, n + 1))


#: US POPULATION, from the Census Bureau's American Community Survey:
#: about 5.5 million people of Chinese origin, alone or in
#: combination, in a population of about 335 million. 1.6 per cent.
#:
#: WHAT THIS COMPARISON IS AND IS NOT. It asks the taxpayer's question
#: directly: a publicly funded laboratory against the public that
#: funds it. It does NOT model who applies to a doctoral programme --
#: graduate admissions do not draw from the general population, and
#: anyone comparing a laboratory with the census is comparing two
#: different things on purpose. The department comparison, which this
#: script also offers, asks the narrower question and is the harder
#: test to pass. Both are reported so a reader can see the difference.
US_POPULATION_SHARE = 0.016
US_POPULATION_SOURCE = (
    "US Census Bureau, American Community Survey: about 5.5 million "
    "people of Chinese origin alone or in combination, in a population "
    "of about 335 million.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", type=float, default=0.05,
                    help="false discovery rate")
    ap.add_argument("--against", choices=["population", "department"],
                    default="population",
                    help="population: the US population share, which is "
                         "the taxpayer comparison the author asked for. "
                         "department: the surrounding department, which "
                         "asks a narrower question.")
    ap.add_argument("--min-share", type=float, default=35.0,
                    help="percent, when comparing with the population: "
                         "the share at which a group is listed")
    ap.add_argument("--min-members", type=int, default=12,
                    help="a group smaller than this cannot carry a share. "
                         "The author rejected an 11-member roster as too "
                         "thin to assert on, whatever its share works out "
                         "at, and that is the floor this encodes.")
    a = ap.parse_args()

    #: A COLLEGE IS NOT A RESEARCH GROUP. The crawler reaches pages
    #: that list people across a whole college or department, and a
    #: share computed over them answers a different question from the
    #: one this table asks -- it is not a principal investigator's own
    #: roster, so there is no hiring decision behind it.
    #: engineering.missouri.edu/research/featured-research-projects
    #: is the College of Engineering's project list and was ranked as
    #: though it were a laboratory.
    NOT_A_GROUP = re.compile(
        r"/(featured-research-projects|research-areas?|research-centers?|"
        r"our-faculty|faculty-directory|all-faculty|directory|"
        r"research-highlights|news)/?$|"
        #: A UNIVERSITY'S OWN STUDENT PAGES. Following a faculty
        #: profile sometimes lands on the institution's student
        #: services rather than the professor's group:
        #: clemson.edu/students, iastate.edu/student-support.
        r"/(students?|student-support|about/students|graduate-students|"
        r"academics|admissions)/?$", re.I)

    doc = json.loads(LABS.read_text())
    #: Rows from the first crawl predate the status field. A row with
    #: a composition is a roster whether or not it says so.
    groups = [g for g in doc.get("groups", [])
              if (g.get("status") in (None, "roster") or g.get("composition"))
              and (g.get("members") or 0) >= a.min_members
              and not NOT_A_GROUP.search(g.get("url", ""))]
    print(f"{len(groups)} groups with {a.min_members}+ members, "
          f"from {doc.get('departments_examined')} departments examined")

    keys = {r[0] for r in duckdb.sql(
        f"SELECT DISTINCT university FROM '{PARQUET}'").fetchall()}

    #: one baseline per (university, field), computed once
    cache: dict = {}

    def baseline(inst: str, field: str):
        k = (inst, field)
        if k in cache:
            return cache[k]
        slug = uni_key(inst, keys)
        words = FIELD_WORDS.get(field) or ()
        if not slug or not words:
            cache[k] = None
            return None
        like = " OR ".join(f"lower(department) LIKE '%{w}%'" for w in words)
        r = duckdb.sql(f"""
            SELECT COUNT(*),
                   SUM(CASE WHEN classification='chinese' THEN 1 ELSE 0 END)
            FROM '{PARQUET}'
            WHERE university = '{slug}' AND degree = 'phd' AND ({like})
        """).fetchone()
        n, cn = int(r[0] or 0), int(r[1] or 0)
        #: A BASELINE NEEDS A DENOMINATOR TOO. Under thirty doctorates
        #: the department rate is itself too noisy to test against, so
        #: the group is reported without a test rather than against a
        #: number that cannot bear it.
        cache[k] = {"slug": slug, "doctorates": n, "chinese_markers": cn,
                    "share": round(cn / n * 100, 1) if n else None} \
            if n >= 30 else None
        return cache[k]

    tested, untested = [], []
    for g in groups:
        b = baseline(g["institution"], g.get("department_field", ""))
        n = g["members"]
        cn = (g.get("composition") or {}).get("markers_chinese") or 0
        if a.against == "population":
            p0 = US_POPULATION_SHARE
            dept_share = b["share"] if b else None
            dept_n = b["doctorates"] if b else None
        else:
            if not b:
                untested.append({**g, "reason": "no department baseline"})
                continue
            p0 = b["share"] / 100
            dept_share, dept_n = b["share"], b["doctorates"]
        tested.append({
            "institution": g["institution"], "title": g.get("title", ""),
            "url": g["url"], "field": g.get("department_field"),
            "members": n, "markers": cn,
            "share": (g.get("composition") or {}).get("share_chinese_markers"),
            "compared_with": a.against,
            "baseline_share": round(p0 * 100, 2),
            "department_share": dept_share,
            "department_doctorates": dept_n,
            "expected": round(p0 * n, 1),
            "p": upper_tail(cn, n, p0),
        })

    #: Benjamini-Hochberg over everything tested
    tested.sort(key=lambda r: r["p"])
    m = len(tested)
    cutoff = 0
    for i, r in enumerate(tested, 1):
        r["rank"] = i
        r["bh_threshold"] = round(a.q * i / m, 5) if m else None
        if m and r["p"] <= a.q * i / m:
            cutoff = i
    for i, r in enumerate(tested, 1):
        r["significant"] = i <= cutoff

    #: RANK BY SHARE, NOT BY P-VALUE, when the comparison is the
    #: population.
    #:
    #: Against 1.6% every research group in American STEM is
    #: "significant", including ones whose share is LOWER than the
    #: department around them -- 13 of the 33 flagged on the first run
    #: were below their own department. A test that calls a 13% group
    #: and a 71% group both significant has stopped discriminating,
    #: and a page built on it would say nothing. What separates these
    #: groups is the share and the size, so that is the ordering, and
    #: the department figure rides along for context.
    if a.against == "population":
        tested.sort(key=lambda r: (-(r["share"] or 0), -r["members"]))
        for r in tested:
            r["significant"] = (r["share"] or 0) >= a.min_share

    sig = [r for r in tested if r["significant"]]
    print(f"\n  {m} testable, {len(sig)} significant at q={a.q} "
          f"after Benjamini-Hochberg")
    print(f"  {len(untested)} had no usable department baseline\n")
    for r in sig[:24]:
        print(f"  {r['share']:>5}%  {r['markers']:>3} of {r['members']:<3} "
              f"(dept {r['department_share']}%)  p={r['p']:.2e}  "
              f"{r['institution'][:22]:24} {r['title'][:34]}")

    write_text(OUT, json.dumps({
        "method": (
            "Each group is compared with its own department's doctorates "
            "in this site's thesis record: same admissions, same funding, "
            "same applicant pool. The p-value is the exact binomial "
            "probability of seeing at least this many marked names in a "
            "group this size if it drew at the department's rate."),
        "why_corrected": (
            "This list was assembled by CRAWLING, not by being given names. "
            f"{m} groups were tested, so an uncorrected table would show "
            "roughly one in twenty as unusual with nothing unusual "
            "happening. Benjamini-Hochberg at q controls the false "
            "discovery rate across the whole set: of the groups called "
            "significant here, about q of them are expected to be "
            "ordinary."),
        "not_a_why": (
            "This says how unusual a composition is. It does not say why, "
            "and this site does not offer one. A group recruits from who "
            "applies, from collaborators, from a shared language, from a "
            "technique taught in few places."),
        "name_markers": (
            "A classifier reading names cannot know citizenship, birthplace "
            "or nationality, and many Americans have names it marks. The "
            "share is of NAMES CARRYING A MARKER and nothing more."),
        "compared_with": a.against,
        "baseline_share_pct": round(US_POPULATION_SHARE * 100, 2)
            if a.against == "population" else "each group's own department",
        "population_source": US_POPULATION_SOURCE
            if a.against == "population" else None,
        "q": a.q, "tested": m, "significant": len(sig),
        "departments_examined": doc.get("departments_examined"),
        "outliers": sig, "all_tested": tested,
        "no_baseline": untested}, indent=2))
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
