#!/usr/bin/env python3
"""Do people working on a temporary visa work longer, and feel less secure?

The leverage argument is usually made structurally: an employer files the
petition, status depends on the job, so the worker has less room to refuse.
That is a claim about the law and it is easy to establish. Whether it shows
up in what people actually work and report is a separate, testable question,
and this asks it.

CURRENT STATUS, NOT STATUS AT THE DOCTORATE. Every other outcome in this
project is grouped by citizenship at the degree (CTZN_DRF), because the
question there is what became of people trained here as foreign nationals.
This one is grouped by CTZN, status NOW, because leverage is a property of
the status a person currently holds -- someone who naturalised twenty years
ago is not subject to it.

WITHIN COHORT. Visa holders are much younger than citizens in this sample,
and hours and seniority both move with career stage, so a pooled comparison
would mostly measure age. Figures are reported by graduation cohort and the
recent cohorts are the ones to read.

Usage:
  python3 scripts/build_working_conditions.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "nsf_workforce" / "doctorate_recipients_2023.zip"
INNER = "psd23Public/epsd23.csv"
OUT = ROOT / "site" / "data" / "working_conditions.json"

# CTZN is status now. Codes are the same set as CTZN_DRF.
CITIZEN = {"1": "US citizen (native)", "2": "US citizen (naturalised)",
           "3": "Permanent resident", "4": "Temporary visa"}
LONG_HOURS = "4"                     # HRSWKP 4 = greater than 40 hours
HOURS = {"1": "20 or less", "2": "21-35", "3": "36-40", "4": "More than 40"}
# Satisfaction runs 1 very satisfied .. 4 very dissatisfied.
DISSATISFIED = {"3", "4"}
SAT = {"SATSEC": "job security", "SATSAL": "salary",
       "SATADV": "advancement opportunities", "JOBSATIS": "the job overall"}
COHORT = {"1975": "1970-79", "1980": "1980-84", "1985": "1985-89",
          "1990": "1990-94", "1995": "1995-99", "2000": "2000-04",
          "2005": "2005-09", "2010": "2010-14", "2015": "2015 or later"}
RECENT = ("2010-14", "2015 or later")


def pct(part: float, whole: float) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def main() -> int:
    if not SRC.exists():
        print(f"  missing {SRC.relative_to(ROOT)}")
        return 1

    hours = defaultdict(lambda: defaultdict(float))
    long_by_cohort = defaultdict(lambda: [0.0, 0.0])
    sat = {k: defaultdict(lambda: [0.0, 0.0]) for k in SAT}
    n_rows = 0

    with zipfile.ZipFile(SRC) as z, z.open(INNER) as fh:
        for r in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig",
                                                 errors="replace")):
            # US-earned doctorates, employed, and living in the US: a person
            # abroad is not subject to any of this.
            if (r.get("MRDGRUS") or "").strip() != "Y":
                continue
            if (r.get("LFSTAT") or "").strip() != "1":
                continue
            cit = CITIZEN.get((r.get("CTZN") or "").strip())
            if not cit:
                continue
            try:
                w = float(r.get("WTSURVY") or 0)
            except ValueError:
                continue
            if w <= 0:
                continue
            n_rows += 1
            coh = COHORT.get((r.get("SDR5YRP") or "").strip())

            h = (r.get("HRSWKP") or "").strip()
            if h in HOURS:
                hours[cit][HOURS[h]] += w
                if coh:
                    b = long_by_cohort[f"{cit} — {coh}"]
                    b[0] += w
                    b[1] += w if h == LONG_HOURS else 0.0

            for var in SAT:
                v = (r.get(var) or "").strip()
                if v in {"1", "2", "3", "4"}:
                    s = sat[var][cit]
                    s[0] += w
                    s[1] += w if v in DISSATISFIED else 0.0

    if n_rows < 1000:
        print(f"  only {n_rows} usable rows")
        return 1

    groups = [c for c in CITIZEN.values() if hours.get(c)]
    hours_pct = {c: {k: pct(v, sum(hours[c].values()))
                     for k, v in sorted(hours[c].items())} for c in groups}
    long_pct = {c: pct(hours[c].get("More than 40", 0), sum(hours[c].values()))
                for c in groups}
    long_cohort = {k: pct(v[1], v[0]) for k, v in sorted(long_by_cohort.items())
                   if v[0] > 0}
    dissat = {SAT[var]: {c: pct(s[1], s[0]) for c, s in d.items() if s[0]}
              for var, d in sat.items()}

    # The comparison the argument rests on, held to recent cohorts.
    recent = {}
    for coh in RECENT:
        vis = long_cohort.get(f"Temporary visa — {coh}")
        nat = long_cohort.get(f"US citizen (native) — {coh}")
        if vis is not None and nat is not None:
            recent[coh] = {"temporary_visa": vis, "us_citizen_native": nat,
                           "gap_pts": round(vis - nat, 1)}

    doc = {
        "_comment": (
            "Hours worked and reported satisfaction, by citizenship status "
            "NOW (CTZN), for employed holders of a US-earned doctorate living "
            "in the United States. Grouped by CURRENT status, unlike the rest "
            "of this project, because leverage attaches to the status a "
            "person holds now. Visa holders are much younger than citizens "
            "here, so READ THE WITHIN-COHORT FIGURES: a pooled comparison "
            "largely measures career stage. SELF-REPORTED, and hours are a "
            "BANDED category ('more than 40'), not a count -- this shows "
            "whether long hours are more common, not how many hours anyone "
            "works. It cannot show WHY, and nothing here identifies visa type "
            "or employer."),
        "source": "NSF NCSES, Survey of Doctorate Recipients 2023 public-use file",
        "restricted_to": "US-earned doctorate, employed, living in the US",
        "sample_rows": n_rows,
        "hours_distribution_pct": hours_pct,
        "long_hours_pct": long_pct,
        "long_hours_by_cohort_pct": long_cohort,
        "long_hours_recent_cohorts": recent,
        "dissatisfied_pct": dissat,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {n_rows:,} weighted respondents")
    print(f"  {'group':28}{'>40 hrs/wk':>12}")
    for c in groups:
        print(f"  {c:28}{long_pct[c]:>11.1f}%")
    print(f"\n  within recent cohorts, share working more than 40 hours:")
    for coh, v in recent.items():
        print(f"   {coh:16} visa {v['temporary_visa']:>5.1f}%   "
              f"citizen {v['us_citizen_native']:>5.1f}%   "
              f"gap {v['gap_pts']:+.1f}")
    print(f"\n  {'dissatisfied with':26}" + "".join(f"{c[:14]:>16}" for c in groups))
    for label, d in dissat.items():
        print(f"  {label:26}" + "".join(f"{d.get(c, 0):>15.1f}%" for c in groups))
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
