#!/usr/bin/env python3
"""Iowa State University.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Iowa State University"

DEPARTMENTS: dict[str, dict] = {
    "biology_biology_people": {
        "url": "https://biology.iastate.edu/people",
        "field": "biology",
        "profiles": 62,
        "parse": None,
    },
    "biology_biology_people_faculty": {
        "url": "https://biology.iastate.edu/people/faculty",
        "field": "biology",
        "profiles": 45,
        "parse": None,
    },
    "chem_chemistry_faculty": {
        "url": "https://chem.iastate.edu/faculty",
        "field": "chemistry",
        "profiles": 38,
        "parse": None,
    },
    "chem_chemistry_people": {
        "url": "https://chem.iastate.edu/people",
        "field": "chemistry",
        "profiles": 94,
        "parse": None,
    },
    "cs_ai_people": {
        "url": "https://cs.iastate.edu/people",
        "field": "ai",
        "profiles": 235,
        "parse": None,
    },
    "cs_ai_people_faculty": {
        "url": "https://cs.iastate.edu/people/faculty",
        "field": "ai",
        "profiles": 43,
        "parse": None,
    },
    "physics_physics_directory_faculty": {
        "url": "https://physics.iastate.edu/directory/faculty",
        "field": "physics",
        "profiles": 27,
        "parse": None,
    },
    "physics_physics_people": {
        "url": "https://physics.iastate.edu/people",
        "field": "physics",
        "profiles": 174,
        "parse": None,
    },
    "physics_physics_people_faculty": {
        "url": "https://physics.iastate.edu/people/faculty",
        "field": "physics",
        "profiles": 27,
        "parse": None,
    },
    "stat_stats_people": {
        "url": "https://stat.iastate.edu/people",
        "field": "stats",
        "profiles": 190,
        "parse": None,
    },
    "stat_stats_people_faculty": {
        "url": "https://stat.iastate.edu/people/faculty",
        "field": "stats",
        "profiles": 37,
        "parse": None,
    },
    "statistics_stats_people": {
        "url": "https://statistics.iastate.edu/people",
        "field": "stats",
        "profiles": 190,
        "parse": None,
    },
    "statistics_stats_people_faculty": {
        "url": "https://statistics.iastate.edu/people/faculty",
        "field": "stats",
        "profiles": 37,
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
