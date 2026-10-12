#!/usr/bin/env python3
"""University of Chicago.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Chicago"

DEPARTMENTS: dict[str, dict] = {
    "physics_physics_people": {
        "url": "https://physics.uchicago.edu/people",
        "field": "physics",
        "profiles": 263,
        "parse": None,
    },
    "stat_stats_people": {
        "url": "https://stat.uchicago.edu/people",
        "field": "stats",
        "profiles": 251,
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
