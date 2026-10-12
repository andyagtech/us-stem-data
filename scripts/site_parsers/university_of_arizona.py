#!/usr/bin/env python3
"""University of Arizona.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "University of Arizona"

DEPARTMENTS: dict[str, dict] = {
    "bme_biomed_people": {
        "url": "https://bme.arizona.edu/people",
        "field": "biomed",
        "profiles": 62,
        "parse": None,
    },
    "bme_biomed_people_faculty": {
        "url": "https://bme.arizona.edu/people/faculty",
        "field": "biomed",
        "profiles": 62,
        "parse": None,
    },
    "cs_ai_people": {
        "url": "https://cs.arizona.edu/people",
        "field": "ai",
        "profiles": 94,
        "parse": None,
    },
    "cs_ai_people_faculty": {
        "url": "https://cs.arizona.edu/people/faculty",
        "field": "ai",
        "profiles": 94,
        "parse": None,
    },
    "math_math_people": {
        "url": "https://math.arizona.edu/people",
        "field": "math",
        "profiles": 267,
        "parse": None,
    },
    "math_math_people_faculty": {
        "url": "https://math.arizona.edu/people/faculty",
        "field": "math",
        "profiles": 110,
        "parse": None,
    },
    "mse_materials_people": {
        "url": "https://mse.arizona.edu/people",
        "field": "materials",
        "profiles": 44,
        "parse": None,
    },
    "mse_materials_people_faculty": {
        "url": "https://mse.arizona.edu/people/faculty",
        "field": "materials",
        "profiles": 44,
        "parse": None,
    },
    "physics_physics_people": {
        "url": "https://physics.arizona.edu/people",
        "field": "physics",
        "profiles": 249,
        "parse": None,
    },
    "physics_physics_people_faculty": {
        "url": "https://physics.arizona.edu/people/faculty",
        "field": "physics",
        "profiles": 34,
        "parse": None,
    },
    "stat_stats_faculty": {
        "url": "https://stat.arizona.edu/faculty",
        "field": "stats",
        "profiles": 54,
        "parse": None,
    },
    "stat_stats_people": {
        "url": "https://stat.arizona.edu/people",
        "field": "stats",
        "profiles": 125,
        "parse": None,
    },
    "stat_stats_people_faculty": {
        "url": "https://stat.arizona.edu/people/faculty",
        "field": "stats",
        "profiles": 125,
        "parse": None,
    },
    "statistics_stats_faculty": {
        "url": "https://statistics.arizona.edu/faculty",
        "field": "stats",
        "profiles": 54,
        "parse": None,
    },
    "statistics_stats_people": {
        "url": "https://statistics.arizona.edu/people",
        "field": "stats",
        "profiles": 125,
        "parse": None,
    },
    "statistics_stats_people_faculty": {
        "url": "https://statistics.arizona.edu/people/faculty",
        "field": "stats",
        "profiles": 125,
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
