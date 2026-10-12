#!/usr/bin/env python3
"""Oregon State University.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Oregon State University"

DEPARTMENTS: dict[str, dict] = {
    "chemistry_chemistry_directory": {
        "url": "https://chemistry.oregonstate.edu/directory",
        "field": "chemistry",
        "profiles": 28,
        "parse": None,
    },
    "eecs_ai_people_faculty_directory": {
        "url": "https://eecs.oregonstate.edu/people/faculty-directory",
        "field": "ai",
        "profiles": 37,
        "parse": None,
    },
    "engineering_x_faculty": {
        "url": "https://engineering.oregonstate.edu/faculty",
        "field": "",
        "profiles": 8,
        "parse": None,
    },
    "engineering_x_people": {
        "url": "https://engineering.oregonstate.edu/people",
        "field": "",
        "profiles": 38,
        "parse": None,
    },
    "math_math_people": {
        "url": "https://math.oregonstate.edu/people",
        "field": "math",
        "profiles": 45,
        "parse": None,
    },
    "physics_physics_directory": {
        "url": "https://physics.oregonstate.edu/directory",
        "field": "physics",
        "profiles": 31,
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
