#!/usr/bin/env python3
"""University of Central Florida.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Central Florida"

DEPARTMENTS: dict[str, dict] = {
    "iems_industrial_directory_people": {
        "url": "https://iems.ucf.edu/directory/people",
        "field": "industrial",
        "profiles": 30,
        "parse": None,
    },
    "iems_industrial_faculty": {
        "url": "https://iems.ucf.edu/faculty",
        "field": "industrial",
        "profiles": 9,
        "parse": None,
    },
    "iems_industrial_people": {
        "url": "https://iems.ucf.edu/people",
        "field": "industrial",
        "profiles": 30,
        "parse": None,
    },
    "mae_mecheng_faculty_directory": {
        "url": "https://mae.ucf.edu/faculty-directory",
        "field": "mecheng",
        "profiles": 47,
        "parse": None,
    },
    "mae_mecheng_people_faculty_directory": {
        "url": "https://mae.ucf.edu/people/faculty-directory",
        "field": "mecheng",
        "profiles": 47,
        "parse": None,
    },
    "mse_materials_about_faculty": {
        "url": "https://mse.ucf.edu/about/faculty",
        "field": "materials",
        "profiles": 27,
        "parse": None,
    },
    "mse_materials_directory_faculty": {
        "url": "https://mse.ucf.edu/directory/faculty",
        "field": "materials",
        "profiles": 27,
        "parse": None,
    },
    "mse_materials_faculty": {
        "url": "https://mse.ucf.edu/faculty",
        "field": "materials",
        "profiles": 27,
        "parse": None,
    },
    "mse_materials_people_faculty": {
        "url": "https://mse.ucf.edu/people/faculty",
        "field": "materials",
        "profiles": 27,
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
