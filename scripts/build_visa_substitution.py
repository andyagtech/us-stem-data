#!/usr/bin/env python3
"""Visa programmes side by side, with the policy changes marked, 2007-2024.

WHAT IT ASSEMBLES. Series that already exist separately on this site, put on
one timeline so that movement between programmes can be seen:
  * State Department nonimmigrant visa ISSUANCES by class (fiscal year):
    F-1, J-1, H-1B, L-1, O-1, TN, E-3.
  * DHS SEVP work authorisations on student status (CALENDAR year): OPT,
    STEM OPT extension, CPT. These need no new visa -- a student already here
    works on the F-1 they hold -- which is why they can keep rising while visa
    issuance falls.
  * USCIS initial H-1B petition denial rate (fiscal year), the clearest record
    of how hard H-1B adjudication was in a given year.
  * Dated federal actions that restricted or expanded these programmes, each
    verified against its primary source (data/policy/visa_policy_events.json).

WHAT IT DOES NOT CLAIM. It shows timing, not cause. Three things confound a
simple reading, and each is carried into the output so the page can say so:
fiscal and calendar years are three months apart; FY2020-21 issuance fell for
every class because consulates closed during the pandemic, not only because of
the June 2020 proclamation; and TN is open only to Canadian and Mexican
citizens, so its movement is not a route for other graduates.

Usage:
  python3 scripts/build_visa_substitution.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

DATA = ROOT / "site" / "data"
VISAS = DATA / "visa_issuances.json"
OPT = DATA / "opt_national.json"
H1B = DATA / "h1b_approvals.json"
EVENTS = ROOT / "data" / "policy" / "visa_policy_events.json"
OUT = DATA / "visa_substitution.json"

YEARS = list(range(2007, 2025))
VISA_CLASSES = {"F1": "F-1 student", "J1": "J-1 exchange", "H1B": "H-1B specialty worker",
                "L1": "L-1 intracompany transfer", "O1": "O-1 extraordinary ability",
                "TN": "TN (Canada & Mexico only)", "E3": "E-3 (Australia only)"}
STUDENT_WORK = {"opt": "OPT", "stem_opt": "STEM OPT extension", "cpt": "CPT"}


def main() -> int:
    for p in (VISAS, OPT, H1B):
        if not p.exists():
            print(f"  missing {p.relative_to(ROOT)}")
            return 1
    visas = json.loads(VISAS.read_text())["totals"]
    opt = json.loads(OPT.read_text())["series"]
    h1b = json.loads(H1B.read_text())
    incomplete = set(map(str, h1b.get("incomplete_years", [])))

    issuance = {c: {str(y): (visas.get(str(y)) or {}).get(c) for y in YEARS} for c in VISA_CLASSES}
    student_work = {k: {str(y): (opt.get(str(y)) or {}).get(k) for y in YEARS} for k in STUDENT_WORK}
    denial = {str(y): (None if str(y) in incomplete else
                       (h1b["series"].get(str(y)) or {}).get("initial_denial_rate_pct"))
              for y in YEARS}

    def change(series: dict, a: int, b: int):
        va, vb = series.get(str(a)), series.get(str(b))
        return round(100 * (vb - va) / va, 1) if va and vb else None

    # The co-movements the page describes, computed rather than typed.
    windows = {
        "h1b_tightening_fy2015_2019": {
            "h1b_initial_denial_rate_pct": {"2015": denial["2015"], "2018": denial["2018"], "2019": denial["2019"]},
            "f1_issuance_change_pct": change(issuance["F1"], 2015, 2019),
            "opt_change_pct": change(student_work["opt"], 2015, 2019),
            "stem_opt_change_pct": change(student_work["stem_opt"], 2015, 2019),
            "cpt_2015": student_work["cpt"]["2015"], "cpt_2018": student_work["cpt"]["2018"],
            "o1_change_pct": change(issuance["O1"], 2015, 2019)},
        "entry_suspension_fy2019_2021": {
            "h1b_issuance_change_pct": change(issuance["H1B"], 2019, 2021),
            "l1_issuance_change_pct": change(issuance["L1"], 2019, 2021),
            "opt_plus_stem_opt_2019": (student_work["opt"]["2019"] or 0) + (student_work["stem_opt"]["2019"] or 0),
            "opt_plus_stem_opt_2021": (student_work["opt"]["2021"] or 0) + (student_work["stem_opt"]["2021"] or 0)},
        "fy2023_2024": {
            "h1b_issuance_change_pct": change(issuance["H1B"], 2023, 2024),
            "opt_change_pct": change(student_work["opt"], 2023, 2024),
            "stem_opt_change_pct": change(student_work["stem_opt"], 2023, 2024),
            "o1_2024": issuance["O1"]["2024"],
            "o1_record": issuance["O1"]["2024"] == max(v for v in issuance["O1"].values() if v)},
    }
    w = windows["entry_suspension_fy2019_2021"]
    w["opt_plus_stem_opt_change_pct"] = round(
        100 * (w["opt_plus_stem_opt_2021"] - w["opt_plus_stem_opt_2019"]) / w["opt_plus_stem_opt_2019"], 1)

    # Twenty-two verified actions fall inside the charted years -- too many to
    # mark without burying the lines. These eight are the turning points the
    # series actually bend around; the rest stay in the list under the chart.
    MARKERS = {"stem_opt_17_month_2008", "stem_opt_24_month_2016",
               "eo_13788_buy_american_hire_american",
               "uscis_pm_602_0157_third_party_worksites_2018",
               "proclamation_10052_nonimmigrant_entry_suspension", "proclamation_10052_expiry",
               "stem_designated_degree_list_2022",
               "h1b_registration_beneficiary_centric_2024"}
    events = json.loads(EVENTS.read_text()) if EVENTS.exists() else []
    last = max(YEARS)
    for e in events:
        fy = int(e.get("fiscal_year") or 0)
        e["charted"] = fy <= last
        e["chart_marker"] = e.get("id") in MARKERS and fy <= last
    missing = MARKERS - {e.get("id") for e in events}
    if missing:
        print(f"  WARNING: marker ids not in the events file: {', '.join(sorted(missing))}")
    out = {
        "_comment": __doc__.split("Usage:")[0].strip(),
        "sources": {"issuance": "US Department of State, Nonimmigrant Visa Detail Tables (fiscal year)",
                    "student_work": "DHS SEVP, OPT / STEM OPT / CPT authorisations (calendar year)",
                    "h1b_denials": "USCIS H-1B Employer Data Hub, initial petitions (fiscal year)",
                    "events": "Federal Register, White House, USCIS -- one primary source per event"},
        "caveats": ["Visa issuance and H-1B decisions are fiscal years (ending 30 September); student "
                    "work authorisations are calendar years.",
                    "FY2020-21 issuance fell in every class while consulates were closed for the pandemic.",
                    "TN is open only to Canadian and Mexican citizens; E-3 only to Australians.",
                    "An issuance is not a person: a visa is re-stamped for travel.",
                    "OPT, STEM OPT and CPT need no new visa; they are work on an F-1 already held.",
                    f"H-1B denial rates for {', '.join(sorted(incomplete)) or 'no year'} are incomplete and omitted."],
        "years": YEARS,
        "labels": {**VISA_CLASSES, **STUDENT_WORK, "h1b_initial_denial_rate_pct": "H-1B initial denial rate"},
        "issuance": issuance,
        "student_work": student_work,
        "h1b_initial_denial_rate_pct": denial,
        "windows": windows,
        "events": events,
    }
    write_json(OUT, out, indent=1)
    print(f"  wrote {OUT.relative_to(ROOT)}: {len(VISA_CLASSES)} visa classes, "
          f"{len(STUDENT_WORK)} student work series, {len(events)} policy events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
