"""The state-section drill-down on the public-sector page.

WHAT THESE GUARD

An employer row in a state section opens onto every filing that employer made.
The filings are not in the page. They are in one JSON per featured state,
fetched when a row opens, and that split is where this can go wrong in ways
nothing else would catch:

  a row whose key is not in the file        the row opens onto nothing
  a file holding a filing twice             the drill-down contradicts the
                                            figure in the stat tile above it
  a merge that is not a merge               "University of Iowa" folded into
                                            "University of Iowa Community
                                            Medical Services" is a university
                                            absorbing a hospital company

So the tests assert the joint: every key in the page resolves in the file,
every filing in the state appears exactly once across the file's employers,
and the per-sector totals equal the figures the page already prints from
`by_state_detail`.

THE MERGE TESTS ARE THE SHARP END. The federal files spell one employer
several ways, and the rule that folds them has to be narrow enough to leave
genuinely different employers apart. Both directions are tested.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_public_sector_page import (                        # noqa: E402
    FEATURED, FILINGS_DIR, SHOW_DEFAULT, SHOW_MORE, TRUNCATED_AT,
    group_employers, merge_key, slugify,
)

PERM = ROOT / "site" / "data" / "public_employer_perm.json"
PAGE = ROOT / "site" / "public-sector-visas.html"


def rec(employer, sector="universities", **kw):
    """One filing, with only the fields the grouping reads."""
    base = {"employer": employer, "sector": sector, "fiscal_year": 2020,
            "decided": "2020-01-01", "job_title": "Lecturer",
            "status": "Certified"}
    base.update(kw)
    return base


# --------------------------------------------------------------------------
# the comparison key

@pytest.mark.parametrize("a,b", [
    # A file that drops the hyphen closes the words up, so replacing
    # punctuation with a space would NOT make these match.
    ("UNIVERSITY OF WISCONSIN-MADISON", "UNIVERSITY OF WISCONSINMADISON"),
    ("EMBRY-RIDDLE AERONAUTICAL UNIVERSITY", "EMBRYRIDDLE AERONAUTICAL UNIVERSITY"),
    ("WINSTON-SALEM/FORSYTH COUNTY SCHOOLS", "WINSTONSALEMFORSYTH COUNTY SCHOOLS"),
    # The legal form is not part of the employer.
    ("GEORGIA CHRISTIAN UNIVERSITY, INC.", "GEORGIA CHRISTIAN UNIVERSITY,INC"),
    ("MOREHOUSE COLLEGE", "MOREHOUSE COLLEGE, INC."),
    # A leading "The" is not either.
    ("THE COLORADO COLLEGE", "COLORADO COLLEGE"),
    # One file writes the ampersand, another writes the word.
    ("STATE OF WASHINGTON DEPT OF LABOR & INDUSTRIES",
     "STATE OF WASHINGTON DEPT OF LABOR AND INDUSTRIES"),
    ("COLLEGE OF WILLIAM & MARY", "COLLEGE OF WILLIAM AND MARY"),
    ("ST. JOHN'S UNIVERSITY", "ST. JOHNS UNIVERSITY"),
    # Some files drop the ampersand instead of spelling it, so mapping "&"
    # to "and" is not enough. 105 filings and 45 filings, one university.
    ("TEXAS A&M UNIVERSITY", "TEXAS AM UNIVERSITY"),
    ("VIRGINIA POLYTECHNIC INSTITUTE & STATE UNIVERSITY",
     "VIRGINIA POLYTECHNIC INSTITUTE  STATE UNIVERSITY"),
    ("S&C ELECTRIC COMPANY", "SC ELECTRIC COMPANY"),
    # "Company" is a legal form like "Inc".
    ("AMEREN SERVICES COMPANY", "AMEREN SERVICES"),
    ("PORTLAND GENERAL ELECTRIC COMPANY", "PORTLAND GENERAL ELECTRIC"),
    ("AMERICAN WATER WORKS SERVICE COMPANY, INC.",
     "AMERICAN WATER WORKS SERVICE CO., INC."),
])
def test_one_employer_spelled_two_ways_has_one_key(a, b):
    assert merge_key(a) == merge_key(b)


@pytest.mark.parametrize("a,b", [
    # Different employers that a looser key would have folded together.
    ("UNIVERSITY OF IOWA", "UNIVERSITY OF IOWA COMMUNITY MEDICAL SERVICES"),
    ("TEXAS TECH UNIVERSITY", "TEXAS TECH UNIVERSITY HEALTH SCIENCES CENTER"),
    ("AUBURN UNIVERSITY", "AUBURN UNIVERSITY AT MONTGOMERY"),
    ("UNIVERSITY OF HOUSTON", "UNIVERSITY OF HOUSTON-CLEAR LAKE"),
    ("MONTANA STATE UNIVERSITY", "MONTANA STATE UNIVERSITY BILLINGS"),
])
def test_two_employers_keep_two_keys(a, b):
    assert merge_key(a) != merge_key(b)


@pytest.mark.parametrize("name", ["LLC", "INC.", "THE", "AND", "& "])
def test_a_filer_named_only_for_a_dropped_word_keeps_a_key(name):
    """Stripping must never strip a name away to nothing.

    An empty key would make every such filer in a sector one employer, and
    the empty string is a prefix of every other key, so the truncation fold
    would pull the whole sector into it.
    """
    assert merge_key(name) != ""


def test_an_employer_row_id_is_never_a_numbered_twin():
    """Two employers can slug the same way. "-2" is not the answer: an id
    that is another id with a number on the end is the signature of a bug
    tests/test_anchor_slugs.py already watches for."""
    page = PAGE.read_text()
    ids = re.findall(r'<tr class="emp" id="(emp-[^"]+)"', page)
    for rid in ids:
        m = re.match(r"^(.*)-(\d+)$", rid)
        assert not (m and m.group(1) in ids), rid


# --------------------------------------------------------------------------
# grouping

def test_spellings_fold_and_the_filings_add_up():
    g = group_employers([
        rec("UNIVERSITY OF PUGET SOUND"),
        rec("THE UNIVERSITY OF PUGET SOUND"),
        rec("UNIVERSITY OF PUGET SOUND"),
    ])
    assert len(g) == 1
    assert g[0]["filings"] == 3
    assert len(g[0]["spellings"]) == 2


def test_the_merged_spellings_are_the_raw_ones_not_the_display_name():
    # The spelling list is evidence. It has to be what the file says.
    g = group_employers([rec("GEORGIA CHRISTIAN UNIVERSITY, INC."),
                         rec("GEORGIA CHRISTIAN UNIVERSITY,INC")])
    assert set(g[0]["spellings"]) == {"GEORGIA CHRISTIAN UNIVERSITY, INC.",
                                      "GEORGIA CHRISTIAN UNIVERSITY,INC"}


def test_the_same_name_in_two_sectors_stays_two_employers():
    g = group_employers([rec("CENTRAL ACADEMY", sector="universities"),
                         rec("CENTRAL ACADEMY", sector="school_districts")])
    assert len(g) == 2


def test_a_truncated_name_folds_into_the_one_it_is_a_prefix_of():
    full = "THE UNIVERSITY OF TEXAS HEALTH SCIENCE CENTER AT HOUSTON"
    cut = full[:50]
    assert len(cut) >= TRUNCATED_AT
    g = group_employers([rec(full), rec(cut), rec(cut)])
    assert len(g) == 1, "a 50-character cut is a truncation, not an employer"
    assert g[0]["filings"] == 3
    assert g[0]["name"].endswith("Houston"), g[0]["name"]


def test_a_short_prefix_is_not_treated_as_a_truncation():
    # The same prefix test, applied without the length rule, folds a
    # university into a hospital company.
    g = group_employers([
        rec("UNIVERSITY OF IOWA"),
        rec("UNIVERSITY OF IOWA COMMUNITY MEDICAL SERVICES, INC"),
    ])
    assert len(g) == 2


def test_an_ambiguous_truncation_is_left_alone():
    # A cut name that could belong to either of two longer names is not
    # evidence of which, so it stays its own row rather than being guessed
    # into the busier one.
    cut = "CALIFORNIA STATE UNIVERSITY SYSTEM OFFICE OF THE C"
    g = group_employers([rec(cut),
                         rec(cut + "HANCELLOR"),
                         rec(cut + "OMPTROLLER")])
    assert len(g) == 3


def test_employers_come_back_busiest_first():
    g = group_employers([rec("A COLLEGE"), rec("B COLLEGE"), rec("B COLLEGE")])
    assert [e["name"] for e in g] == ["B College", "A College"]


def test_filings_inside_an_employer_are_newest_first():
    g = group_employers([rec("A COLLEGE", fiscal_year=2015),
                         rec("A COLLEGE", fiscal_year=2022),
                         rec("A COLLEGE", fiscal_year=2019)])
    assert [r["fiscal_year"] for r in g[0]["rows"]] == [2022, 2019, 2015]


# --------------------------------------------------------------------------
# the published files, against the published page

@pytest.fixture(scope="module")
def perm():
    return json.loads(PERM.read_text())


@pytest.fixture(scope="module")
def page():
    return PAGE.read_text()


@pytest.fixture(scope="module")
def states(perm):
    return [st for st in FEATURED if st in perm.get("by_state_detail", {})]


def test_every_featured_state_has_a_file(states):
    assert states
    for st in states:
        assert (FILINGS_DIR / f"{slugify(st)}.json").exists(), st


def test_a_state_file_holds_every_filing_in_that_state_exactly_once(perm, states):
    for st in states:
        j = json.loads((FILINGS_DIR / f"{slugify(st)}.json").read_text())
        at = j["fields"].index("case_number")
        got = sorted(r[at] for e in j["employers"] for r in e["rows"])
        want = sorted(r["case_number"] for r in perm["records"]
                      if r["state"] == st)
        assert got == want, st


def test_a_state_file_agrees_with_the_figures_the_page_already_prints(perm, states):
    # The stat tiles come from by_state_detail. If the drill-down disagreed
    # with them, one of the two numbers on the screen would be wrong.
    for st in states:
        j = json.loads((FILINGS_DIR / f"{slugify(st)}.json").read_text())
        det = perm["by_state_detail"][st]
        assert j["filings"] == det["filings"], st
        by_sector: dict = {}
        for e in j["employers"]:
            by_sector[e["sector"]] = by_sector.get(e["sector"], 0) + e["filings"]
        for sec, s in det["sectors"].items():
            assert by_sector.get(sec) == s["filings"], (st, sec)


def test_every_row_in_the_page_resolves_to_an_employer_in_its_state_file(page, states):
    """The join the reader depends on. A row whose key is not in the file
    opens onto an error message, and nothing else would notice."""
    rows = re.findall(
        r'<tr class="emp" id="(emp-[^"]+)" data-state="([^"]+)" '
        r'data-key="([^"]+)"', page)
    assert len(rows) > 300, f"only {len(rows)} state employer rows"
    files = {slugify(st): json.loads(
        (FILINGS_DIR / f"{slugify(st)}.json").read_text()) for st in states}
    for rid, slug, key in rows:
        assert slug in files, rid
        keys = {e["key"] for e in files[slug]["employers"]}
        assert key.replace("&amp;", "&") in keys, rid


def test_every_employer_in_a_state_file_has_a_row_in_the_page(page, states):
    for st in states:
        j = json.loads((FILINGS_DIR / f"{slugify(st)}.json").read_text())
        for e in j["employers"]:
            assert f'data-key="{e["key"]}"' in page.replace("&amp;", "&"), \
                (st, e["key"])


def test_every_employer_row_id_is_unique(page):
    ids = re.findall(r'<tr class="emp" id="(emp-[^"]+)"', page)
    assert len(ids) == len(set(ids))


def test_a_detail_row_is_named_after_the_row_it_belongs_to(page):
    """The script derives the detail row's id rather than the page carrying a
    second copy of it, so the two spellings must match exactly."""
    for rid in re.findall(r'<tr class="emp" id="(emp-[^"]+)"', page):
        assert f'<tr class="detail" id="d-{rid}" hidden>' in page, rid


def test_every_state_section_has_a_drill_table(page, states):
    for st in states:
        sec = page.split(f'<section class="block" id="state-'
                         f'{st.replace(" ", "-")}">')[1].split("</section>")[0]
        assert 'class="t drill"' in sec, st
        assert sec.count('<tr class="emp"') > 0, st


def test_the_page_offers_the_three_depths_the_author_asked_for(page):
    assert SHOW_DEFAULT == 10
    assert SHOW_MORE == 50
    assert "var FIRST = 10, MORE = 50;" in page
    assert "'Show ' + MORE" in page
    assert "'Show All'" in page


def test_the_filings_are_not_inlined(page):
    """The whole point of the split. A case number in the page would mean the
    state sections had started shipping their filings again, and the page
    would be the size of the four state files put together."""
    uw = page.split('id="d-emp-washington--university-of-washington"')[1][:800]
    assert "A-2" not in uw, "a case number is in the page"
    assert '<div class="filings"></div>' in uw


def test_the_page_says_where_the_filings_come_from(page, states):
    # A reader with no JavaScript gets nothing from a row, so the file has to
    # be linked in the prose.
    for st in states:
        assert f'/data/public_sector_filings/{slugify(st)}.json' in page, st
