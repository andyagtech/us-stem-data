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
    "https://lavi-lab.github.io/symposium2026/":
        "A symposium held in China. It is an event programme, not a "
        "US research team, and the people on it were never a roster.",
}

#: A group that has moved. The crawler found the old page; this is the
#: one the professor maintains.
REPLACE_URL: dict[str, str] = {
    "https://pages.mtu.edu/~shene/NSF-3/":
        "https://pages.mtu.edu/~shene/NSF-2/index.html",
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


def apply(rows: list[dict]) -> list[dict]:
    """Drop, redirect and nest. Returns rows in display order."""
    kept = [r for r in rows if r.get("url") not in DROP]
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
