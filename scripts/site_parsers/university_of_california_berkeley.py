#!/usr/bin/env python3
"""University of California-Berkeley.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of California-Berkeley"

DEPARTMENTS: dict[str, dict] = {
    "aero_aerospace_directory_faculty": {
        "url": "https://aero.berkeley.edu/directory/faculty",
        "field": "aerospace",
        "profiles": 27,
        "parse": None,
    },
    "aero_aerospace_faculty": {
        "url": "https://aero.berkeley.edu/faculty",
        "field": "aerospace",
        "profiles": 27,
        "parse": None,
    },
    "aero_aerospace_people": {
        "url": "https://aero.berkeley.edu/people",
        "field": "aerospace",
        "profiles": 27,
        "parse": None,
    },
    "biology_biology_people": {
        "url": "https://biology.berkeley.edu/people",
        "field": "biology",
        "profiles": 18,
        "parse": None,
    },
    "biology_biology_people_faculty": {
        "url": "https://biology.berkeley.edu/people/faculty",
        "field": "biology",
        "profiles": 18,
        "parse": None,
    },
    "ce_civileng_people": {
        "url": "https://ce.berkeley.edu/people",
        "field": "civileng",
        "profiles": 48,
        "parse": None,
    },
    "ce_civileng_people_faculty": {
        "url": "https://ce.berkeley.edu/people/faculty",
        "field": "civileng",
        "profiles": 48,
        "parse": None,
    },
    "cee_civileng_people": {
        "url": "https://cee.berkeley.edu/people",
        "field": "civileng",
        "profiles": 48,
        "parse": None,
    },
    "cee_civileng_people_faculty": {
        "url": "https://cee.berkeley.edu/people/faculty",
        "field": "civileng",
        "profiles": 48,
        "parse": None,
    },
    "chemistry_chemistry_people": {
        "url": "https://chemistry.berkeley.edu/people",
        "field": "chemistry",
        "profiles": 17,
        "parse": None,
    },
    "chemistry_chemistry_people_faculty": {
        "url": "https://chemistry.berkeley.edu/people/faculty",
        "field": "chemistry",
        "profiles": 17,
        "parse": None,
    },
    "math_math_people": {
        "url": "https://math.berkeley.edu/people",
        "field": "math",
        "profiles": 7,
        "parse": None,
    },
    "math_math_people_faculty": {
        "url": "https://math.berkeley.edu/people/faculty",
        "field": "math",
        "profiles": 107,
        "parse": None,
    },
    "me_mecheng_directory_faculty": {
        "url": "https://me.berkeley.edu/directory/faculty",
        "field": "mecheng",
        "profiles": 50,
        "parse": None,
    },
    "me_mecheng_faculty": {
        "url": "https://me.berkeley.edu/faculty",
        "field": "mecheng",
        "profiles": 50,
        "parse": None,
    },
    "physics_physics_people": {
        "url": "https://physics.berkeley.edu/people",
        "field": "physics",
        "profiles": 7,
        "parse": None,
    },
    "physics_physics_people_faculty": {
        "url": "https://physics.berkeley.edu/people/faculty",
        "field": "physics",
        "profiles": 7,
        "parse": None,
    },
    "stat_stats_people_faculty": {
        "url": "https://stat.berkeley.edu/people/faculty",
        "field": "stats",
        "profiles": 48,
        "parse": None,
    },
    "statistics_stats_people_faculty": {
        "url": "https://statistics.berkeley.edu/people/faculty",
        "field": "stats",
        "profiles": 48,
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
