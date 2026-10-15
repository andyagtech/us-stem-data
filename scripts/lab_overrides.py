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
#: ONE UNIVERSITY, ONE NAME. The crawlers learn an institution's name
#: from whatever the page gave them, so one university arrives under
#: several spellings and gets counted several times. The published
#: figure said 39 universities when it was 36 -- Stanford, Georgia Tech
#: and UW each appeared twice -- and this map was written to fix those
#: three by hand. It then happened again, on the next crawl, with
#: "UC Santa Barbara" beside "University of California-Santa Barbara".
#:
#: A HAND MAP CANNOT KEEP UP, so the rule is derived instead:
#: institution_keys resolves a spelling to a record key through the
#: IPEDS UNITID join, and the registered name for that key is the one
#: the list uses. The map below is only for universities OUTSIDE the
#: 106 in the thesis record, which have no key to resolve to.
CANONICAL_INSTITUTION: dict[str, str] = {}


def canonical_institution(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return name
    if name in CANONICAL_INSTITUTION:
        return CANONICAL_INSTITUTION[name]
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import institution_keys
    key = institution_keys.key_for(name)
    return institution_keys.official_name(key) if key else name


#: LABS THE AUTHOR REQUIRES IN THE TABLE, whatever the thresholds say.
#:
#: WHY THIS EXISTS AND WHY IT IS SAFE. DROP has always let a person
#: take a row OUT after looking at the page. This is the same power in
#: the other direction, and it was asked for in the same terms: "those
#: may not pass the threshold but I demand they be added. I will have
#: more and more special cases."
#:
#: WHAT IT DOES NOT DO. It does not invent a figure. A row here is
#: still measured by the same extractor, the same classifier and the
#: same denominator as every other row; the override decides whether
#: the row is PUBLISHED, never what it says. A URL that was never
#: crawled, or whose page carries no readable roster, cannot be forced
#: in by writing it here -- there would be nothing to show.
#:
#: AND IT SAYS SO ON THE ROW. Every row added this way carries
#: included_by="author", because a table that mixes "cleared a stated
#: threshold" with "the author required it" and does not say which is
#: which is making a claim about the second that only the first earns.
#: The Benjamini-Hochberg correction is computed over the groups
#: TESTED, and is unaffected either way.
#: url -> (institution, field, why). The institution is written down
#: rather than guessed from the host, because a lab on its own domain
#: tells a crawler nothing about which university pays for it.
#:
#: scripts/harvest_required_labs.py fetches anything here that the
#: crawl has not already reached and merges the measurement into the
#: pool, so this one list is the whole interface: add a URL, run that
#: script, rebuild.
ALWAYS_INCLUDE: dict[str, tuple] = {
    "https://people.umass.edu/fanwar/": (
        "University of Massachusetts-Amherst", "ee",
        "Supplied by the author, 2026-10-14."),
    "https://people.cs.umass.edu/~amir/Research.html": (
        "University of Massachusetts-Amherst", "cs",
        "Supplied by the author, 2026-10-14."),
    "https://people.cs.umass.edu/~shiqingma/": (
        "University of Massachusetts-Amherst", "cs",
        "Supplied by the author, 2026-10-14. Six members, which is "
        "below every floor this project has used."),
}


def apply(rows: list[dict], all_tested: list | None = None) -> list[dict]:
    """Drop, redirect, canonicalise the institution, and nest.

    `all_tested` is every group the ranker measured. It is needed only
    to honour ALWAYS_INCLUDE: a required lab was measured like any
    other and simply did not clear a threshold, so its row is already
    in there and is pulled across rather than invented.

    Returns rows in display order.
    """
    kept = [r for r in rows if r.get("url") not in DROP]
    if ALWAYS_INCLUDE:
        have = {r.get("url") for r in kept}
        for r in all_tested or ():
            u = r.get("url")
            if u in ALWAYS_INCLUDE and u not in have and u not in DROP:
                r = dict(r)
                r["included_by"] = "author"
                r["included_because"] = ALWAYS_INCLUDE[u][2]
                kept.append(r)
                have.add(u)
        missing = [u for u in ALWAYS_INCLUDE if u not in have]
        if missing and all_tested is not None:
            #: LOUD, NOT SILENT. A required lab that is not in the
            #: tested set was never measured -- the page would not
            #: answer, or carried no roster, or the crawl has not
            #: reached it. Printing it is the only way the author
            #: learns that what he asked for is not there.
            print(f"  lab_overrides: {len(missing)} required lab(s) are "
                  f"not in the tested set and cannot be shown:")
            for u in missing:
                print(f"    {u}")
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
