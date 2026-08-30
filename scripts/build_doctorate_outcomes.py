#!/usr/bin/env python3
"""What US-trained doctorate holders earn and where they work, by citizenship.

Stay rates say people remain in the country. They say nothing about what
those people then do, and the project had no answer to that: retention was
half-covered, evidenced by residence alone.

The Survey of Doctorate Recipients closes it. It is a longitudinal sample of
people holding a US research doctorate, and its public-use file carries
citizenship, employment sector, occupation and salary together -- the only
federal source that does.

WEIGHTS ARE NOT OPTIONAL. The SDR is a stratified sample, not a census, and
WTSURVY is the population weight. Counting rows instead of weighting them
describes the sample rather than the population, and the two differ by
design: the survey deliberately over-samples small groups.

WHAT IT DOES NOT SHOW. A salary gap here is not a like-for-like comparison:
citizens and visa holders differ in field, years since doctorate and sector,
and none of that is controlled for. Read it as what the two populations earn,
not as what the same person would be paid under two statuses.

Usage:
  python3 scripts/build_doctorate_outcomes.py
"""
from __future__ import annotations

import csv
import io
import json
import statistics
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "nsf_workforce" / "doctorate_recipients_2023.zip"
MEMBER = "psd23Public/epsd23.csv"
OUT = ROOT / "site" / "data" / "doctorate_outcomes.json"

SECTOR = {"1": "Educational institution", "2": "Government",
          "3": "Business or industry"}

# Citizenship, on the same code set at two points in time. CTZN_DRF is the
# status held AT THE DOCTORATE, from the Doctorate Records File; CTZN is the
# status now.
#
# Splitting on the current status was the first attempt and it was wrong.
# Anyone who arrived on a visa and later naturalised counts as a citizen
# there, so "non-citizen" in the older cohorts is a residue -- the people who
# never naturalised -- and comparing their pay to everyone else's produced
# gaps of $80,000 that described selection, not earnings. The question the
# project is actually asking is what became of people this country trained
# while they were foreign nationals, which is the status at the degree.
CITIZENSHIP = {"1": "US citizen at doctorate (native)",
               "2": "US citizen at doctorate (naturalised)",
               "3": "Permanent resident at doctorate",
               "4": "Temporary visa at doctorate",
               "5": "Non-US, living abroad"}
TRAINED_FOREIGN = "Temporary visa at doctorate"
LFS = {"1": "Employed", "2": "Unemployed", "3": "Not in labour force"}

# Doctorate cohort. This is the control that matters: the headline gap is
# largely age. Non-citizens holding US doctorates skew recent, and a recent
# doctorate earns less than one twenty years old whatever passport it holds.
# Comparing within a cohort is the only way to see whether anything else is
# going on.
COHORT = {"1975": "1970-79", "1980": "1980-84", "1985": "1985-89",
          "1990": "1990-94", "1995": "1995-99", "2000": "2000-04",
          "2005": "2005-09", "2010": "2010-14", "2015": "2015 or later"}


def rows():
    with zipfile.ZipFile(SRC) as z:
        with z.open(MEMBER) as fh:
            yield from csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig",
                                                       errors="replace"))


def wmedian(pairs):
    """Weighted median. sorted by value, walk to half the weight."""
    pairs = sorted(pairs)
    total = sum(w for _v, w in pairs)
    if not total:
        return None
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= total / 2:
            return int(v)
    return int(pairs[-1][0])


