#!/usr/bin/env python3
"""University of Kansas.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Kansas"

DEPARTMENTS: dict[str, dict] = {
    "biology_biology_faculty": {
        "url": "https://biology.ku.edu/faculty",
        "field": "biology",
        "profiles": 9,
        "parse": None,
    },
    "chem_chemistry_faculty": {
        "url": "https://chem.ku.edu/faculty",
        "field": "chemistry",
        "profiles": 18,
        "parse": None,
    },
    "eecs_ai_faculty": {
        "url": "https://eecs.ku.edu/faculty",
        "field": "ai",
        "profiles": 16,
        "parse": None,
    },
    "ise_industrial_faculty": {
        "url": "https://ise.ku.edu/faculty",
        "field": "industrial",
        "profiles": 12,
        "parse": None,
    },
    "math_math_faculty": {
        "url": "https://math.ku.edu/faculty",
        "field": "math",
        "profiles": 39,
        "parse": None,
    },
    "me_mecheng_faculty": {
        "url": "https://me.ku.edu/faculty",
        "field": "mecheng",
        "profiles": 14,
        "parse": None,
    },
    "physics_physics_faculty": {
        "url": "https://physics.ku.edu/faculty",
        "field": "physics",
        "profiles": 27,
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
