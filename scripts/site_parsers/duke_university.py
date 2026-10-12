#!/usr/bin/env python3
"""Duke University.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Duke University"

DEPARTMENTS: dict[str, dict] = {
    "bme_biomed_faculty": {
        "url": "https://bme.duke.edu/faculty",
        "field": "biomed",
        "profiles": 40,
        "parse": None,
    },
    "bme_biomed_people": {
        "url": "https://bme.duke.edu/people",
        "field": "biomed",
        "profiles": 31,
        "parse": None,
    },
    "cee_civileng_faculty": {
        "url": "https://cee.duke.edu/faculty",
        "field": "civileng",
        "profiles": 24,
        "parse": None,
    },
    "cee_civileng_people": {
        "url": "https://cee.duke.edu/people",
        "field": "civileng",
        "profiles": 27,
        "parse": None,
    },
    "cee_civileng_people_faculty": {
        "url": "https://cee.duke.edu/people/faculty",
        "field": "civileng",
        "profiles": 24,
        "parse": None,
    },
    "ece_ee_faculty": {
        "url": "https://ece.duke.edu/faculty",
        "field": "ee",
        "profiles": 40,
        "parse": None,
    },
    "ece_ee_people": {
        "url": "https://ece.duke.edu/people",
        "field": "ee",
        "profiles": 33,
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
