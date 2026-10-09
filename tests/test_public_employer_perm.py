"""Tests for the public-employer PERM read path and its classifier.

These exist because of two specific mistakes made while writing it, both of the
same kind: a classifier that silently dropped rows nobody then looked for.

First, "ACADEMY" on its own put ACADEMY, LTD. D/B/A ACADEMY SPORTS AND
OUTDOORS -- a sporting-goods retailer -- into the school-district sector.

Second, and worse, the fix for that demanded an ACADEMY also carry CHARTER or
PREPARATORY in its name before it counted as a school. That removed 1,224
filings by 567 employers, nearly all of them real charter schools, to exclude
the 23 filed by the retailer. The exclusions are a named list now, because a
named list can be audited and a clever rule cannot.

Third, the named exclusion was tested only on the school branch, so WEIL TENNIS
ACADEMY & COLLEGE was thrown out as a school and picked straight back up as a
university on the word "college".

The wage tests exist because PERM states a wage and its unit separately, and
the unit varies within a single employer. A histogram of the raw numbers would
bin an hourly rate against an annual salary.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_public_employer_perm import (                      # noqa: E402
    annual_wage, anomalies, distributions, histogram, sector,
    COUNT_BINS, NON_WORK_VISA, WAGE_BINS,
)


# --------------------------------------------------------------------------
# the classifier

@pytest.mark.parametrize("name", [
    "LISA ACADEMY",                        # an Arkansas charter network, 50 filings
    "YINGHUA ACADEMY",                     # Chinese immersion charter, Minneapolis
    "SEJONG ACADEMY OF MINNESOTA",
    "EAST POINT ACADEMY",
    "TORCHLIGHT ACADEMY",
    "SEATTLE PUBLIC SCHOOLS",
    "LOS ANGELES UNIFIED SCHOOL DISTRICT",
    "FAIRFAX COUNTY SCHOOLS",
    "HORIZON SCIENCE ACADEMY CLEVELAND HIGH SCHOOL",
    "WONDERLAND MONTESSORI ACADEMY, LLC",
])
def test_real_schools_are_schools(name):
    assert sector(name) == "school_districts"


@pytest.mark.parametrize("name", [
    "ACADEMY, LTD. D/B/A ACADEMY SPORTS AND OUTDOORS",
    "ACADEMY, LTD. DBA ACADEMY SPORTS AND OUTDOORS",
    "AMERICAN MARTIAL ARTS ACADEMY -NAPERVILLE INC",
    "YONG IN MARTIAL ARTS ACADEMY, INC.",
    "ASM BEAUTY WORLD ACADEMY",
    "KHAN ACADEMY, INC.",
    "BRAZILIAN STORM SOCCER AND FUTSAL ACADEMY CORP",
    "JC AIR ACADEMY INC",
])
def test_businesses_named_academy_are_not_schools(name):
    assert sector(name) is None


def test_the_exclusion_guards_every_branch_not_just_the_school_one():
    """WEIL TENNIS ACADEMY & COLLEGE must not re-enter as a university.

    This is the bug the exclusion-before-dispatch ordering fixes. If the
    exclusion is moved back inside the school branch, this test goes red.
    """
    assert sector("WEIL TENNIS ACADEMY & COLLEGE") is None


@pytest.mark.parametrize("name,want", [
    ("UNIVERSITY OF MONTANA", "universities"),
    ("THE REGENTS OF THE UNIVERSITY OF CALIFORNIA", "universities"),
    ("ABRAHAM BALDWIN AGRICULTURAL COLLEGE", "universities"),
    ("WASHINGTON STATE DEPARTMENT OF LICENSING", "state_agencies"),
    ("CALIFORNIA DEPARTMENT OF CORRECTIONS AND REHABILITATION", "state_agencies"),
    ("NEW YORK STATE OFFICE OF MENTAL HEALTH", "state_agencies"),
    ("GOOGLE LLC", None),
    ("INFOSYS LIMITED", None),
])
def test_other_sectors(name, want):
    assert sector(name) == want


def test_a_university_run_high_school_lands_in_k12():
    """School is tested before university, deliberately. A name that says
    'high school' is a high school whatever institution runs it."""
    assert sector("UNIVERSITY OF CHICAGO LABORATORY HIGH SCHOOL") == "school_districts"


# --------------------------------------------------------------------------
# the wage annualiser

@pytest.mark.parametrize("raw,unit,want", [
    ("75000", "Year", 75_000),
    ("$75,000.00", "yr", 75_000),
    ("6250", "Month", 75_000),
    ("1442.31", "Week", 75_000),      # 1442.31 * 52
    ("36.06", "Hour", 75_005),        # 36.06 * 2080
    ("2884.62", "Bi-Weekly", 75_000),
])
def test_wages_annualise_onto_one_scale(raw, unit, want):
    got = annual_wage(raw, unit)
    assert got == pytest.approx(want, abs=60), f"{raw}/{unit} -> {got}"


@pytest.mark.parametrize("raw,unit", [
    ("", "Year"),            # no wage stated
    ("0", "Year"),           # a zero is not a wage
    ("75000", ""),           # no unit, so no scale
    ("75000", "Fortnight"),  # a unit we do not know
    ("abc", "Year"),
    ("1000", "Year"),        # below the floor: cannot be an annual salary
    ("75000", "Hour"),       # an annual figure mislabelled hourly
])
def test_unreadable_wages_are_none_never_a_guess(raw, unit):
    """A guessed wage would set the histogram's whole scale by itself.

    The last case is the one that matters: 75000/hour annualises to $156m and
    would push every real wage into the first bin.
    """
    assert annual_wage(raw, unit) is None


# --------------------------------------------------------------------------
# histograms

def test_histogram_counts_every_value_exactly_once():
    values = [10_000, 35_000, 45_000, 45_500, 55_000, 1_500_000]
    bins = histogram(values, WAGE_BINS, money=True)
    assert sum(b["count"] for b in bins) == len(values)


def test_histogram_bins_are_half_open_so_an_edge_lands_in_one_bin():
    bins = histogram([40_000], WAGE_BINS, money=True)
    hit = [b for b in bins if b["count"]]
    assert len(hit) == 1
    assert hit[0]["from"] == 40_000


def test_the_last_bin_is_open_ended():
    bins = histogram([5_000_000_000], COUNT_BINS, money=False)
    assert bins[-1]["count"] == 1
    assert bins[-1]["to"] is None
    assert bins[-1]["label"].endswith("+")


def test_bin_labels_are_built_from_the_edges_not_written_out():
    """A hand-written label can survive a change to the edges. These cannot."""
    bins = histogram([], WAGE_BINS, money=True)
    assert bins[0]["label"] == "$0–$30k"
    assert [b["from"] for b in bins] == WAGE_BINS[:-1]


# --------------------------------------------------------------------------
# distributions and anomalies

def rec(**kw):
    base = dict(fiscal_year=2024, sector="universities", employer="U",
                job_title="Professor", citizenship="India", birth_country="India",
                visa_held="H-1B", state="OHIO", city="X", status="Certified",
                decided="2024-01-01", wage=90_000)
    base.update(kw)
    return base


def test_filings_per_employer_measures_employers_not_filings():
    rows = [rec(employer="A") for _ in range(10)] + [rec(employer="B")]
    d = distributions(rows)["universities"]["filings_per_employer"]
    assert d["employers"] == 2
    assert d["max"] == 10
    assert sum(b["count"] for b in d["bins"]) == 2


def test_top10_share_is_a_share_of_filings():
    rows = [rec(employer=f"E{i}") for i in range(20)]
    d = distributions(rows)["universities"]["filings_per_employer"]
    assert d["top10_share"] == 50.0


def test_unpriced_filings_are_counted_not_dropped():
    rows = [rec(wage=None), rec(wage=None), rec(wage=50_000)]
    w = distributions(rows)["universities"]["wage"]
    assert w["n"] == 1 and w["unpriced"] == 2


def test_non_work_visa_filings_are_flagged_with_the_class_that_flagged_them():
    rows = [rec(visa_held="B-2"), rec(visa_held="H-1B")]
    flagged = anomalies(rows)["sponsored_while_not_work_authorised"]
    assert len(flagged) == 1
    assert "B-2" in flagged[0]["why"]


def test_h1b_is_not_an_anomaly():
    assert "H-1B" not in NON_WORK_VISA
    rows = [rec(visa_held="H-1B")]
    assert not anomalies(rows).get("sponsored_while_not_work_authorised")


def test_citizenship_birth_mismatch_is_flagged_and_names_both():
    rows = [rec(citizenship="Hong Kong", birth_country="China")]
    flagged = anomalies(rows)["citizenship_differs_from_birth_country"]
    assert len(flagged) == 1
    assert "Hong Kong" in flagged[0]["why"] and "China" in flagged[0]["why"]


def test_a_missing_birth_country_is_not_a_mismatch():
    """An empty field disagrees with everything. Flagging it would fill the
    table with filings from the years before DOL published the column."""
    rows = [rec(birth_country=""), rec(birth_country="Not In Usa")]
    assert not anomalies(rows).get("citizenship_differs_from_birth_country")


def test_a_unique_job_title_is_judged_within_its_own_sector():
    """'Teacher' is unremarkable in a school district and singular in a state
    agency. Counting titles across sectors would hide both facts."""
    rows = ([rec(sector="school_districts", job_title="Teacher") for _ in range(5)]
            + [rec(sector="state_agencies", job_title="Teacher")])
    flagged = anomalies(rows)["job_title_unique_in_its_sector"]
    assert [r["sector"] for r in flagged] == ["state_agencies"]


def test_a_us_citizen_is_its_own_finding_not_a_birth_mismatch():
    """A US citizen cannot need a labour certification, so the filing is
    defective however the birth country reads. Leaving these in the mismatch
    table buried the real finding among 2,000 ordinary naturalisations."""
    rows = [rec(citizenship="United States Of America", birth_country="Romania")]
    out = anomalies(rows)
    assert len(out["a_us_citizen_named_on_the_filing"]) == 1
    assert not out.get("citizenship_differs_from_birth_country")


def test_a_us_born_us_citizen_is_still_flagged():
    rows = [rec(citizenship="United States Of America",
                birth_country="United States Of America")]
    assert len(anomalies(rows)["a_us_citizen_named_on_the_filing"]) == 1


def test_an_ordinary_naturalisation_stays_in_the_mismatch_table():
    rows = [rec(citizenship="Canada", birth_country="Iran")]
    out = anomalies(rows)
    assert len(out["citizenship_differs_from_birth_country"]) == 1
    assert not out.get("a_us_citizen_named_on_the_filing")


# --------------------------------------------------------------------------
# the worksite state

def test_both_spellings_of_a_state_fold_together():
    """The older PERM files write MONTANA and the newer ones write MT.

    Left alone each state appears twice holding about half its filings, which
    is how Montana came out as 36 and 36 instead of 72. This is the header
    drift this repo already guards against, one level down: a value, not a
    column name.
    """
    from build_public_employer_perm import normalise_state
    assert normalise_state("MT") == normalise_state("MONTANA") == "MONTANA"
    assert normalise_state("wa") == normalise_state("Washington") == "WASHINGTON"


def test_every_code_maps_to_a_name_that_maps_to_itself():
    """No code may point at a name the normaliser would not itself accept."""
    from build_public_employer_perm import STATE_NAMES, normalise_state
    for code, name in STATE_NAMES.items():
        assert normalise_state(code) == name
        assert normalise_state(name) == name


def test_an_unknown_state_is_a_crash_not_a_silent_drop():
    """A dropped state is a state missing from every total, and nobody looks
    for a row that was never there."""
    from build_public_employer_perm import normalise_state
    with pytest.raises(SystemExit):
        normalise_state("ZZ")


def test_an_empty_state_is_empty_not_an_error():
    from build_public_employer_perm import normalise_state
    assert normalise_state("") == ""


# --------------------------------------------------------------------------
# the gaps a reader found

@pytest.mark.parametrize("name", [
    "SAVANNAHCHATHAM COUNTY PUBLIC SCHOOL SYSTEM",   # 108 filings, missed
    "NEW YORK CITY DEPARTMENT OF EDUCATION",
    "HOBBS MUNICIPAL SCHOOLS",
    "ANCHORAGE SCHOOL DISTRICT",
])
def test_districts_that_do_not_say_public_schools(name):
    """Found by scanning one year for public-looking employers in no sector.

    The pattern had PUBLIC SCHOOLS and the Savannah district calls itself a
    PUBLIC SCHOOL SYSTEM; New York City files as a DEPARTMENT OF EDUCATION
    rather than a board. Both were simply absent from every figure.
    """
    assert sector(name) == "school_districts"


def test_a_utility_is_found_by_industry_not_by_name():
    """'Electric' in a name means nothing. Schneider Electric and Milwaukee
    Electric Tool make equipment; the NAICS code is what says utility."""
    from build_public_employer_perm import is_utility
    assert is_utility("221122") and is_utility("2211")
    assert not is_utility("334413")      # semiconductor manufacturing
    assert not is_utility("")
    assert sector("SCHNEIDER ELECTRIC USA, INC.") is None


def test_public_ownership_is_a_flag_and_not_a_filter():
    """Most of NAICS 221 is investor-owned and runs the same grid. Excluding
    them would misrepresent the sector; the flag lets the page say which is
    which."""
    from build_public_employer_perm import PUBLICLY_OWNED
    assert PUBLICLY_OWNED.search("OMAHA PUBLIC POWER DISTRICT")
    assert PUBLICLY_OWNED.search("NEW YORK POWER AUTHORITY")
    assert not PUBLICLY_OWNED.search("ENTERGY SERVICES, LLC")


@pytest.mark.parametrize("name", [
    "VIRGINIA DEPARTMENT OF EDUCATION",
    "NEBRASKA DEPARTMENT OF EDUCATION",
    "ARIZONA DEPARTMENT OF EDUCATION",
    "LOUISIANA BOARD OF REGENTS",
])
def test_a_state_education_body_is_a_state_agency(name):
    """Widening the school pattern to catch NEW YORK CITY DEPARTMENT OF
    EDUCATION swept up every STATE department of education with it, and the
    state-agency count fell from 87 to 74 without anything looking wrong."""
    assert sector(name) in ("state_agencies",)


def test_a_city_education_department_is_still_a_district():
    assert sector("NEW YORK CITY DEPARTMENT OF EDUCATION") == "school_districts"
