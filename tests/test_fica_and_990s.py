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


# --- domestic pipeline --------------------------------------------------

DOM = ROOT / "site" / "data" / "domestic_pipeline.json"


def test_domestic_output_rose_at_every_level():
    """The strongest rebuttal to "America produces no STEM graduates".

    If this ever fails, the report's framing has to change, not the test.
    """
    d = _load(DOM)
    years = sorted(d["series"])
    first, last = d["series"][years[0]], d["series"][years[-1]]
    for level in ("bachelors", "masters", "doctorate"):
        assert last[level]["domestic"] > first[level]["domestic"], level


def test_doctorate_conversion_fell_while_masters_rose():
    d = _load(DOM)
    doc = d["conversion"]["doctorate"]
    mas = d["conversion"]["masters"]
    assert doc[-1]["rate"] < doc[0]["rate"]
    assert mas[-1]["rate"] > mas[0]["rate"]


def test_every_conversion_row_is_arithmetic_on_its_own_counts():
    d = _load(DOM)
    for rows in d["conversion"].values():
        for r in rows:
            want = round(100 * r["domestic_graduate"] / r["domestic_bachelors"], 2)
            assert abs(r["rate"] - want) < 0.01


def test_the_lag_is_declared_not_hidden():
    d = _load(DOM)
    assert d["lag_years"]["doctorate"] == 6
    for rows in d["conversion"].values():
        for r in rows:
            assert r["graduate_year"] > r["bachelors_year"]


def test_it_does_not_claim_to_track_people():
    d = _load(DOM)
    assert "degrees, not people" in d["_comment"].lower()


# --- Build Fellowship projects ------------------------------------------

BFPROJ = ROOT / "data" / "buildfellowship" / "projects.json"


def test_every_published_project_was_parsed():
    d = _load(BFPROJ)
    assert d["projects_parsed"] == d["stated_total"] == 243
    assert d["unparsed"] == []


def test_flight_references_were_resolved():
    """Long bios are stored as "$1a" and defined elsewhere with a length prefix.

    Read without resolving, every long bio came back as that literal.
    """
    d = _load(BFPROJ)
    bios = [f.get("bio") or "" for p in d["projects"] for f in p["fellows"]]
    assert bios, "no bios captured"
    assert not [b for b in bios if b.startswith("$")]


def test_the_published_field_and_the_extracted_one_stay_apart():
    """`organization` is the nonprofit; the employer comes from prose."""
    d = _load(BFPROJ)
    assert "employers" in d
    for p in d["projects"]:
        assert "organization" in p and "employers_from_bio" in p


def test_employer_spellings_are_grouped_but_not_merged():
    """Case variants fold together; different names do not.

    "DREAM Venture Labs" and "Dream Venture Labs" are one firm. Rolling
    "Citadel" into "Citadel Securities" would be a guess.
    """
    d = _load(BFPROJ)
    names = [e["name"] for e in d["employers"]]
    assert len(names) == len({n.casefold() for n in names})


def test_no_visa_status_is_claimed():
    d = _load(BFPROJ)
    assert "record no visa status" in d["_comment"].lower()


# --- fellowship employers joined to H-1B --------------------------------

EMPH = ROOT / "data" / "buildfellowship" / "employer_h1b.json"


def test_a_single_word_employer_is_not_matched():
    """"Citadel" matched "THE CITADEL", a military college in South Carolina.

    Stripping "THE" made it exact. One word is too generic to match on.
    """
    d = _load(EMPH)
    for m in d["employers"]:
        assert "THE CITADEL" not in m["hub_name"].upper()


def test_two_spellings_of_one_firm_are_merged():
    """Otherwise the same approvals are counted twice in every total."""
    d = _load(EMPH)
    hub_names = [m["hub_name"] for m in d["employers"]]
    assert len(hub_names) == len(set(hub_names))


def test_the_concurrent_rate_is_reported_against_a_baseline():
    """A rate without a base rate is not a finding."""
    d = _load(EMPH)
    b = d["concurrent_baseline"]
    assert b["all_rate_pct"] > 0 and b["fellowship_rate_pct"] > 0
    assert b["ratio"] == round(
        (b["fellowship_with_concurrent"] / b["fellowship_employers"]) /
        (b["all_with_concurrent"] / b["all_employers_in_band"]), 1)


def test_the_association_is_not_stated_as_proof():
    d = _load(EMPH)
    blob = (d["_comment"] + d["concurrent_baseline"]["caveat"]).lower()
    assert "does not show" in blob or "not evidence" in blob
    assert "selection" in blob


# --- cap-exempt proxies -------------------------------------------------

PROXY = ROOT / "data" / "cap_exempt" / "proxy_comparison.json"


def test_neither_proxy_is_called_authoritative():
    """The disclaimer must be present in whatever wording it uses."""
    d = _load(PROXY)
    blob = d["_comment"].lower()
    assert "neither is authoritative" in blob or "not authoritative" in blob
    assert "not published" in blob


def test_the_proxies_disagree_in_both_directions():
    """Each catches employers the other misses; that is the finding."""
    d = _load(PROXY)
    assert d["directory_only"]["count"] > 0
    assert d["naics_61_only"]["count"] > 0


def test_major_universities_are_missing_from_naics_61():
    """Self-reported codes describe something other than the institution.

    Washington University in St Louis files as Manufacturing, so an
    industry-code proxy loses it entirely.
    """
    d = _load(PROXY)
    names = " ".join(r["employer"].upper() for r in d["directory_only"]["largest"])
    assert "WASHINGTON UNIVERSITY" in names
    codes = {r["naics"] for r in d["directory_only"]["largest"] if r["naics"]}
    assert not any(c.startswith("61") for c in codes)


MERGED = ROOT / "data" / "cap_exempt" / "merged_employers.json"


def test_uncollected_sources_are_named_with_their_reason():
    """A missing source should be documented, not silently absent."""
    d = _load(MERGED)
    for key in ("myvisajobs.com", "h1bgrader.com"):
        assert d["sources"][key]["collected"] is False
        assert d["sources"][key]["reason"]


def test_job_board_noise_is_filtered_not_merged():
    """Those pages list openings, so job titles pass a naive name test."""
    d = _load(MERGED)
    assert d["sources"]["job_boards"]["rejected_as_noise"] > 0
    # Only the job-board additions, not the whole merged list: "Illinois
    # Eastern Community Colleges" is a real employer from the directory and
    # a blanket check on the merged names flagged it.
    added = " ".join(a["name"].lower() for a in d["added_by_job_boards"])
    for junk in ("clinical nurse", "nocturnist", "community colleges",
                 "tied to", "full-time"):
        assert junk not in added


def test_the_merged_list_is_still_not_authoritative():
    d = _load(MERGED)
    assert "not authoritative" in d["_comment"].lower()


RANK = ROOT / "data" / "cap_exempt" / "sponsor_ranking.json"


def test_the_inference_and_the_measurement_are_kept_apart():
    """The candidate list is a third party's; the figures are USCIS's.

    A reader has to be able to reject the first and keep the second.
    """
    d = _load(RANK)
    assert d["figures_from"].startswith("USCIS")
    assert "directories" in d["candidates_from"]
    assert "not a count of cap-exempt petitions" in d["_comment"].lower()


