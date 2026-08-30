#!/usr/bin/env python3
"""The payroll-tax differential on OPT employment, stated as a rate.

Under IRC 3121(b)(19), students in F-1 or J-1 status are exempt from Social
Security and Medicare tax on employment authorised for their visa, and IRS
guidance lists practical training explicitly. The exemption therefore covers
OPT and the 24-month STEM extension.

The consequence is arithmetic, not interpretation: an employer hiring an OPT
graduate pays no employer-side FICA on those wages, while the same job filled
by a U.S. worker carries 7.65% (6.2% Social Security + 1.45% Medicare). The
worker's own 7.65% is likewise not withheld, and no Social Security credits
accrue.

WHAT THIS SCRIPT WILL NOT DO. It will not publish a national total. Sizing
one requires OPT wages, and no agency publishes them -- not SEVP, which counts
authorisations, nor DOL, whose wage data covers H-1B rather than OPT. Instead
it computes the differential per $100,000 of payroll, and applies a scenario
grid over the actual authorisation counts, every wage figure labelled as an
assumption rather than a measurement.

The LCA medians in this project are shown as context for choosing a scenario.
They are H-1B wages at universities, a different population from OPT
graduates in industry, and are not used as a substitute for OPT wages.

Usage:
  python3 scripts/build_fica_exposure.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPT_NATIONAL = ROOT / "data" / "h1b" / "opt_national.json"
LCA = ROOT / "data" / "h1b" / "lca_by_university.json"
OUT = ROOT / "data" / "h1b" / "fica_exposure.json"
# The report's payroll-tax page reads this, and so does the site, so it is
# published alongside the working copy rather than copied by hand.
PUBLISHED = ROOT / "site" / "data" / "fica_exposure.json"

SS_RATE, MEDICARE_RATE = 0.062, 0.0145
EMPLOYER_RATE = SS_RATE + MEDICARE_RATE          # 7.65%
COMBINED_RATE = EMPLOYER_RATE * 2                # employer + employee

# Wage points for the scenario grid. Chosen to bracket plausible early-career
# STEM salaries; each is an assumption, and the output says so.
SCENARIOS = (60_000, 80_000, 100_000)


def main() -> int:
    if not OPT_NATIONAL.exists():
        print(f"  {OPT_NATIONAL.relative_to(ROOT)} not found; run parse_opt_reports first")
        return 1
    series = json.loads(OPT_NATIONAL.read_text())["series"]
    years = sorted(int(y) for y in series)
    latest = str(years[-1])
    rec = series[latest]

    lca_context = None
    if LCA.exists():
        med = [v["wage_median"] for v in json.loads(LCA.read_text()).values()
               if v.get("wage_median")]
        if med:
            lca_context = {
                "median_of_university_medians": round(statistics.median(med)),
                "n_universities": len(med),
                "note": ("H-1B wages at universities, shown only to inform the "
                         "choice of scenario. Not OPT wages, and not used as a "
                         "substitute for them."),
            }

    grid = []
    for wage in SCENARIOS:
        for key, label in (("opt", "OPT"), ("stem_opt", "STEM OPT")):
            n = rec.get(key)
            if not n:
                continue
            grid.append({
                "population": label,
                "authorisations": n,
                "assumed_annual_wage": wage,
                "employer_side_forgone": round(n * wage * EMPLOYER_RATE),
                "combined_forgone": round(n * wage * COMBINED_RATE),
            })

    doc = {
        "_comment": ("Payroll-tax differential on OPT employment. The RATES are "
                     "statutory and the AUTHORISATION COUNTS are published; the "
                     "WAGES are assumptions and every derived total is a "
                     "scenario, not a measurement. No agency publishes OPT "
                     "wages, which is why no single national figure appears "
                     "here."),
        "statute": "IRC 3121(b)(19); IRS guidance lists practical training as exempt",
        "rates": {"social_security": SS_RATE, "medicare": MEDICARE_RATE,
                  "employer_side": EMPLOYER_RATE, "employer_plus_employee": COMBINED_RATE},
        "per_100k_payroll": {"employer_side": round(100_000 * EMPLOYER_RATE),
                             "employer_plus_employee": round(100_000 * COMBINED_RATE)},
        "year": int(latest),
        "authorisations": {"opt": rec.get("opt"), "stem_opt": rec.get("stem_opt"),
                           "total_records_with_opt": rec.get("total_sevis_with_opt")},
        "scenarios": grid,
        "lca_wage_context": lca_context,
        "caveats": [
            "The exemption ends when the holder becomes a resident alien for tax "
            "purposes, generally after five calendar years in F or J status.",
            "Exempt wages accrue no Social Security credits for the worker.",
            "Authorisations are not full-time-equivalent years of employment, so "
            "applying an annual wage to a count overstates a single year.",
        ],
    }
    text = json.dumps(doc, indent=1) + "\n"
    for path in (OUT, PUBLISHED):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    print(f"  statutory employer-side rate: {EMPLOYER_RATE:.2%}  "
          f"(${doc['per_100k_payroll']['employer_side']:,} per $100k of payroll)")
    print(f"  FY{latest}: OPT {rec.get('opt'):,}, STEM OPT {rec.get('stem_opt'):,}")
    for g in grid:
        if g["population"] == "OPT":
            print(f"   scenario @ ${g['assumed_annual_wage']:,}/yr: employer-side "
                  f"${g['employer_side_forgone']:,} across {g['authorisations']:,} OPT")
    if lca_context:
        print(f"  context: median university LCA wage "
              f"${lca_context['median_of_university_medians']:,} (H-1B, not OPT)")
    for path in (OUT, PUBLISHED):
        print(f"  wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
