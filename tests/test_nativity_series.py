#!/usr/bin/env python3
"""The occupation-by-nativity series, parsed from nineteen archived releases.

Each test ties the parse to something independent of it, because a table
parser that reads the wrong column produces plausible numbers -- this project
has already published computing as 61.4% foreign born from the second column
when the native-born figures are in the fourth.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "data" / "nativity_labour.json"
OCC = "Computer and mathematical"


@pytest.fixture(scope="module")
def d():
    if not DATA.exists():
        pytest.skip("nativity_labour.json not built")
    return json.loads(DATA.read_text())


def test_the_latest_year_matches_the_single_year_table(d):
    """Same release, two parsers: they must agree."""
    latest = max(d["occupation_series"])
    series = d["occupation_series"][latest][OCC]["foreign_born_share_pct"]
    single = d["employment_by_occupation"][f"{OCC} occupations"]["foreign_born_share_pct"]
    assert series == single


def test_employment_totals_match_the_api_series(d):
    """Table 4's employed totals against the CPS series fetched from the BLS API."""
    api = d["cps_series"]["employed_thousands"]
    checked = 0
    for year, row in d["occupation_series"].items():
        if year in api:
            assert row["employed_thousands"]["foreign_born"] == api[year]["foreign_born"], year
            assert row["employed_thousands"]["native_born"] == api[year]["native_born"], year
            checked += 1
    assert checked >= 15


def test_the_native_born_column_is_not_the_second(d):
    """Reading column two made computing 61.4% foreign born; it is about 20-30%."""
    for year, row in d["occupation_series"].items():
        share = row[OCC]["foreign_born_share_pct"]
        assert 15 < share < 40, f"{year}: {share}"


def test_every_break_is_recorded(d):
    """Classification changes and the partial 2025 must travel with the data."""
    br = d["occupation_series_breaks"]
    assert {"2011", "2020", "2025"} <= set(br)
    assert "11-month" in br["2025"]
    c = d["_comment"].lower() if isinstance(d["_comment"], str) else " ".join(d["_comment"]).lower()
    assert "population controls" in c


def test_series_covers_every_archived_release(d):
    releases = list((ROOT / "data" / "bls_nativity" / "archives").glob("forbrn_*.htm"))
    if not releases:
        pytest.skip("archived releases not on disk")
    assert len(d["occupation_series"]) == len(releases)
    assert not d["warnings"], d["warnings"]
