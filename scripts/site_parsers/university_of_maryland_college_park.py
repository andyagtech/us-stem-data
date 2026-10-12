#!/usr/bin/env python3
"""University of Maryland-College Park.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Maryland-College Park"

DEPARTMENTS: dict[str, dict] = {
    "biology_biology_people": {
        "url": "https://biology.umd.edu/people",
        "field": "biology",
        "profiles": 34,
        "parse": None,
    },
    "biology_biology_people_faculty": {
        "url": "https://biology.umd.edu/people/faculty",
        "field": "biology",
        "profiles": 11,
        "parse": None,
    },
    "chem_chemistry_people": {
        "url": "https://chem.umd.edu/people",
        "field": "chemistry",
        "profiles": 31,
        "parse": None,
    },
    "cs_ai_faculty": {
        "url": "https://cs.umd.edu/faculty",
        "field": "ai",
        "profiles": 167,
        "parse": None,
    },
    "cs_ai_people_faculty": {
        "url": "https://cs.umd.edu/people/faculty",
        "field": "ai",
        "profiles": 167,
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
