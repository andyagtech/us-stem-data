"""Guards on two datasets that are easy to quote wrongly.

The FICA figures are a rate applied to an assumption. Nothing stops someone
lifting a scenario total and citing it as a measurement, so the structure
itself has to say what it is.

The 990 data attributes real finances to a named organisation on the strength
of an EIN match. A wrong EIN puts another charity's revenue in a document
going to legislators.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

FICA = ROOT / "data" / "h1b" / "fica_exposure.json"
N990 = ROOT / "data" / "h1b" / "nonprofit_990s.json"


def _load(p):
    if not p.exists():
        pytest.skip(f"{p.name} not built")
    return json.loads(p.read_text())


def test_the_statutory_rates_are_exact():
    d = _load(FICA)
    r = d["rates"]
    assert r["social_security"] == 0.062
    assert r["medicare"] == 0.0145
    assert round(r["employer_side"], 4) == 0.0765
    assert round(r["employer_plus_employee"], 4) == 0.153
    assert d["per_100k_payroll"]["employer_side"] == 7650


def test_no_single_national_total_is_published():
    """OPT wages are not published, so a national total cannot be measured.

    Every dollar figure must be attached to a stated wage assumption. A bare
    total at the top level would get quoted as though it were counted.
    """
    d = _load(FICA)
    for key in ("national_total", "total_forgone", "annual_cost"):
        assert key not in d, f"{key} implies a measurement that does not exist"
    for row in d["scenarios"]:
        assert row["assumed_annual_wage"] > 0
        assert "employer_side_forgone" in row


def test_every_scenario_is_arithmetic_on_its_own_assumption():
    d = _load(FICA)
    rate = d["rates"]["employer_side"]
    for row in d["scenarios"]:
        want = round(row["authorisations"] * row["assumed_annual_wage"] * rate)
        assert row["employer_side_forgone"] == want


def test_the_caveats_survive():
    """These are the three things that make the number honest."""
    d = _load(FICA)
    blob = " ".join(d["caveats"]).lower()
    assert "five calendar years" in blob        # the exemption ends
    assert "credits" in blob                    # the worker loses accrual
    assert "full-time-equivalent" in blob       # counts are not FTE-years


def test_lca_wages_are_labelled_as_not_opt_wages():
    d = _load(FICA)
    ctx = d.get("lca_wage_context")
    if ctx:
        assert "not opt wages" in ctx["note"].lower() or "not OPT wages" in ctx["note"]


# --- 990s ---------------------------------------------------------------

def test_filings_are_ordered_and_carry_a_year():
    d = _load(N990)
    for org in d["organizations"].values():
        years = [f["year"] for f in org["filings"]]
        assert years == sorted(years)
        assert all(isinstance(y, int) for y in years)


def test_growth_matches_the_first_and_last_filing():
    d = _load(N990)
    for org in d["organizations"].values():
        f = org["filings"]
        if org.get("revenue_growth_pct") is None or not f[0].get("revenue"):
            continue
        want = round(100 * (f[-1]["revenue"] / f[0]["revenue"] - 1), 1)
        assert abs(org["revenue_growth_pct"] - want) < 0.15


def test_the_ein_is_a_nine_digit_string_matching_its_key():
    """An EIN typo silently attributes another organisation's finances."""
    d = _load(N990)
    for ein, org in d["organizations"].items():
        assert ein.isdigit() and len(ein) == 9
        assert org["ein"] == ein


def test_revenue_is_not_described_as_sponsorships():
    d = _load(N990)
    assert "not a count of sponsorships" in d["_comment"].lower()
    assert "no cap status" in d["_comment"].lower()


# --- EB-2 / NIW ---------------------------------------------------------

EB2 = ROOT / "data" / "h1b" / "eb2_niw.json"


def test_every_eb2_row_reconciles_within_rounding():
    """USCIS rounds to the nearest 10, so parts need not sum exactly.

    Demanding exact equality rejected most of the table; allowing anything
    would let a mis-parsed row through. Ten is the rounding unit.
    """
    d = _load(EB2)
    for year, rec in d["series"].items():
        for measure, v in rec.items():
            assert abs(v["non_niw"] + v["niw"] - v["total"]) <= 10, (year, measure)


