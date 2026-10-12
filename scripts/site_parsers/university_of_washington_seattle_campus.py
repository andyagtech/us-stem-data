#!/usr/bin/env python3
"""University of Washington-Seattle Campus.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Washington-Seattle Campus"

DEPARTMENTS: dict[str, dict] = {
    "chem_chemistry_people": {
        "url": "https://chem.washington.edu/people",
        "field": "chemistry",
        "profiles": 121,
        "parse": None,
    },
    "chem_chemistry_people_faculty": {
        "url": "https://chem.washington.edu/people/faculty",
        "field": "chemistry",
        "profiles": 21,
        "parse": None,
    },
    "math_math_people": {
        "url": "https://math.washington.edu/people",
        "field": "math",
        "profiles": 144,
        "parse": None,
    },
    "math_math_people_faculty": {
        "url": "https://math.washington.edu/people/faculty",
        "field": "math",
        "profiles": 87,
        "parse": None,
    },
    "phys_physics_people": {
        "url": "https://phys.washington.edu/people",
        "field": "physics",
        "profiles": 363,
        "parse": None,
    },
    "phys_physics_people_faculty": {
        "url": "https://phys.washington.edu/people/faculty",
        "field": "physics",
        "profiles": 61,
        "parse": None,
    },
}


def targets() -> list[dict]:
    """Every department directory this university publishes."""
    return [
        {"url": d["url"], "institution": INSTITUTION,
         "department_field": d["field"], "department": key,
         "profiles_seen": d.get("profiles")}
        for key, d in DEPARTMENTS.items()
    ]


def reader_for(url: str):
    """That department's own reader, or None for the shared one."""
    for d in DEPARTMENTS.values():
        if d["url"] == url:
            return d.get("parse")
    return None
