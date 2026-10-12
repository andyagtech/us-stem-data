#!/usr/bin/env python3
"""Penn State department graduate-student directories.

GPMS gives FACULTY. The author also found that departments publish
their own graduate-student directories at a predictable path --
abe.psu.edu/directory/graduate-students -- and those are the people
a lab actually hires.

The hosts follow from the department abbreviation, so the list is
enumerable rather than crawled. A host that does not answer is
skipped; nothing here guesses a name.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harvest_lab_rosters import best_names                    # noqa: E402

INSTITUTION = "Pennsylvania State University-Main Campus"

#: department host -> the field key this site already uses
DEPARTMENTS = {
    "abe": "agriculture", "aero": "aerospace", "bme": "biomed",
    "cbe": "chemeng", "ceee": "civileng", "chemistry": "chemistry",
    "ems": "geoscience", "esm": "mecheng", "ist": "ai",
    "matse": "materials", "me": "mecheng", "mne": "mining",
    "nuce": "nuclear", "phys": "physics", "stat": "stats",
    "math": "math", "eecs": "ee", "ee": "ee", "cse": "ai",
    "ie": "industrial", "bee": "agriculture", "agecon": "agriculture",
    "ento": "biology", "plantpath": "biology", "hort": "agriculture",
    "foodscience": "agriculture", "vbs": "biology",
    "geosc": "geoscience", "meteo": "geoscience", "energy": "energy",
}
PATHS = ("/directory/graduate-students", "/directory/students",
         "/people/graduate-students", "/graduate-students")


def targets() -> list[dict]:
    out = []
    for host, field in DEPARTMENTS.items():
        for path in PATHS:
            out.append({
                "url": f"https://{host}.psu.edu{path}",
                "institution": INSTITUTION,
                "department_field": field,
                "title": f"{host.upper()} graduate students, Penn State",
                "roster_kind": "department graduate students",
            })
    return out


def parse(url: str, html: str) -> list[str] | None:
    if ".psu.edu" not in url:
        return None
    #: these are ordinary directory pages; the generic extractor reads
    #: them well once it is pointed at the right URL, which is the
    #: whole value of enumerating the hosts
    names = best_names(html)
    return names or None
