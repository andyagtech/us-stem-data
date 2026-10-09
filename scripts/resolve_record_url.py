#!/usr/bin/env python3
"""Turn a repository's own identifier into a URL a reader can click.

THE PAGE PROMISES THIS. The thesis lists say "every name links to the
university's institutional repository for direct verification", and that
promise is the reason those pages persuade: a reader can check any single
row at its source. For 8,491 records out of 708,393 it was not true. The
harvest had faithfully recorded the repository's internal identifier rather
than a URL, so the link resolved against our own host and 404ed:

    href="10.1184/R1/12755750.v1"
      -> https://phd-demographics.andy-barr.com/10.1184/R1/12755750.v1

Three identifier schemes cover 8,467 of the 8,491, and each was verified
against the live repository before being added here.

WHAT IS DELIBERATELY NOT RESOLVED. Twenty-four records carry something that
is not an identifier at all -- a bare number, or a citation string that
landed in the URL column. There is no safe mapping for those, so they return
None and the page renders the name WITHOUT a link. An unlinked name is
honest. A link that 404s is worse than no link, because it tells the reader
the record cannot be verified while claiming it can.
"""
from __future__ import annotations

import re

#: A DOI. doi.org resolves every registrant, so this needs no per-host table.
DOI = re.compile(r"^10\.\d{4,9}/\S+$")

#: An OAI-PMH identifier: oai:<host>:<local-id>. On a bepress Digital
#: Commons site the local id is <series>-<number> and the page is
#: https://<host>/<series>/<number>. Only hosts confirmed to follow that
#: pattern are listed: the shape is a convention, not a standard, and
#: guessing it for an unknown host would manufacture new dead links.
OAI = re.compile(r"^oai:([^:]+):(.+)$")
BEPRESS_HOSTS = {"pdxscholar.library.pdx.edu"}

#: Michigan State's Islandora identifier.
MSU_ETD = re.compile(r"^etd:(\d+)$")


def resolve_record_url(raw: str) -> str | None:
    """A clickable absolute URL, or None when there is no safe mapping."""
    if not isinstance(raw, str):
        return None
    u = raw.strip()
    if not u:
        return None
    if u.startswith(("http://", "https://")):
        return u
    #: A root-relative path is ours and already works.
    if u.startswith("/"):
        return u
    if DOI.match(u):
        return "https://doi.org/" + u
    m = OAI.match(u)
    if m:
        host, local = m.group(1), m.group(2)
        if host in BEPRESS_HOSTS and "-" in local:
            series, _, number = local.rpartition("-")
            if number.isdigit() and series:
                return f"https://{host}/{series}/{number}"
        return None
    m = MSU_ETD.match(u)
    if m:
        return f"https://d.lib.msu.edu/etd/{m.group(1)}"
    return None