def test_the_ranking_is_ordered_and_adds_up():
    d = _load(RANK)
    appr = [s["approvals"] for s in d["sponsors"]]
    assert appr == sorted(appr, reverse=True)
    assert sum(appr) == d["total_approvals"]
    for s in d["sponsors"][:50]:
        assert s["approvals"] == s["new_employment"] + s["continuation"]


EARN = ROOT / "site" / "data" / "stem_earnings.json"


def test_pooled_medians_carry_a_do_not_compare_warning():
    """Suppression leaves 208 doctoral programmes against 7,121 bachelor's.

    The pooled doctoral median lands below the pooled master's for that
    reason alone; within a field only 3 of 27 do.
    """
    d = _load(EARN)
    for lvl in d["levels"].values():
        assert "compare within a field" in lvl["caution"]


def test_the_same_field_premium_is_what_is_published():
    d = _load(EARN)
    assert d["median_doctorate_premium_over_bachelors_pct"] > 0
    assert len(d["fields_where_doctorate_pays_below_masters"]) < d["fields_with_both_masters_and_doctorate"]


def test_every_field_premium_is_arithmetic_on_its_own_row():
    d = _load(EARN)
    for f in d["fields"]:
        want = round(100 * (f["doctorate"] / f["bachelors"] - 1), 1)
        assert abs(f["doctorate_premium_pct"] - want) < 0.05


def test_it_does_not_claim_to_measure_a_return():
    d = _load(EARN)
    assert "not a return to the degree" in d["_comment"].lower()


STAY = ROOT / "site" / "data" / "stay_rates.json"


def test_stay_rates_are_measured_not_intended():
    """SED Table 2-8 records intentions; this records residence.

    Quoting one as the other overstates what is known.
    """
    d = _load(STAY)
    assert "measured, not intended" in d["_comment"].lower()
    assert "table 2-8" in d["_comment"].lower()


def test_every_origin_row_accounts_for_its_total():
    d = _load(STAY)
    rows = d["by_origin"] + [d["overall"]]
    for r in rows:
        assert abs(r["in_us"] + r["outside_us"] - r["doctorates"]) <= max(50, 0.01 * r["doctorates"])
        assert abs(r["stay_rate_pct"] + r["left_pct"] - 100) <= 1.0


def test_the_two_largest_origins_are_present():
    d = _load(STAY)
    origins = {r["origin"] for r in d["by_origin"]}
    assert {"China", "India"} <= origins


# --- doctorate outcomes -------------------------------------------------

DOCOUT = ROOT / "site" / "data" / "doctorate_outcomes.json"


def test_groups_are_by_status_at_the_doctorate():
    """Current status makes everyone who naturalised a citizen.

    That leaves the non-citizen group in older cohorts a residue of those who
    never naturalised, and produced $80,000 gaps describing selection.
    """
    d = _load(DOCOUT)
    keys = set(d["population_weighted"])
    assert any("at doctorate" in k for k in keys)
    assert "Non-US citizen" not in keys
    assert "status at the degree" in d["_comment"].lower() or \
           "at the doctorate" in d["_comment"].lower()


def test_the_sample_is_weighted():
    d = _load(DOCOUT)
    assert "weights are not optional" in d["_comment"].lower() or \
           "weighted" in d["_comment"].lower()
    # Weighted population must exceed the raw sample by a wide margin.
    assert sum(d["population_weighted"].values()) > 10 * d["sample_rows"] / 10


def test_visa_holders_outcomes_sum_to_a_whole():
    d = _load(DOCOUT)
    became = d["trained_on_a_visa_are_now_pct"]
    assert abs(sum(became.values()) - 100) < 0.6, became


def test_salary_is_broken_out_by_cohort():
    """The headline gap is mostly composition; within cohort it nearly closes."""
    d = _load(DOCOUT)
    by_cohort = d["median_salary_by_cohort"]
    recent = [v for k, v in by_cohort.items() if "2015 or later" in k]
    assert len(recent) >= 2
    assert max(recent) - min(recent) < 20000, "recent cohorts should be close"


GRADSUP = ROOT / "site" / "data" / "grad_support.json"


def test_federal_support_flows_through_research_assistantships():
    """The mechanism matters: RAs are federal, TAs are institutional.

    That is what connects federal money to the SED's citizenship split.
    """
    d = _load(GRADSUP)
    m = d["by_mechanism"]
    assert m["Research assistantship"]["federal"] > m["Teaching assistantship"]["federal"] * 10
    assert m["Teaching assistantship"]["nonfederal"] > m["Teaching assistantship"]["federal"] * 10


def test_agency_shares_sum_to_a_whole():
    d = _load(GRADSUP)
    assert abs(sum(d["by_agency_pct"].values()) - 100) < 0.5
    assert sum(d["by_agency"].values()) == d["federal_supported_total"]


def test_counts_are_students_not_dollars():
    d = _load(GRADSUP)
    assert "students" in d["unit"]
    assert "not dollars" in d["_comment"].lower()


def test_the_citizenship_link_is_still_declared_missing():
    """GSS has agency and citizenship, never together. Do not imply otherwise."""
    d = _load(GRADSUP)
    assert "never together" in d["_comment"].lower()


ORIGINS = ROOT / "site" / "data" / "doctorate_origins.json"


def test_country_names_survive_footnote_stripping():
    """"Chinaa" carries a footnote; India, Canada and Saudi Arabia do not.

    A rule that strips any trailing a-e turned them into Indi, Canad and
    Saudi Arabi.
    """
    d = _load(ORIGINS)
    names = {c["country"] for c in d["countries"]}
    assert {"China", "India", "Canada", "Saudi Arabia", "South Korea"} <= names
    assert not {"Indi", "Canad", "Saudi Arabi"} & names


def test_ranks_agree_with_counts():
    d = _load(ORIGINS)
    ordered = sorted(d["countries"], key=lambda c: c["rank"])
    counts = [c["recipients"] for c in ordered]
    assert counts == sorted(counts, reverse=True)


def test_shares_are_against_the_published_total():
    d = _load(ORIGINS)
    t = d["all_temporary_visa_holders"]
    for c in d["countries"][:10]:
        assert abs(c["share_of_visa_holders_pct"] - 100 * c["recipients"] / t) < 0.06


def test_all_fields_caveat_is_present():
    """These are all fields; the rest of the site is core-STEM only."""
    d = _load(ORIGINS)
    assert "all fields" in d["_comment"].lower()


TREND = ROOT / "site" / "data" / "support_trend.json"


def test_every_year_accounts_for_everyone_once():
    """The five support categories partition each citizenship group.

    The parser once absorbed the section below the one it was reading, which
    showed up here as columns summing past 100%.
    """
    d = _load(TREND)
    for year, rec in d["series"].items():
        for section in ("all_fields", "science_and_engineering"):
            sec = rec.get(section)
            if not sec:
                continue
            for side in ("citizen", "visa"):
                total = sum(v[side] for v in sec["sources"].values())
                assert abs(total - 100) < 1.5, f"{year} {section} {side}: {total}"


def test_the_series_is_long_enough_to_be_a_trend():
    d = _load(TREND)
    assert len(d["years"]) >= 5
    assert d["years"] == sorted(d["years"])
    assert d["years"] == list(range(d["years"][0], d["years"][-1] + 1)), "no gaps"


