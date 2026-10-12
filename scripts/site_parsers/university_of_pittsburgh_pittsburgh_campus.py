#!/usr/bin/env python3
"""University of Pittsburgh-Pittsburgh Campus.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Pittsburgh-Pittsburgh Campus"

DEPARTMENTS: dict[str, dict] = {
    "biology_biology_people": {
        "url": "https://biology.pitt.edu/people",
        "field": "biology",
        "profiles": 358,
        "parse": None,
    },
    "chem_chemistry_people": {
        "url": "https://chem.pitt.edu/people",
        "field": "chemistry",
        "profiles": 45,
        "parse": None,
    },
    "chem_chemistry_people_faculty": {
        "url": "https://chem.pitt.edu/people/faculty",
        "field": "chemistry",
        "profiles": 10,
        "parse": None,
    },
    "chemistry_chemistry_people": {
        "url": "https://chemistry.pitt.edu/people",
        "field": "chemistry",
        "profiles": 45,
        "parse": None,
    },
    "chemistry_chemistry_people_faculty": {
        "url": "https://chemistry.pitt.edu/people/faculty",
        "field": "chemistry",
        "profiles": 10,
        "parse": None,
    },
    "stat_stats_people": {
        "url": "https://stat.pitt.edu/people",
        "field": "stats",
        "profiles": 20,
        "parse": None,
    },
    "stat_stats_people_faculty": {
        "url": "https://stat.pitt.edu/people/faculty",
        "field": "stats",
        "profiles": 10,
        "parse": None,
    },
    "statistics_stats_people": {
        "url": "https://statistics.pitt.edu/people",
        "field": "stats",
        "profiles": 69,
        "parse": None,
    },
    "statistics_stats_people_faculty": {
        "url": "https://statistics.pitt.edu/people/faculty",
        "field": "stats",
        "profiles": 16,
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
