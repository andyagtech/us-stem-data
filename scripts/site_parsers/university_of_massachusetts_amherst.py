#!/usr/bin/env python3
"""University of Massachusetts-Amherst.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Massachusetts-Amherst"

DEPARTMENTS: dict[str, dict] = {
    "che_chemeng_directory_faculty": {
        "url": "https://che.umass.edu/directory/faculty",
        "field": "chemeng",
        "profiles": 6,
        "parse": None,
    },
    "che_chemeng_faculty": {
        "url": "https://che.umass.edu/faculty",
        "field": "chemeng",
        "profiles": 6,
        "parse": None,
    },
    "che_chemeng_people": {
        "url": "https://che.umass.edu/people",
        "field": "chemeng",
        "profiles": 6,
        "parse": None,
    },
    "che_chemeng_people_faculty": {
        "url": "https://che.umass.edu/people/faculty",
        "field": "chemeng",
        "profiles": 6,
        "parse": None,
    },
    "chem_chemistry_faculty": {
        "url": "https://chem.umass.edu/faculty",
        "field": "chemistry",
        "profiles": 32,
        "parse": None,
    },
    "chem_chemistry_people": {
        "url": "https://chem.umass.edu/people",
        "field": "chemistry",
        "profiles": 10,
        "parse": None,
    },
    "math_math_directory_faculty": {
        "url": "https://math.umass.edu/directory/faculty",
        "field": "math",
        "profiles": 85,
        "parse": None,
    },
    "math_math_people": {
        "url": "https://math.umass.edu/people",
        "field": "math",
        "profiles": 10,
        "parse": None,
    },
    "math_math_people_faculty": {
        "url": "https://math.umass.edu/people/faculty",
        "field": "math",
        "profiles": 85,
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
