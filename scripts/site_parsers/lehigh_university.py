#!/usr/bin/env python3
"""Lehigh University.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Lehigh University"

DEPARTMENTS: dict[str, dict] = {
    "cbe_chemeng_directory": {
        "url": "https://cbe.lehigh.edu/directory",
        "field": "chemeng",
        "profiles": 119,
        "parse": None,
    },
    "engineering_x_faculty": {
        "url": "https://engineering.lehigh.edu/faculty",
        "field": "",
        "profiles": 130,
        "parse": None,
    },
    "engineering_x_faculty_index_html": {
        "url": "https://engineering.lehigh.edu/faculty/index.html",
        "field": "",
        "profiles": 137,
        "parse": None,
    },
    "matsci_materials_faculty": {
        "url": "https://matsci.lehigh.edu/faculty",
        "field": "materials",
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
