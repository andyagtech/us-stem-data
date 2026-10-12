#!/usr/bin/env python3
"""University of California-Los Angeles.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of California-Los Angeles"

DEPARTMENTS: dict[str, dict] = {
    "math_math_people": {
        "url": "https://math.ucla.edu/people",
        "field": "math",
        "profiles": 23,
        "parse": None,
    },
    "math_math_people_all_faculty": {
        "url": "https://math.ucla.edu/people/all-faculty",
        "field": "math",
        "profiles": 24,
        "parse": None,
    },
    "math_math_people_faculty": {
        "url": "https://math.ucla.edu/people/faculty",
        "field": "math",
        "profiles": 23,
        "parse": None,
    },
    "math_math_people_faculty_directory": {
        "url": "https://math.ucla.edu/people/faculty-directory",
        "field": "math",
        "profiles": 24,
        "parse": None,
    },
    "math_math_people_index_html": {
        "url": "https://math.ucla.edu/people/index.html",
        "field": "math",
        "profiles": 23,
        "parse": None,
    },
    "math_math_people_professors": {
        "url": "https://math.ucla.edu/people/professors",
        "field": "math",
        "profiles": 24,
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
