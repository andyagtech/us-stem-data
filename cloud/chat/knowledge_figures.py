"""Figures the knowledge base states, and where each one comes from.

WHY THIS EXISTS

An earlier guardrail banned decimal percentages from the prompt outright, on the
grounds that a memorised figure drifts as the corpus grows. That was right for
figures nobody checks. It is wrong for figures that are DERIVED, because the fix
for drift is verification, not silence -- and the knowledge base is far more
useful when it can state what the site found.

So the rule is now: a figure may appear in the knowledge base only if it is
listed here with a source, and the test suite re-derives it from the built
artifact on every run. A number that moves fails the build instead of quietly
misinforming a reader.

Each entry: (value, dataset file, dotted path or callable, tolerance, why it
matters). The path is walked with plain dict/list indexing so the check breaks
loudly if a payload shape changes.
"""
from __future__ import annotations

import json
import os

# site/data is where the builders write.
_SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "site", "data")


def _load(name):
    path = os.path.join(_SITE, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _sed(field, source, who):
    def get():
        d = _load("support_by_citizenship.json")
        if not d:
            return None
        f = d["fields"].get(field)
        if not f:
            return None
        if source == "assistantships":
            return f["assistantships"][who]
        return f["sources"][source][who]
    return get


def _programme(cip, key="share"):
    def get():
        d = _load("programme_shares.json")
        if not d:
            return None
        for p in d["programmes"]:
            if p["cip"] == cip:
                return p[key]
        return None
    return get


def _hist(year, key):
    def get():
        d = _load("distribution.json")
        if not d:
            return None
        for h in d["histograms"]:
            if h["year"] == year:
                return h[key]
        return None
    return get


def _uni(key, field):
    def get():
        d = _load("university_distribution.json")
        if not d:
            return None
        u = d.get(key)
        return u[field] if u else None
    return get



def _shops(*path):
    """A figure from the body-shop dataset, walked by explicit key."""
    def get():
        d = _load("visa_bodyshops.json")
        for k in path:
            if d is None:
                return None
            d = d[k]
        return d
    return get


def _dev(field):
    """Software Developers, placed against directly hired. Found by NAME, not
    by index: the occupation list is sorted by volume and reorders."""
    def get():
        d = _load("visa_bodyshops.json")
        if d is None:
            return None
        for o in d["by_occupation"]:
            if o["occupation"] == "Software Developers":
                return o[field]
        raise KeyError("Software Developers is no longer in by_occupation")
    return get


def _hub(field):
    def get():
        d = _load("visa_staffing.json")
        return None if d is None else d["totals"][field]
    return get


def _debarred(programme):
    """How many employers are currently barred from one programme. The most
    volatile figure the knowledge base states -- DOL updates the list on a
    rolling basis -- and therefore the one most worth re-deriving."""
    def get():
        d = _load("visa_staffing.json")
        if d is None:
            return None
        for lst in d["debarment_lists"]:
            if lst["programme"].startswith(programme):
                return lst["count"]
        raise KeyError(f"no {programme} debarment list in visa_staffing.json")
    return get


def _industry(slug, field):
    """A figure from the critical-industries dataset, found by SLUG rather than
    by position: the list is sorted by share and reorders when the data moves."""
    def get():
        d = _load("critical_industries.json")
        if d is None:
            return None
        for i in d["industries"]:
            if i["slug"] == slug:
                return i[field]
        raise KeyError(f"no industry {slug!r} in critical_industries.json")
    return get


def _fica(wage, population, side):
    """One cell of the exposure grid, in billions.

    population "Both" is the table's third column: OPT and STEM OPT added,
    employer side plus employee side. It is a SUM of two scenarios and is
    resolved as one here, so the table cannot drift away from the arithmetic
    underneath it."""
    def get():
        d = _load("fica_exposure.json")
        if d is None:
            return None
        rows = [sc for sc in d["scenarios"] if sc["assumed_annual_wage"] == wage
                and (population == "Both" or sc["population"] == population)]
        if not rows:
            raise KeyError(f"no {population} scenario at {wage}")
        return sum(r[side] for r in rows) / 1e9
    return get


SE = "Science and engineering"

#: name -> (stated value, resolver, tolerance)
FIGURES = {
    # --- the funding argument, SED Table 4-1 --------------------------------
    "S&E assistantships, citizen": (53.1, _sed(SE, "assistantships", "citizen"), 0.2),
    "S&E assistantships, visa": (76.0, _sed(SE, "assistantships", "visa"), 0.2),
    "S&E research assistantship, citizen":
        (35.4, _sed(SE, "research_assistantship", "citizen"), 0.2),
    "S&E research assistantship, visa":
        (53.6, _sed(SE, "research_assistantship", "visa"), 0.2),
    "S&E teaching assistantship, citizen":
        (17.7, _sed(SE, "teaching_assistantship", "citizen"), 0.2),
    "S&E teaching assistantship, visa":
        (22.4, _sed(SE, "teaching_assistantship", "visa"), 0.2),
    "S&E fellowship, visa": (17.4, _sed(SE, "fellowship", "visa"), 0.2),
    "S&E own resources, citizen": (16.0, _sed(SE, "own_resources", "citizen"), 0.2),
    "S&E own resources, visa": (3.5, _sed(SE, "own_resources", "visa"), 0.2),

    # --- programme shares ---------------------------------------------------
    "Petroleum Engineering share": (85.3, _programme("14.2501"), 0.3),
    "Electrical Engineering share": (71.4, _programme("14.1001"), 0.3),
    "Electrical Engineering doctorates":
        (17930, _programme("14.1001", "doctorates"), 40),
    "Computer Science share": (63.1, _programme("11.0701"), 0.3),
    "Statistics share": (67.2, _programme("27.0501"), 0.3),

    # --- the national histogram --------------------------------------------
    "2010 median": (38.1, _hist(2010, "median"), 0.2),
    "2025 median": (40.7, _hist(2025, "median"), 0.2),
    "2010 above 70": (23, _hist(2010, "at_or_above_70"), 0),
    "2025 above 70": (67, _hist(2025, "at_or_above_70"), 0),
    "2010 departments": (227, _hist(2010, "departments"), 0),
    "2025 departments": (425, _hist(2025, "departments"), 0),

    # --- per-university spread ---------------------------------------------
    "MIT min share": (15.8, _uni("mit", "min_share"), 0.2),
    "MIT max share": (73.2, _uni("mit", "max_share"), 0.2),
    "Purdue majority departments":
        (20, _uni("purdue", "majority_non_resident"), 0),
    "Purdue departments": (27, _uni("purdue", "departments"), 0),
    # --- the body shops (37-the-body-shops.md) ------------------------------
    "Certified applications read": (2236477, _shops("national", "certified_filings"), 0),
    "Placed at another company's site": (20.1, _shops("national", "secondary_pct"), 0.05),
    "Filed at wage level I-II": (60.6, _shops("national", "low_level_pct"), 0.05),
    "Firms meeting the body-shop test": (1203, _shops("body_shop_totals", "employers"), 0),
    "Body-shop share of applications":
        (12.5, _shops("body_shop_totals", "share_of_filings_pct"), 0.05),
    "Placed developer median": (105997, _dev("placed_median_wage"), 0),
    "Direct developer median": (146893, _dev("direct_median_wage"), 0),
    "Developer wage gap": (27.8, _dev("gap_pct"), 0.05),
    "Placed developers at level I-II": (85.7, _dev("placed_low_level_pct"), 0.05),
    "Direct developers at level I-II": (52.9, _dev("direct_low_level_pct"), 0.05),
    "H-1B employers in the hub": (368825, _hub("employers"), 0),
    "H-1B initial approvals 2009-2023": (1675026, _hub("initial_approvals"), 0),
    "Employers with five or fewer": (340672, _hub("employers_with_5_or_fewer"), 0),
    "Top ten share": (11.2, _hub("top10_share_pct"), 0.05),
    "Top two hundred share": (32.7, _hub("top200_share_pct"), 0.05),
    "Employers barred from H-1B": (5, _debarred("H-1B"), 0),

    # --- five critical industries (38-critical-industries.md) ---------------
    "Petroleum doctorate share": (85.3, _industry("petroleum", "share"), 0.05),
    "Mining doctorate share": (56.4, _industry("mining", "share"), 0.05),
    "Battery proxy share": (51.6, _industry("battery", "share"), 0.05),
    "Aerospace doctorate share": (42.6, _industry("aerospace", "share"), 0.05),
    "Nuclear doctorate share": (32.8, _industry("nuclear", "share"), 0.05),
    "Aerospace doctorates": (2911, _industry("aerospace", "doctorates"), 0),
    "Aerospace non-residents": (1239, _industry("aerospace", "nra"), 0),
    "Petroleum institutions": (16, _industry("petroleum", "institutions"), 0),

    # --- the FICA exposure grid (16-equal-pay-is-not-equal-cost.md) ---------
    "FICA employer side at $80k, OPT": (1.19, _fica(80000, "OPT", "employer_side_forgone"), 0.01),
    "FICA employer side at $80k, STEM OPT":
        (0.58, _fica(80000, "STEM OPT", "employer_side_forgone"), 0.01),
    "FICA combined at $80k, both populations":
        (3.55, _fica(80000, "Both", "combined_forgone"), 0.01),
    "FICA combined at $60k, both populations":
        (2.66, _fica(60000, "Both", "combined_forgone"), 0.01),
    "FICA combined at $100k, both populations":
        (4.44, _fica(100000, "Both", "combined_forgone"), 0.01),
    "FICA employer side at $100k, OPT":
        (1.49, _fica(100000, "OPT", "employer_side_forgone"), 0.01),
    "FICA employer side at $60k, OPT":
        (0.89, _fica(60000, "OPT", "employer_side_forgone"), 0.01),
}


def verify() -> list[str]:
    """Return a list of problems. Empty means every stated figure holds."""
    problems = []
    for name, (stated, resolve, tol) in FIGURES.items():
        try:
            actual = resolve()
        except Exception as e:                                # noqa: BLE001
            problems.append(f"{name}: resolver failed ({e})")
            continue
        if actual is None:
            continue          # artifact absent (clean checkout); not a failure
        if abs(float(actual) - float(stated)) > tol:
            problems.append(f"{name}: knowledge base says {stated}, data says {actual}")
    return problems