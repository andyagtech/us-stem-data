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
    "astro_physics_directory": {
        "url": "https://astro.arizona.edu/directory",
        "field": "physics",
        "profiles": 542,
        "parse": None,
    },
    "astro_physics_people_all_faculty": {
        "url": "https://astro.arizona.edu/people/all-faculty",
        "field": "physics",
        "profiles": 99,
        "parse": None,
    },
    "astro_physics_people_faculty": {
        "url": "https://astro.arizona.edu/people/faculty",
        "field": "physics",
        "profiles": 90,
        "parse": None,
    },
    "astro_physics_people_faculty_directory": {
        "url": "https://astro.arizona.edu/people/faculty-directory",
        "field": "physics",
        "profiles": 537,
        "parse": None,
    },
    "astro_physics_people_index_html": {
        "url": "https://astro.arizona.edu/people/index.html",
        "field": "physics",
        "profiles": 537,
        "parse": None,
    },
    "astro_physics_people_professors": {
        "url": "https://astro.arizona.edu/people/professors",
        "field": "physics",
        "profiles": 537,
        "parse": None,
    },
    "bme_biomed_faculty_staff": {
        "url": "https://bme.arizona.edu/faculty-staff",
        "field": "biomed",
        "profiles": 52,
        "parse": None,
    },
    "bme_biomed_people": {
        "url": "https://bme.arizona.edu/people",
        "field": "biomed",
        "profiles": 62,
        "parse": None,
    },
    "bme_biomed_people_all_faculty": {
        "url": "https://bme.arizona.edu/people/all-faculty",
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
    "bme_biomed_people_faculty_directory": {
        "url": "https://bme.arizona.edu/people/faculty-directory",
        "field": "biomed",
        "profiles": 62,
        "parse": None,
    },
    "bme_biomed_people_index_html": {
        "url": "https://bme.arizona.edu/people/index.html",
        "field": "biomed",
        "profiles": 62,
        "parse": None,
    },
    "bme_biomed_people_professors": {
        "url": "https://bme.arizona.edu/people/professors",
        "field": "biomed",
        "profiles": 62,
        "parse": None,
    },
    "cs_ai_about_faculty": {
        "url": "https://cs.arizona.edu/about/faculty",
        "field": "ai",
        "profiles": 29,
        "parse": None,
    },
    "cs_ai_people": {
        "url": "https://cs.arizona.edu/people",
        "field": "ai",
        "profiles": 94,
        "parse": None,
    },
    "cs_ai_people_all_faculty": {
        "url": "https://cs.arizona.edu/people/all-faculty",
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
    "cs_ai_people_faculty_directory": {
        "url": "https://cs.arizona.edu/people/faculty-directory",
        "field": "ai",
        "profiles": 94,
        "parse": None,
    },
    "cs_ai_people_index_html": {
        "url": "https://cs.arizona.edu/people/index.html",
        "field": "ai",
        "profiles": 94,
        "parse": None,
    },
    "cs_ai_people_professors": {
        "url": "https://cs.arizona.edu/people/professors",
        "field": "ai",
        "profiles": 94,
        "parse": None,
    },
    "geo_geoscience_about_people_faculty": {
        "url": "https://geo.arizona.edu/about/people/faculty",
        "field": "geoscience",
        "profiles": 52,
        "parse": None,
    },
    "geo_geoscience_faculty": {
        "url": "https://geo.arizona.edu/faculty",
        "field": "geoscience",
        "profiles": 52,
        "parse": None,
    },
    "geo_geoscience_people": {
        "url": "https://geo.arizona.edu/people",
        "field": "geoscience",
        "profiles": 167,
        "parse": None,
    },
    "geo_geoscience_people_all_faculty": {
        "url": "https://geo.arizona.edu/people/all-faculty",
        "field": "geoscience",
        "profiles": 167,
        "parse": None,
    },
    "geo_geoscience_people_faculty": {
        "url": "https://geo.arizona.edu/people/faculty",
        "field": "geoscience",
        "profiles": 52,
        "parse": None,
    },
    "geo_geoscience_people_faculty_directory": {
        "url": "https://geo.arizona.edu/people/faculty-directory",
        "field": "geoscience",
        "profiles": 167,
        "parse": None,
    },
    "geo_geoscience_people_index_html": {
        "url": "https://geo.arizona.edu/people/index.html",
        "field": "geoscience",
        "profiles": 167,
        "parse": None,
    },
    "geo_geoscience_people_professors": {
        "url": "https://geo.arizona.edu/people/professors",
        "field": "geoscience",
        "profiles": 167,
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
    "mining_mining_faculty_staff": {
        "url": "https://mining.arizona.edu/faculty-staff",
        "field": "mining",
        "profiles": 40,
        "parse": None,
    },
    "mining_mining_people": {
        "url": "https://mining.arizona.edu/people",
        "field": "mining",
        "profiles": 43,
        "parse": None,
    },
    "mining_mining_people_all_faculty": {
        "url": "https://mining.arizona.edu/people/all-faculty",
        "field": "mining",
        "profiles": 43,
        "parse": None,
    },
    "mining_mining_people_faculty": {
        "url": "https://mining.arizona.edu/people/faculty",
        "field": "mining",
        "profiles": 43,
        "parse": None,
    },
    "mining_mining_people_faculty_directory": {
        "url": "https://mining.arizona.edu/people/faculty-directory",
        "field": "mining",
        "profiles": 43,
        "parse": None,
    },
    "mining_mining_people_index_html": {
        "url": "https://mining.arizona.edu/people/index.html",
        "field": "mining",
        "profiles": 43,
        "parse": None,
    },
    "mining_mining_people_professors": {
        "url": "https://mining.arizona.edu/people/professors",
        "field": "mining",
        "profiles": 43,
        "parse": None,
    },
    "mse_materials_faculty_staff": {
        "url": "https://mse.arizona.edu/faculty-staff",
        "field": "materials",
        "profiles": 44,
        "parse": None,
    },
    "mse_materials_people": {
        "url": "https://mse.arizona.edu/people",
        "field": "materials",
        "profiles": 44,
        "parse": None,
    },
    "mse_materials_people_all_faculty": {
        "url": "https://mse.arizona.edu/people/all-faculty",
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
    "mse_materials_people_faculty_directory": {
        "url": "https://mse.arizona.edu/people/faculty-directory",
        "field": "materials",
        "profiles": 44,
        "parse": None,
    },
    "mse_materials_people_index_html": {
        "url": "https://mse.arizona.edu/people/index.html",
        "field": "materials",
        "profiles": 44,
        "parse": None,
    },
    "mse_materials_people_professors": {
        "url": "https://mse.arizona.edu/people/professors",
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
    "physics_physics_people_all_faculty": {
        "url": "https://physics.arizona.edu/people/all-faculty",
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
    "physics_physics_people_faculty_directory": {
        "url": "https://physics.arizona.edu/people/faculty-directory",
        "field": "physics",
        "profiles": 249,
        "parse": None,
    },
    "physics_physics_people_index_html": {
        "url": "https://physics.arizona.edu/people/index.html",
        "field": "physics",
        "profiles": 249,
        "parse": None,
    },
    "physics_physics_people_professors": {
        "url": "https://physics.arizona.edu/people/professors",
        "field": "physics",
        "profiles": 249,
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
    "stat_stats_people_all_faculty": {
        "url": "https://stat.arizona.edu/people/all-faculty",
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
    "stat_stats_people_faculty_directory": {
        "url": "https://stat.arizona.edu/people/faculty-directory",
        "field": "stats",
        "profiles": 125,
        "parse": None,
    },
    "stat_stats_people_index_html": {
        "url": "https://stat.arizona.edu/people/index.html",
        "field": "stats",
        "profiles": 125,
        "parse": None,
    },
    "stat_stats_people_professors": {
        "url": "https://stat.arizona.edu/people/professors",
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
    "statistics_stats_people_all_faculty": {
        "url": "https://statistics.arizona.edu/people/all-faculty",
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
    "statistics_stats_people_faculty_directory": {
        "url": "https://statistics.arizona.edu/people/faculty-directory",
        "field": "stats",
        "profiles": 125,
        "parse": None,
    },
    "statistics_stats_people_index_html": {
        "url": "https://statistics.arizona.edu/people/index.html",
        "field": "stats",
        "profiles": 125,
        "parse": None,
    },
    "statistics_stats_people_professors": {
        "url": "https://statistics.arizona.edu/people/professors",
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
