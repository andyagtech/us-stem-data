#!/usr/bin/env python3
"""University of Notre Dame.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Notre Dame"

DEPARTMENTS: dict[str, dict] = {
    "biology_biology_people": {
        "url": "https://biology.nd.edu/people",
        "field": "biology",
        "profiles": 60,
        "parse": None,
    },
    "biology_biology_people_faculty": {
        "url": "https://biology.nd.edu/people/faculty",
        "field": "biology",
        "profiles": 60,
        "parse": None,
    },
    "cbe_chemeng_faculty": {
        "url": "https://cbe.nd.edu/faculty",
        "field": "chemeng",
        "profiles": 7,
        "parse": None,
    },
    "chemistry_chemistry_faculty": {
        "url": "https://chemistry.nd.edu/faculty",
        "field": "chemistry",
        "profiles": 60,
        "parse": None,
    },
    "chemistry_chemistry_people_faculty": {
        "url": "https://chemistry.nd.edu/people/faculty",
        "field": "chemistry",
        "profiles": 60,
        "parse": None,
    },
    "cse_ai_faculty": {
        "url": "https://cse.nd.edu/faculty",
        "field": "ai",
        "profiles": 10,
        "parse": None,
    },
    "ee_ee_faculty": {
        "url": "https://ee.nd.edu/faculty",
        "field": "ee",
        "profiles": 10,
        "parse": None,
    },
    "math_math_people": {
        "url": "https://math.nd.edu/people",
        "field": "math",
        "profiles": 42,
        "parse": None,
    },
    "math_math_people_faculty": {
        "url": "https://math.nd.edu/people/faculty",
        "field": "math",
        "profiles": 42,
        "parse": None,
    },
    "mse_materials_people": {
        "url": "https://mse.nd.edu/people",
        "field": "materials",
        "profiles": 81,
        "parse": None,
    },
    "mse_materials_people_faculty": {
        "url": "https://mse.nd.edu/people/faculty",
        "field": "materials",
        "profiles": 81,
        "parse": None,
    },
    "physics_physics_people": {
        "url": "https://physics.nd.edu/people",
        "field": "physics",
        "profiles": 96,
        "parse": None,
    },
    "physics_physics_people_faculty": {
        "url": "https://physics.nd.edu/people/faculty",
        "field": "physics",
        "profiles": 96,
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