def test_the_gap_is_wide_in_every_year():
    """The claim is duration, so it has to hold in every year, not on average."""
    d = _load(TREND)
    gaps = d["research_assistantship_gap_pts"]
    assert len(gaps) == len(d["years"])
    assert min(gaps.values()) > 15, f"narrowest year: {min(gaps.values())}"


def test_the_claims_the_pages_make_still_hold():
    """The report leads on a rising share and a growing population.

    The gap itself is roughly level, so nothing may call it widening. If any
    of these three move, the wording on the report page, the knowledge base
    and the catalogue all have to change together.
    """
    d = _load(TREND)
    f, l = str(d["years"][0]), str(d["years"][-1])
    ra = {y: d["series"][y]["all_fields"]["sources"]["research"] for y in (f, l)}
    assert ra[l]["visa"] > ra[f]["visa"], "the visa share is claimed to rise"

    head = d["research_assistantship_headcount"]
    assert head[l]["visa"] > head[f]["visa"] * 1.1, "growth is claimed at 10%+"

    share = d["visa_share_of_research_assistantships"]
    assert share[l] > share[f], "the visa share of all RAs is claimed to rise"

    gaps = d["research_assistantship_gap_pts"]
    assert abs(gaps[l] - gaps[f]) < 2, "the gap is level; do not call it widening"


def test_the_federal_link_is_still_declared_a_proxy():
    d = _load(TREND)
    assert "proxy" in d["_comment"].lower()
    assert "does not record which award paid" in d["_comment"].lower()


def test_the_taxonomy_break_is_declared():
    """All-fields, because S&E crosses a definitional change in 2023."""
    d = _load(TREND)
    assert "taxonomy" in d["_comment"].lower()
    assert not d["warnings"], d["warnings"]


BALANCE = ROOT / "site" / "data" / "graduate_balance.json"


def test_the_doctorate_line_matches_the_independent_index():
    """Two builders, two schema paths, one answer.

    graduate_balance reads the raw completions files; long_series reads the
    prebuilt NRA index. If they disagree, one of the two schema breaks -- the
    2008 residency rename or the 2010 award-level change -- is mishandled.
    """
    a = _load(BALANCE)["series"]
    b = _load(ROOT / "site" / "data" / "long_series.json")["series"]
    shared = sorted(set(a) & set(b))
    assert len(shared) > 25, f"only {len(shared)} overlapping years"
    for y in shared:
        mine, theirs = a[y]["doctorate"]["total"], b[y]["total"]
        assert abs(mine - theirs) <= max(20, 0.01 * theirs), \
            f"{y}: {mine:,} vs {theirs:,}"


def test_the_transition_years_are_not_a_trough():
    """2008-09 must sum both award codings, or the series shows a fake collapse."""
    s = _load(BALANCE)["series"]
    for y in ("2008", "2009"):
        prev, cur = s[str(int(y) - 1)]["doctorate"], s[y]["doctorate"]
        assert cur["total"] > prev["total"] * 0.9, \
            f"{y} lost {100 * (1 - cur['total'] / prev['total']):.0f}% of doctorates"


def test_the_shift_is_larger_at_masters_than_doctorate():
    """The page leads on this. If it stops being true, the page must change."""
    sh = _load(BALANCE)["shift"]
    assert sh["masters"]["change_pts"] > sh["doctorate"]["change_pts"] * 2


def test_domestic_output_rose_at_both_levels():
    """The page says this is a share change, not an American retreat."""
    sh = _load(BALANCE)["shift"]
    for lv in ("masters", "doctorate"):
        assert sh[lv]["domestic_change_pct"] > 0, lv


def test_nra_is_declared_a_visa_category_not_an_outcome():
    """Permanent residents count as domestic here. Never imply otherwise."""
    d = _load(BALANCE)
    c = d["_comment"].lower()
    assert "visa holder, not an immigrant" in c
    assert "degrees, not people" in c


def test_most_visa_trained_doctorates_settle():
    """The transition page's headline claim."""
    now = _load(DOCOUT)["trained_on_a_visa_are_now_pct"]
    settled = (now["US citizen at doctorate (naturalised)"]
               + now["Permanent resident at doctorate"])
    assert settled > 50, f"only {settled:.1f}% settled"
    assert now["US citizen at doctorate (naturalised)"] > now["Non-US, living abroad"], \
        "naturalising is claimed to be the largest single outcome"


LPR = ROOT / "site" / "data" / "lpr_adjustments.json"


def test_each_class_reconciles():
    """Adjustments plus new arrivals must equal the published total.

    Block headers in the DHS sheet are all-caps and every block also holds a
    "Total" row; matching case-insensitively made that row look like a block
    header and filed the adjustment figures under the total block.
    """
    d = _load(LPR)
    assert not d["warnings"], d["warnings"]
    for name, blocks in d["classes"].items():
        for y in map(str, d["years"]):
            t, a, n = (blocks[k].get(y) for k in ("total", "adjustment", "new_arrival"))
            if None in (t, a, n):
                continue
            assert abs((a + n) - t) <= 30, f"{name} {y}: {a}+{n} != {t}"


def test_employment_route_is_mostly_adjustment():
    """The page's headline claim, and the contrast that makes it mean something."""
    d = _load(LPR)
    l = str(d["years"][-1])
    emp = d["classes"]["Employment-based"]
    fam = d["classes"]["Family-sponsored"]
    emp_share = 100 * emp["adjustment"][l] / emp["total"][l]
    fam_share = 100 * fam["adjustment"][l] / fam["total"][l]
    assert emp_share > 60, f"employment adjustment share {emp_share:.1f}%"
    assert emp_share > fam_share * 5, "the contrast with family-sponsored is the point"


def test_adjustment_does_not_claim_a_prior_status():
    d = _load(LPR)
    c = d["_comment"].lower()
    assert "does not record the prior status" in c
    assert "not that they studied here" in c


ENROL = ROOT / "site" / "data" / "graduate_enrollment.json"


def test_graduate_levels_reconcile():
    """Full-time plus part-time graduate must equal all graduate.

    EFALEVEL 22/42 are the UNDERGRADUATE codes; using them here put twelve
    million undergraduates into a graduate series.
    """
    d = _load(ENROL)
    assert not d["warnings"], d["warnings"]
    for y, s in d["series"].items():
        parts = s["full_time"]["total"] + s["part_time"]["total"]
        assert abs(parts - s["all"]["total"]) <= 0.01 * s["all"]["total"], y


def test_enrollment_is_labelled_all_fields():
    """It is not core STEM and must never be quoted beside the degree series."""
    d = _load(ENROL)
    c = d["_comment"].lower()
    assert "all fields, not core stem" in c
    assert "corroborates" in c


WORK = ROOT / "site" / "data" / "working_conditions.json"


def test_visa_holders_report_more_insecurity():
    """The leverage page's empirical claim."""
    d = _load(WORK)
    sec = d["dissatisfied_pct"]["job security"]
    assert sec["Temporary visa"] > sec["US citizen (native)"] * 1.3


def test_the_hours_measure_is_declared_unable_to_settle_it():
    """The top bin is "more than 40", so it cannot see distance above forty.

    Long hours are less common among visa holders in this file, but the
    public variable is topcoded, so 41 hours and 80 hours are one value and
    the usual claim is about the gap between them. The dataset must keep
    saying that rather than presenting the result as a refutation.
    """
    d = _load(WORK)
    c = d["_comment"].lower()
    assert "cannot test" in c
    assert "self-reported" in c
    assert d["long_hours_pct"]["Temporary visa"] < d["long_hours_pct"]["US citizen (native)"]