def main() -> int:
    if not SRC.exists():
        print(f"  {SRC.relative_to(ROOT)} not found")
        return 1

    pop = defaultdict(float)                     # citizenship -> weighted n
    sal = defaultdict(list)                      # citizenship -> [(salary, w)]
    sec = defaultdict(lambda: defaultdict(float))
    lab = defaultdict(lambda: defaultdict(float))
    sal_by_sector = defaultdict(list)
    sal_by_cohort = defaultdict(list)
    became = defaultdict(float)
    cohort_mix = defaultdict(lambda: defaultdict(float))
    n_rows = skipped_us = 0

    for r in rows():
        # US-earned doctorates only: the question is what happens to people
        # this country trained, not to every doctorate holder living here.
        if (r.get("MRDGRUS") or "").strip() != "Y":
            skipped_us += 1
            continue
        n_rows += 1
        try:
            w = float(r.get("WTSURVY") or 0)
        except ValueError:
            continue
        if w <= 0:
            continue
        cit = CITIZENSHIP.get((r.get("CTZN_DRF") or "").strip())
        if not cit:
            continue
        pop[cit] += w

        lf = (r.get("LFSTAT") or "").strip()
        if lf in LFS:
            lab[cit][LFS[lf]] += w

        s = (r.get("EMSECSM") or "").strip()
        if s in SECTOR:
            sec[cit][SECTOR[s]] += w

        # Where they ended up: current status, for the visa group only.
        if cit == TRAINED_FOREIGN:
            now = CITIZENSHIP.get((r.get("CTZN") or "").strip())
            if now:
                became[now] += w

        coh = COHORT.get((r.get("SDR5YRP") or "").strip())
        if coh:
            cohort_mix[cit][coh] += w

        raw = (r.get("SALARYP") or "").strip()
        if raw.isdigit() and lf == "1":
            v = int(raw)
            # 0 is a logical skip for the not-employed, and the top code
            # would drag a mean; the median is unaffected either way.
            if v > 0:
                sal[cit].append((v, w))
                if s in SECTOR:
                    sal_by_sector[(cit, SECTOR[s])].append((v, w))
                if coh:
                    sal_by_cohort[(cit, coh)].append((v, w))

    if not pop:
        print("  no rows matched; check MRDGRUS / WTSURVY")
        return 1

    def share(d):
        t = sum(d.values())
        return {k: round(100 * v / t, 1) for k, v in sorted(d.items())} if t else {}

    doc = {
        "_comment": ("US-trained research doctorate holders: employment and "
                     "earnings by citizenship, from the NSF Survey of Doctorate "
                     "Recipients 2023 public-use file. WEIGHTED with WTSURVY -- "
                     "the SDR is a stratified sample and unweighted counts "
                     "describe the sample, not the population. A salary "
                     "difference here is NOT like-for-like: field, years since "
                     "doctorate and sector are uncontrolled. Groups are by "
                     "status AT THE DOCTORATE (CTZN_DRF), not current status: "
                     "splitting on current status makes everyone who "
                     "naturalised a citizen, leaving the non-citizen group in "
                     "older cohorts a residue of those who never did."),
        "source": "NSF NCSES, Survey of Doctorate Recipients 2023, public-use file",
        "restricted_to": "doctorate earned in the United States (MRDGRUS = Y)",
        "sample_rows": n_rows,
        "rows_excluded_foreign_doctorate": skipped_us,
        "population_weighted": {k: int(v) for k, v in sorted(pop.items())},
        "median_salary": {k: wmedian(v) for k, v in sorted(sal.items())},
        "salaried_sample": {k: len(v) for k, v in sorted(sal.items())},
        "employment_sector_pct": {k: share(v) for k, v in sorted(sec.items())},
        "labour_force_pct": {k: share(v) for k, v in sorted(lab.items())},
        "median_salary_by_sector": {
            f"{c} — {s}": wmedian(v) for (c, s), v in sorted(sal_by_sector.items())},
        "cohort_mix_pct": {k: share(v) for k, v in sorted(cohort_mix.items())},
        "trained_on_a_visa_are_now_pct": share(became),
        "median_salary_by_cohort": {
            f"{c} — {y}": wmedian(v) for (c, y), v in sorted(sal_by_cohort.items())
            if len(v) >= 50},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {n_rows:,} US-earned doctorate records "
          f"({skipped_us:,} foreign doctorates excluded)")
    for k in sorted(pop):
        print(f"  {k:16} weighted {int(pop[k]):>9,}   median salary "
              f"${doc['median_salary'].get(k) or 0:>7,}")
    print("  employment sector:")
    for k, v in doc["employment_sector_pct"].items():
        print(f"    {k:16} " + "  ".join(f"{n} {p}%" for n, p in v.items()))
    if became:
        print("  people on a temporary visa at their doctorate are now:")
        for k, v in sorted(doc["trained_on_a_visa_are_now_pct"].items(),
                           key=lambda kv: -kv[1]):
            print(f"    {v:>5.1f}%  {k}")
    print("  median salary within doctorate cohort:")
    for y in COHORT.values():
        a = doc["median_salary_by_cohort"].get(f"US citizen at doctorate (native) — {y}")
        b = doc["median_salary_by_cohort"].get(f"{TRAINED_FOREIGN} — {y}")
        if a and b:
            print(f"    {y:14} native ${a:>7,}   visa-at-degree ${b:>7,}   "
                  f"gap ${a-b:>+7,}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
