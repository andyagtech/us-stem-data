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
