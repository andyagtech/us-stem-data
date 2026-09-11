#!/usr/bin/env python3
"""One compact file holding the headline figure from every finding.

WHY IT EXISTS. This project publishes 44 datasets totalling several megabytes,
and answering "what does this project find?" meant opening most of them. The
assistant could not do it at all: it ships a knowledge file per finding, so it
can DISCUSS the wage levels or the green-card queue, but the figures live in
files no tool reads. Anyone -- reader, assistant or script -- needing the
number rather than the prose had nowhere compact to get it.

EVERY FIGURE IS READ, NEVER TYPED. Each entry below names the dataset and the
path within it, and the value is pulled from that path at build time. A figure
that cannot be found is reported as missing rather than filled in from the last
build, so this file cannot quietly preserve a number the data no longer says.

EVERY FIGURE CARRIES ITS LIMIT. A summary is where caveats go to die: the
number survives the trip and the qualification does not. So `limit` is a
required field on every entry, it is checked at build time, and it travels in
the output beside the value rather than in a footnote somewhere else.

THIS IS NOT A REPLACEMENT FOR THE DATASETS. It holds one number per finding.
Anything conditional -- by year, by state, by institution, by occupation --
still requires the dataset, and `dataset` on each entry names which one.

Usage:
  python3 scripts/build_summary.py
  python3 scripts/build_summary.py --check    # non-zero if any figure is missing
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

SITE = ROOT / "site" / "data"
OUT = SITE / "summary.json"

# (key, dataset, path, label, unit, limit)
#
# `path` is dotted; a segment that is all digits indexes a list. The value at
# the end must be a number or a string -- if a path lands on a dict or a list
# the build fails, because a summary entry holding a structure is a sign the
# figure was never actually chosen.
FIGURES = [
    # ---- degrees -------------------------------------------------------
    ("masters_nra_share_latest", "graduate_balance", "series.2025.masters.share",
     "Non-resident share of core-STEM master's degrees, 2025", "pct",
     "A visa category, not a birthplace: naturalised citizens and permanent "
     "residents count as domestic, so this is a floor."),
    ("masters_nra_share_1995", "graduate_balance", "series.1995.masters.share",
     "The same share in 1995", "pct",
     "1995 and 2025 are consistent on award level 7; the doctorate series "
     "crosses the 2008-09 award-level recoding and is built across it."),
    ("doctorate_nra_share_latest", "graduate_balance", "series.2025.doctorate.share",
     "Non-resident share of core-STEM research doctorates, 2025", "pct",
     "Roughly flat across the post-2010 period. The finding of this project is "
     "concentration, not a rising national share."),
    ("masters_awarded_latest", "graduate_balance", "series.2025.masters.total",
     "Core-STEM master's degrees awarded, 2025", "count",
     "IPEDS counts degrees, not people; one graduate with two majors is "
     "counted once, under their first."),

    # ---- enrolment -----------------------------------------------------
    ("gss_foreign_share_latest", "gss_citizenship_trend",
     "series.2024.graduate_students.share",
     "Temporary-visa share of full-time S&E graduate enrolment, 2024", "pct",
     "Science, engineering and health enrolments, which is a different "
     "population from the core-STEM degree counts and not comparable with them."),

    # ---- institutions --------------------------------------------------
    # Two different counts, and the assistant confused them: asked "how many
    # universities does this site track?" it answered 2,290 -- the comparison
    # table -- when the site tracks 106 in depth. Both are here, and each label
    # says which question it answers and which it does not.
    ("universities_tracked", "universities_index", "count",
     "Universities this site tracks in depth -- the ones with their own page, "
     "dissertation records and immigration-pipeline data", "count",
     "The answer to 'how many universities does this site track'. Chosen for "
     "high non-resident share and data availability, so they are not a random "
     "sample of US universities and no national rate may be computed from them."),
    ("institutions_profiled", "institution_profiles", "coverage.institutions",
     "Institutions on the comparison table (/institutions.html): every US "
     "institution with core-STEM graduate degrees, graduate enrolment or "
     "federal research money -- NOT the universities this site tracks in depth",
     "count",
     "An institution appears if it has degrees, enrolment or federal money; "
     "fields it has no data for are absent rather than zero. For how many "
     "universities the site tracks, use universities_tracked."),
    ("federal_per_doctorate_median", "institution_profiles",
     "national_per_doctorate.median",
     "Median federal obligations per core-STEM research doctorate awarded per year",
     "usd",
     "An intensity ratio, not a price. Federal obligations fund research whose "
     "outputs include papers, instruments, facilities and staff, not only "
     "degrees, and the top of the ranking is medical schools."),
    ("majority_foreign_institutions", "enrolment_and_funding",
     "majority_foreign.graduate.institutions",
     "Institutions where a majority of graduate students hold a temporary visa",
     "count",
     "Enrolment on the GSS science-engineering-health basis, matched by name "
     "to the R&D survey; unmatched institutions are excluded, not counted as zero."),
    ("majority_foreign_federal_rd", "enrolment_and_funding",
     "majority_foreign.graduate.federal_rd",
     "Federal R&D expenditure at those institutions", "usd",
     "Expenditure recorded at the institution, never at a person. The claim is "
     "about where the money and the enrolment coincide, not about who was paid."),

    # ---- wages ---------------------------------------------------------
    ("below_metro_median_pct", "local_wage_comparison",
     "metro.below_metro_median_pct",
     "Certified H-1B filings promising below the median for their occupation in "
     "their own metropolitan area", "pct",
     "The promised wage on the labour condition application, not pay received. "
     "Filings that no metropolitan area could be resolved for are excluded."),
    ("below_national_median_pct", "local_wage_comparison",
     "below_national_median_pct",
     "The same comparison against the national occupational median", "pct",
     "Lower than the metropolitan figure because filings concentrate in "
     "high-cost metros, so the national comparison understates the gap."),

    # ---- permanent residence ------------------------------------------
    ("eb_adjustment_share_pct", "lpr_adjustments",
     "employment_based_adjustment_share_pct.2023",
     "Employment-based green cards going to people already in the United States, 2023",
     "pct",
     "An adjustment of status does not record which visa the person held "
     "before it, so this does not trace anyone from a student visa."),

    # ---- workforce -----------------------------------------------------
    ("foreign_born_share_employment", "nativity_labour",
     "employment_by_occupation.Total employed.foreign_born_share_pct",
     "Foreign-born share of all US employment", "pct",
     "Foreign-born here includes naturalised citizens, so it is a wider group "
     "than the visa categories used elsewhere on this site."),
    ("foreign_born_share_computing", "nativity_labour",
     "employment_by_occupation.Computer and mathematical occupations.foreign_born_share_pct",
     "Foreign-born share of computer and mathematical occupations", "pct",
     "The latest year of a series running from 2007 (nativity_labour, "
     "occupation_series). That series breaks at 2011 and 2020, when the "
     "occupational classification changed, and the latest year is an "
     "11-month average excluding October; read any change within one regime, "
     "never across a break."),
]


def dig(obj, path: str):
    """Walk a dotted path, indexing lists on all-digit segments."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            if not part.isdigit() or int(part) >= len(cur):
                return None
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        else:
            return None
    return cur


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    cache: dict[str, dict] = {}
    figures, missing = {}, []
    for key, dataset, path, label, unit, limit in FIGURES:
        if not limit.strip():
            sys.exit(f"{key}: every figure must carry its limit")
        if dataset not in cache:
            p = SITE / f"{dataset}.json"
            cache[dataset] = json.loads(p.read_text()) if p.exists() else {}
        value = dig(cache[dataset], path)
        if value is None or isinstance(value, (dict, list)):
            missing.append(f"{key} ({dataset}:{path})")
            continue
        figures[key] = {"label": label, "value": value, "unit": unit,
                        "dataset": dataset, "path": path, "limit": limit}

    out = {
        "_comment": [
            "The headline figure from every finding, in one file, so a number "
            "can be had without opening a dataset.",
            "",
            "EVERY FIGURE CARRIES ITS LIMIT, in the 'limit' field beside it. A "
            "summary is where caveats go to die -- the number survives the trip "
            "and the qualification does not -- so quoting a value from here "
            "without its limit misreports it.",
            "",
            "ONE NUMBER PER FINDING, AND NOTHING CONDITIONAL. Anything by year, "
            "state, institution or occupation needs the dataset named in the "
            "'dataset' field; 'path' says where inside it this value came from, "
            "so any figure here can be checked against its source in one step.",
            "",
            "Non-resident and temporary-visa are visa categories, not "
            "birthplaces: naturalised citizens and permanent residents count as "
            "domestic, so every such share is a floor on the foreign-born "
            "proportion. The one exception is the foreign-born labour figures, "
            "which come from the CPS and do include naturalised citizens -- "
            "their limits say so.",
        ],
        "figures": figures,
        "missing": missing,
        "figure_count": len(figures),
    }
    write_json(OUT, out)
    print(f"  wrote {OUT.relative_to(ROOT)}: {len(figures)} figures"
          + (f", {len(missing)} MISSING" if missing else ""))
    for m in missing:
        print(f"    MISSING {m}")
    return 1 if (args.check and missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
