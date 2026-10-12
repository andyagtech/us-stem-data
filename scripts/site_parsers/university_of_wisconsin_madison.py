#!/usr/bin/env python3
"""University of Wisconsin-Madison.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Wisconsin-Madison"

DEPARTMENTS: dict[str, dict] = {
    "biostat_stats_directory_people": {
        "url": "https://biostat.wisc.edu/directory/people",
        "field": "stats",
        "profiles": 139,
        "parse": None,
    },
    "biostat_stats_people": {
        "url": "https://biostat.wisc.edu/people",
        "field": "stats",
        "profiles": 139,
        "parse": None,
    },
    "cems_x_about_faculty": {
        "url": "https://cems.wisc.edu/about/faculty",
        "field": "",
        "profiles": 42,
        "parse": None,
    },
    "cems_x_about_people_faculty": {
        "url": "https://cems.wisc.edu/about/people/faculty",
        "field": "",
        "profiles": 42,
        "parse": None,
    },
    "cems_x_directory_faculty": {
        "url": "https://cems.wisc.edu/directory/faculty",
        "field": "",
        "profiles": 42,
        "parse": None,
    },
    "cems_x_faculty": {
        "url": "https://cems.wisc.edu/faculty",
        "field": "",
        "profiles": 42,
        "parse": None,
    },
    "cems_x_people_faculty": {
        "url": "https://cems.wisc.edu/people/faculty",
        "field": "",
        "profiles": 42,
        "parse": None,
    },
    "chem_chemistry_about_faculty": {
        "url": "https://chem.wisc.edu/about/faculty",
        "field": "chemistry",
        "profiles": 60,
        "parse": None,
    },
    "chem_chemistry_about_people_faculty": {
        "url": "https://chem.wisc.edu/about/people/faculty",
        "field": "chemistry",
        "profiles": 60,
        "parse": None,
    },
    "chem_chemistry_directory_faculty": {
        "url": "https://chem.wisc.edu/directory/faculty",
        "field": "chemistry",
        "profiles": 60,
        "parse": None,
    },
    "chem_chemistry_directory_people": {
        "url": "https://chem.wisc.edu/directory/people",
        "field": "chemistry",
        "profiles": 17,
        "parse": None,
    },
    "chem_chemistry_faculty": {
        "url": "https://chem.wisc.edu/faculty",
        "field": "chemistry",
        "profiles": 60,
        "parse": None,
    },
    "chem_chemistry_people": {
        "url": "https://chem.wisc.edu/people",
        "field": "chemistry",
        "profiles": 17,
        "parse": None,
    },
    "chem_chemistry_people_faculty": {
        "url": "https://chem.wisc.edu/people/faculty",
        "field": "chemistry",
        "profiles": 60,
        "parse": None,
    },
    "physics_physics_people": {
        "url": "https://physics.wisc.edu/people",
        "field": "physics",
        "profiles": 9,
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
