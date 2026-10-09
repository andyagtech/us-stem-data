"""The public-sector PERM tools, and the failure that made them necessary.

Asked which Washington state agencies had sponsored foreign workers and where
those workers came from, the deployed assistant answered that the PERM files
do not record nationality. They do. Given a knowledge file saying so, it then
answered the same question with "87 certified filings" -- the NATIONAL total.
Washington has six.

Prose can tell a model that a figure exists. Only a tool can hand it the right
one. These tests hold the second half of that.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud" / "chat"))

tps = pytest.importorskip("tools_public_sector")


@pytest.fixture(scope="module")
def data():
    d = tps._load()
    if not d:
        pytest.skip("public_employer_perm_compact.json is not built")
    return d


def overview():
    return tps.IMPL["public_sector_overview"]({})


def by_state(name):
    return tps.IMPL["public_sector_by_state"]({"state": name})


def test_both_tools_are_registered_with_the_chat_registry():
    """An extension that fails to import degrades to an absent tool, silently.
    These two must not: without them the model answers state questions from
    the national total rather than saying it cannot."""
    import tools
    assert "public_sector_overview" in tools.DATA_TOOLS
    assert "public_sector_by_state" in tools.DATA_TOOLS


def test_the_overview_is_labelled_national(data):
    o = overview()
    assert o["scope"] == "national"
    assert "national" in o["note"].lower()


def test_a_state_payload_names_its_own_state(data):
    """The scope travels in the payload, not only in the schema description
    the model saw once, because the payload is what it reads back."""
    assert by_state("WA")["scope"] == "Washington"


def test_a_code_and_a_name_reach_the_same_state(data):
    assert by_state("WA") == by_state("Washington")
    assert by_state("mt") == by_state("MONTANA")


def test_a_state_total_is_not_the_national_total(data):
    """The specific wrong answer that prompted this module."""
    nat = overview()["sectors"]["state_agencies"]["filings"]
    wa = by_state("Washington")["sectors"]["state_agencies"]["filings"]
    assert wa < nat


def test_every_state_agency_filing_is_returned_whole(data):
    """There are 87 in the country. A sample would be a choice; the whole
    list is a record, and it is small enough to be one."""
    rows = by_state("Washington")["state_agency_filings"]
    assert rows
    for r in rows:
        for field in ("employer", "job_title", "citizenship", "birth_country",
                      "visa_held", "fiscal_year", "case_number", "source_file"):
            assert field in r


def test_a_filing_carries_the_federal_file_it_came_from(data):
    """A reader checking a claim must be able to open the source."""
    r = by_state("Washington")["state_agency_filings"][0]
    assert r["source_file"].lower().endswith((".xlsx", ".csv"))
    assert r["case_number"]


def test_a_state_with_no_agency_filings_says_so_rather_than_returning_nothing(data):
    """An empty list reads to a model as 'I could not find it', and it then
    reaches for the national figure. The absence has to be stated."""
    mt = by_state("Montana")
    assert mt["state_agency_filings"] == []
    assert "finding, not missing data" in mt["state_agency_filings_note"]


def test_an_unknown_state_is_an_error_not_an_empty_answer(data):
    out = by_state("Atlantis")
    assert "error" in out
    assert out["states_available"]


def test_every_payload_carries_the_window_and_the_caveat(data):
    """Both answers can be quoted directly to a reader, so each has to carry
    that the series ends at FY2024 and that a filing is not a hire."""
    for payload in (overview(), by_state("Washington"), by_state("Montana")):
        assert "FY2024" in payload["window_note"]
        assert "not a hire" in payload["caveat"]


def test_the_page_link_points_at_the_state_section(data):
    assert by_state("Montana")["page"].endswith("#state-MONTANA")
