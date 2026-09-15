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


def test_the_sidebar_is_open_unless_this_reader_hid_it():
    """Open by default: the collapsed class is only ever applied from a stored
    choice, and that choice is only ever written by the reader's click."""
    src = _src()
    assert "if (readHidden()) document.body.classList.add('sb-hidden');" in src
    assert src.count("classList.add('sb-hidden')") == 1
    assert "localStorage.getItem(HIDDEN_KEY) === '1'" in src


def test_the_university_list_is_ranked_by_the_figure_it_shows():
    src = _src()
    assert re.search(r"sort\(\(a, b\) =>\s*\(\(b\.nra \?\? -1\) - \(a\.nra \?\? -1\)\)", src)
    assert "Ranked by NRA share of STEM doctoral completions (IPEDS)." in src


def test_the_homepage_link_row_breaks_only_between_links():
    html = (SIDEBAR.parent / "index.html").read_text()
    row = re.search(r'<p class="hero-note">(.*?)</p>', html, re.S).group(1)
    assert row.count("&middot;") == row.count("&nbsp;&middot; ") > 0
    assert ".hero-note a { white-space: nowrap; }" in html
