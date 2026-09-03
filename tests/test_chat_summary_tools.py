#!/usr/bin/env python3
"""Tests for the summary artifact and the tools that let the assistant read it.

The assistant's failure mode is silence, not error: an extension that cannot
import is logged and skipped, and the tool it carried simply is not offered.
Nothing fails, nobody is told, and the assistant answers a question it should
have looked up. Several of these tests exist only to make that loud.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "site" / "data" / "summary.json"
sys.path.insert(0, str(ROOT / "cloud"))


@pytest.fixture(scope="module")
def tools():
    return pytest.importorskip("chat.tools")


@pytest.fixture(scope="module")
def summary():
    if not SUMMARY.exists():
        pytest.skip("summary.json not built")
    return json.loads(SUMMARY.read_text())


def test_every_extension_loads(tools):
    """A tool lost to an import error is invisible: no error, just absent.

    tools_levels.py imported data_store without the package fallback its four
    sibling extensions use, so under the package layout it raised, was logged
    at WARNING and dropped -- taking level_rankings with it. That tool's own
    description calls it "the only tool on this assistant that can answer a
    master's question", and the master's expansion is the central thesis here.
    """
    names = {t["function"]["name"] for t in tools.TOOLS}
    for expected in ("level_rankings", "pipeline_for", "by_state",
                     "coverage_for", "find_departments",
                     "key_figures", "compare_institutions"):
        assert expected in names, f"{expected} is missing from TOOLS"


def test_every_figure_carries_a_limit(summary):
    """A summary is where caveats go to die. These have to travel."""
    assert summary["figures"], "no figures built"
    for key, fig in summary["figures"].items():
        assert fig["limit"].strip(), f"{key} has no limit"
        assert len(fig["limit"]) > 40, f"{key}'s limit is too short to be one"
        assert fig["dataset"] and fig["path"], f"{key} is not traceable"


def test_no_figure_is_missing(summary):
    """A path that stops resolving must fail the build, not vanish quietly."""
    assert summary["missing"] == [], summary["missing"]
    assert summary["figure_count"] == len(summary["figures"])


def test_figures_match_their_source_datasets(summary):
    """Every value is read from the dataset it names, so it can be checked."""
    site = ROOT / "site" / "data"
    for key, fig in summary["figures"].items():
        path = site / f"{fig['dataset']}.json"
        if not path.exists():
            pytest.skip(f"{fig['dataset']} not built")
        cur = json.loads(path.read_text())
        for part in fig["path"].split("."):
            cur = cur[int(part)] if isinstance(cur, list) else cur[part]
        assert cur == fig["value"], f"{key} drifted from {fig['dataset']}"


def test_key_figures_returns_the_published_numbers(tools, summary):
    r = tools.run_data_tool("key_figures", {})
    assert "error" not in r
    assert set(r["figures"]) == set(summary["figures"])
    assert "limit" in r["caution"].lower()


def test_key_figures_reports_unknown_keys_rather_than_inventing(tools):
    r = tools.run_data_tool("key_figures", {"keys": ["not_a_real_figure"]})
    assert r["unknown_keys"] == ["not_a_real_figure"]
    assert r["figures"] == {}
    assert r["available_keys"], "should say what it does have"


def test_lookup_prefers_the_institution_actually_asked_for(tools):
    """'Purdue University' matched six campuses and returned every one but it.

    Ranking by shortest name put Global, Northwest and Fort Wayne first and cut
    the main campus off the end of the list.
    """
    r = tools.run_data_tool("compare_institutions",
                            {"mode": "lookup", "names": ["Purdue University"]})
    assert r["rows"][0]["n"] == "Purdue University-Main Campus"
    r = tools.run_data_tool("compare_institutions",
                            {"mode": "lookup", "names": ["Stanford University"]})
    assert r["rows"][0]["n"] == "Stanford University"


def test_lookup_reports_names_it_could_not_find(tools):
    r = tools.run_data_tool("compare_institutions",
                            {"mode": "lookup", "names": ["Hogwarts"]})
    assert r["not_found"] == ["hogwarts"]
    assert r["rows"] == []


def test_absent_fields_are_absent_not_zero(tools):
    """A university with no HERD row was not surveyed; it did not spend nothing."""
    r = tools.run_data_tool("compare_institutions",
                            {"mode": "lookup", "names": ["Purdue University Global"]})
    row = r["rows"][0]
    assert "fo" not in row and "fpd" not in row


def test_per_doctorate_ranking_carries_the_intensity_warning(tools):
    """The top of it is medical schools; the caution has to say so."""
    r = tools.run_data_tool("compare_institutions",
                            {"mode": "rank", "measure": "federal_per_doctorate"})
    caution = r["caution"].lower()
    assert "intensity ratio" in caution
    assert "not a price" in caution
    assert "medical" in caution


def test_unknown_ranking_lists_the_real_ones(tools):
    r = tools.run_data_tool("compare_institutions",
                            {"mode": "rank", "measure": "vibes"})
    assert "error" in r
    assert "federal_per_doctorate" in r["available"]


def test_state_rollup_shares_come_from_sums(tools):
    r = tools.run_data_tool("compare_institutions", {"mode": "state", "state": "TX"})
    st = r["states"][0]
    expected = round(st["masters_non_resident"] / st["masters_awarded"] * 100, 1)
    assert st["masters_non_resident_share"] == expected
    assert "averaged" in r["caution"]


def test_every_result_carries_a_source(tools):
    for name, args in (("key_figures", {}),
                       ("compare_institutions", {"mode": "state"}),
                       ("compare_institutions",
                        {"mode": "rank", "measure": "federal_obligations"}),
                       ("compare_institutions",
                        {"mode": "lookup", "names": ["Stanford"]})):
        r = tools.run_data_tool(name, args)
        assert r.get("source"), f"{name} returned no source"


def test_compact_rows_stay_faithful_to_the_full_table(tools):
    """The trimmed row must not drift from the published profile."""
    full = ROOT / "site" / "data" / "institution_profiles.json"
    if not full.exists():
        pytest.skip("institution_profiles.json not built")
    profiles = {p["unitid"]: p for p in json.loads(full.read_text())["institutions"]}
    r = tools.run_data_tool("compare_institutions",
                            {"mode": "lookup",
                             "names": ["Missouri University of Science"]})
    row = r["rows"][0]
    src = profiles[row["u"]]
    assert row["n"] == src["institution"]
    assert row["ms"] == src["masters"]["share"]
    assert row["fpd"] == src["federal_per_doctorate"]
