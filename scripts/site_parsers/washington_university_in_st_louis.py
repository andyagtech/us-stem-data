#!/usr/bin/env python3
"""Washington University in St Louis.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Washington University in St Louis"

DEPARTMENTS: dict[str, dict] = {
    "biology_biology_faculty_staff": {
        "url": "https://biology.wustl.edu/faculty-staff",
        "field": "biology",
        "profiles": 22,
        "parse": None,
    },
    "biology_biology_people": {
        "url": "https://biology.wustl.edu/people",
        "field": "biology",
        "profiles": 22,
        "parse": None,
    },
    "chemistry_chemistry_faculty_staff": {
        "url": "https://chemistry.wustl.edu/faculty-staff",
        "field": "chemistry",
        "profiles": 20,
        "parse": None,
    },
    "chemistry_chemistry_people": {
        "url": "https://chemistry.wustl.edu/people",
        "field": "chemistry",
        "profiles": 20,
        "parse": None,
    },
    "math_math_faculty_staff": {
        "url": "https://math.wustl.edu/faculty-staff",
        "field": "math",
        "profiles": 22,
        "parse": None,
    },
    "math_math_people": {
        "url": "https://math.wustl.edu/people",
        "field": "math",
        "profiles": 22,
        "parse": None,
    },
    "physics_physics_faculty_staff": {
        "url": "https://physics.wustl.edu/faculty-staff",
        "field": "physics",
        "profiles": 19,
        "parse": None,
    },
    "physics_physics_people": {
        "url": "https://physics.wustl.edu/people",
        "field": "physics",
        "profiles": 19,
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
