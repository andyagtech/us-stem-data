#!/usr/bin/env python3
"""Massachusetts Institute of Technology.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Massachusetts Institute of Technology"

DEPARTMENTS: dict[str, dict] = {
    "biology_biology_directory_faculty": {
        "url": "https://biology.mit.edu/directory/faculty",
        "field": "biology",
        "profiles": 61,
        "parse": None,
    },
    "biology_biology_faculty": {
        "url": "https://biology.mit.edu/faculty",
        "field": "biology",
        "profiles": 61,
        "parse": None,
    },
    "biology_biology_people": {
        "url": "https://biology.mit.edu/people",
        "field": "biology",
        "profiles": 61,
        "parse": None,
    },
    "biology_biology_people_faculty": {
        "url": "https://biology.mit.edu/people/faculty",
        "field": "biology",
        "profiles": 61,
        "parse": None,
    },
    "chemistry_chemistry_faculty": {
        "url": "https://chemistry.mit.edu/faculty",
        "field": "chemistry",
        "profiles": 28,
        "parse": None,
    },
    "cse_ai_people": {
        "url": "https://cse.mit.edu/people",
        "field": "ai",
        "profiles": 43,
        "parse": None,
    },
    "stat_stats_people": {
        "url": "https://stat.mit.edu/people",
        "field": "stats",
        "profiles": 10,
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
