#!/usr/bin/env python3
"""North Carolina State University at Raleigh.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "North Carolina State University at Raleigh"

DEPARTMENTS: dict[str, dict] = {
    "ece_ee_directory_faculty": {
        "url": "https://ece.ncsu.edu/directory/faculty",
        "field": "ee",
        "profiles": 53,
        "parse": None,
    },
    "ece_ee_faculty": {
        "url": "https://ece.ncsu.edu/faculty",
        "field": "ee",
        "profiles": 53,
        "parse": None,
    },
    "ece_ee_people": {
        "url": "https://ece.ncsu.edu/people",
        "field": "ee",
        "profiles": 53,
        "parse": None,
    },
    "ise_industrial_directory_faculty": {
        "url": "https://ise.ncsu.edu/directory/faculty",
        "field": "industrial",
        "profiles": 68,
        "parse": None,
    },
    "ise_industrial_faculty": {
        "url": "https://ise.ncsu.edu/faculty",
        "field": "industrial",
        "profiles": 68,
        "parse": None,
    },
    "ise_industrial_people": {
        "url": "https://ise.ncsu.edu/people",
        "field": "industrial",
        "profiles": 8,
        "parse": None,
    },
    "mae_mecheng_directory_faculty": {
        "url": "https://mae.ncsu.edu/directory/faculty",
        "field": "mecheng",
        "profiles": 31,
        "parse": None,
    },
    "mae_mecheng_people": {
        "url": "https://mae.ncsu.edu/people",
        "field": "mecheng",
        "profiles": 31,
        "parse": None,
    },
    "mse_materials_people": {
        "url": "https://mse.ncsu.edu/people",
        "field": "materials",
        "profiles": 14,
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
