#!/usr/bin/env python3
"""Florida State University.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Florida State University"

DEPARTMENTS: dict[str, dict] = {
    "ce_civileng_directory": {
        "url": "https://ce.fsu.edu/directory",
        "field": "civileng",
        "profiles": 8,
        "parse": None,
    },
    "physics_physics_people": {
        "url": "https://physics.fsu.edu/people",
        "field": "physics",
        "profiles": 50,
        "parse": None,
    },
    "stat_stats_directory": {
        "url": "https://stat.fsu.edu/directory",
        "field": "stats",
        "profiles": 35,
        "parse": None,
    },
    "stat_stats_people": {
        "url": "https://stat.fsu.edu/people",
        "field": "stats",
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
