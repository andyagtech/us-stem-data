#!/usr/bin/env python3
"""Tests for the per-institution profile table.

Each test here corresponds to a mistake that was actually made building it, or
to a mistake this project has made before on the same kind of join. They are
written against the built artefact rather than the builder so that a change of
source vintage cannot quietly reintroduce one.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "site" / "data" / "institution_profiles.json"


@pytest.fixture(scope="module")
def data():
    if not PROFILES.exists():
        pytest.skip("institution_profiles.json not built")
    return json.loads(PROFILES.read_text())


@pytest.fixture(scope="module")
def by_unitid(data):
    return {p["unitid"]: p for p in data["institutions"]}


def test_grand_total_row_is_not_counted_as_a_field(by_unitid):
    """IPEDS files a CIP 99 row repeating every detail row for the institution.

    The core-STEM filter excluded it by accident; the count across all fields
    did not, and every all-field total came out at exactly twice its true
    value. The tell was that core-STEM read as exactly 50.0% of all research
    doctorates at institutions that award nothing but core-STEM doctorates.
    """
    # Missouri S&T awards core-STEM research doctorates and essentially
    # nothing else, so the two counts must very nearly coincide.
    mst = by_unitid["178411"]
    assert mst["cost_basis_share_of_all_doctorates"] > 95, \
        "core-STEM should be nearly all of this institution's doctorates"
    shares = [p["cost_basis_share_of_all_doctorates"] for p in by_unitid.values()
              if p.get("cost_basis_share_of_all_doctorates")]
    assert sum(1 for s in shares if s == 50.0) < len(shares) * 0.05, \
        "a pile-up on exactly 50% is the doubled-denominator signature"


def test_per_doctorate_reproduces_the_published_basis(by_unitid):
    """The funding page quotes this ratio; the two must not drift apart.

    Missouri S&T is published at $107,334 on FY2023 obligations over the
    2015-2022 annual rate of core-STEM research doctorates.
    """
    assert by_unitid["178411"]["federal_per_doctorate"] == 107_334


def test_per_doctorate_carries_its_caveat(data):
    """It is an intensity ratio and the artefact has to say so.

    It was once dropped from the report altogether to fix a page overflow,
    which is the wrong way to handle a figure that needs a caveat.
    """
    c = " ".join(data["_comment"]).lower()
    assert "intensity ratio, not a price" in c
    assert "not only degrees" in c


def test_a_partial_denominator_is_visible_not_asserted(by_unitid):
    """The top of the per-doctorate ranking is medical schools.

    Federal obligations fund every field while the denominator counts only
    core-STEM research doctorates, so an institution whose output is mostly
    medical shows an enormous ratio without doing anything unusual. Every row
    that carries the ratio must also carry what makes that legible.
    """
    for p in by_unitid.values():
        if p.get("federal_per_doctorate"):
            assert p.get("cost_basis_share_of_all_doctorates") is not None
            assert p.get("cost_basis_professional_doctorates") is not None
    einstein = next(p for p in by_unitid.values()
                    if p["institution"].startswith("Albert Einstein College"))
    assert einstein["cost_basis_professional_doctorates"] > 100, \
        "a medical school's professional doctorates must be visible"


def test_names_are_never_resolved_by_subset_match(by_unitid):
    """Subset matching on token sets was tried and rejected.

    It maps 'Florida A&M U.' onto the University of Florida, 'Kutztown U.
    Pennsylvania' onto the University of Pennsylvania and 'State U. New York,
    Maritime C.' onto New York University, because a short famous name is a
    subset of many longer unrelated ones. This project has already turned a
    military college into a trading firm once.
    """
    uf = by_unitid.get("134130")          # University of Florida
    famu = by_unitid.get("133650")        # Florida A&M University
    assert uf and famu
    # Both exist separately and neither has swallowed the other's money.
    if uf.get("federal") and famu.get("federal"):
        assert famu["federal"].get("rd_total", 0) < uf["federal"].get("rd_total", 1)
    nyu = by_unitid.get("193900")
    if nyu and nyu.get("federal"):
        summed = nyu["federal"].get("herd_rows_summed", [])
        assert not any("Maritime" in n or "State U. New York" in n for n in summed)


def test_unmatched_federal_dollars_stay_small_and_are_explained(data):
    """What cannot be resolved is reported, not guessed at."""
    x = data["crosswalk"]
    assert x["herd_unmatched_dollars_pct"] < 5
    assert x["federal_support_unmatched_dollars_pct"] < 6
    for u in x["largest_unmatched"]:
        assert u["reason"] in ("not_ipeds", "system_office", "no exact match"), u
    # The biggest unmatched names should be genuine non-IPEDS research bodies,
    # not universities the crosswalk simply missed.
    biggest = [u["name"] for u in x["largest_unmatched"][:6]]
    assert any("Scripps" in n or "Woods Hole" in n for n in biggest), biggest


def test_multi_campus_names_do_not_collapse(by_unitid):
    """'U. Michigan' is three institutions; the money belongs to Ann Arbor."""
    ann_arbor = by_unitid["170976"]
    assert ann_arbor["institution"] == "University of Michigan-Ann Arbor"
    assert ann_arbor["federal"]["obligations"] > 500_000_000
    for u in ("171137", "171146"):        # Dearborn, Flint
        p = by_unitid.get(u)
        assert p["institution"].startswith("University of Michigan-")
        if p.get("federal"):
            assert p["federal"].get("obligations", 0) < 50_000_000, p["institution"]


def test_rows_summed_into_one_unitid_are_recorded(by_unitid):
    """IPEDS files Denver and Anschutz as one unit; HERD files them as two.

    Summing is right, but silently summing is not: the profile has to name the
    rows it absorbed or the figure cannot be traced back.
    """
    denver = by_unitid.get("126562")
    assert denver and denver.get("federal")
    summed = denver["federal"].get("herd_rows_summed")
    assert summed and len(summed) >= 2, summed


def test_match_kind_flags_money_that_covers_more_than_the_campus(by_unitid):
    """Vanderbilt's HERD row includes a medical centre that enrols nobody."""
    vandy = by_unitid["221999"]
    assert "campus_plus_affiliate" in vandy["federal"]["match_kind"]


