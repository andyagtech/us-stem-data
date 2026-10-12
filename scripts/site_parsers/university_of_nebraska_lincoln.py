#!/usr/bin/env python3
"""University of Nebraska-Lincoln.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Nebraska-Lincoln"

DEPARTMENTS: dict[str, dict] = {
    "che_chemeng_faculty_staff": {
        "url": "https://che.unl.edu/faculty-staff",
        "field": "chemeng",
        "profiles": 20,
        "parse": None,
    },
    "chem_chemistry_faculty_directory": {
        "url": "https://chem.unl.edu/faculty-directory",
        "field": "chemistry",
        "profiles": 40,
        "parse": None,
    },
    "cheme_chemeng_faculty_staff": {
        "url": "https://cheme.unl.edu/faculty-staff",
        "field": "chemeng",
        "profiles": 20,
        "parse": None,
    },
    "chemistry_chemistry_faculty_directory": {
        "url": "https://chemistry.unl.edu/faculty-directory",
        "field": "chemistry",
        "profiles": 40,
        "parse": None,
    },
    "civil_civileng_faculty_staff": {
        "url": "https://civil.unl.edu/faculty-staff",
        "field": "civileng",
        "profiles": 55,
        "parse": None,
    },
    "engineering_x_faculty": {
        "url": "https://engineering.unl.edu/faculty",
        "field": "",
        "profiles": 17,
        "parse": None,
    },
    "me_mecheng_directory": {
        "url": "https://me.unl.edu/directory",
        "field": "mecheng",
        "profiles": 51,
        "parse": None,
    },
    "mem_mecheng_faculty_staff": {
        "url": "https://mem.unl.edu/faculty-staff",
        "field": "mecheng",
        "profiles": 11,
        "parse": None,
    },
    "physics_physics_directory": {
        "url": "https://physics.unl.edu/directory",
        "field": "physics",
        "profiles": 49,
        "parse": None,
    },
    "statistics_stats_faculty": {
        "url": "https://statistics.unl.edu/faculty",
        "field": "stats",
        "profiles": 17,
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
