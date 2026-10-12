#!/usr/bin/env python3
"""University of Tennessee-Knoxville.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Tennessee-Knoxville"

DEPARTMENTS: dict[str, dict] = {
    "cbe_chemeng_directory_faculty": {
        "url": "https://cbe.utk.edu/directory/faculty",
        "field": "chemeng",
        "profiles": 8,
        "parse": None,
    },
    "cbe_chemeng_faculty": {
        "url": "https://cbe.utk.edu/faculty",
        "field": "chemeng",
        "profiles": 8,
        "parse": None,
    },
    "cee_civileng_directory_faculty": {
        "url": "https://cee.utk.edu/directory/faculty",
        "field": "civileng",
        "profiles": 32,
        "parse": None,
    },
    "cee_civileng_faculty": {
        "url": "https://cee.utk.edu/faculty",
        "field": "civileng",
        "profiles": 32,
        "parse": None,
    },
    "chem_chemistry_directory_faculty": {
        "url": "https://chem.utk.edu/directory/faculty",
        "field": "chemistry",
        "profiles": 29,
        "parse": None,
    },
    "chem_chemistry_faculty": {
        "url": "https://chem.utk.edu/faculty",
        "field": "chemistry",
        "profiles": 29,
        "parse": None,
    },
    "eecs_ai_directory_faculty": {
        "url": "https://eecs.utk.edu/directory/faculty",
        "field": "ai",
        "profiles": 49,
        "parse": None,
    },
    "eecs_ai_faculty": {
        "url": "https://eecs.utk.edu/faculty",
        "field": "ai",
        "profiles": 49,
        "parse": None,
    },
    "math_math_directory_faculty": {
        "url": "https://math.utk.edu/directory/faculty",
        "field": "math",
        "profiles": 92,
        "parse": None,
    },
    "math_math_faculty": {
        "url": "https://math.utk.edu/faculty",
        "field": "math",
        "profiles": 92,
        "parse": None,
    },
    "ne_nuclear_directory_faculty": {
        "url": "https://ne.utk.edu/directory/faculty",
        "field": "nuclear",
        "profiles": 21,
        "parse": None,
    },
    "ne_nuclear_faculty": {
        "url": "https://ne.utk.edu/faculty",
        "field": "nuclear",
        "profiles": 21,
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
