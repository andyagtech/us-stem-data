#!/usr/bin/env python3
"""Case Western Reserve University.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Case Western Reserve University"

DEPARTMENTS: dict[str, dict] = {
    "biology_biology_about_faculty": {
        "url": "https://biology.case.edu/about/faculty",
        "field": "biology",
        "profiles": 45,
        "parse": None,
    },
    "biology_biology_about_people_faculty": {
        "url": "https://biology.case.edu/about/people/faculty",
        "field": "biology",
        "profiles": 45,
        "parse": None,
    },
    "biology_biology_directory_faculty": {
        "url": "https://biology.case.edu/directory/faculty",
        "field": "biology",
        "profiles": 45,
        "parse": None,
    },
    "biology_biology_faculty": {
        "url": "https://biology.case.edu/faculty",
        "field": "biology",
        "profiles": 45,
        "parse": None,
    },
    "biology_biology_people_faculty": {
        "url": "https://biology.case.edu/people/faculty",
        "field": "biology",
        "profiles": 45,
        "parse": None,
    },
    "chemistry_chemistry_about_faculty": {
        "url": "https://chemistry.case.edu/about/faculty",
        "field": "chemistry",
        "profiles": 19,
        "parse": None,
    },
    "chemistry_chemistry_about_people_faculty": {
        "url": "https://chemistry.case.edu/about/people/faculty",
        "field": "chemistry",
        "profiles": 19,
        "parse": None,
    },
    "chemistry_chemistry_directory_faculty": {
        "url": "https://chemistry.case.edu/directory/faculty",
        "field": "chemistry",
        "profiles": 19,
        "parse": None,
    },
    "chemistry_chemistry_directory_people": {
        "url": "https://chemistry.case.edu/directory/people",
        "field": "chemistry",
        "profiles": 27,
        "parse": None,
    },
    "chemistry_chemistry_faculty": {
        "url": "https://chemistry.case.edu/faculty",
        "field": "chemistry",
        "profiles": 19,
        "parse": None,
    },
    "chemistry_chemistry_people": {
        "url": "https://chemistry.case.edu/people",
        "field": "chemistry",
        "profiles": 27,
        "parse": None,
    },
    "chemistry_chemistry_people_faculty": {
        "url": "https://chemistry.case.edu/people/faculty",
        "field": "chemistry",
        "profiles": 19,
        "parse": None,
    },
    "physics_physics_about_faculty": {
        "url": "https://physics.case.edu/about/faculty",
        "field": "physics",
        "profiles": 28,
        "parse": None,
    },
    "physics_physics_directory_faculty": {
        "url": "https://physics.case.edu/directory/faculty",
        "field": "physics",
        "profiles": 28,
        "parse": None,
    },
    "physics_physics_faculty": {
        "url": "https://physics.case.edu/faculty",
        "field": "physics",
        "profiles": 28,
        "parse": None,
    },
    "physics_physics_people_faculty": {
        "url": "https://physics.case.edu/people/faculty",
        "field": "physics",
        "profiles": 28,
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