def test_non_resident_never_exceeds_the_total(by_unitid):
    for p in by_unitid.values():
        for key in ("masters", "doctorate", "all_research_doctorates"):
            block = p.get(key) or {}
            if block.get("awarded"):
                assert block["non_resident"] <= block["awarded"], \
                    f"{p['institution']} {key}"
        for key in ("graduate_enrolment", "total_enrolment"):
            block = p.get(key) or {}
            if block.get("total"):
                assert block["non_resident"] <= block["total"], \
                    f"{p['institution']} {key}"


def test_second_majors_are_not_counted_as_extra_degrees(by_unitid):
    """IPEDS files a second row per second major; MAJORNUM 1 only.

    Counting both awards two degrees to one graduate. Michigan's graduate
    enrolment and its degree output have to stay in a believable relation.
    """
    mich = by_unitid["170976"]
    annual_masters = mich["masters"]["awarded"] / 5
    assert annual_masters < (mich["graduate_enrolment"]["total"] or 0), \
        "more master's a year than graduate students is a double count"


def test_state_shares_come_from_sums_not_means(data):
    """A department of nine must not outvote a university of nine thousand."""
    for st in data["states"]:
        if st["masters_awarded"]:
            expected = round(st["masters_non_resident"] / st["masters_awarded"] * 100, 1)
            assert st["masters_non_resident_share"] == expected, st["state"]
        if st["graduate_enrolment"]:
            expected = round(st["graduate_non_resident"] / st["graduate_enrolment"] * 100, 1)
            assert st["graduate_non_resident_share"] == expected, st["state"]


def test_states_sum_to_the_national_table(data):
    total = sum(st["masters_awarded"] for st in data["states"])
    direct = sum(p["masters"]["awarded"] for p in data["institutions"])
    assert total == direct


def test_share_rankings_respect_their_floor(data):
    """Ranking a share without a floor puts a programme of five top of the country."""
    floors = data["floors"]
    by = {p["unitid"]: p for p in data["institutions"]}
    for name, gate, floor_key in (
            ("stem_masters_non_resident_share", "masters", "masters"),
            ("stem_doctorates_non_resident_share", "doctorate", "doctorate")):
        for row in data["rankings"][name]:
            awarded = by[row["unitid"]][gate]["awarded"]
            assert awarded >= floors[floor_key], f"{name}: {row['institution']}"


def test_rankings_are_ordered_and_point_at_real_institutions(data):
    by = {p["unitid"]: p for p in data["institutions"]}
    for name, rows in data["rankings"].items():
        values = [r["value"] for r in rows]
        assert values == sorted(values, reverse=True), name
        for i, r in enumerate(rows, 1):
            assert r["rank"] == i, name
            assert r["unitid"] in by, f"{name}: {r['unitid']}"
            assert by[r["unitid"]]["institution"] == r["institution"]


def test_visa_status_is_not_read_as_birthplace(data):
    """Non-resident excludes naturalised citizens and permanent residents."""
    c = " ".join(data["_comment"]).lower()
    assert "visa category" in c
    assert "floor on the foreign-born" in c


def test_missing_is_absent_rather_than_zero(by_unitid):
    """A university with no HERD row was not surveyed; it did not spend nothing."""
    no_federal = [p for p in by_unitid.values() if "federal" not in p]
    assert no_federal, "some institutions should have no federal block at all"
    for p in no_federal[:50]:
        assert "federal_per_doctorate" not in p
