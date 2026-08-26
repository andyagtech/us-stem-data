"""The OPT reports are two different kinds of number wearing the same name.

opt_national.json is a complete national count. The per-school and
per-employer tables are TOP-N RANKINGS -- a school absent from a year placed
outside the top 100 that year, it did not have zero OPT students. Confusing
the two produces a national total that is silently a floor.

These tests pin the parsing of both, and the guards that stop a changed PDF
layout from putting the wrong rank, or the wrong school, on a page.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import parse_opt_reports as O  # noqa: E402


# --- the national table ------------------------------------------------

NAT = """      Total number of annual OPT, STEM OPT and CPT Authorizations
    OPT Type      2007      2008      2009
    OPT              24,838    45,357    46,198
    STEM OPT              2     2,128     5,869
    Total SEVIS
    IDs w/ OPT      24,838    47,432    51,985
    CPT             57,403    61,171    48,568
"""


def test_the_national_table_parses_every_row():
    got = O.parse_national(NAT)
    assert sorted(got) == ["2007", "2008", "2009"]
    assert got["2007"] == {"opt": 24838, "stem_opt": 2,
                           "total_sevis_with_opt": 24838, "cpt": 57403}
    assert got["2009"]["stem_opt"] == 5869


def test_a_table_without_a_year_header_yields_nothing():
    assert O.parse_national("OPT  1,2,3\nSTEM OPT 4") == {}


# --- the school tables -------------------------------------------------

SCHOOL = """                 2023 Top 100 School Campuses with OPT (Pre- + Post-Completion)

Campus Name                    School Name                    Students Employed    Authorizations Issued
Columbia University            Columbia University            5,861                4,331
Northeastern University        Northeastern University        5,105                3,585
"""


def test_school_rows_carry_rank_in_published_order():
    rows = O.parse_school_table(SCHOOL)
    assert [r["rank"] for r in rows] == [1, 2]
    assert rows[0]["students_employed"] == 5861
    assert rows[0]["authorizations"] == 4331
    assert rows[1]["school"] == "Northeastern University"


def test_the_data_year_comes_from_the_title_not_the_filename():
    """24_0510_...-2023-... is the 2023 report PUBLISHED in 2024."""
    assert O.year_of(SCHOOL, "24_0510_hsi_sevp-sevis-btn-2023-top100.pdf") == 2023
    assert O.year_of("Calendar Year 2017\n", "whatever.pdf") == 2017


@pytest.mark.parametrize("name,text,want", [
    ("x-stem-opt-schools.pdf", "", "stem_opt"),
    ("x-prepost-opt-schools.pdf", "", "opt"),
    ("2024_Top100_SchoolCampusesWithSTEM_OPT.pdf", "", "stem_opt"),
    ("plain.pdf", "Top 100 School Campuses with OPT (Pre- + Post-Completion)", "opt"),
])
def test_both_flavours_are_told_apart(name, text, want):
    assert O.kind_of(name, text) == want


# --- the employer table ------------------------------------------------

EMP = """                    2024 Top 200 Employers for OPT and STEM-OPT Students
Amazon                                     10,167              5,379              6,679
University of California                    2,916              2,112              1,278
"""


def test_employer_columns_do_not_have_to_sum_to_the_total():
    """A student on both programmes is counted once in total, twice across.

    Requiring opt + stem == total threw away 96% of the table and kept only
    the rows that happened to fit, leaving a "top employers" list whose first
    entry was a foundation nobody has heard of instead of Amazon.
    """
    rows = O.parse_employers(EMP)
    assert [r["employer"] for r in rows] == ["Amazon", "University of California"]
    a = rows[0]
    assert (a["total"], a["opt"], a["stem_opt"]) == (10167, 5379, 6679)
    assert a["opt"] + a["stem_opt"] > a["total"]


def test_an_impossible_employer_row_is_rejected():
    bad = "Nonsense Inc                        10              9,000              9,000\n"
    assert O.parse_employers(bad) == []


# --- name matching -----------------------------------------------------

RAW = {"UNIVERSITY OF ILLINOIS URBANA-CHAMPAIGN": "uiuc",
       "SOUTHERN ILLINOIS UNIVERSITY": "siu",
       "UNIVERSITY OF MEMPHIS": "umemphis",
       "DUKE UNIVERSITY": "duke",
       "UNIVERSITY OF TEXAS AT AUSTIN": "utaustin",
       "UNIVERSITY OF TEXAS AT DALLAS": "utdallas"}
NRM = {O._norm(k): v for k, v in RAW.items()}


@pytest.mark.parametrize("school,want", [
    ("University of Illinois", "uiuc"),                   # SEVP uses the short form
    ("Southern Illinois University Carbondale", "siu"),   # ...and a campus suffix
    ("The University of Memphis", "umemphis"),            # ...and a leading "The"
    ("Duke University & Health Sys.", "duke"),            # ...and an abbreviation
])
def test_sevp_spellings_resolve(school, want):
    assert O.match_school(school, school, RAW, NRM) == want


def test_an_ambiguous_name_is_refused_rather_than_guessed():
    """"University of Texas" is a prefix of several campuses.

    Guessing one would put another institution's students on its page, and
    nothing downstream could detect it.
    """
    assert O.match_school("University of Texas", "University of Texas", RAW, NRM) is None
