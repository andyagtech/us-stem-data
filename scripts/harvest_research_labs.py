#!/usr/bin/env python3
"""Archive each declared lab's roster and attach its PI's NSF awards.

The roster gives composition; the award record gives the public money.
The second is the fact the page rests on, because it is exact and
carries an identifier. The first is context and is reported with its
denominator every time.

Run:
  python3 scripts/harvest_research_labs.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402
import harvest_lab_rosters as hl                               # noqa: E402
import lab_name_cache as name_cache                            # noqa: E402
import lab_store                                               # noqa: E402
from rank_research_labs import (                               # noqa: E402
    US_POPULATION_SHARE, US_POPULATION_SOURCE,
)
from research_labs import LABS                                 # noqa: E402

OUT = ROOT / "data" / "labs" / "research_labs.json"
SNAP = ROOT / "data" / "labs" / "snapshots"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}


def department_baseline(uni_slug: str, words: tuple) -> dict:
    """The department's OWN doctorates, as the comparison.

    "Out of sample" is only a claim if the sample is named. The right
    comparison for a laboratory is not the national figure and not the
    university's: it is the department that laboratory sits in, whose
    graduates came through the same admissions, the same funding and
    the same applicant pool. If a group differs from that, the
    difference is about the group.
    """
    import duckdb
    pq = ROOT / "site" / "data" / "exports" / "stem_records.parquet"
    like = " OR ".join(f"lower(department) LIKE '%{w}%'" for w in words)
    r = duckdb.sql(f"""
        SELECT COUNT(*),
               SUM(CASE WHEN classification = 'chinese' THEN 1 ELSE 0 END)
        FROM '{pq}'
        WHERE university = '{uni_slug}' AND degree = 'phd' AND ({like})
    """).fetchone()
    n, cn = int(r[0] or 0), int(r[1] or 0)
    return {"doctorates": n, "chinese_markers": cn,
            "share": round(cn / n * 100, 1) if n else None}


def upper_tail(k: int, n: int, p: float) -> float:
    """P(X >= k) for a binomial, computed exactly.

    Exactly, not by a normal approximation: n here is a dozen or two
    and the approximation is poor in the tail, which is the only part
    anybody is looking at.
    """
    from math import comb
    if not 0 < p < 1 or n <= 0:
        return 1.0
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i)
               for i in range(k, n + 1))


def main() -> int:
    SNAP.mkdir(parents=True, exist_ok=True)
    rows = []
    for lab in LABS:
        print(f"\n{lab.pi} - {lab.name[:48]}")
        try:
            r = requests.get(lab.roster_url, headers=UA, timeout=30)
            html, code = r.text, r.status_code
        except requests.RequestException as e:
            print(f"  roster unreachable: {type(e).__name__}")
            html, code = "", 0

        names = hl.best_names(html) if code == 200 else []
        #: A ROSTER THE CRAWLER CANNOT FETCH BUT A PERSON CAN READ.
        #: The whole of engineering.virginia.edu sits behind a
        #: Cloudflare javascript challenge, so two laboratories the
        #: author named there could not be measured at all -- not for
        #: want of a public roster, but for want of a way to read it.
        #: He read both pages in a browser and supplied them.
        #:
        #: The names go into the local cache, which is outside the
        #: repository, and ONLY the composition is written to
        #: data/labs. That is rule 1 of this module: totals only, no
        #: per-person label stored, shown or written to disk.
        supplied = False
        if not names:
            cached = name_cache.get(lab.roster_url)
            if cached:
                names, supplied = cached, True
                print(f"  roster  supplied; the live page answered {code}")
        comp = hl.composition(names) if names else {}
        snap = ""
        if html:
            import hashlib
            from datetime import datetime, timezone
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            h = hashlib.sha256(lab.roster_url.encode()).hexdigest()[:12]
            f = SNAP / f"lab_{h}_{stamp}.html"
            write_text(f, html)
            snap = str(f.relative_to(ROOT))

        n = comp.get("members_detected") or 0
        cn = comp.get("markers_chinese") or 0
        base = department_baseline(lab.uni_slug, lab.baseline_words)
        #: THE DISTRIBUTION IS THE COUNTRY. A laboratory the public pays
        #: for, against the public that pays for it. The department
        #: rate is computed too and reported beside it, because it is
        #: the harder test and a reader should see both.
        pval = upper_tail(cn, n, US_POPULATION_SHARE) if n else None
        p0 = (base["share"] or 0) / 100
        pval_dept = upper_tail(cn, n, p0) if (n and p0) else None
        print(f"  roster  {code}  {n} names listed")
        if n:
            print(f"          {comp.get('markers_chinese')} of {n} carry a "
                  f"Chinese name marker ({comp.get('share_chinese_markers')}%)")
        if base["doctorates"]:
            print(f"  dept    {base['chinese_markers']} of "
                  f"{base['doctorates']} doctorates = {base['share']}%")
        if pval is not None:
            print(f"  country expected {US_POPULATION_SHARE * n:.1f} at the "
                  f"US population rate; P(>= {cn}) = {pval:.2e}"
                  + (f"  1 in {round(1 / pval):,}" if pval else ""))
        if pval_dept is not None:
            print(f"  dept    expected {p0 * n:.1f} at the department rate; "
                  f"P(>= {cn}) = {pval_dept:.4f}"
                  + (f"  1 in {round(1 / pval_dept):,}" if pval_dept else ""))

        rows.append({
            "roster_read_from": ("a roster supplied by the author, because "
                                 "the live page is behind a challenge this "
                                 "crawler cannot pass")
                                if supplied else "the live page",
            "name": lab.name, "pi": lab.pi, "institution": lab.institution,
            "department": lab.department, "field": lab.field,
            "roster_url": lab.roster_url, "home_url": lab.home_url,
            "note": lab.note,
            "http_status": code,
            "members_listed": n,
            #: TOTALS ONLY. No per-person label is written here.
            "composition": comp,
            "snapshot": snap,
            #: THE DISTRIBUTION, named in the field rather than left
            #: to a reader to infer from a bare p-value.
            "compared_with": "the general population of the United States",
            "population_share_pct": round(US_POPULATION_SHARE * 100, 2),
            "population_source": US_POPULATION_SOURCE,
            "expected_at_population_rate": (
                round(US_POPULATION_SHARE * n, 1) if n else None),
            #: SIGNIFICANT FIGURES, NOT DECIMAL PLACES. Against the
            #: country the probabilities run to 1e-14, and rounding to
            #: eight decimals wrote them down as 0.0 -- which reads as
            #: "p = 0" and is not a thing.
            "p_value": float(f"{pval:.3g}") if pval is not None else None,
            "one_in": round(1 / pval) if pval else None,
            #: and the narrower, harder comparison beside it
            "department_baseline": base,
            "expected_at_department_rate": round(p0 * n, 1) if n else None,
            "p_value_against_department": (
                round(pval_dept, 5) if pval_dept is not None else None),
            "one_in_against_department": (
                round(1 / pval_dept) if pval_dept else None),
        })
        time.sleep(1.5)

    write_text(OUT, json.dumps({
        "what_this_is": (
            "Research groups with a public member list, archived, with the "
            "principal investigator's federal award record. The awards are "
            "exact and carry identifiers. The composition is a count of "
            "names carrying a marker, which is an INFERENCE from names and "
            "not a statement of anyone's citizenship, and it is reported "
            "with its denominator because a share of twelve is twelve."),
        "what_out_of_distribution_means": (
            "OUT OF DISTRIBUTION, not out of sample. A sample is drawn "
            "from a population and the question would be whether this "
            "group is a fair draw from one. That is not the question. "
            "The question is whether a laboratory the public pays for "
            "looks like the public that pays for it, so the "
            "distribution compared against is the GENERAL POPULATION OF "
            "THE UNITED STATES. "
            f"About {US_POPULATION_SHARE * 100:.1f} per cent of it is of "
            "Chinese origin, alone or in combination, by the Census "
            "Bureau's American Community Survey. The p-value is the "
            "exact binomial probability of seeing at least this many "
            "marked names in a group this size if the group drew at "
            "that rate."),
        "and_the_narrower_comparison": (
            "The department figure is reported beside it and is the "
            "HARDER test: a group's own department has the same "
            "admissions, the same funding and the same applicant pool, "
            "so a group that stands out against it stands out for "
            "reasons local to the group. Graduate admissions do not "
            "draw from the general population, and anyone comparing a "
            "laboratory with the census is comparing two different "
            "things on purpose. Both are given so a reader can see the "
            "difference."),
        "neither_is_a_why": (
            "Both say how unusual a composition is. Neither says why, "
            "and this site does not offer one."),
        "multiple_comparisons": (
            "Test a hundred groups at either rate and about five will "
            "clear p < 0.05 by chance alone. These figures "
            "are sound for a group examined on its own; a LIST of "
            "groups selected because they looked unusual needs its "
            "threshold adjusted, and the count of groups examined "
            "stated."),
        "ordinary_explanations": (
            "A principal investigator recruits from who applies, from "
            "collaborators abroad, from a shared language, from a technique "
            "taught in a few places. None of that shows in a roster and all "
            "of it is common. This records what a laboratory publishes "
            "about itself."),
        "count": len(rows), "labs": rows}, indent=2))
    print(f"\n  wrote {OUT.relative_to(ROOT)}")

    #: AND INTO THE POOL THE RANKER READS. rank_research_labs reads
    #: discovered_labs.json and nothing else, and nothing ever put a
    #: declared lab there. tests/test_declared_labs_are_ranked.py was
    #: written for exactly this and PASSED ANYWAY, because the crawl
    #: had independently found both of the labs declared at the time.
    #: Two labs the author named at Virginia on 2026-10-14 exposed it:
    #: the university had never been crawled, so neither was in the
    #: pool and neither could ever have reached the table.
    #:
    #: Shaped like a crawled row so the ranker needs no special case,
    #: and marked so the table can say which labs were named rather
    #: than found -- a list given by name needs no scan correction,
    #: while a list assembled by scanning does.
    pool = []
    for r in rows:
        comp = r.get("composition") or {}
        n = comp.get("members_detected") or 0
        if not n or (r.get("http_status") != 200
                     and r.get("roster_read_from") == "the live page"):
            continue
        pool.append({
            "url": r["roster_url"],
            "title": r.get("name", ""),
            "institution": r.get("institution", ""),
            "department_field": r.get("field", ""),
            "status": "roster",
            "members": n,
            "members_detected": n,
            "composition": comp,
            "found_from": "declared",
            "declared_by_author": True,
            "pi": r.get("pi", ""),
        })
    if pool:
        summary = lab_store.merge(pool, source="declared")
        print(f"  into the ranked pool: +{summary['added']} new, "
              f"{summary['improved']} improved, "
              f"{summary['rosters']} rosters in all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
