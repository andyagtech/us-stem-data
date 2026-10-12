#!/usr/bin/env python3
"""University of Connecticut.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Connecticut"

DEPARTMENTS: dict[str, dict] = {
    "astro_physics_directory_people": {
        "url": "https://astro.uconn.edu/directory/people",
        "field": "physics",
        "profiles": 23,
        "parse": None,
    },
    "astro_physics_people": {
        "url": "https://astro.uconn.edu/people",
        "field": "physics",
        "profiles": 23,
        "parse": None,
    },
    "chemistry_chemistry_about_faculty": {
        "url": "https://chemistry.uconn.edu/about/faculty",
        "field": "chemistry",
        "profiles": 77,
        "parse": None,
    },
    "chemistry_chemistry_about_people_faculty": {
        "url": "https://chemistry.uconn.edu/about/people/faculty",
        "field": "chemistry",
        "profiles": 77,
        "parse": None,
    },
    "chemistry_chemistry_directory_faculty": {
        "url": "https://chemistry.uconn.edu/directory/faculty",
        "field": "chemistry",
        "profiles": 77,
        "parse": None,
    },
    "chemistry_chemistry_faculty": {
        "url": "https://chemistry.uconn.edu/faculty",
        "field": "chemistry",
        "profiles": 77,
        "parse": None,
    },
    "chemistry_chemistry_people_faculty": {
        "url": "https://chemistry.uconn.edu/people/faculty",
        "field": "chemistry",
        "profiles": 77,
        "parse": None,
    },
    "engineering_x_about_faculty": {
        "url": "https://engineering.uconn.edu/about/faculty",
        "field": "",
        "profiles": 286,
        "parse": None,
    },
    "engineering_x_about_people_faculty": {
        "url": "https://engineering.uconn.edu/about/people/faculty",
        "field": "",
        "profiles": 286,
        "parse": None,
    },
    "engineering_x_directory_faculty": {
        "url": "https://engineering.uconn.edu/directory/faculty",
        "field": "",
        "profiles": 286,
        "parse": None,
    },
    "engineering_x_directory_people": {
        "url": "https://engineering.uconn.edu/directory/people",
        "field": "",
        "profiles": 286,
        "parse": None,
    },
    "engineering_x_faculty": {
        "url": "https://engineering.uconn.edu/faculty",
        "field": "",
        "profiles": 286,
        "parse": None,
    },
    "engineering_x_people": {
        "url": "https://engineering.uconn.edu/people",
        "field": "",
        "profiles": 286,
        "parse": None,
    },
    "engineering_x_people_faculty": {
        "url": "https://engineering.uconn.edu/people/faculty",
        "field": "",
        "profiles": 286,
        "parse": None,
    },
    "math_math_about_faculty": {
        "url": "https://math.uconn.edu/about/faculty",
        "field": "math",
        "profiles": 127,
        "parse": None,
    },
    "math_math_about_people_faculty": {
        "url": "https://math.uconn.edu/about/people/faculty",
        "field": "math",
        "profiles": 127,
        "parse": None,
    },
    "math_math_directory_faculty": {
        "url": "https://math.uconn.edu/directory/faculty",
        "field": "math",
        "profiles": 127,
        "parse": None,
    },
    "math_math_directory_people": {
        "url": "https://math.uconn.edu/directory/people",
        "field": "math",
        "profiles": 127,
        "parse": None,
    },
    "math_math_faculty": {
        "url": "https://math.uconn.edu/faculty",
        "field": "math",
        "profiles": 127,
        "parse": None,
    },
    "math_math_people": {
        "url": "https://math.uconn.edu/people",
        "field": "math",
        "profiles": 127,
        "parse": None,
    },
    "math_math_people_faculty": {
        "url": "https://math.uconn.edu/people/faculty",
        "field": "math",
        "profiles": 127,
        "parse": None,
    },
    "physics_physics_about_faculty": {
        "url": "https://physics.uconn.edu/about/faculty",
        "field": "physics",
        "profiles": 45,
        "parse": None,
    },
    "physics_physics_about_people_faculty": {
        "url": "https://physics.uconn.edu/about/people/faculty",
        "field": "physics",
        "profiles": 45,
        "parse": None,
    },
    "physics_physics_directory_faculty": {
        "url": "https://physics.uconn.edu/directory/faculty",
        "field": "physics",
        "profiles": 45,
        "parse": None,
    },
    "physics_physics_directory_people": {
        "url": "https://physics.uconn.edu/directory/people",
        "field": "physics",
        "profiles": 59,
        "parse": None,
    },
    "physics_physics_faculty": {
        "url": "https://physics.uconn.edu/faculty",
        "field": "physics",
        "profiles": 45,
        "parse": None,
    },
    "physics_physics_people": {
        "url": "https://physics.uconn.edu/people",
        "field": "physics",
        "profiles": 59,
        "parse": None,
    },
    "physics_physics_people_faculty": {
        "url": "https://physics.uconn.edu/people/faculty",
        "field": "physics",
        "profiles": 45,
        "parse": None,
    },
    "statistics_stats_faculty_directory": {
        "url": "https://statistics.uconn.edu/faculty-directory",
        "field": "stats",
        "profiles": 40,
        "parse": None,
    },
    "statistics_stats_people_faculty_directory": {
        "url": "https://statistics.uconn.edu/people/faculty-directory",
        "field": "stats",
        "profiles": 40,
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