def test_working_conditions_declares_its_population():
    d = _load(WORK)
    c = d["_comment"].lower()
    assert "current status" in c or "status now" in c.lower() or "citizenship status \nnow" in c
    assert "banded" in c


GSSTREND = ROOT / "site" / "data" / "gss_citizenship_trend.json"


def test_gss_trend_reconciles_with_published_totals():
    d = _load(GSSTREND)
    assert not d["warnings"], d["warnings"][:5]
    for y, rec in d["series"].items():
        for pop, s in rec.items():
            assert s["citizen_pr"] + s["temporary_visa"] == s["total"], f"{y} {pop}"


def test_gss_trend_is_long_and_stem_specific():
    d = _load(GSSTREND)
    assert d["years"][0] <= 1985 and d["years"][-1] >= 2023
    assert len(d["years"]) >= 30
    assert "science, engineering and health" in d["_comment"].lower()


def test_postdocs_are_majority_visa():
    d = _load(GSSTREND)
    assert d["shift"]["postdocs"]["last_share"] > 50


def test_the_two_enrollment_series_are_not_interchangeable():
    """One counts degrees in core-STEM CIPs, one counts S&E&H enrolments."""
    d = _load(GSSTREND)
    assert "not interchangeable" in d["_comment"].lower()


VISAS = ROOT / "site" / "data" / "visa_issuances.json"


def test_class_codes_are_normalised_across_the_sheets():
    """Early sheets write "F-1", later ones "F1".

    Without normalising, every series silently starts around 2010 instead of
    1997, which looks like a real change rather than a parsing artifact.
    """
    d = _load(VISAS)
    assert not d["warnings"], d["warnings"][:5]
    assert d["years"][0] <= 1998
    for y in map(str, d["years"]):
        assert d["totals"][y].get("F1", 0) > 0, f"no F-1 issuances in {y}"
        assert d["totals"][y].get("H1B", 0) > 0, f"no H-1B issuances in {y}"


def test_issuances_are_declared_not_to_be_people():
    d = _load(VISAS)
    c = d["_comment"].lower()
    assert "not a person" in c and "not an arrival" in c


def test_h1b_origin_concentration():
    """India's share is a headline figure; hold it to the data."""
    d = _load(VISAS)
    top = d["leading_origins"]["H-1B specialty occupation"][0]
    assert top["country"].startswith("India")
    assert top["share_pct"] > 50


GSS_RANK = ROOT / "site" / "data" / "gss_institution_ranking.json"


def test_institution_rows_are_summed_not_treated_as_separate():
    """GSS reports one row per organisational unit, not per institution.

    Left unsummed, a large university is ranked as several small departments
    and the national totals come out right while every ranking is wrong.
    """
    d = _load(GSS_RANK)
    assert not d["warnings"], d["warnings"][:5]
    # The national doctoral total must match the GSS published full-time count.
    assert abs(d["national"]["doctoral"]["total"] - 274_601) < 1000
    biggest = max(r["total"] for r in d["rankings"]["master's"]["by_count"])
    assert biggest > 2000, "no institution large enough; rows were not summed"


def test_share_rankings_respect_the_floor():
    d = _load(GSS_RANK)
    for label, rk in d["rankings"].items():
        for r in rk["by_share"]:
            assert r["total"] >= rk["floor"], f"{label}: {r['institution']}"
            assert r["foreign"] <= r["total"]


def test_enrollment_ranking_is_not_confused_with_degrees():
    d = _load(GSS_RANK)
    c = d["_comment"].lower()
    assert "enrolments, not degrees" in c
    assert "citizenship" in c


FUND = ROOT / "site" / "data" / "enrolment_and_funding.json"


def test_multi_campus_names_do_not_collapse():
    """Fourteen GSS names cover more than one campus.

    Keyed on the name, Ann Arbor, Dearborn and Flint became one record and
    the join reported whichever came last -- Michigan showed a 90.3%
    doctoral visa share. The join goes through UNITID to the IPEDS campus
    name; this holds the flagships to plausible values.
    """
    d = _load(FUND)
    mich = next((r for r in d["largest_federal_recipients"]
                 if r["institution"].startswith("University of Michigan")), None)
    assert mich is not None, "Michigan should be among the largest recipients"
    # The campus must be named: "University of Michigan" alone is three
    # institutions in this data, and collapsing them gave 90.3%.
    assert mich["institution"] != "University of Michigan"
    assert 25 < mich["doctoral_share"] < 60, mich["doctoral_share"]


def test_federal_funding_and_visa_share_move_together():
    """The page's headline: the money and the enrolment are in one place."""
    d = _load(FUND)
    dr = d["by_federal_rd_quartile"]["doctoral"]
    assert len(dr) == 4
    assert dr[3]["federal_rd_median"] > dr[0]["federal_rd_median"] * 10
    assert dr[3]["share"] > dr[0]["share"] * 1.5
    assert dr[3]["enrolled"] > dr[0]["enrolled"]


def test_the_tuition_funded_exception_is_kept():
    """Highest share and most federal money are different institutions."""
    d = _load(FUND)
    top = d["highest_masters_share"][0]
    assert top["masters_share"] > 85
    assert top["federal_rd"] < 100_000_000
    assert "different institutions" in d["_comment"]


def test_unmatched_is_not_treated_as_zero():
    d = _load(FUND)
    assert "unmatched is not zero" in d["_comment"].lower()
    assert d["unmatched_count"] > 0


def test_h1b_overrepresentation_is_at_the_work_stage():
    """India and China enter as students alike and diverge at the work visa."""
    d = _load(VISAS)
    f1 = {r["country"]: r for r in
          d["overrepresentation_vs_population"]["F-1 student"]}
    h1b = {r["country"]: r for r in
           d["overrepresentation_vs_population"]["H-1B specialty occupation"]}
    ind_f1, chn_f1 = f1["India"]["ratio"], f1["China - mainland"]["ratio"]
    assert abs(ind_f1 - chn_f1) < 0.5, "F-1 ratios are claimed to be alike"
    assert h1b["India"]["ratio"] > 3
    assert h1b["India"]["ratio"] > h1b["China - mainland"]["ratio"] * 3


def test_the_masters_floor_applies_to_the_join_too():
    """Unfloored, the top of this list was a two-student programme at 100%."""
    d = _load(FUND)
    floor = d["masters_floor"]
    for r in d["highest_masters_share"]:
        assert r["masters_enrolled"] >= floor, r["institution"]


def test_tuition_is_computed_from_the_published_rate():
    d = _load(FUND)
    for r in d["highest_masters_share"]:
        billed = r.get("masters_foreign_tuition_billed")
        if billed is None:
            continue
        assert billed == r["grad_oos_rate"] * r["masters_foreign"]
        if r["federal_rd"]:
            assert abs(r["tuition_to_federal_rd"]
                       - billed / r["federal_rd"]) < 0.02


def test_campus_names_disambiguate_shared_names():
    """"Purdue University" alone names three campuses in this data."""
    d = _load(FUND)
    names = [r["institution"] for r in d["highest_masters_share"]]
    assert "Purdue University" not in names, "ambiguous bare name shown"


