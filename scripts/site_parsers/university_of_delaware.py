#!/usr/bin/env python3
"""University of Delaware.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Delaware"

DEPARTMENTS: dict[str, dict] = {
    "bme_biomed_directory_people": {
        "url": "https://bme.udel.edu/directory/people",
        "field": "biomed",
        "profiles": 18,
        "parse": None,
    },
    "bme_biomed_people": {
        "url": "https://bme.udel.edu/people",
        "field": "biomed",
        "profiles": 18,
        "parse": None,
    },
    "me_mecheng_about_faculty": {
        "url": "https://me.udel.edu/about/faculty",
        "field": "mecheng",
        "profiles": 30,
        "parse": None,
    },
    "me_mecheng_about_people_faculty": {
        "url": "https://me.udel.edu/about/people/faculty",
        "field": "mecheng",
        "profiles": 30,
        "parse": None,
    },
    "me_mecheng_directory_faculty": {
        "url": "https://me.udel.edu/directory/faculty",
        "field": "mecheng",
        "profiles": 30,
        "parse": None,
    },
    "me_mecheng_faculty": {
        "url": "https://me.udel.edu/faculty",
        "field": "mecheng",
        "profiles": 30,
        "parse": None,
    },
    "me_mecheng_people_faculty": {
        "url": "https://me.udel.edu/people/faculty",
        "field": "mecheng",
        "profiles": 30,
        "parse": None,
    },
    "me_mecheng_people_index_html": {
        "url": "https://me.udel.edu/people/index.html",
        "field": "mecheng",
        "profiles": 30,
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
