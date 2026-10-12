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
    "amath_math_people": {
        "url": "https://amath.washington.edu/people",
        "field": "math",
        "profiles": 362,
        "parse": None,
    },
    "biostat_stats_people": {
        "url": "https://biostat.washington.edu/people",
        "field": "stats",
        "profiles": 28,
        "parse": None,
    },
    "biostat_stats_people_faculty": {
        "url": "https://biostat.washington.edu/people/faculty",
        "field": "stats",
        "profiles": 19,
        "parse": None,
    },
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
    "ischool_ai_people": {
        "url": "https://ischool.washington.edu/people",
        "field": "ai",
        "profiles": 212,
        "parse": None,
    },
    "ischool_ai_people_faculty": {
        "url": "https://ischool.washington.edu/people/faculty",
        "field": "ai",
        "profiles": 212,
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
