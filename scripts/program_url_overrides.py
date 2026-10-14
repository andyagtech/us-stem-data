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
    #: USF, 2026-10-14. The author sent three laboratories from
    #: electrical engineering and said there would be many more across
    #: STEM. The resolver had found only 4 of 18 fields, because USF
    #: puts its departments on a PATH under one host and names them by
    #: acronym -- /engineering/chbme/, /engineering/imse/ -- and the
    #: pattern list probes subdomains and spelled-out names. Each of
    #: these was read off USF's own department index and checked.
    ("University of South Florida", "cs"): {
        "url": "https://www.usf.edu/engineering/cse/",
        "faculty_url": "https://www.usf.edu/engineering/cse/people/faculty/index.aspx",
        "title": "Computer Science and Engineering, USF",
        "status": "ok", "supplied_by": "read from USF's own department index, 2026-10-14",
    },
    ("University of South Florida", "ai"): {
        "url": "https://www.usf.edu/engineering/cse/",
        "faculty_url": "https://www.usf.edu/engineering/cse/people/faculty/index.aspx",
        "title": "Computer Science and Engineering, USF",
        "status": "ok", "supplied_by": "read from USF's own department index, 2026-10-14",
    },
    ("University of South Florida", "chemeng"): {
        "url": "https://www.usf.edu/engineering/chbme/",
        "faculty_url": "https://www.usf.edu/engineering/chbme/people/index.aspx",
        "title": "Chemical, Biological and Materials Engineering, USF",
        "status": "ok", "supplied_by": "read from USF's own department index, 2026-10-14",
    },
    ("University of South Florida", "battery"): {
        "url": "https://www.usf.edu/engineering/chbme/",
        "faculty_url": "https://www.usf.edu/engineering/chbme/people/index.aspx",
        "title": "Chemical, Biological and Materials Engineering, USF",
        "status": "ok", "supplied_by": "read from USF's own department index, 2026-10-14",
    },
    ("University of South Florida", "civil"): {
        "url": "https://www.usf.edu/engineering/cee/",
        "faculty_url": "https://www.usf.edu/engineering/cee/faculty-staff/index.aspx",
        "title": "Civil and Environmental Engineering, USF",
        "status": "ok", "supplied_by": "read from USF's own department index, 2026-10-14",
    },
    ("University of South Florida", "industrial"): {
        "url": "https://www.usf.edu/engineering/imse/",
        "faculty_url": "https://www.usf.edu/engineering/imse/people/index.aspx",
        "title": "Industrial and Management Systems Engineering, USF",
        "status": "ok", "supplied_by": "read from USF's own department index, 2026-10-14",
    },
    ("University of South Florida", "me"): {
        "url": "https://www.usf.edu/engineering/mae/",
        "faculty_url": "https://www.usf.edu/engineering/mae/people/index.aspx",
        "title": "Mechanical and Aerospace Engineering, USF",
        "status": "ok", "supplied_by": "read from USF's own department index, 2026-10-14",
    },
    ("University of South Florida", "aerospace"): {
        "url": "https://www.usf.edu/engineering/mae/",
        "faculty_url": "https://www.usf.edu/engineering/mae/people/index.aspx",
        "title": "Mechanical and Aerospace Engineering, USF",
        "status": "ok", "supplied_by": "read from USF's own department index, 2026-10-14",
    },
    ("University of South Florida", "biomed"): {
        "url": "https://www.usf.edu/engineering/bme/",
        "faculty_url": "https://www.usf.edu/engineering/bme/faculty-staff/index.aspx",
        "title": "Medical Engineering, USF",
        "status": "ok", "supplied_by": "read from USF's own department index, 2026-10-14",
    },
    ("University of South Florida", "oceanatmos"): {
        "url": "https://www.usf.edu/marine-science/",
        "title": "College of Marine Science, USF",
        "status": "ok", "supplied_by": "read from USF's own site, 2026-10-14",
    },
    ("University of South Florida", "ee"): {
        "url": "https://www.usf.edu/engineering/ece/",
        "faculty_url": "https://www.usf.edu/engineering/ece/faculty-staff/index.aspx",
        "title": "Electrical Engineering, USF",
        "status": "ok", "supplied_by": "read from USF's own department index, 2026-10-14",
    },
    #: Supplied by the author, 2026-10-12. Both sit on a PATH under
    #: the university's own domain rather than a department host, so
    #: the probe never tried them.
    ("Stony Brook", "math"): {
        "url": "https://www.stonybrook.edu/ams/",
        "title": "Applied Mathematics and Statistics, Stony Brook",
        "status": "ok",
        "supplied_by": "author, 2026-10-12",
    },
    ("SMU", "math"): {
        "url": "https://www.smu.edu/dedman/academics/departments/math",
        "title": "Mathematics, Southern Methodist University",
        "status": "ok",
        "supplied_by": "author, 2026-10-12",
    },
    ("University of Wyoming", "petroleum"): {
        "faculty_url": "https://www.uwyo.edu/petroleum/faculty-staff/index.html",
        "source": "supplied by the author, 2026-10-11",
    },
    ("Missouri University of Science and Technology", "chemeng"): {
        "directory_url": "https://chbe.mst.edu/people/facultydirectory/",
        "source": "supplied by the author, 2026-10-11",
        "note": ("the resolver's link included administrative staff; this "
                 "is the faculty directory"),
    },
    ("Missouri University of Science and Technology", "petroleum"): {
        "directory_url": "https://ese.mst.edu/faculty/",
        "source": "supplied by the author, 2026-10-11",
    },
    ("Missouri S&T", "chemeng"): {
        "directory_url": "https://chbe.mst.edu/people/facultydirectory/",
        "source": "supplied by the author, 2026-10-11",
    },
    ("Missouri S&T", "petroleum"): {
        "directory_url": "https://ese.mst.edu/faculty/",
        "source": "supplied by the author, 2026-10-11",
    },
    #: Stanford CS has a faculty page and NO student page; the
    #: resolver had found a programme-overview page and read its
    #: navigation as a roster.
    ("Stanford University", "cs"): {
        "students_url": None,
        "faculty_url": "https://www.cs.stanford.edu/people-cs/faculty-name",
        "no_student_roster": True,
        "source": "supplied by the author, 2026-10-11",
    },
    ("Stanford", "cs"): {
        "students_url": None,
        "faculty_url": "https://www.cs.stanford.edu/people-cs/faculty-name",
        "no_student_roster": True,
        "source": "supplied by the author, 2026-10-11",
    },
    ("Missouri University of Science and Technology", "nuclear"): {
        "students_url": "https://nuclear.mst.edu/people/",
        "source": "supplied by the author, 2026-10-11",
    },
    ("Missouri S&T", "nuclear"): {
        "students_url": "https://nuclear.mst.edu/people/",
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
    """Force every override onto the matching row. Returns how many.

    AN OVERRIDE FOR A ROW THAT DOES NOT EXIST USED TO DO NOTHING. The
    author supplied Stony Brook's Applied Mathematics and SMU's
    Mathematics; neither had a row with that sector, so both were
    silently ignored and the table still said "not resolved" about
    departments whose address was sitting in this file. A missing row
    is now created.
    """
    have = {(r.get("institution"), r.get("sector")) for r in rows}
    for key, o in OVERRIDES.items():
        if key in have:
            continue
        inst, sector = key
        #: an override that only supplies a FACULTY link has no
        #: department page to stand a row up on; adding one left
        #: "status: ok" beside url None, which reads as resolved and
        #: links nowhere.
        if not o.get("url"):
            continue
        rows.append({
            "institution": inst, "sector": sector,
            "status": o.get("status", "ok"),
            "url": o.get("url"), "title": o.get("title"),
            "faculty_url": o.get("faculty_url"),
            "students_url": o.get("students_url"),
            "directory_url": o.get("directory_url"),
            "added_by_override": True,
        })

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
