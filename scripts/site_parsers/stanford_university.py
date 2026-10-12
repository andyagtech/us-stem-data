#!/usr/bin/env python3
"""Stanford University.

One entry per department, each with a faculty directory that
answered when probed. DEPARTMENTS is the thing to edit: add a
department, correct a URL, or give one its own reader where this
university's markup defeats the shared one.

"parse" is None while the shared reader works. A department that
needs its own gets a function here, and only that department changes.
"""
from __future__ import annotations

INSTITUTION = "Stanford University"

DEPARTMENTS: dict[str, dict] = {
    "beam_biomed_people": {
        "url": "https://beam.stanford.edu/people",
        "field": "biomed",
        "profiles": 23,
        "parse": None,
    },
    "bioe_biomed_people": {
        "url": "https://bioe.stanford.edu/people",
        "field": "biomed",
        "profiles": 39,
        "parse": None,
    },
    "bioe_biomed_people_faculty": {
        "url": "https://bioe.stanford.edu/people/faculty",
        "field": "biomed",
        "profiles": 38,
        "parse": None,
    },
    "biology_biology_faculty": {
        "url": "https://biology.stanford.edu/faculty",
        "field": "biology",
        "profiles": 46,
        "parse": None,
    },
    "biology_biology_people": {
        "url": "https://biology.stanford.edu/people",
        "field": "biology",
        "profiles": 46,
        "parse": None,
    },
    "biology_biology_people_faculty": {
        "url": "https://biology.stanford.edu/people/faculty",
        "field": "biology",
        "profiles": 46,
        "parse": None,
    },
    "cee_civileng_people": {
        "url": "https://cee.stanford.edu/people",
        "field": "civileng",
        "profiles": 33,
        "parse": None,
    },
    "cee_civileng_people_faculty": {
        "url": "https://cee.stanford.edu/people/faculty",
        "field": "civileng",
        "profiles": 33,
        "parse": None,
    },
    "cheme_chemeng_people": {
        "url": "https://cheme.stanford.edu/people",
        "field": "chemeng",
        "profiles": 35,
        "parse": None,
    },
    "cheme_chemeng_people_faculty": {
        "url": "https://cheme.stanford.edu/people/faculty",
        "field": "chemeng",
        "profiles": 26,
        "parse": None,
    },
    "chemistry_chemistry_faculty": {
        "url": "https://chemistry.stanford.edu/faculty",
        "field": "chemistry",
        "profiles": 5,
        "parse": None,
    },
    "chemistry_chemistry_people_faculty": {
        "url": "https://chemistry.stanford.edu/people/faculty",
        "field": "chemistry",
        "profiles": 5,
        "parse": None,
    },
    "earth_geoscience_people_faculty": {
        "url": "https://earth.stanford.edu/people/faculty",
        "field": "geoscience",
        "profiles": 154,
        "parse": None,
    },
    "engineering_x_faculty": {
        "url": "https://engineering.stanford.edu/faculty",
        "field": "",
        "profiles": 39,
        "parse": None,
    },
    "engineering_x_people": {
        "url": "https://engineering.stanford.edu/people",
        "field": "",
        "profiles": 38,
        "parse": None,
    },
    "engineering_x_people_faculty": {
        "url": "https://engineering.stanford.edu/people/faculty",
        "field": "",
        "profiles": 39,
        "parse": None,
    },
    "geo_geoscience_faculty": {
        "url": "https://geo.stanford.edu/faculty",
        "field": "geoscience",
        "profiles": 17,
        "parse": None,
    },
    "geo_geoscience_people": {
        "url": "https://geo.stanford.edu/people",
        "field": "geoscience",
        "profiles": 17,
        "parse": None,
    },
    "geo_geoscience_people_faculty": {
        "url": "https://geo.stanford.edu/people/faculty",
        "field": "geoscience",
        "profiles": 17,
        "parse": None,
    },
    "geology_geoscience_faculty": {
        "url": "https://geology.stanford.edu/faculty",
        "field": "geoscience",
        "profiles": 17,
        "parse": None,
    },
    "geology_geoscience_people": {
        "url": "https://geology.stanford.edu/people",
        "field": "geoscience",
        "profiles": 17,
        "parse": None,
    },
    "geology_geoscience_people_faculty": {
        "url": "https://geology.stanford.edu/people/faculty",
        "field": "geoscience",
        "profiles": 17,
        "parse": None,
    },
    "me_mecheng_people": {
        "url": "https://me.stanford.edu/people",
        "field": "mecheng",
        "profiles": 37,
        "parse": None,
    },
    "me_mecheng_people_faculty": {
        "url": "https://me.stanford.edu/people/faculty",
        "field": "mecheng",
        "profiles": 38,
        "parse": None,
    },
    "mse_materials_people_faculty": {
        "url": "https://mse.stanford.edu/people/faculty",
        "field": "materials",
        "profiles": 39,
        "parse": None,
    },
    "physics_physics_faculty": {
        "url": "https://physics.stanford.edu/faculty",
        "field": "physics",
        "profiles": 45,
        "parse": None,
    },
    "physics_physics_people_faculty": {
        "url": "https://physics.stanford.edu/people/faculty",
        "field": "physics",
        "profiles": 45,
        "parse": None,
    },
    "statistics_stats_people": {
        "url": "https://statistics.stanford.edu/people",
        "field": "stats",
        "profiles": 38,
        "parse": None,
    },
    "statistics_stats_people_faculty": {
        "url": "https://statistics.stanford.edu/people/faculty",
        "field": "stats",
        "profiles": 38,
        "parse": None,
    },
    "stats_stats_people": {
        "url": "https://stats.stanford.edu/people",
        "field": "stats",
        "profiles": 38,
        "parse": None,
    },
    "stats_stats_people_faculty": {
        "url": "https://stats.stanford.edu/people/faculty",
        "field": "stats",
        "profiles": 38,
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
