#!/usr/bin/env python3
"""Hand corrections to the crawled lab list.

WHY THIS EXISTS. The crawler reaches a URL and reads who is listed on
it. It cannot tell that a page is a conference rather than a team, that
a professor has moved his group to a newer page, or that two entries
are the same group seen twice. A reader can, and those judgements
belong somewhere reviewable rather than inside a regex.

Applied LAST, after ranking, so a later crawl cannot undo one.
"""
from __future__ import annotations

#: Dropped, with the reason. A URL here is excluded from the table.
#: The 11-member Rubinstein Lab the author rejected is no longer named
#: here: --min-members 12 in the ranker now covers that case as a rule
#: rather than one hand-written exception.
DROP: dict[str, str] = {
    "https://rubenstein.group":
        "The extractor read this site's PUBLICATION CO-AUTHORS, not "
        "its roster: Stony Brook collaborators off recent papers, plus "
        "'Latest Publications' and 'Past Editions' counted as people. "
        "The group's actual students are at /people/ and are visibly "
        "mixed. The 45.5% was measured on the wrong list.",
    "https://lavi-lab.github.io/symposium2026/":
        "A symposium held in China. It is an event programme, not a "
        "US research team, and the people on it were never a roster.",
}

#: A group that has moved. The crawler found the old page; this is the
#: one the professor maintains.
REPLACE_URL: dict[str, str] = {
    #: Shene's move is now recorded in the crawl data itself, with the
    #: new page's own member count, rather than swapped in at render
    #: time over figures read from the old one.
}

#: A second page worth linking beside the roster, and what it shows.
ALSO_SEE: dict[str, tuple[str, str]] = {
    "https://pages.mtu.edu/~shene/NSF-2/index.html": (
        "https://pages.mtu.edu/~shene/PUBLICATIONS/index.html",
        "Publications"),
}

#: child URL -> parent URL. A group that sits inside a larger one is
#: shown indented under it rather than as a separate row, because
#: listing both as peers counts the same laboratory twice.
PARENT: dict[str, str] = {
    "https://users.cs.duke.edu/~bdhingra/#prospective":
        "https://nlplab.cs.duke.edu/people/",
}


#: ONE NAME PER UNIVERSITY.
#: The directory was assembled by four crawlers that learned an institution's
#: name from different places -- the IPEDS name on a department page, the short
#: name in this site's own tables, whatever a lab's own page called itself. So
#: the same university arrived under two strings, and the published count of
#: institutions counted both. "94 labs at 39 universities" was really 36: the
#: list carried Stanford twice, Georgia Tech twice and the University of
#: Washington twice.
#:
#: The right-hand side is the name the rest of this site uses.
CANONICAL_INSTITUTION = {
    "Stanford": "Stanford University",
    "Georgia Tech": "Georgia Institute of Technology-Main Campus",
    "UW Seattle": "University of Washington-Seattle Campus",
}


def canonical_institution(name: str) -> str:
    return CANONICAL_INSTITUTION.get((name or "").strip(), (name or "").strip())


def apply(rows: list[dict]) -> list[dict]:
    """Drop, redirect, canonicalise the institution, and nest.

    Returns rows in display order.
    """
    kept = [r for r in rows if r.get("url") not in DROP]
    for r in kept:
        if r.get("institution"):
            r["institution"] = canonical_institution(r["institution"])
    for r in kept:
        new = REPLACE_URL.get(r.get("url", ""))
        if new:
            r["url"] = new
        extra = ALSO_SEE.get(r.get("url", ""))
        if extra:
            r["also_see"] = {"url": extra[0], "label": extra[1]}

    by_url = {r.get("url"): r for r in kept}
    out, children = [], {}
    for r in kept:
        parent = PARENT.get(r.get("url", ""))
        if parent and parent in by_url:
            children.setdefault(parent, []).append(r)
        else:
            out.append(r)
    #: a child follows its parent immediately, marked for indenting
    ordered: list[dict] = []
    for r in out:
        ordered.append(r)
        for c in children.get(r.get("url"), []):
            c["child_of"] = r.get("url")
            ordered.append(c)
    return ordered
