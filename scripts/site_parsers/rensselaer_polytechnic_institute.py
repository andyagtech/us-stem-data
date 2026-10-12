#!/usr/bin/env python3
"""Rensselaer Polytechnic Institute.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Rensselaer Polytechnic Institute"

DEPARTMENTS: dict[str, dict] = {
    "compsci_ai_faculty": {
        "url": "https://compsci.rpi.edu/faculty",
        "field": "ai",
        "profiles": 11,
        "parse": None,
    },
    "compsci_ai_people": {
        "url": "https://compsci.rpi.edu/people",
        "field": "ai",
        "profiles": 11,
        "parse": None,
    },
    "earth_geoscience_faculty": {
        "url": "https://earth.rpi.edu/faculty",
        "field": "geoscience",
        "profiles": 13,
        "parse": None,
    },
    "earth_geoscience_people": {
        "url": "https://earth.rpi.edu/people",
        "field": "geoscience",
        "profiles": 13,
        "parse": None,
    },
    "math_math_faculty": {
        "url": "https://math.rpi.edu/faculty",
        "field": "math",
        "profiles": 6,
        "parse": None,
    },
    "math_math_people": {
        "url": "https://math.rpi.edu/people",
        "field": "math",
        "profiles": 6,
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
