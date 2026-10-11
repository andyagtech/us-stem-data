#!/usr/bin/env python3
"""URLs supplied by hand, which the resolver must never overwrite.

WHY THIS EXISTS. Automated roster detection has a ceiling and these two
Lehigh pages are where it sits:

  /ise/students                          24 person-shaped strings
  /ise/faculty/post-docs-and-phd-students 20 person-shaped strings

The first is a page of course listings and student groups. The second
is the actual roster. Every test available here -- the heading
extractor, the text-node extractor, the profile-link extractor, a
count, a stoplist -- scores them the same or scores the WRONG one
higher, because the real roster's names sit in plain text beside
"Harold S. Mohler Laboratory" and "Back To Top".

A person looked at both pages and knew in a second. So when the author
supplies a URL it is recorded here and treated as authoritative. The
resolver merges around these rather than through them; re-running a
crawl cannot silently replace a checked link with a guessed one.

Each entry says who supplied it and when, because an override is a
claim by a person and should carry their name the way a figure carries
its dataset.
"""
from __future__ import annotations

#: (institution, sector) -> fields to force
OVERRIDES: dict[tuple[str, str], dict] = {
    ("University of Wyoming", "petroleum"): {
        "faculty_url": "https://www.uwyo.edu/petroleum/faculty-staff/index.html",
        "source": "supplied by the author, 2026-10-11",
    },
    ("University of Tulsa", "petroleum"): {
        "faculty_url": "https://utulsa.edu/departments/petroleum-engineering/",
        "no_student_roster": True,
        "source": "supplied by the author, 2026-10-11",
        "note": ("ten named professors, each written '<name>, Ph.D.', which "
                 "none of the three extractors reads -- they look for a "
                 "heading, a bare text node or a profile link. The author "
                 "also checked that this department publishes no student "
                 "list, so the card should say so rather than leave the "
                 "absence ambiguous."),
    },
    ("Lehigh University", "industrial"): {
        "students_url": ("https://engineering.lehigh.edu/ise/faculty/"
                         "post-docs-and-phd-students"),
        "source": "supplied by the author, 2026-10-11",
        "note": ("the resolver had found /ise/students, which lists course "
                 "listings and student groups and no people"),
    },
}


def apply_to(rows: list[dict]) -> int:
    """Force every override onto the matching row. Returns how many."""
    n = 0
    for r in rows:
        key = (r.get("institution"), r.get("sector"))
        o = OVERRIDES.get(key)
        if not o:
            continue
        for field, value in o.items():
            if field in ("source", "note", "no_student_roster"):
                continue
            r[field] = value
        #: A CHECKED ABSENCE IS A RESULT. Where the author has confirmed
        #: a department publishes no student list, clear any guess and
        #: record that somebody looked -- otherwise the next crawl finds
        #: a plausible-looking page and the absence quietly becomes a
        #: wrong link.
        if o.get("no_student_roster"):
            r["students_url"] = None
            r["student_roster_checked_absent"] = o.get("source", True)
        r["overridden_by_hand"] = o.get("source", "hand-supplied")
        if o.get("note"):
            r["override_note"] = o["note"]
        n += 1
    return n
