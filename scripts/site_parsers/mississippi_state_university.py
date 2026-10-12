#!/usr/bin/env python3
"""Mississippi State University.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Mississippi State University"

DEPARTMENTS: dict[str, dict] = {
    "ae_aerospace_people_faculty": {
        "url": "https://ae.msstate.edu/people/faculty",
        "field": "aerospace",
        "profiles": 6,
        "parse": None,
    },
    "cee_civileng_about_faculty": {
        "url": "https://cee.msstate.edu/about/faculty",
        "field": "civileng",
        "profiles": 6,
        "parse": None,
    },
    "cee_civileng_directory_faculty": {
        "url": "https://cee.msstate.edu/directory/faculty",
        "field": "civileng",
        "profiles": 6,
        "parse": None,
    },
    "cee_civileng_faculty": {
        "url": "https://cee.msstate.edu/faculty",
        "field": "civileng",
        "profiles": 6,
        "parse": None,
    },
    "cee_civileng_people_faculty": {
        "url": "https://cee.msstate.edu/people/faculty",
        "field": "civileng",
        "profiles": 6,
        "parse": None,
    },
    "che_chemeng_about_faculty": {
        "url": "https://che.msstate.edu/about/faculty",
        "field": "chemeng",
        "profiles": 10,
        "parse": None,
    },
    "che_chemeng_directory_faculty": {
        "url": "https://che.msstate.edu/directory/faculty",
        "field": "chemeng",
        "profiles": 10,
        "parse": None,
    },
    "che_chemeng_people_faculty": {
        "url": "https://che.msstate.edu/people/faculty",
        "field": "chemeng",
        "profiles": 10,
        "parse": None,
    },
    "chemistry_chemistry_people_faculty": {
        "url": "https://chemistry.msstate.edu/people/faculty",
        "field": "chemistry",
        "profiles": 8,
        "parse": None,
    },
    "ece_ee_about_faculty": {
        "url": "https://ece.msstate.edu/about/faculty",
        "field": "ee",
        "profiles": 9,
        "parse": None,
    },
    "ece_ee_directory_faculty": {
        "url": "https://ece.msstate.edu/directory/faculty",
        "field": "ee",
        "profiles": 9,
        "parse": None,
    },
    "ece_ee_faculty": {
        "url": "https://ece.msstate.edu/faculty",
        "field": "ee",
        "profiles": 9,
        "parse": None,
    },
    "ece_ee_people_faculty": {
        "url": "https://ece.msstate.edu/people/faculty",
        "field": "ee",
        "profiles": 9,
        "parse": None,
    },
    "ise_industrial_about_faculty": {
        "url": "https://ise.msstate.edu/about/faculty",
        "field": "industrial",
        "profiles": 5,
        "parse": None,
    },
    "ise_industrial_directory_faculty": {
        "url": "https://ise.msstate.edu/directory/faculty",
        "field": "industrial",
        "profiles": 5,
        "parse": None,
    },
    "ise_industrial_faculty": {
        "url": "https://ise.msstate.edu/faculty",
        "field": "industrial",
        "profiles": 5,
        "parse": None,
    },
    "ise_industrial_people_faculty": {
        "url": "https://ise.msstate.edu/people/faculty",
        "field": "industrial",
        "profiles": 5,
        "parse": None,
    },
    "me_mecheng_about_faculty": {
        "url": "https://me.msstate.edu/about/faculty",
        "field": "mecheng",
        "profiles": 6,
        "parse": None,
    },
    "me_mecheng_directory_faculty": {
        "url": "https://me.msstate.edu/directory/faculty",
        "field": "mecheng",
        "profiles": 6,
        "parse": None,
    },
    "me_mecheng_faculty": {
        "url": "https://me.msstate.edu/faculty",
        "field": "mecheng",
        "profiles": 6,
        "parse": None,
    },
    "me_mecheng_people_faculty": {
        "url": "https://me.msstate.edu/people/faculty",
        "field": "mecheng",
        "profiles": 6,
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
