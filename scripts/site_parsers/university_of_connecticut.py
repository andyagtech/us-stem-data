#!/usr/bin/env python3
"""University of Connecticut.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Connecticut"

DEPARTMENTS: dict[str, dict] = {
    "chemistry_chemistry_directory_faculty": {
        "url": "https://chemistry.uconn.edu/directory/faculty",
        "field": "chemistry",
        "profiles": 77,
        "parse": None,
    },
    "chemistry_chemistry_faculty": {
        "url": "https://chemistry.uconn.edu/faculty",
        "field": "chemistry",
        "profiles": 77,
        "parse": None,
    },
    "chemistry_chemistry_people_faculty": {
        "url": "https://chemistry.uconn.edu/people/faculty",
        "field": "chemistry",
        "profiles": 77,
        "parse": None,
    },
    "math_math_directory_faculty": {
        "url": "https://math.uconn.edu/directory/faculty",
        "field": "math",
        "profiles": 127,
        "parse": None,
    },
    "math_math_faculty": {
        "url": "https://math.uconn.edu/faculty",
        "field": "math",
        "profiles": 127,
        "parse": None,
    },
    "math_math_people": {
        "url": "https://math.uconn.edu/people",
        "field": "math",
        "profiles": 127,
        "parse": None,
    },
    "math_math_people_faculty": {
        "url": "https://math.uconn.edu/people/faculty",
        "field": "math",
        "profiles": 127,
        "parse": None,
    },
    "physics_physics_directory_faculty": {
        "url": "https://physics.uconn.edu/directory/faculty",
        "field": "physics",
        "profiles": 45,
        "parse": None,
    },
    "physics_physics_faculty": {
        "url": "https://physics.uconn.edu/faculty",
        "field": "physics",
        "profiles": 45,
        "parse": None,
    },
    "physics_physics_people": {
        "url": "https://physics.uconn.edu/people",
        "field": "physics",
        "profiles": 59,
        "parse": None,
    },
    "physics_physics_people_faculty": {
        "url": "https://physics.uconn.edu/people/faculty",
        "field": "physics",
        "profiles": 45,
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
