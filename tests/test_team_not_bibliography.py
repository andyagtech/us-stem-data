"""A research team is not a list of co-authors.

The author named the distinction and it is the right one. A TEAM is a
hiring decision: someone chose those people and pays them. A CO-AUTHOR
LIST records who published together, and it carries collaborators at
other institutions, students who left a decade ago, and the authors of
any paper the page happens to host.

Seven of the 100 published labs were publication lists on 2026-10-14.
The extraction gave them away, because paper titles were being counted
as members -- and once a paper title is a "member", the denominator the
share is computed over is wrong as well as the numerator.

Citation networks are worth having. They answer who works with whom,
which is a different question from who is on the payroll, and they
belong in their own dataset rather than in this table.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from harvest_lab_rosters import clean_member, page_signals    # noqa: E402

#: string -> the page that counted it as a member of a published lab
A_PAPER_NOT_A_PERSON = {
    "Computer Graphics": "pages.mtu.edu/~shene/NSF-2",
    "Computer-Aided Design": "pages.mtu.edu/~shene/NSF-2",
    "Graphics Gems IV": "pages.mtu.edu/~shene/NSF-2",
    "Hierarchical Streamline Bundles": "pages.mtu.edu/~shene/NSF-2",
    "The Computer Journal": "pages.mtu.edu/~shene/NSF-2",
    "Dropout Reduces Underfitting": "cs.princeton.edu/~zhuangl",
    "Highlighted Paper": "cs.princeton.edu/~zhuangl",
    "Oral Presentation": "cs.princeton.edu/~zhuangl",
    "Spotlight Presentation": "cs.princeton.edu/~zhuangl",
    "Rhythmic RFID Authentication": "eecis.udel.edu/~ruizhang",
    "Object Oriented Programming": "eecis.udel.edu/~ruizhang",
    "IEEE CNS": "eecis.udel.edu/~ruizhang",
    "Causal Bandit Algorithms": "muratkocaoglu.com/CausalML",
    "Entropic Causal Inference": "muratkocaoglu.com/CausalML",
    "Pensieve Website": "cs.princeton.edu/~ravian",
    "Personal Website": "lolab.ucsd.edu/team-2",
    "Journal Cover Art": "lilabs.org/people",
    "Software Releases": "sites.google.com/view/fenglab",
    "HPC Security": "xgao-work.github.io/members",
    "GPU Server": "udel.edu/~amotong/group",
    "AI Software Engineer": "udel.edu/~amotong/group",
    "GPU Profiling": "abdelzaher.cs.illinois.edu/people",
    "Process Engineer": "qingcaolab.matse.illinois.edu/group",
    "Senior Product Engineer": "qingcaolab.matse.illinois.edu/group",
    "Hardware Security": "saliganelab.com/team",
    "Wireless Communications": "www2.egr.uh.edu/~zhan2",
}

#: Real members of published labs. Every one of these must survive.
A_PERSON = [
    "Yifan Dai", "Jianfeng Lu", "Jenq-Neng Hwang", "Xinrui Liu",
    "Michael W. Chen", "Chih-Hao Chang", "Jean Anne Incorvia",
    "Deji Akinwande", "Maria del Carmen Lopez", "Emanuel Tutuc",
    "Zongru Li", "Joaquim Bila", "Ellie Berkland",
]

#: WORDS THAT ARE ALSO SURNAMES may not go in the blocklist. Reviewing
#: every string the rule drops across 163,300 cached names turned these
#: up being thrown out by publisher and publishing words.
A_SURNAME_THAT_IS_ALSO_A_WORD = [
    "Roxanne P. Springer",      # physics, Duke
    "Martin Springer",
    "Thomas Cover",             # information theory
]


@pytest.mark.parametrize("name,page", sorted(A_PAPER_NOT_A_PERSON.items()))
def test_a_paper_title_is_not_a_member(name, page):
    assert clean_member(name) == "", (
        f"{name!r} was counted as a member on {page}; it is a paper, a "
        f"product or a job title")


@pytest.mark.parametrize("name", A_PERSON)
def test_a_real_member_survives(name):
    assert clean_member(name) == name, f"{name!r} is a person"


@pytest.mark.parametrize("name", A_SURNAME_THAT_IS_ALSO_A_WORD)
def test_a_surname_is_not_a_blocked_word(name):
    assert clean_member(name) == name, (
        f"{name!r} is a real person. A word that is also a surname "
        f"cannot go in the blocklist -- 'Journal Cover Art' has to be "
        f"caught by 'journal', not by 'cover'.")


def test_role_words_and_venue_words_are_counted_separately():
    roster = """<html><body>
      <h2>Lab Members</h2>
      <p>Wen Yu &mdash; PhD Student</p>
      <p>Jiali Fan &mdash; Postdoctoral Scholar</p>
      <p>Yvette Chen &mdash; Research Scientist</p>
    </body></html>"""
    bib = """<html><body>
      <h2>Publications</h2>
      <p>R. Zhang et al., Proceedings of IEEE CNS, vol. 4, pp. 11-20.</p>
      <p>R. Zhang et al., arXiv preprint, submitted to NeurIPS.</p>
      <p>doi:10.1000/xyz, Journal of Something, conference on things.</p>
    </body></html>"""
    r, b = page_signals(roster), page_signals(bib)
    assert r["role_markers"] >= 3 and r["venue_markers"] == 0
    assert b["venue_markers"] >= 4 and b["role_markers"] == 0


def test_signals_count_distinct_phrases_not_occurrences():
    """A long list must not score higher than a short one for length.

    A bibliography repeats "et al." once per entry and a roster repeats
    "PhD Student" once per member, so raw counts would measure the
    length of the list rather than its kind.
    """
    one = "<html><body><p>A. B. et al.</p></body></html>"
    many = "<html><body>" + "<p>A. B. et al.</p>" * 50 + "</body></html>"
    assert page_signals(one)["venue_markers"] == \
        page_signals(many)["venue_markers"]


def test_no_published_lab_counts_a_paper_as_a_member():
    """The table itself, checked against the cached extraction."""
    import lab_name_cache as cache
    import lab_overrides
    out = json.loads(
        (ROOT / "data" / "labs" / "lab_outliers.json").read_text())
    bad = []
    for r in lab_overrides.apply(out["outliers"]):
        for n in cache.get(r["url"]) or []:
            if not clean_member(n):
                bad.append((r["url"], n))
    assert not bad, (
        f"{len(bad)} strings counted as members are not people: "
        f"{bad[:8]}. Run scripts/recompute_lab_composition.py.")


#: A PROFESSOR'S HOMEPAGE AT /~user. These were the last bibliographies
#: in the table, and the hole they came through was a tilde: the address
#: filter accepted "~" as evidence that a page lists people. A tilde
#: says WHOSE site it is, not that anyone is listed on it.
#:
#: The page labels are recorded beside each one. They are why the
#: tilde had to go rather than a threshold being tuned: role and venue
#: counts cannot separate ~ravian (5 roles, 4 venues) from a lab page
#: that also lists its papers, and the real covert.stanford.edu/people
#: has no role word at all.
A_HOMEPAGE_NOT_A_ROSTER = {
    "https://www.eecis.udel.edu/~ruizhang/": "5 roles, 37 venues",
    "https://pages.mtu.edu/~shene/NSF-2/index.html": "3 roles, 67 venues",
    "http://graphics.stanford.edu/~maneesh": "2 roles, 167 venues, "
                                             "and 438 'members'",
    "https://cs.princeton.edu/~zhuangl": "4 roles, 6 venues",
    "https://cs.princeton.edu/~ravian": "5 roles, 4 venues",
    "https://cs.princeton.edu/~funk": "5 roles, 4 venues",
    "https://hfarid.org": "10 roles, 8 venues",
    "https://www2.isye.gatech.edu/~nemirovs/": "a homepage",
    "http://www.cs.ucsb.edu/~xyan/": "a homepage",
    "http://www2.egr.uh.edu/~zhan2/": "a homepage",
}

#: and the tilde pages that ARE rosters say so in the address.
A_TILDE_PAGE_THAT_IS_A_ROSTER = [
    "http://merlot.stat.uconn.edu/~dey/students.html",
    "http://www2.egr.uh.edu/~jchen70/People/People.html",
    "https://web.stanford.edu/~fringer/group.html",
    "https://www.stat.uchicago.edu/~lekheng/work/people.html",
    "https://sites.math.duke.edu/~jianfeng/group.htm",
    "http://users.ece.utexas.edu/~bevans/students/index.html",
    #: no role word on the page at all, and still a team page
    "https://www.covert.stanford.edu/people",
]


@pytest.mark.parametrize("url,signals", sorted(A_HOMEPAGE_NOT_A_ROSTER.items()))
def test_a_professors_homepage_is_not_a_team_page(url, signals):
    from lab_page_filter import is_a_research_group
    keep, why = is_a_research_group(url, "")
    assert not keep, (
        f"{url} ({signals}) was admitted as a research team. Its names "
        f"are the professor's co-authors.")


@pytest.mark.parametrize("url", A_TILDE_PAGE_THAT_IS_A_ROSTER)
def test_a_tilde_page_that_says_it_lists_people_survives(url):
    from lab_page_filter import is_a_research_group
    keep, why = is_a_research_group(url, "")
    assert keep, f"{url} is a roster and says so in its address: {why}"


def test_no_published_lab_reads_like_a_bibliography():
    """The page labels, as an invariant over the published table.

    label_roster_pages.py records how many distinct role phrases and
    venue phrases each roster page uses. The address rules are what
    exclude a bibliography; this asserts they did, against evidence
    gathered independently of them.
    """
    import lab_overrides
    labs = {x["url"]: x for x in json.loads(
        (ROOT / "data" / "labs" / "discovered_labs.json").read_text()
    )["groups"]}
    pub = lab_overrides.apply(json.loads(
        (ROOT / "data" / "labs" / "lab_outliers.json").read_text())["outliers"])
    bad = []
    for r in pub:
        x = labs.get(r["url"], {})
        if "role_markers" not in x:
            continue
        if x["venue_markers"] >= 5 and x["venue_markers"] > x["role_markers"]:
            bad.append((r["url"], x["role_markers"], x["venue_markers"]))
    assert not bad, f"published pages that name more venues than roles: {bad}"