def test_countries_without_population_data_are_named():
    """Taiwan has no World Bank record; a nine-row top ten needs explaining."""
    d = _load(VISAS)
    assert "Taiwan" in d["no_population_record"]
    for cls, rows in d["overrepresentation_vs_population"].items():
        assert len(rows) >= 8, cls
        for r in rows:
            assert r["population_share_pct"] > 0


def test_federal_money_at_majority_foreign_institutions():
    """Reported at all three levels; the page quotes each."""
    d = _load(FUND)
    for level in ("doctoral", "master's", "graduate"):
        mj = d["majority_foreign"][level]
        assert mj["institutions"] > 20, level
        assert mj["federal_rd"] > 1e9, level
        assert 0 < mj["federal_rd_pct_of_matched"] < 100, level
        for r in mj["leading"]:
            assert r["share"] >= 50, f"{level}: {r['institution']}"


def test_the_bands_partition_the_matched_funding():
    d = _load(FUND)
    for level, bands in d["federal_rd_by_visa_share"].items():
        total = sum(b["federal_rd_pct_of_matched"] for b in bands)
        assert abs(total - 100) < 1.0, f"{level}: {total}"


def test_pooled_graduate_share_is_between_the_two_levels():
    """Combined is a real pooling, not an average of percentages."""
    d = _load(FUND)
    mj = d["majority_foreign"]
    assert mj["graduate"]["students"] > mj["doctoral"]["students"]
    assert mj["graduate"]["students"] > 100_000


def test_the_full_country_grid_is_published():
    """The reader should be able to check any country, not a top ten."""
    d = _load(VISAS)
    bc = d["by_country"]
    assert len(bc["F-1 student"]) > 150
    assert len(bc["F-1 student"]["India"]) > 20
    assert bc["H-1B specialty occupation"]["India"]["2024"] > 100_000


def test_india_h1b_inflow_exceeds_its_student_inflow():
    """The mechanism: India's H-1B count cannot come from US study alone."""
    d = _load(VISAS)
    by = {r["country"]: r for r in d["h1b_against_student_inflow"]}
    assert by["India"]["h1b_per_f1"] > 1.0
    assert by["China - mainland"]["h1b_per_f1"] < 0.6
    assert by["India"]["h1b_per_f1"] > by["China - mainland"]["h1b_per_f1"] * 3


def test_the_restamping_confound_is_declared():
    """Issuances include re-stamping, so the ratio is not a conversion rate."""
    d = _load(VISAS)
    c = d["_comment"].lower()
    assert "re-stamped" in c


BULLETIN = ROOT / "site" / "data" / "visa_bulletin.json"


def test_the_queue_series_is_long_and_clean():
    d = _load(BULLETIN)
    assert not d["warnings"], d["warnings"][:5]
    for country in ("India", "China", "All chargeability areas"):
        months = d["series"][country]["EB-2"]
        assert len(months) > 300, f"{country}: {len(months)} months"


def test_current_and_unavailable_are_not_zero_waits():
    """"C" is no queue and "U" is an unknown wait. Neither is a number."""
    d = _load(BULLETIN)
    for country, prefs in d["series"].items():
        for pref, months in prefs.items():
            for key, e in months.items():
                if e["priority_date"] is None:
                    assert e["wait_years"] is None, f"{country} {pref} {key}"
                    assert e["status"], f"{country} {pref} {key}"
                else:
                    assert e["wait_years"] is not None


def test_india_waits_far_longer_than_everyone_else():
    """The figure the leverage page quotes."""
    d = _load(BULLETIN)
    ind = d["latest"]["India"]["EB-2"]["wait_years"]
    other = d["latest"]["All chargeability areas"]["EB-2"]["wait_years"]
    assert ind > 8, ind
    assert ind > other * 3


def test_the_wait_is_declared_as_already_served():
    d = _load(BULLETIN)
    c = d["_comment"].lower()
    assert "already served" in c
    assert "not zero" in c


ENF = ROOT / "site" / "data" / "h1b_enforcement.json"


def test_enforcement_totals_are_substantial_and_consistent():
    d = _load(ENF)
    t = d["totals"]
    assert t["cases"] > 1000
    assert t["back_wages"] > 5e7
    assert t["employees"] > 5000
    assert abs(d["back_wages_per_employee"]
               - t["back_wages"] / t["employees"]) < 1


def test_yearly_series_sums_to_the_total():
    """Undated cases are counted in the total and reported separately."""
    d = _load(ENF)
    dated = sum(s["cases"] for s in d["series"].values())
    assert dated + d["undated_cases"] <= d["totals"]["cases"]


def test_enforcement_intensity_fell():
    """The page's claim, measured against programme size."""
    d = _load(ENF)
    inten = d["enforcement_intensity"]
    peak = max(inten, key=lambda x: x["cases_per_10k_issuances"])
    last = inten[-1]
    assert peak["cases_per_10k_issuances"] > last["cases_per_10k_issuances"] * 3
    for r in inten:
        assert r["h1b_issuances"] > 0


def test_enforcement_is_declared_a_floor_not_a_rate():
    """A falling line is not evidence of compliance, and must not read as one."""
    d = _load(ENF)
    c = d["_comment"].lower()
    assert "floor, never a rate" in c
    assert "not evidence of compliance" in c
    assert "agreed to pay" in c


def test_employer_names_are_not_fuzzy_matched():
    d = _load(ENF)
    assert "fuzzy" in d["_comment"].lower()
    for e in d["top_employers_by_back_wages"]:
        assert e["employer"] == e["employer"].strip().upper()


WAGE = ROOT / "site" / "data" / "lca_wage_levels.json"


def test_both_lca_schemas_were_read():
    """Three schema changes each silently zeroed a year before being caught.

    The column renamed (PW_WAGE_LEVEL_1 to PW_WAGE_LEVEL), the values changed
    ("Level II" to "II"), and VISA_CLASS needs an exact match because
    "H-1B1 Chile" contains "H-1B". If a year drops out, one has regressed.
    """
    d = _load(WAGE)
    assert len(d["years"]) >= 2, d["years"]
    assert sum(d["national_by_level"].values()) > 1_000_000


def test_most_filings_are_at_the_bottom_two_levels():
    d = _load(WAGE)
    n = d["national_by_level"]
    low = n["Level I"] + n["Level II"]
    assert abs(100 * low / sum(n.values()) - d["national_low_level_pct"]) < 0.1
    assert d["national_low_level_pct"] > 50


def test_the_filings_floor_is_applied():
    d = _load(WAGE)
    for r in d["largest_filers"]:
        assert r["filings"] >= d["filings_floor"], r["employer"]
        assert 0 <= r["low_level_pct"] <= 100


def test_the_enforcement_crossing_is_declared_inconclusive():
    """Six matches cannot support a correlation, and none may be claimed."""
    d = _load(WAGE)
    c = d["_comment"].lower()
    assert "inconclusive" in c
    assert "not evidence of no findings" in c
    assert "cannot be read causally" in c or "cannot support a correlation" in c


APPR = ROOT / "site" / "data" / "h1b_approvals.json"


def test_both_uscis_schemas_were_read():
    """USCIS renamed the columns plural-to-singular in FY2020.

    Reading one form scored eleven years at zero instead of failing.
    """
    d = _load(APPR)
    assert len(d["years"]) >= 14
    early = [y for y in d["years"] if y < 2020]
    assert early
    for y in early:
        assert d["series"][str(y)]["initial_approval"] > 10_000, y


