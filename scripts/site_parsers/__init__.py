"""Parsers for sites whose rosters the generic extractor cannot read.

Most lab pages yield to one extractor with the roster's own
annotations stripped. A few do not, and they are worth writing by
hand because they are STRUCTURED: a university that publishes a
directory system has every programme behind one URL pattern, so one
parser reaches hundreds of rosters rather than one.

Each module exposes:
    targets() -> list[dict]   the URLs it knows how to reach
    parse(url, html) -> list[str] | None   names, or None if not mine
"""
