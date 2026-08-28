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
