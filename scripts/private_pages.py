#!/usr/bin/env python3
"""The pages that ship with the site but are not part of it.

WHY. Keeping a page private takes four separate omissions -- the sitemap, the
table of contents, the chat assistant's site map, and robots.txt -- and any one
of them forgotten puts the URL back in public view. analytics.html was
password-protected and still listed in sitemap.xml, contents.html and the
assistant's navigation index, so the URL was discoverable by a crawler, by a
reader of the contents page, and by anyone who asked the assistant where the
traffic figures were. The password held; the privacy did not.

So privacy is declared once, here, and every generator reads it. A page added
to PRIVATE disappears from all four at the next build, and
check_consistency.py fails the build if it reappears in any of them.

A private page is NOT a secret page. The URL being unlisted is not the control
-- the password on the API behind it is. This module keeps the URL from being
advertised; it does not make an unauthenticated endpoint safe.
"""
from __future__ import annotations

# filename -> why it is not part of the public site
PRIVATE: dict[str, str] = {
    "analytics.html": "traffic for this site; the owner's dashboard, password-gated",
    "chat-admin.html": "a retired admin page kept only as a pointer to the CLI",
}

# The <meta> every private page must carry, so that a crawler which finds the
# URL some other way (a referrer header, a shared link) still does not index
# it. build_static_pages.build_sitemap() also keys off the word "noindex".
NOINDEX = '<meta name="robots" content="noindex, nofollow">'


def is_private(name: str) -> bool:
    """True for a site-relative path or bare filename that is private."""
    return name.lstrip("/").split("/")[-1] in PRIVATE


def robots_lines() -> list[str]:
    """Disallow lines for robots.txt, in a stable order."""
    return [f"Disallow: /{name}" for name in sorted(PRIVATE)]
