"""The baked ids and the runtime ids have to be the same ids.

Anchor targets come from two places that must agree exactly:
add_section_anchors.py bakes them into the HTML ahead of time, and
site/anchors.js computes them again in the browser for headings the baker
did not reach. When the two disagree, the sidebar links to one name and the
page answers to the other, and the link scrolls nowhere.

They diverged once already: the baker reads raw source with entities intact
while anchors.js reads textContent, where the browser has already decoded
them, so any heading containing an entity got two different slugs.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from add_section_anchors import BLOCK_CLASSES, slugify  # noqa: E402


@pytest.mark.parametrize("text,want", [
    # The entity case that actually broke.
    ("The Master&rsquo;s Expansion", "the-master-s-expansion"),
    ("Caf&eacute; &amp; Co", "cafe-co"),
    ("R&amp;D vs American PhDs", "r-d-vs-american-phds"),
    # Leading enumerators are dropped so reordering a page does not rename
    # every anchor on it.
    ("1. Institutions", "institutions"),
    ("A. Full Pipeline", "full-pipeline"),
    ("6. Outcomes", "outcomes"),
    # The enumerator is only dropped when whitespace follows it, so a
    # heading that is bare punctuation keeps its digit rather than
    # slugging to nothing.
    ("6.", "6"),
    # Accents fold; punctuation separates.
    ("Who files the visas?", "who-files-the-visas"),
    ("Zürich, then and now", "zurich-then-and-now"),
    ("  spaced   out  ", "spaced-out"),
])
def test_slug_matches_the_runtime_rules(text, want):
    assert slugify(text) == want


def test_long_headings_cut_on_a_word_boundary():
    s = slugify("This is an estimate and here is exactly what it rests upon")
    assert len(s) <= 48
    assert not s.endswith("-")
    assert s == s.rstrip("-")


def test_the_two_implementations_share_one_rule_set():
    """anchors.js documents itself as kept in step with the Python slugify.

    Not a behavioural test -- it pins the pieces that have to move together,
    so a change to one side is visibly a change to a shared contract.
    """
    js = (ROOT / "site" / "anchors.js").read_text(encoding="utf-8")
    assert "add_section_anchors.py" in js, (
        "anchors.js no longer names the script it must agree with"
    )
    for rule in (r"replace(/\s+/g, ' ')", "normalize('NFKD')",
                 "replace(/[^a-z0-9]+/g, '-')", "48"):
        assert rule in js, f"anchors.js lost the shared rule: {rule}"


def test_chart_section_counts_as_a_block():
    """A heading inside one is addressed by the section, not by a twin id.

    'chart-section' is the commonest section class on the site, and it was
    absent here while plain 'section' was present -- classes are matched as
    whole names, so it never matched. Headings inside those sections were
    treated as having no block and got ids of their own beside the section's,
    e.g. 'institutions-2' next to 'institutions'.
    """
    assert "chart-section" in BLOCK_CLASSES


def test_no_page_ships_a_numbered_twin_id():
    """A '-2' id is the signature of that bug, so no page should carry one."""
    offenders = []
    for page in (ROOT / "site").glob("*.html"):
        for m in re.finditer(r'id="([a-z0-9-]+?)-(\d+)"', page.read_text(
                encoding="utf-8", errors="replace")):
            base = m.group(1)
            if f'id="{base}"' in page.read_text(encoding="utf-8", errors="replace"):
                offenders.append(f"{page.name}#{m.group(0)}")
    assert not offenders, (
        "these ids duplicate one already on the page: " + ", ".join(offenders[:6])
    )
