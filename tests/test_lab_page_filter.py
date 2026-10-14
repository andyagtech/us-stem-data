"""A department's whole doctoral cohort is not a laboratory.

The lab table says a group's composition is unusual, and the implicit
claim is that there is a hiring decision behind it. That claim fails
completely for a page listing every doctoral student in a department --
and such a page produces the most convincing wrong number this table
could print, because it is large and the share is real:

  isye.gatech.edu/people/phd-students                 173 members, 30.1%
  mccormick.northwestern.edu/.../graduate-students    254 members, 36.6%

This site already measures departments, from the thesis record, with a
denominator it can defend. Measuring one again through a crawled page
and calling it a research group is the error.

Every URL below was in the tested set on 2026-10-14. The old rule was
a regex literal inside rank_research_labs.main() that matched only at
the END of a path, so anything with a segment after it passed.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lab_page_filter import is_a_research_group                # noqa: E402

#: url -> what it actually is. None of these is a PI's roster.
NOT_GROUPS = {
    "https://www.isye.gatech.edu/people/phd-students":
        "a department's doctoral cohort, 173 people",
    "https://www.mccormick.northwestern.edu/industrial/people/graduate-students/faculty":
        "a department's doctoral cohort, 254 people",
    "https://www.isye.gatech.edu/people/advisory-board":
        "an industry advisory board, 217 people",
    "https://math.gatech.edu/undergraduate-research":
        "an undergraduate programme page, 227 people",
    "https://math.gatech.edu/faculty-research-interests":
        "a faculty index by subject",
    "https://chemistry.brown.edu/people/faculty-research-area":
        "a faculty index by subject",
    "https://alps-lab.github.io/teaching/alumni":
        "a lab's alumni, who have left -- this one reached the table",
    "https://cas.gsu.edu/alumni-partners/alumni-2/":
        "a college's alumni page, 77 people",
    "https://www.clemson.edu/cecas/departments/computing/people/emeritus.html":
        "emeritus faculty",
    "https://mae.ncsu.edu/group/faculty/emeritus/":
        "emeritus faculty",
    "https://pratt.duke.edu/about/awards/nae-members/":
        "prize recipients, 51 people",
    "https://www.pnnl.gov/undergraduate-students":
        "a national laboratory's interns, 85 people",
    "https://www.denver7.com/about/news-team":
        "a television station's news team, 63 people",
    "https://www.jpl.nasa.gov/news/nasas-roman-team-snaps-test-coronagraph-image/":
        "a press release; the extractor read the bylines",
    "https://news.engineering.asu.edu/welcome/rumena-begum/":
        "a news post about one new hire",
    "https://www.clemson.edu/cecas/departments/ce/people/advisory.html":
        "an advisory board, 85 people",
}

#: Real groups, every one of them in the published table. A .edu rule
#: would delete a quarter of it: these are professors' own domains.
REAL_GROUPS = [
    "https://www.vita-group.space/team/",
    "http://furong-huang.com/people/",
    "https://morphingmatter.org/people",
    "https://www.saliganelab.com/team",
    "https://sites.google.com/uw.edu/light/members",
    "https://www.zhaowei.us/people.html",
    "https://yuanliu.group/people/",
    "https://glycobio.wixsite.com/wangglycan/about",
    "http://weisongshi.org/students.html",
    "https://hlchen.gatech.edu/nano-aces-chen-lab-georgia-tech/people/",
]


@pytest.mark.parametrize("url,what", sorted(NOT_GROUPS.items()))
def test_a_page_that_is_not_a_group_is_excluded(url, what):
    keep, why = is_a_research_group(url)
    assert not keep, f"{what} was admitted as a research group: {url}"
    assert why, "an exclusion must say what it saw"


@pytest.mark.parametrize("url", REAL_GROUPS)
def test_a_real_group_on_its_own_domain_survives(url):
    keep, why = is_a_research_group(url)
    assert keep, (
        f"a published group was excluded by {why!r}: {url}. 24 of the 95 "
        f"are not on a .edu host; the host rule is a deny list, never an "
        f"allow list.")


def test_the_published_table_holds_no_page_the_filter_rejects():
    """The filter and the published list may not disagree."""
    import lab_overrides
    out = json.loads(
        (ROOT / "data" / "labs" / "lab_outliers.json").read_text())
    bad = []
    for r in lab_overrides.apply(out["outliers"]):
        keep, why = is_a_research_group(r["url"])
        if not keep:
            bad.append((r["url"], why))
    assert not bad, f"published rows the filter rejects: {bad}"


#: A page called "students" is the ROSTER on a professor's own site and
#: STUDENT SERVICES on a university's. Both shapes were in the data.
STUDENTS_PAGES = {
    "http://weisongshi.org/students.html": True,
    "http://merlot.stat.uconn.edu/~dey/students.html": True,
    "https://www.clemson.edu/students": False,
    "https://www.iastate.edu/student-support": False,
    "https://engineering.purdue.edu/ECE/students": False,
}


@pytest.mark.parametrize("url,keep", sorted(STUDENTS_PAGES.items()))
def test_whose_students_page_it_is(url, keep):
    got, why = is_a_research_group(url)
    assert got is keep, (
        f'"students" on {url}: expected keep={keep}, got {got} ({why})')


def test_a_lab_whose_name_contains_a_rejected_word_survives():
    """The rule is about path segments, not letters appearing somewhere."""
    for url in ("https://alumnilab.mit.edu/people",
                "https://cs.example.edu/awardslab/team",
                "https://boardgames-lab.stanford.edu/members"):
        keep, why = is_a_research_group(url)
        assert keep, f"{url} excluded by {why!r} on a substring match"


def test_the_filter_rejects_a_fifth_of_nothing_by_accident():
    """A filter that drops most of the pool is a bug, not a filter."""
    out = json.loads(
        (ROOT / "data" / "labs" / "lab_outliers.json").read_text())
    tested = out["all_tested"]
    rejected = sum(1 for r in tested if not is_a_research_group(r["url"])[0])
    assert rejected == 0, (
        f"{rejected} rows in all_tested would now be rejected; the ranker "
        f"applies this filter, so the file is stale -- re-run "
        f"scripts/rank_research_labs.py")


#: A page reached twice is one group. Each pair below was two rows in
#: the tested set on 2026-10-14.
SAME_PAGE = [
    ("https://chemistry.brown.edu/people/faculty",
     "https://chemistry.brown.edu/people/faculty#menu"),
    ("https://chemistry.brown.edu/people/faculty",
     "https://chemistry.brown.edu/people/faculty#flyout_search"),
    ("http://www.jiang-lab.net/members.html",
     "https://www.jiang-lab.net/members.html"),
    ("https://jiang-lab.net/members.html",
     "https://www.jiang-lab.net/members.html"),
    ("https://emprise.cs.cornell.edu/people",
     "https://emprise.cs.cornell.edu/people/"),
]

#: and these are genuinely different pages, so the query may not go.
DIFFERENT_PAGES = [
    ("https://secure.gradsch.psu.edu/gpms/index.cfm?prog=BME",
     "https://secure.gradsch.psu.edu/gpms/index.cfm?prog=BUSAD"),
    ("https://lab.edu/people", "https://lab.edu/alumni2"),
]


@pytest.mark.parametrize("a,b", SAME_PAGE)
def test_one_page_has_one_identity(a, b):
    from lab_page_filter import canonical
    assert canonical(a) == canonical(b), (
        f"{a} and {b} count as two groups; a fragment, a scheme and a "
        f"leading www. are not a different page. One lab reached the "
        f"published table twice this way, at 73.3% of 60.")


@pytest.mark.parametrize("a,b", DIFFERENT_PAGES)
def test_different_pages_keep_different_identities(a, b):
    from lab_page_filter import canonical
    assert canonical(a) != canonical(b)


def test_a_graduate_programmes_faculty_list_is_not_a_group():
    """156 of 1,772 tested rows were this one Penn State page."""
    keep, why = is_a_research_group(
        "https://secure.gradsch.psu.edu/gpms/index.cfm"
        "?searchType=fac&prog=BME")
    assert not keep, "a programme's faculty list was admitted as a group"
    assert "programme" in why or "faculty" in why


def test_the_published_table_has_no_page_twice():
    import lab_overrides
    from lab_page_filter import canonical
    out = json.loads(
        (ROOT / "data" / "labs" / "lab_outliers.json").read_text())
    seen = {}
    for r in lab_overrides.apply(out["outliers"]):
        seen.setdefault(canonical(r["url"]), []).append(r["url"])
    twice = {k: v for k, v in seen.items() if len(v) > 1}
    assert not twice, f"the same page is in the table more than once: {twice}"
