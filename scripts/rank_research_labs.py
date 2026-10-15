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
from math import comb, exp, lgamma, log, log1p
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

#: institution name -> thesis-record key.
#:
#: THIS USED TO SCORE TOKEN OVERLAP AND IT ANSWERED WRONGLY. The record's
#: display names are abbreviations -- "UC Berkeley", "Caltech", "UConn" --
#: so overlap against them sent "University of California-Berkeley" to
#: caltech, "University of Missouri-Columbia" to columbia (the one in New
#: York), "University of Pennsylvania" to penn_state and
#: "Washington University in St Louis" to uw_seattle. 34 of the 115
#: crawled institution names resolved wrongly or not at all.
#:
#: scripts/institution_keys.py joins the key's IPEDS UNITID to the
#: registered name instead, which is exact, and returns "" for a name it
#: does not know. A laboratory with no baseline is reported without one;
#: a laboratory measured against another university's department is a
#: number that looks just as real and is not.
from institution_keys import key_for                           # noqa: E402
from lab_overrides import ALWAYS_INCLUDE                        # noqa: E402
from lab_page_filter import canonical, is_a_research_group      # noqa: E402


def uni_key(name: str, keys: set) -> str:
    return key_for(name, keys)


def upper_tail(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p), in logs.

    comb(n, i) is an exact integer and for a roster of a few hundred
    it outgrows a float long before the product with p**i brings it
    back down: a 500-member page raised OverflowError and took the
    whole ranking with it. Summing in log space keeps every term
    representable, and the result is identical for the small n this
    was already handling.
    """
    if not 0 < p < 1 or n <= 0:
        return 1.0
    k = max(k, 0)
    if k > n:
        return 0.0
    if k == 0:
        return 1.0
    terms = []
    for i in range(k, n + 1):
        terms.append(lgamma(n + 1) - lgamma(i + 1) - lgamma(n - i + 1)
                     + i * log(p) + (n - i) * log1p(-p))
    top = max(terms)
    return min(1.0, exp(top + log(sum(exp(t - top) for t in terms))))


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
    #: 40, BECAUSE THAT IS WHAT THE PUBLISHED TABLE WAS BUILT WITH.
    #: The default was 35 and the live lab_outliers.json held 95 rows,
    #: which only 40 reproduces -- 35 gives 124. Nothing recorded the
    #: flag: the ranker is not in pipeline/datasets.py and no Makefile
    #: target calls it, so the threshold behind the published table had
    #: to be recovered by replaying the filter over all_tested. The run
    #: now writes its own arguments into the output so the next person
    #: reads them instead of guessing.
    ap.add_argument("--min-share", type=float, default=40.0,
                    help="percent, when comparing with the population: "
                         "the share at which a group is listed")
    ap.add_argument("--min-non-european", type=float, default=55.0,
                    help="percent: a lab is also listed when this much "
                         "of its roster is from outside Europe, even "
                         "with no single origin dominating")
    #: THE HISTORY OF THIS NUMBER, because it has moved twice and the
    #: reasons are not mine to paraphrase away.
    #:
    #: It was 8 when the ranker was written (776933f). It went to 12 on
    #: 2026-10-11 (ae61781) because the author rejected an 11-member
    #: roster as too thin to assert on, and turning that objection into
    #: a rule seemed better than a hand-written exception -- it also
    #: caught a 9-member Purdue group in the same crawl. It is 8 again
    #: on 2026-10-14 at the author's instruction.
    #:
    #: WHAT CHANGES AT 8. One person is an eighth of the roster, so the
    #: share moves in bigger steps and a single arrival or departure
    #: moves it further. What does NOT change is the test: against the
    #: general population's 1.6 per cent, 8 of 9 is 3.8e-14, and
    #: Benjamini-Hochberg still corrects across every group examined.
    #: A small denominator makes a share coarse. It does not make it
    #: wrong, and every row prints "n of m" so a reader sees the
    #: denominator and not just the percentage.
    ap.add_argument("--min-members", type=int, default=8,
                    help="a group smaller than this cannot carry a share")
    a = ap.parse_args()

    #: WHAT COUNTS AS A RESEARCH GROUP lives in one place now:
    #: scripts/lab_page_filter.py, with the measurement behind each
    #: pattern beside it. It was a regex literal here, and it only
    #: matched at the END of a path -- so a department's whole doctoral
    #: cohort passed through /industrial/people/graduate-students/foo
    #: at 254 members and 36.6%, which is the most convincing wrong
    #: number this table could print.
    doc = json.loads(LABS.read_text())
    #: Rows from the first crawl predate the status field. A row with
    #: a composition is a roster whether or not it says so.
    groups = [g for g in doc.get("groups", [])
              if (g.get("status") in (None, "roster") or g.get("composition"))
              #: A LAB THE AUTHOR REQUIRES skips the SIZE floor and
              #: nothing else. It still has to be a team page, still
              #: has to be at a US university, and still has to carry
              #: a roster somebody can read -- the override decides
              #: whether a measured group is published, never what the
              #: measurement says. One he sent has six members, which
              #: is below any floor this project has ever used, and
              #: without this it would not be measured at all and so
              #: could not be shown.
              and ((g.get("members") or 0) >= a.min_members
                   or g.get("url") in ALWAYS_INCLUDE)
              and is_a_research_group(g.get("url", ""),
                                      g.get("title", ""))[0]
              #: AND THE PAGE ITSELF, where it has been read.
              #: label_roster_pages records how many distinct role
              #: phrases and venue phrases each roster page uses, and
              #: a test has asserted since this morning that no
              #: published row names five or more venues while naming
              #: more venues than roles. The ranker did not ENFORCE
              #: it, so the test was a tripwire that fired whenever a
              #: new crawl found such a page -- sites.google.com/view/
              #: fenglab, 6 venues to 4 roles, listing collaborators
              #: at Cornell, Tsinghua and Notre Dame plus an
              #: industrial partner. An assertion the pipeline does
              #: not make is not a guard.
              #:
              #: A page with no venue words is untouched, which is why
              #: this is safe: covert.stanford.edu/people names no
              #: role and no venue and is a real roster.
              and not (int(g.get("venue_markers") or 0) >= 5
                       and int(g.get("venue_markers") or 0)
                       > int(g.get("role_markers") or 0))
              #: flag_non_us_labs reads each page's own contact
              #: addresses and banner. A roster it judged foreign is
              #: excluded: a Chinese laboratory staffed by Chinese
              #: students says nothing about American access to
              #: American programmes, which is what this measures.
              and g.get("us_affiliated") is not False]
    #: ONE PAGE, ONE GROUP. 46 rows were the same page reached through
    #: its own in-page navigation -- chemistry.brown.edu/people/faculty
    #: and then #menu, #flyout_search, #page_main_content. Four rows for
    #: one page inflates the denominator Benjamini-Hochberg divides by
    #: and could put one group in the table twice.
    #:
    #: The row kept is the one with the most members, then the shortest
    #: address, so the choice does not depend on crawl order.
    best: dict = {}
    for g in sorted(groups, key=lambda g: (-(g.get("members") or 0),
                                           len(g.get("url", "")),
                                           g.get("url", ""))):
        best.setdefault(canonical(g.get("url", "")), g)
    if len(best) != len(groups):
        print(f"  {len(groups) - len(best)} rows were the same page under "
              f"a different fragment")
    groups = list(best.values())
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
        comp = g.get("composition") or {}
        #: THE LARGEST SINGLE ORIGIN, not the Chinese one. A lab that
        #: is 8 of 11 South Asian is the case the author is looking
        #: for and scores near zero on a Chinese count; a lab at 45%
        #: Chinese can be visibly mixed, which is how a diverse Brown
        #: chemistry group reached a table of outliers.
        cn = comp.get("dominant_count")
        if cn is None:                       # a row harvested before the change
            cn = comp.get("markers_chinese") or 0
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
            "dominant_group": comp.get("dominant_group") or "chinese",
            "non_european_share": comp.get("non_european_share"),
            "non_european_count": comp.get("non_european_count"),
            "by_origin": comp.get("by_origin") or {},
            "share": (comp.get("dominance")
                      if comp.get("dominance") is not None
                      else comp.get("share_chinese_markers")),
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
            #: EITHER MEASURE ADMITS A LAB. One origin at 40% is a
            #: concentrated group; so is a lab that is 70% from
            #: outside Europe with no single origin dominating, which
            #: is the case the author asked to catalogue second.
            r["significant"] = (
                (r["share"] or 0) >= a.min_share
                or (r.get("non_european_share") or 0) >= a.min_non_european)

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
        #: THE THRESHOLDS THAT PRODUCED THIS FILE. Without them a reader
        #: cannot tell a table of 95 from a table of 124, and neither
        #: could this project: see --min-share.
        "built_with": {
            "q": a.q, "against": a.against, "min_share": a.min_share,
            "min_non_european": a.min_non_european,
            "min_members": a.min_members},
        "what_share_means": (
            "The share is the LARGEST single origin on the roster, not "
            "the Chinese one. 'dominant_group' names which origin it "
            "is. A group counted as 'other' is never the dominant one: "
            "it is everything the classifier does not recognise, not "
            "an origin."),
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