def test_only_the_all_job_types_table_was_read():
    """Table 2 repeats the row shape for STEM jobs only.

    FY2023 receipts are 93,010 across all job types and 53,960 in STEM. If
    the smaller figure appears, the parser ran past the Table 2 heading.
    """
    d = _load(EB2)
    assert d["series"]["2023"]["receipts"]["total"] == 93010


def test_the_niw_share_is_derived_from_its_own_row():
    d = _load(EB2)
    for rec in d["series"].values():
        for v in rec.values():
            if v["total"]:
                assert abs(v["niw_share"] - 100 * v["niw"] / v["total"]) < 0.1


def test_receipts_are_not_described_as_people():
    d = _load(EB2)
    assert "filings, not people" in d["_comment"].lower()


# --- J-1 scholars -------------------------------------------------------

J1 = ROOT / "data" / "h1b" / "j1_scholars.json"


def test_the_partial_year_is_excluded_from_every_comparison():
    """2025 is data through about March.

    Measuring 2015 against it turns a 33% fall in research scholars into a
    51% one -- a full year against a quarter.
    """
    d = _load(J1)
    assert 2025 in d["partial_years"]
    assert 2025 not in d["complete_years"]
    for change in d["change_between_complete_years"].values():
        assert change["to_year"] not in d["partial_years"]


def test_the_partial_year_is_still_published():
    """Excluded from comparisons, not hidden."""
    d = _load(J1)
    assert "2025" in d["series"]


def test_the_research_scholar_change_is_the_complete_year_one():
    d = _load(J1)
    c = d["change_between_complete_years"]["research_scholar"]
    assert c["from_year"] == 2015 and c["to_year"] == 2024
    assert -40 < c["pct"] < -25, c


# --- PERM ---------------------------------------------------------------

PERM = ROOT / "data" / "h1b" / "perm_pipeline.json"


def test_class_of_admission_shares_sum_sanely():
    d = _load(PERM)
    total = sum(r["count"] for r in d["class_of_admission"])
    assert total <= d["applications"]
    assert d["class_of_admission"][0]["value"] == "H-1B"


def test_a_certification_is_not_called_a_green_card():
    d = _load(PERM)
    blob = d["_comment"].lower()
    assert "not a green card" in blob
    assert "applications, not people" in blob


def test_certified_expired_is_kept_distinct_from_certified():
    """A lapsed certification is not a successful one."""
    d = _load(PERM)
    values = {r["value"] for r in d["case_status"]}
    assert "CERTIFIED" in values and "CERTIFIED-EXPIRED" in values


# --- Build Fellowship partners ------------------------------------------

BFP = ROOT / "data" / "h1b" / "build_fellowship_partners.json"


def test_every_published_partner_resolved_to_ipeds():
    d = _load(BFP)
    assert d["partners_matched"] == d["partners_published"] == 54
    assert d["unmatched"] == []


def test_partner_unitids_are_distinct():
    """A BOM read the UNITID column as None and collapsed all 54 onto one key."""
    d = _load(BFP)
    ids = [p["unitid"] for p in d["partners"]]
    assert len(set(ids)) == len(ids)
    assert all(u and u.isdigit() for u in ids)


def test_completions_were_actually_summed():
    """Filtering for family rollups that IPEDS does not carry summed nothing.

    CIP codes are six digits; only CIPCODE 99 is a rollup.
    """
    d = _load(BFP)
    assert any(p["masters"]["total"] for p in d["partners"])
    top = max(d["partners"], key=lambda p: p["masters"]["nra"] + p["doctorate"]["nra"])
    assert top["masters"]["nra"] + top["doctorate"]["nra"] > 1000


def test_a_partnership_is_not_described_as_sponsorship():
    d = _load(BFP)
    blob = d["_comment"].lower()
    assert "does not mean the university sponsors" in blob
    assert "own claim" in blob