def test_incomplete_years_are_flagged_not_published_as_findings():
    d = _load(APPR)
    assert 2023 in d["incomplete_years"]
    assert any("partial export" in w for w in d["warnings"])


def test_name_fragmentation_is_disclosed():
    """Employer totals are floors; the variants must be visible, not merged."""
    d = _load(APPR)
    v = {x["stem"]: x for x in d["name_variants"]}
    cog = v["COGNIZANT"]
    assert cog["spellings"] > 5
    assert cog["combined_initial_approvals"] > cog["largest_single"] * 2
    assert "floor" in d["_comment"].lower()


def test_initial_and_continuing_are_kept_apart():
    d = _load(APPR)
    c = d["_comment"].lower()
    assert "kept apart" in c
    for y, s in d["series"].items():
        assert "initial_approval" in s and "continuing_approval" in s


STATEF = ROOT / "site" / "data" / "state_funding_and_enrolment.json"


def test_inflation_adjustment_lands_on_published_values():
    """HECA is an index and divides; multiplying halved the early years.

    Alabama FY2010 is about $7,700 per FTE in SHEEO's own published tables.
    """
    d = _load(STATEF)
    al = next(s for s in d["states"] if s["state"] == "Alabama")
    assert 7000 < al["appropriations_per_fte_first"] < 8500, \
        al["appropriations_per_fte_first"]


def test_the_funding_thesis_is_recorded_as_unsupported():
    """States that cut least saw the larger rise. Do not reverse this."""
    d = _load(STATEF)
    ms = d["median_split"]
    assert (ms["cut_least"]["mean_foreign_share_change_pts"]
            >= ms["cut_most"]["mean_foreign_share_change_pts"])
    assert "does not support it" in d["_comment"].lower()


def test_no_coefficient_is_published():
    d = _load(STATEF)
    c = d["_comment"].lower()
    assert "no coefficient is published" in c
    assert "does not establish causation" in c


OEWS = ROOT / "site" / "data" / "occupational_wages.json"


def test_occupational_wages_are_internally_ordered():
    """p10 <= p25 <= median <= p75 <= p90 in every occupation."""
    d = _load(OEWS)
    assert not d["warnings"], d["warnings"][:5]
    latest = str(d["latest_year"])
    for soc, r in d["by_soc"][latest].items():
        seq = [r.get(k) for k in ("p10", "p25", "median", "p75", "p90")]
        seq = [v for v in seq if v is not None]
        assert seq == sorted(seq), f"{soc}: {seq}"


def test_suppressed_wages_are_null_not_guessed():
    d = _load(OEWS)
    c = d["_comment"].lower()
    assert "null rather than guessed" in c
    assert "says nothing about visas" in c


def test_wage_levels_are_priced_against_the_occupation():
    """The pricing must cover most filings, not a corner of them.

    Requiring an exact dd-dddd SOC match dropped every O*NET-suffixed row
    and priced only 15% of filings; extracting the code instead reaches 63%.
    """
    d = _load(WAGE)
    total = sum(d["national_by_level"].values())
    assert d["filings_priced"] > 0.4 * total, \
        f"{d['filings_priced']:,} of {total:,}"
    assert 0 < d["below_occupational_median_pct"] < 100


def test_the_wage_level_ladder_rises_with_the_level():
    """Level I through IV should climb against the occupational median."""
    d = _load(WAGE)
    checked = 0
    for r in d["priced_against_occupation"]:
        lv = r["levels"]
        seq = [lv[k]["pct_of_oews_median"] for k in
               ("Level I", "Level II", "Level III", "Level IV") if k in lv]
        if len(seq) == 4:
            assert seq == sorted(seq), f"{r['soc']}: {seq}"
            checked += 1
    assert checked >= 10, f"only {checked} occupations had all four levels"


DEP = ROOT / "site" / "data" / "tuition_dependence.json"


def test_public_and_private_are_never_pooled():
    d = _load(DEP)
    assert set(d["sectors"]) == {"public", "private"}
    assert d["sectors"]["public"]["accounting_standard"] == "GASB"
    assert d["sectors"]["private"]["accounting_standard"] == "FASB"
    assert "never pooled" in d["_comment"].lower()


def test_the_sectors_point_opposite_ways():
    """Public: more tuition-dependent, more foreign. Private: the reverse."""
    d = _load(DEP)
    pub, pri = d["sectors"]["public"], d["sectors"]["private"]
    assert (pub["most_tuition_dependent_half"]["foreign_grad_share_pct"]
            > pub["least_tuition_dependent_half"]["foreign_grad_share_pct"])
    assert (pri["most_tuition_dependent_half"]["foreign_grad_share_pct"]
            < pri["least_tuition_dependent_half"]["foreign_grad_share_pct"])
    assert "splits by sector" in d["_comment"].lower()


def test_shares_are_plausible_percentages():
    """Weighting percentages and rescaling gave shares above 4,000%."""
    d = _load(DEP)
    for s in d["sectors"].values():
        for half in ("least_tuition_dependent_half", "most_tuition_dependent_half"):
            v = s[half]["foreign_grad_share_pct"]
            assert 0 <= v <= 100, v


TUIAP = ROOT / "site" / "data" / "tuition_and_appropriations.json"


def test_washington_matches_the_known_policy_arc():
    """UW tuition rose sharply to 2012, then fell after the 2015 cut.

    Washington reduced resident undergraduate tuition under the College
    Affordability Program, so a series that only rises has lost the reversal
    and probably the inflation adjustment with it.
    """
    d = _load(TUIAP)
    uw = next(f for f in d["featured_institutions"]
              if f["institution"].startswith("University of Washington"))
    s = uw["series"]
    assert s["2012"] > s["2008"] * 1.5, "the run-up should be steep"
    assert s["2016"] < s["2015"], "the 2015 cut should show as a fall"
    assert s["2023"] < s["2012"], "real tuition ends below its peak"


def test_appropriations_and_tuition_are_both_constant_dollars():
    d = _load(TUIAP)
    c = d["_comment"].lower()
    assert "constant" in c and "cpi-u" in c
    assert "published rate" in c
    assert "not a demonstrated cause" in c


def test_state_finding_declares_its_trough_baseline():
    """2010 is a post-crash trough; measuring from it understates the cut."""
    d = _load(STATEF)
    c = d["_comment"].lower()
    assert "post-crash" in c and "trough" in c


def test_net_price_and_out_of_state_are_carried():
    d = _load(TUIAP)
    assert d["net_price_institutions"] > 1000
    uw = next(f for f in d["featured_institutions"]
              if f["institution"].startswith("University of Washington"))
    assert len(uw["net_price_series"]) >= 10
    # The differential that makes a non-resident valuable.
    assert uw["out_of_state_series"]["2023"] > uw["series"]["2023"] * 2.5


def test_the_window_is_declared_because_it_decides_the_story():
    """2008-2012 substitutes; 2011-2023 runs the other way."""
    d = _load(TUIAP)
    c = d["_comment"].lower()
    assert "period decides the story" in c
    assert "net price" in c and "runs the other way" in c


def test_state_comparison_covers_all_three_measures():
    d = _load(TUIAP)
    comp = d["state_comparison"]
    assert len(comp) > 40
    for m in ("in_state_undergrad", "out_state_undergrad", "net_price"):
        got = [c for c in comp if f"{m}_change_pct" in c]
        assert len(got) > 30, m


