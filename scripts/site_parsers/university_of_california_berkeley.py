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
    "aero_aerospace_about_faculty": {
        "url": "https://aero.berkeley.edu/about/faculty",
        "field": "aerospace",
        "profiles": 27,
        "parse": None,
    },
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
    "astro_physics_people": {
        "url": "https://astro.berkeley.edu/people",
        "field": "physics",
        "profiles": 19,
        "parse": None,
    },
    "astro_physics_people_all_faculty": {
        "url": "https://astro.berkeley.edu/people/all-faculty",
        "field": "physics",
        "profiles": 20,
        "parse": None,
    },
    "astro_physics_people_faculty": {
        "url": "https://astro.berkeley.edu/people/faculty",
        "field": "physics",
        "profiles": 20,
        "parse": None,
    },
    "astro_physics_people_faculty_directory": {
        "url": "https://astro.berkeley.edu/people/faculty-directory",
        "field": "physics",
        "profiles": 20,
        "parse": None,
    },
    "astro_physics_people_index_html": {
        "url": "https://astro.berkeley.edu/people/index.html",
        "field": "physics",
        "profiles": 19,
        "parse": None,
    },
    "astro_physics_people_professors": {
        "url": "https://astro.berkeley.edu/people/professors",
        "field": "physics",
        "profiles": 20,
        "parse": None,
    },
    "biology_biology_people": {
        "url": "https://biology.berkeley.edu/people",
        "field": "biology",
        "profiles": 18,
        "parse": None,
    },
    "biology_biology_people_all_faculty": {
        "url": "https://biology.berkeley.edu/people/all-faculty",
        "field": "biology",
        "profiles": 19,
        "parse": None,
    },
    "biology_biology_people_faculty": {
        "url": "https://biology.berkeley.edu/people/faculty",
        "field": "biology",
        "profiles": 18,
        "parse": None,
    },
    "biology_biology_people_faculty_directory": {
        "url": "https://biology.berkeley.edu/people/faculty-directory",
        "field": "biology",
        "profiles": 19,
        "parse": None,
    },
    "biology_biology_people_index_html": {
        "url": "https://biology.berkeley.edu/people/index.html",
        "field": "biology",
        "profiles": 18,
        "parse": None,
    },
    "biology_biology_people_professors": {
        "url": "https://biology.berkeley.edu/people/professors",
        "field": "biology",
        "profiles": 19,
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
    "chemistry_chemistry_people_all_faculty": {
        "url": "https://chemistry.berkeley.edu/people/all-faculty",
        "field": "chemistry",
        "profiles": 18,
        "parse": None,
    },
    "chemistry_chemistry_people_faculty": {
        "url": "https://chemistry.berkeley.edu/people/faculty",
        "field": "chemistry",
        "profiles": 17,
        "parse": None,
    },
    "chemistry_chemistry_people_faculty_directory": {
        "url": "https://chemistry.berkeley.edu/people/faculty-directory",
        "field": "chemistry",
        "profiles": 18,
        "parse": None,
    },
    "chemistry_chemistry_people_index_html": {
        "url": "https://chemistry.berkeley.edu/people/index.html",
        "field": "chemistry",
        "profiles": 17,
        "parse": None,
    },
    "chemistry_chemistry_people_professors": {
        "url": "https://chemistry.berkeley.edu/people/professors",
        "field": "chemistry",
        "profiles": 18,
        "parse": None,
    },
    "ieor_industrial_about_faculty": {
        "url": "https://ieor.berkeley.edu/about/faculty",
        "field": "industrial",
        "profiles": 23,
        "parse": None,
    },
    "ieor_industrial_directory_faculty": {
        "url": "https://ieor.berkeley.edu/directory/faculty",
        "field": "industrial",
        "profiles": 23,
        "parse": None,
    },
    "ieor_industrial_faculty": {
        "url": "https://ieor.berkeley.edu/faculty",
        "field": "industrial",
        "profiles": 23,
        "parse": None,
    },
    "ieor_industrial_people_faculty": {
        "url": "https://ieor.berkeley.edu/people/faculty",
        "field": "industrial",
        "profiles": 23,
        "parse": None,
    },
    "ieor_industrial_people_faculty_directory": {
        "url": "https://ieor.berkeley.edu/people/faculty-directory",
        "field": "industrial",
        "profiles": 23,
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
    "me_mecheng_about_faculty": {
        "url": "https://me.berkeley.edu/about/faculty",
        "field": "mecheng",
        "profiles": 50,
        "parse": None,
    },
    "me_mecheng_about_people_faculty": {
        "url": "https://me.berkeley.edu/about/people/faculty",
        "field": "mecheng",
        "profiles": 50,
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
    "physics_physics_directory": {
        "url": "https://physics.berkeley.edu/directory",
        "field": "physics",
        "profiles": 7,
        "parse": None,
    },
    "physics_physics_people": {
        "url": "https://physics.berkeley.edu/people",
        "field": "physics",
        "profiles": 7,
        "parse": None,
    },
    "physics_physics_people_all_faculty": {
        "url": "https://physics.berkeley.edu/people/all-faculty",
        "field": "physics",
        "profiles": 8,
        "parse": None,
    },
    "physics_physics_people_faculty": {
        "url": "https://physics.berkeley.edu/people/faculty",
        "field": "physics",
        "profiles": 7,
        "parse": None,
    },
    "physics_physics_people_faculty_directory": {
        "url": "https://physics.berkeley.edu/people/faculty-directory",
        "field": "physics",
        "profiles": 8,
        "parse": None,
    },
    "physics_physics_people_index_html": {
        "url": "https://physics.berkeley.edu/people/index.html",
        "field": "physics",
        "profiles": 7,
        "parse": None,
    },
    "physics_physics_people_professors": {
        "url": "https://physics.berkeley.edu/people/professors",
        "field": "physics",
        "profiles": 8,
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
