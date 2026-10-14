"""The multi-university pages must ask for a university before doing anything.

`departments-stem.html` and `departments-nonstem.html` carry the national charts, but the name lists,
funding, enrolment and H-1B panels are all per-university.  Before compaction
those pages shipped four toggles that looked live: clicking one flipped
`aria-checked` and rewrote the body classes, and nothing appeared, because
there was no university selected to show a panel for.  It read as broken.

The fix is the `no-uni` body class.  These tests pin the three halves of it —
the class is on at load, the prompt is in the markup, and every toggle refuses
while it is set — so a future edit to the generator cannot quietly undo it.
"""
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1] / "site"
TOGGLES = ("toggleMs", "toggleFunding", "toggleEnrollment", "toggleH1b")


def _page(name):
    p = SITE / name
    if not p.exists():
        pytest.skip(f"{name} not built")
    return p.read_text(encoding="utf-8", errors="replace")


@pytest.mark.parametrize("page", ["departments-stem.html", "departments-nonstem.html"])
def test_the_page_loads_asking_for_a_university(page):
    html = _page(page)
    body = html[html.index("<body"):html.index(">", html.index("<body")) + 1]
    assert "no-uni" in body, f"{page} does not start in the no-uni state: {body}"
    assert "Pick a university to begin" in html


@pytest.mark.parametrize("page", ["departments-stem.html", "departments-nonstem.html"])
def test_every_toggle_refuses_without_a_university(page):
    html = _page(page)
    for fn in TOGGLES:
        i = html.find(f"function {fn}(")
        assert i != -1, f"{fn} missing from {page}"
        head = html[i:i + 260]
        assert "no-uni" in head and "return" in head, (
            f"{fn} in {page} runs with no university selected:\n{head}"
        )


def test_choosing_a_university_lifts_the_block():
    html = _page("departments-stem.html")
    i = html.find("function showUni(")
    assert i != -1
    assert "classList.remove('no-uni')" in html[i:i + 300], (
        "showUni does not clear no-uni, so the toggles would stay dead"
    )


def test_a_university_page_is_not_blocked():
    p = SITE / "universities" / "mit.html"
    if not p.exists():
        pytest.skip("university pages not built")
    html = p.read_text(encoding="utf-8", errors="replace")
    body = html[html.index("<body"):html.index(">", html.index("<body")) + 1]
    assert "no-uni" not in body, f"mit.html should not block its own toggles: {body}"
