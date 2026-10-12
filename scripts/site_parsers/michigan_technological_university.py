#!/usr/bin/env python3
"""Michigan Technological University.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Michigan Technological University"

DEPARTMENTS: dict[str, dict] = {
    "cee_civileng_people": {
        "url": "https://cee.mtu.edu/people",
        "field": "civileng",
        "profiles": 39,
        "parse": None,
    },
    "cee_civileng_people_all_faculty": {
        "url": "https://cee.mtu.edu/people/all-faculty",
        "field": "civileng",
        "profiles": 39,
        "parse": None,
    },
    "cee_civileng_people_faculty": {
        "url": "https://cee.mtu.edu/people/faculty",
        "field": "civileng",
        "profiles": 39,
        "parse": None,
    },
    "cee_civileng_people_faculty_directory": {
        "url": "https://cee.mtu.edu/people/faculty-directory",
        "field": "civileng",
        "profiles": 39,
        "parse": None,
    },
    "cee_civileng_people_index_html": {
        "url": "https://cee.mtu.edu/people/index.html",
        "field": "civileng",
        "profiles": 39,
        "parse": None,
    },
    "cee_civileng_people_professors": {
        "url": "https://cee.mtu.edu/people/professors",
        "field": "civileng",
        "profiles": 39,
        "parse": None,
    },
    "math_math_people_all_faculty": {
        "url": "https://math.mtu.edu/people/all-faculty",
        "field": "math",
        "profiles": 33,
        "parse": None,
    },
    "math_math_people_faculty": {
        "url": "https://math.mtu.edu/people/faculty",
        "field": "math",
        "profiles": 33,
        "parse": None,
    },
    "math_math_people_faculty_directory": {
        "url": "https://math.mtu.edu/people/faculty-directory",
        "field": "math",
        "profiles": 33,
        "parse": None,
    },
    "math_math_people_index_html": {
        "url": "https://math.mtu.edu/people/index.html",
        "field": "math",
        "profiles": 33,
        "parse": None,
    },
    "math_math_people_professors": {
        "url": "https://math.mtu.edu/people/professors",
        "field": "math",
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
