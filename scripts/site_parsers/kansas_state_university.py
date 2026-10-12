#!/usr/bin/env python3
"""Kansas State University.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Kansas State University"

DEPARTMENTS: dict[str, dict] = {
    "ce_civileng_about_people_faculty": {
        "url": "https://ce.k-state.edu/about/people/faculty",
        "field": "civileng",
        "profiles": 13,
        "parse": None,
    },
    "che_chemeng_about_people_faculty": {
        "url": "https://che.k-state.edu/about/people/faculty",
        "field": "chemeng",
        "profiles": 10,
        "parse": None,
    },
    "ece_ee_about_people_faculty": {
        "url": "https://ece.k-state.edu/about/people/faculty",
        "field": "ee",
        "profiles": 20,
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
