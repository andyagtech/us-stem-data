#!/usr/bin/env python3
"""Two properties of site/sidebar.js that broke on the pages people actually see.

Both passed every render check at the time, because the checks loaded
/index.html rather than "/", and measured a table's box rather than its rows.
These read the script itself, so they hold whatever a browser check loads.
"""
from __future__ import annotations

import re
from pathlib import Path

SIDEBAR = Path(__file__).resolve().parents[1] / "site" / "sidebar.js"


def _src() -> str:
    return SIDEBAR.read_text()


def test_the_root_url_is_the_homepage_and_not_a_drawer_page():
    """ "/" fell back to stem.html; when stem.html became a drawer page the
    site's front door lost its sidebar -- at "/" only."""
    src = _src()
    fallback = re.search(r"const currentPage = .*?\|\|\s*'([^']+)'", src).group(1)
    drawer = set(re.findall(r"'([^']+\.html)'",
                            re.search(r"DRAWER_PAGES = new Set\(\[(.*?)\]\)", src, re.S).group(1)))
    assert fallback == "index.html"
    assert fallback not in drawer


def test_tables_are_never_made_block_boxes():
    """table{display:block} keeps the box at 100% but lays rows out at their
    content width: a three-column table stopped three-quarters of the way
    across its card. Overflowing tables are wrapped in a scroll box instead."""
    css = re.sub(r"/\*.*?\*/", "", _src(), flags=re.S)
    assert not re.search(r"(^|[\s,}])table\s*\{[^}]*display\s*:\s*block", css)
    assert "function wrapOverflowingTables" in _src()
