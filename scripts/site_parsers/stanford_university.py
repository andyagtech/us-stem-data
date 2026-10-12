#!/usr/bin/env python3
"""Stanford University.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Stanford University"

DEPARTMENTS: dict[str, dict] = {
    "biology_biology_faculty": {
        "url": "https://biology.stanford.edu/faculty",
        "field": "biology",
        "profiles": 46,
        "parse": None,
    },
    "biology_biology_people": {
        "url": "https://biology.stanford.edu/people",
        "field": "biology",
        "profiles": 46,
        "parse": None,
    },
    "biology_biology_people_faculty": {
        "url": "https://biology.stanford.edu/people/faculty",
        "field": "biology",
        "profiles": 46,
        "parse": None,
    },
    "cee_civileng_people": {
        "url": "https://cee.stanford.edu/people",
        "field": "civileng",
        "profiles": 33,
        "parse": None,
    },
    "cee_civileng_people_faculty": {
        "url": "https://cee.stanford.edu/people/faculty",
        "field": "civileng",
        "profiles": 33,
        "parse": None,
    },
    "chemistry_chemistry_faculty": {
        "url": "https://chemistry.stanford.edu/faculty",
        "field": "chemistry",
        "profiles": 5,
        "parse": None,
    },
    "chemistry_chemistry_people_faculty": {
        "url": "https://chemistry.stanford.edu/people/faculty",
        "field": "chemistry",
        "profiles": 5,
        "parse": None,
    },
    "me_mecheng_people": {
        "url": "https://me.stanford.edu/people",
        "field": "mecheng",
        "profiles": 37,
        "parse": None,
    },
    "me_mecheng_people_faculty": {
        "url": "https://me.stanford.edu/people/faculty",
        "field": "mecheng",
        "profiles": 38,
        "parse": None,
    },
    "mse_materials_people_faculty": {
        "url": "https://mse.stanford.edu/people/faculty",
        "field": "materials",
        "profiles": 39,
        "parse": None,
    },
    "physics_physics_faculty": {
        "url": "https://physics.stanford.edu/faculty",
        "field": "physics",
        "profiles": 45,
        "parse": None,
    },
    "physics_physics_people_faculty": {
        "url": "https://physics.stanford.edu/people/faculty",
        "field": "physics",
        "profiles": 45,
        "parse": None,
    },
    "statistics_stats_people": {
        "url": "https://statistics.stanford.edu/people",
        "field": "stats",
        "profiles": 38,
        "parse": None,
    },
    "statistics_stats_people_faculty": {
        "url": "https://statistics.stanford.edu/people/faculty",
        "field": "stats",
        "profiles": 38,
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
