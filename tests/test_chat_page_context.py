#!/usr/bin/env python3
"""The assistant has to know what page the reader is on.

The widget sends `location.pathname`: "/" on the homepage and
"/departments-stem.html" elsewhere. The site map keys those "/index" and
"/departments-stem". They never joined, so the system prompt said "the user is
currently on /" -- a path appearing nowhere in the map it had just been given.

The homepage is the most-visited page on the site, 143 of 611 views in the
fortnight after it was shared. Asked "how much federal funding goes to THESE
programs?" from it, the assistant deflected: it could not say what "these"
referred to, because it could not say what page it was looking at.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from chat import prompt as P                                        # noqa: E402
from chat import data_store as ds                                   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.mark.parametrize("sent,expected", [
    ("/", "/index"),
    ("/index.html", "/index"),
    ("/index", "/index"),
    ("/departments-stem.html", "/departments-stem"),
    ("/lab-directory", "/lab-directory"),
    ("/query.html?x=1", "/query"),
    ("/query.html#tables", "/query"),
    ("/universities/mit.html", "/universities/mit"),
])
def test_the_widgets_path_becomes_the_site_maps_path(sent, expected):
    assert P.normalise_page_path(sent) == expected


def test_every_normalised_path_resolves_in_the_site_map():
    """The join is the point. A page the widget can report but the map does
    not carry gives the model a location it cannot identify.

    The allowance is build_site_map.EXCLUDE -- the single place a page is
    declared absent from the assistant's navigation -- rather than a list
    kept here, which would drift the moment a page moved. Private pages and
    redirect stubs are already in that set."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_site_map import EXCLUDE                              # noqa: PLC0415
    known = {p["path"] for p in ds.site_map().get("pages", [])}
    unresolved = [f.name for f in sorted((ROOT / "site").glob("*.html"))
                  if f.name not in EXCLUDE
                  and P.normalise_page_path("/" + f.name) not in known]
    assert unresolved == [], unresolved


def test_the_homepage_is_named_not_just_located():
    s = P.page_suffix({"path": "/"})
    assert "currently on /" in s
    assert "Landing page" in s, s


def test_a_university_page_is_named_from_its_path_alone():
    """The widget does not always send university_key; the path carries it."""
    s = P.page_suffix({"path": "/universities/mit.html"})
    assert "the page for" in s and "mit" in s


def test_the_demonstrative_rule_is_stated():
    s = P.page_suffix({"path": "/lab-directory"})
    assert "these programmes" in s
    assert "rather than asking which they meant" in s


def test_the_university_clause_does_not_land_mid_sentence():
    """It used to be appended after the instruction, giving
    '...rather than asking which they meant, which is the page for MIT'."""
    s = P.page_suffix({"path": "/universities/mit.html"})
    assert s.index("the page for") < s.index("A demonstrative")


def test_an_unknown_path_still_produces_a_usable_suffix():
    s = P.page_suffix({"path": "/no-such-page.html"})
    assert s.startswith("[The user is currently on /no-such-page.html")
    assert "A demonstrative" in s


def test_the_page_block_stays_last_in_the_prompt():
    """Provider caching keys on the longest common prefix; the only
    request-specific part must come last."""
    full = P.build_system_prompt({"path": "/lab-directory"})
    assert full.rstrip().endswith("auto:true.]")


# --- the retry, for when the model has the page and hedges anyway ----------

from chat import handler as H                                       # noqa: E402

HEDGE = "Could you clarify which programs or universities you're interested in?"


def test_a_hedge_about_a_known_page_is_retried():
    assert H._dodged_with_a_question(
        HEDGE, "How much federal money goes into these programmes?", {"path": "/"})


def test_a_hedge_on_a_university_page_is_retried():
    assert H._dodged_with_a_question(
        "I need to know which departments you are referring to.",
        "What is the foreign share in these departments?",
        {"path": "/universities/mit.html"})


def test_a_real_answer_is_not_retried():
    assert not H._dodged_with_a_question(
        "In 2025, 63.1% went to non-residents.",
        "What share of these programmes go to foreigners?", {"path": "/"})


def test_a_question_with_no_demonstrative_is_left_alone():
    """Asking which year is a fair question; the page does not carry a year."""
    assert not H._dodged_with_a_question(
        "Could you clarify which year you mean?",
        "How many visas were issued?", {"path": "/"})


def test_no_page_means_no_retry():
    assert not H._dodged_with_a_question(
        HEDGE, "How much federal money goes into these programmes?", None)