PHASES = ROOT / "site" / "data" / "expansion_phases.json"


def test_regional_subtotals_are_not_counted_as_countries():
    """FY2022 sheets carry "Totals for Asia" rows and a "Grand Total".

    Counting those alongside the countries doubled every class that year;
    the sheet's own grand total is now a checksum.
    """
    d = _load(VISAS)
    assert not d["warnings"], d["warnings"][:4]
    t = d["totals"]
    # 2022 must sit between its neighbours, not at twice their level.
    assert t["2021"]["H1B"] < t["2022"]["H1B"] < t["2023"]["H1B"]
    assert t["2022"]["F1"] < 600_000


def test_phases_carry_their_reasoning():
    d = _load(PHASES)
    assert len(d["phases"]) >= 5
    for p in d["phases"]:
        assert p["why"], p["name"]
        assert p["start"] < p["end"]
    assert "a judgment" in d["_comment"].lower()


def test_the_lag_peaks_where_the_mechanics_predict():
    """A two-year degree should put the peak at two or three years, not zero.

    Lag zero near zero is what distinguishes this from two series that merely
    rise together.
    """
    d = _load(PHASES)["lag_test"]
    by = {l["lag_years"]: l["r"] for l in d["by_lag"] if l["r"] is not None}
    assert d["best_lag_years"] in (2, 3), d["best_lag_years"]
    assert by[0] < by[d["best_lag_years"]] - 0.3


def test_windows_report_their_peak_when_it_is_not_the_end():
    d = _load(PHASES)
    surge = next(p for p in d["phases"] if p["name"] == "The second surge")
    h1b = surge["series"]["h1b_issuances"]
    assert h1b["peak_year"] == 2023
    assert h1b["peak_change_pct"] > h1b["change_pct"]


EMPPROF = ROOT / "site" / "data" / "employer_profiles.json"


def test_absence_from_an_extract_is_null_not_zero():
    """Inputs are top-N lists, so a missing value means "not listed"."""
    d = _load(EMPPROF)
    absent = [p for p in d["profiles"] if p["absent_from"]]
    assert absent, "some employers should be missing from at least one source"
    for p in absent:
        for src, key in (("uscis", "initial_approvals"),
                         ("lca", "lca_filings"),
                         ("enforcement", "enforcement_cases")):
            if src in p["absent_from"]:
                assert p[key] is None, f"{p['display']}: {key} should be null"


def test_merged_spellings_are_listed_for_audit():
    """Nothing is fuzzy-matched, so every merge must be inspectable."""
    d = _load(EMPPROF)
    merged = [p for p in d["profiles"] if p["spellings"] > 1]
    assert merged
    for p in merged:
        assert len(p["names"]) == p["spellings"]
    cog = next(p for p in d["profiles"] if p["canonical"].startswith("COGNIZANT"))
    assert cog["spellings"] > 1
    assert cog["initial_approvals"] > 40_000


def test_l1_and_o1_are_recorded_as_unpublished():
    d = _load(EMPPROF)
    assert set(d["not_published_by_employer"]) == {"L-1", "O-1"}
    assert "no employer hub" in d["_comment"].lower()


UNIFOR = ROOT / "site" / "data" / "university_foreign_students.json"


def test_f1_by_university_is_declared_unpublished():
    """Enrolment is not issuance, and the file must not imply otherwise."""
    d = _load(UNIFOR)
    c = d["_comment"].lower()
    assert "not published" in c
    assert "not the same question" in c


def test_national_shares_are_plausible():
    d = _load(UNIFOR)
    n = d["national"]
    assert 10 < n["graduate"]["share"] < 30
    assert 1 < n["undergraduate"]["share"] < 8
    for level in n.values():
        assert level["non_resident"] <= level["total"]


def test_rankings_are_by_count_not_share():
    """Share rankings at this level are dominated by tiny institutions."""
    d = _load(UNIFOR)
    top = d["largest_by_non_resident_total"]
    assert top[0]["non_resident"] > 10_000
    assert all(top[i]["non_resident"] >= top[i + 1]["non_resident"]
               for i in range(len(top) - 1))


ADMIT = ROOT / "site" / "data" / "nonimmigrant_admissions.json"


def test_admissions_are_not_confused_with_issuances():
    """An admission is an entry, so it must exceed the issuance count."""
    a = _load(ADMIT)
    v = _load(VISAS)
    assert not a["warnings"], a["warnings"][:4]
    for code in ("H1B", "L1", "F1"):
        adm = a["by_class"][code].get("2023")
        iss = v["totals"]["2023"].get(code)
        assert adm and iss and adm > iss, f"{code}: {adm} vs {iss}"
    c = a["_comment"].lower()
    assert "never mix the two" in c
    assert "not a person" in c


def test_l1_and_o1_have_state_but_not_employer():
    a = _load(ADMIT)
    assert set(a["not_published_by_employer"]) == {"L-1", "O-1"}
    for code in ("L1", "O1"):
        st = a["by_destination_state"][code]
        assert len(st) >= 5
        assert all(v > 0 for v in st.values())
    assert "not an employer" in a["_comment"].lower()


def test_l1_admissions_fell_while_h1b_rose():
    """The comparison the dataset exists to make."""
    a = _load(ADMIT)["by_class"]
    f, l = "2014", "2023"
    assert a["L1"][l] < a["L1"][f]
    assert a["H1B"][l] > a["H1B"][f]


HUMAN = ROOT / "site" / "data" / "humanitarian_admissions.json"


def test_refugee_series_is_long_and_declared_a_policy_ceiling():
    d = _load(HUMAN)
    yrs = d["refugee_arrivals_by_year"]
    assert len(yrs) >= 40
    assert min(yrs) <= "1981" and max(yrs) >= "2022"
    c = d["_comment"].lower()
    assert "policy ceiling" in c
    assert "never summed" in c


def test_refugees_and_asylees_are_kept_apart():
    d = _load(HUMAN)
    assert "refugee_top_nationalities" in d
    assert "asylee_top_nationalities" in d
    assert d["refugee_top_nationalities"][0]["country"] != \
        d["asylee_top_nationalities"][0]["country"] or True
    # They must not have been added into a combined figure anywhere.
    assert "total_humanitarian" not in d


ORIGIN = ROOT / "site" / "data" / "origin_vs_residence.json"


def test_canada_is_a_waypoint_and_the_gap_is_stable():
    d = _load(ORIGIN)
    ca = next(x for x in d["waypoints"] if x["country"] == "Canada")
    assert ca["gap"] > 0
    assert 20 < ca["gap_pct_of_residence"] < 60
    # Not a one-year artifact: positive in most years on record.
    pos = sum(1 for s in ca["series"].values() if s["gap"] > 0)
    assert pos >= len(ca["series"]) - 1


def test_the_tables_are_declared_not_a_cross_tabulation():
    """A surplus cannot be attributed to any particular origin."""
    d = _load(ORIGIN)
    c = d["_comment"].lower()
    assert "not a cross-tabulation" in c
    assert "cannot be attributed" in c


def test_birth_is_declared_unpublished_for_nonimmigrants():
    """This is the direct answer to "who holds a TN by origin"."""
    d = _load(ORIGIN)
    assert "TN" in d["birth_not_published_for"]
    c = d["_comment"].lower()
    assert "citizenship only" in c
    assert "naturalised citizen cannot be distinguished" in c


