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


def test_every_declared_section_is_rendered():
    """The group list was assembled from hardcoded indices -- [0, uni, 1, 2] --
    written when there were three sections. A fourth was added later and fell
    off the end: the About group, holding the tip line and the support link,
    rendered on no page at all, and every link check still passed because it
    only followed links that were there. Assembly is by name now."""
    src = _src()
    declared = re.findall(r"\{ title: ['\"](.+?)['\"], items: \[", src)
    assert len(declared) >= 4, declared
    body = re.search(r"function buildGroups\(\).*?\n  \}", src, re.S).group(0)
    # An index list cannot say that it is incomplete. Every declared section
    # must reach the output through a map over `sections`, not a literal list.
    assert "sections.map(" in body, "groups must be assembled from every section"
    assert not re.search(r"\[\s*groupHtml\[\d+\]", body), \
        "groups assembled from hardcoded indices drop any section added later"


def test_a_page_listed_in_two_sections_is_the_same_page():
    """Two pages answer to two steps of the argument and are listed twice. A
    duplicate must be the same href and label, or the rail teaches readers
    that two entries mean two different pages."""
    src = _src()
    entries = re.findall(r"\{ href: '(/[^']+)', label: (\"[^\"]+\"|'[^']+')", src)
    by_href: dict[str, set] = {}
    for href, label in entries:
        by_href.setdefault(href, set()).add(label.strip("\"'"))
    duplicated = {h: l for h, l in by_href.items() if len(l) > 1}
    assert not duplicated, f"same page listed under different labels: {duplicated}"


def test_the_sidebar_script_parses_as_javascript():
    """A backtick inside a CSS comment in the injected stylesheet ended the
    template literal and the whole file became a syntax error -- so no page had
    a sidebar at all. Nothing in a Python suite notices that, and the file is
    injected on every page, so it is the single worst file here to break."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    r = subprocess.run([node, "--check", str(SIDEBAR)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[:400]
