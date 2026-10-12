#!/usr/bin/env python3
"""Brown University.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Brown University"

DEPARTMENTS: dict[str, dict] = {
    "chemistry_chemistry_faculty": {
        "url": "https://chemistry.brown.edu/faculty",
        "field": "chemistry",
        "profiles": 14,
        "parse": None,
    },
    "chemistry_chemistry_people_faculty": {
        "url": "https://chemistry.brown.edu/people/faculty",
        "field": "chemistry",
        "profiles": 14,
        "parse": None,
    },
    "cs_ai_people": {
        "url": "https://cs.brown.edu/people",
        "field": "ai",
        "profiles": 5,
        "parse": None,
    },
    "cs_ai_people_faculty": {
        "url": "https://cs.brown.edu/people/faculty",
        "field": "ai",
        "profiles": 64,
        "parse": None,
    },
    "physics_physics_people": {
        "url": "https://physics.brown.edu/people",
        "field": "physics",
        "profiles": 5,
        "parse": None,
    },
    "physics_physics_people_faculty": {
        "url": "https://physics.brown.edu/people/faculty",
        "field": "physics",
        "profiles": 7,
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