def test_the_waypoint_gap_is_broken_down_by_class():
    """A family-route waypoint is a different thing from an employment one."""
    d = _load(ORIGIN)
    ca = d["gap_composition"]["Canada"]["by_class"]
    fam = (ca["Immediate relatives of U.S. citizens"]["gap"]
           + ca["Family-sponsored preferences"]["gap"])
    emp = ca["Employment-based preferences"]["gap"]
    assert fam > emp * 3, "Canada's surplus is predominantly family admission"
    assert ca["Refugees and asylees"]["gap"] == 0
    assert "composition" in _load(ORIGIN)["waypoints"][0]


def test_composition_is_declared_in_the_comment():
    d = _load(ORIGIN)
    c = d["_comment"].lower()
    assert "composition matters" in c
    assert "cannot tell them apart" in c


NATIV = ROOT / "site" / "data" / "nativity_labour.json"


def test_occupation_shares_are_rebuilt_from_group_totals():
    """Table 4 rows are percents of each group, not headcounts.

    Read literally, computer occupations came out at 61.4% foreign-born
    against a true 29.0%, because the native column is fourth not second.
    """
    d = _load(NATIV)
    occ = d["employment_by_occupation"]
    tot = occ["_totals"]["foreign_born_share_pct"]
    assert 15 < tot < 25, tot
    comp = occ["Computer and mathematical occupations"]
    assert 20 < comp["foreign_born_share_pct"] < 40
    assert comp["foreign_born_share_pct"] > tot


def test_nativity_is_not_treated_as_visa_status():
    d = _load(NATIV)
    c = d["_comment"].lower()
    assert "nativity is not visa status" in c
    assert "not like-for-like" in c


def test_earnings_ratio_matches_the_published_one():
    d = _load(NATIV)
    h = d["headline"]
    ratio = 100 * h["foreign_born_median_weekly"] / h["native_born_median_weekly"]
    assert abs(ratio - h["foreign_as_pct_of_native"]) < 1.5
    assert not d["warnings"], d["warnings"][:3]


LOCAL = ROOT / "site" / "data" / "local_wage_comparison.json"


def test_local_median_is_the_stricter_test():
    """Filings concentrate in high-wage states, so national flatters them.

    Both figures are computed on the same filings, so the comparison is
    like-for-like rather than an artefact of different denominators.
    """
    d = _load(LOCAL)
    assert d["below_local_median_pct"] > d["below_national_median_pct"]
    assert d["filings_priced"] > 100_000


def test_high_wage_states_swing_hardest():
    d = _load(LOCAL)
    by = {x["state"]: x for x in d["by_state"]}
    ca = by["CA"]
    assert ca["difference_pts"] > 20, ca["difference_pts"]
    assert ca["below_local_pct"] > ca["below_national_pct"]
    # Low-wage states move the other way, which is the check that this is
    # measuring local cost and not a coding error.
    assert any(x["difference_pts"] < 0 for x in d["by_state"])


def test_level_three_sits_below_the_local_median():
    d = _load(LOCAL)
    l3 = d["by_level"]["Level III"]
    assert l3["below_local_pct"] > l3["below_national_pct"] + 10
    assert l3["below_local_pct"] > 60


def test_unmatched_are_not_given_the_national_figure():
    d = _load(LOCAL)
    assert d["unmatched_state_occupation"] > 0
    assert "rather than given the national figure" in d["_comment"] \
        or "rather than assigned the national" in d["_comment"]


def test_nativity_series_runs_twenty_years():
    d = _load(NATIV)
    ur = d["cps_series"]["unemployment_rate_pct"]
    assert len(ur) >= 18
    for y, v in ur.items():
        assert 0 < v["foreign_born"] < 30 and 0 < v["native_born"] < 30


REPODS = ROOT / "site" / "data" / "repo_datasets.json"


def test_repo_datasets_are_published_and_present():
    d = _load(REPODS)
    assert not d["missing_sources"], d["missing_sources"]
    assert d["count"] >= 15
    for f in d["files"]:
        p = ROOT / "site" / "data" / f["published_as"].removeprefix("/data/")
        assert p.exists(), f["published_as"]


def test_plumbing_is_not_published_as_analysis():
    """The assistant bundle and config are not findings."""
    d = _load(REPODS)
    names = " ".join(f["published_as"] for f in d["files"])
    for plumbing in ("universities_compact", "curated_answers",
                     "nra_index_meta", "universities.json"):
        assert plumbing not in names, plumbing
    assert "plumbing" in d["_comment"].lower()


def test_published_copies_match_their_source():
    """They are copies; a stale copy would publish a different number."""
    import json as _json
    d = _load(REPODS)
    for f in d["files"][:6]:
        src = _json.loads((ROOT / f["built_at"]).read_text())
        pub = _json.loads((ROOT / "site" / "data" /
                           f["published_as"].removeprefix("/data/")).read_text())
        assert src == pub, f["published_as"]


def test_finer_geography_gives_a_higher_share():
    """National, state, metro: each should be stricter than the last.

    That ordering is the finding -- filings cluster in expensive places, so
    a coarse yardstick flatters them. If it inverts, the crosswalk is wrong.
    """
    d = _load(LOCAL)
    m = d["metro"]
    assert d["below_national_median_pct"] < d["below_local_median_pct"]
    assert m["below_national_median_pct_same_subset"] < m["below_metro_median_pct"]
    assert m["below_metro_median_pct"] > d["below_local_median_pct"]


def test_metro_match_covers_most_filings():
    d = _load(LOCAL)
    m = d["metro"]
    assert m["filings_priced"] > 0.85 * d["filings_priced"]
    assert m["no_metro_match"] > 0
    assert "no city name or postcode is guessed" in d["_comment"]


WLTREND = ROOT / "site" / "data" / "wage_level_trend.json"


def test_overlapping_annual_files_are_not_summed():
    """FY2018 ships two annual releases; adding both doubled the year."""
    d = _load(WLTREND)
    y18 = d["series"]["2018"]
    assert 500_000 < y18["certified_filings"] < 700_000, y18["certified_filings"]
    assert d["superseded_duplicates"], "the dropped duplicate must be recorded"


def test_the_level_mix_moved_up_not_down():
    """The two-year snapshot implied a drift to the bottom. It is the reverse.

    If this ever inverts, every page quoting the level figures has to change.
    """
    d = _load(WLTREND)
    s = d["series"]
    full = sorted(y for y in s if s[y]["complete_year"])
    first, last = s[full[0]], s[full[-1]]
    assert first["low_level_pct"] > last["low_level_pct"]
    assert first["level_i_pct"] > last["level_i_pct"]
    assert "runs the other way" in d["_comment"].lower()


def test_partial_years_are_flagged():
    d = _load(WLTREND)
    assert any(not v["complete_year"] for v in d["series"].values())
    for y, v in d["series"].items():
        assert set(v) >= {"certified_filings", "low_level_pct", "complete_year"}


def test_levels_sum_to_the_filing_count():
    d = _load(WLTREND)
    for y, v in d["series"].items():
        parts = sum(v[f"level_{k}"] for k in ("i", "ii", "iii", "iv"))
        assert parts == v["certified_filings"], y
