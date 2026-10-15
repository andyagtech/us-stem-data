#!/usr/bin/env python3
"""Is this page a principal investigator's research group, or not?

ONE DECLARATION, BECAUSE THE ANSWER DECIDES WHAT GETS PUBLISHED. The
rule lived inside rank_research_labs.main() as a regex literal; it is
here so it can be tested, and so the evidence for each line sits next
to the line.

WHAT A SCAN PICKS UP. The crawler follows a department page to a
faculty profile to a group site, and the shapes it keeps are "a link
whose text or address says lab, group, team or members". Plenty of
pages match that and are not a research group. Measured over the 1,913
rows tested on 2026-10-14, 163 had an address that said so outright:

  isye.gatech.edu/people/phd-students                 173 members, 30.1%
  mccormick.northwestern.edu/.../graduate-students    254 members, 36.6%
  isye.gatech.edu/people/advisory-board               217 members
  math.gatech.edu/undergraduate-research              227 members
  math.gatech.edu/faculty-research-interests           52 members
  pratt.duke.edu/about/awards/nae-members              51 members
  clemson.edu/.../people/emeritus.html                 42 members
  cas.gsu.edu/alumni-partners/alumni-2                 77 members
  denver7.com/about/news-team                          63 members
  jpl.nasa.gov/news/nasas-roman-team-snaps-...         23 members
  pnnl.gov/undergraduate-students                      85 members

A DEPARTMENT'S OWN STUDENT LIST IS THE WORST OF THESE, because it
looks the most like a finding. 173 doctoral students at 30% is a real
measurement of a department -- and this site already measures
departments, from the thesis record, with a denominator it can defend.
Reported as a laboratory it says there is a hiring decision behind it,
and there is not.

AN ALUMNI PAGE IS NOT A ROSTER either, and one reached the published
table: alps-lab.github.io/teaching/alumni, 11 of 13. Those are people
who have left.

WHY NOT SIMPLY REQUIRE A .edu HOST. Because 24 of the 95 published
groups are not on one, and they are the real thing -- vita-group.space,
morphingmatter.org, furong-huang.com/people. A professor's group site
on its own domain is normal. So the host rule is a short DENY list of
hosts that are not universities at all, not an allow list.

Nothing here is a judgement about a particular group. Those live in
scripts/lab_overrides.py, are applied after ranking, and carry a
written reason each.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

#: A page about a group, department or college rather than one PI's team.
#:
#: MATCHED ON PATH SEGMENTS, NOT ON A SUBSTRING. The first version was
#: one regex anchored at the end of the path, and three shapes walked
#: straight through it:
#:
#:   /alumni-partners/alumni-2/   the segment is not exactly "alumni"
#:   /undergraduate-research      "undergraduate" is followed by "-"
#:   /people/emeritus.html        the path ends ".html", not "/"
#:
#: So the path is split, each segment has any file extension stripped,
#: and a segment is tested whole -- as an exact name or as a prefix.
#: That is also why a lab called "alumniLab" would survive: the rule is
#: about segments, not about the letters appearing somewhere.

#: Segments that are the whole subject of the page, each matched
#: against the WHOLE segment.
#:
#: WHY FULLMATCH AND NOT A PREFIX. A plain prefix test let "awardslab"
#: match "awards", so a group calling itself the Awards Lab would have
#: been thrown out. Each entry below says for itself how far it may
#: run: "alumni" may carry a suffix after a separator (alumni-2,
#: alumni-partners) but not more letters; "undergrad" may run on into
#: "undergraduate".
SEGMENT_PATTERNS = re.compile("|".join((
    #: PEOPLE WHO ARE NOT IN THE GROUP.
    r"alumn[iy](?:[-_]\w+)*", r"alums?(?:[-_]\w+)*",
    r"(?:former|past)[-_]?members?(?:[-_]\w+)*",
    r"emerit(?:i|us)(?:[-_]\w+)*",
    r"advisory(?:[-_]\w+)*", r"(?:industrial[-_])?advisory(?:[-_]\w+)*",
    r"board[-_]of[-_]\w+",
    r"awards?(?:[-_]\w+)*", r"honors?(?:[-_]\w+)*",
    r"prizes?(?:[-_]\w+)*",
    #: A FACULTY INDEX BY SUBJECT is a department page.
    r"faculty[-_]research[-_](?:interests?|areas?)(?:[-_]\w+)*",
    r"research[-_]interests?(?:[-_]\w+)*",
    r"by[-_]research[-_]area(?:[-_]\w+)*",
    #: A COLLEGE OR DEPARTMENT INDEX.
    r"featured[-_]research[-_]projects?(?:[-_]\w+)*",
    r"research[-_]areas?(?:[-_]\w+)*",
    r"research[-_]centers?(?:[-_]\w+)*",
    r"areas[-_]of[-_]research(?:[-_]\w+)*",
    r"our[-_]faculty", r"faculty[-_]directory", r"all[-_]faculty",
    r"faculty[-_]lists?", r"research[-_]highlights?",
    r"research[-_]faculty", r"faculty[-_]staff", r"our[-_]people",
    r"people[-_]groups?", r"laboratories", r"facilities",
    #: STUDENT SERVICES. Following a profile sometimes lands here:
    #: clemson.edu/students, iastate.edu/student-support.
    r"student[-_]support", r"admissions",
    #: A DEPARTMENT'S FACULTY-AND-STAFF INDEX, under /people or not.
    #: stonybrook.edu/geosciences/people/faculty.html and
    #: clemson.edu/.../ece/faculty_staff/index.html both arrived as
    #: "group sites" and would have been read as rosters.
    r"faculty[-_]?staff", r"staff[-_]?directory", r"people[-_]directory",
    #: A LOGIN OR SIGN-UP WALL has no roster behind it.
    r"(?:member[-_])?log[-_]?in", r"sign[-_]?in", r"sign[-_]?up",
    r"membership", r"member[-_]login",
)), re.I)

#: An institutional host's FRONT PAGE. web.stanford.edu/index.html came
#: back as a group site; a roster is never the root of a university's
#: general-purpose web host. A lab on its own domain is the opposite
#: case -- billingtonlab.org IS the lab -- so this only applies to the
#: hosts universities use for everyone's pages.
GENERIC_HOST_PREFIX = ("www.", "web.", "sites.", "people.", "home.",
                       "homepages.", "pages.", "users.", "my.")

#: A HOST A UNIVERSITY GIVES ITS PEOPLE, where the first path segment
#: is whose page it is. The tilde is the classic form and the rule
#: above already allows it; these hosts are the same idea without one,
#: and myweb.ttu.edu/rpal/students.html -- a professor's own list of
#: his students, sent by the author -- was being thrown out as "the
#: university's own students page" because of it. www. is deliberately
#: absent: www.clemson.edu/students IS the university's.
PERSONAL_HOST = ("myweb.", "people.", "sites.", "users.", "home.",
                 "homepages.", "pages.", "faculty.", "my.")

#: A DEGREE COHORT, as a path segment. Separated from the patterns
#: above because this is the one group of them that depends on WHOSE
#: page it is: a department's cohort is not a team, and a professor's
#: own students are. The worst of these looks the most like a finding --
#: 254 people at 36.6% is a real measurement of a department, not of
#: anyone's hiring.
COHORT_SEGMENT = re.compile("|".join((
    r"(?:graduate|grad|phd|doctoral|masters|current|prospective|"
    r"incoming|former)[-_]?students?(?:[-_]\w+)*",
    r"undergrad\w*(?:[-_]\w+)*",
    r"reu(?:[-_]\w+)*",
)), re.I)

#: Segments that are only disqualifying as the WHOLE page, because the
#: word is ordinary inside a lab's own address. "labs" ends a
#: department's list of laboratories; "mylab/labs/photos" does not.
SEGMENT_EXACT_TAIL = frozenset({
    "academics", "directory", "news", "labs", "lab-directory",
    "centers", "center",
    #: A LABORATORY HAS NO "FACULTY". It has a principal investigator
    #: and members. A page whose last segment is "faculty" is a
    #: department's list of professors --
    #: stonybrook.edu/geosciences/people/faculty.html arrived as a
    #: "group site" and would have been read as a roster.
    "faculty",
})

#: "students" IS THE ROSTER, ON A PROFESSOR'S OWN SITE. Two published
#: groups are exactly that:
#:
#:   weisongshi.org/students.html             18 members
#:   merlot.stat.uconn.edu/~dey/students.html
#:
#: and two junk pages are the same word on a university's own site:
#:
#:   clemson.edu/students                     student services
#:   iastate.edu/student-support
#:
#: What separates them is whose site it is. A page called "students" is
#: the university's when the host is the institution's own domain and
#: the path is not someone's home directory; otherwise it is the
#: professor's list of his students, which is the thing being measured.
STUDENTS = frozenset({"students", "student"})

#: Hosts that are not a university at all. Each one put a row in the
#: tested set: a TV station's news team, a press release, a national
#: laboratory's intern page, a professional society's committee, an
#: archived copy, and a literature database's author list.
NOT_A_UNIVERSITY = frozenset({
    "web.archive.org", "archive.org",
    "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov",
    "scholar.google.com", "researchgate.net", "linkedin.com",
    "asce.org", "asme.org", "ieee.org", "acm.org", "aps.org", "acs.org",
    "jpl.nasa.gov", "nasa.gov", "pnnl.gov", "ornl.gov", "anl.gov",
    "lbl.gov", "llnl.gov", "sandia.gov", "nrel.gov", "nist.gov",
    "denver7.com",
})

#: Hosts matched by shape rather than by name, because there are too
#: many to list. Every one of these came back from follow_lab_links as
#: "the professor's own group site" in a single run:
#:
#:   utaustin.wd1.myworkdayjobs.com/UTstaff/job/...   a job advert
#:   soundcloud.com/user-458541487/the-health-risks...  a podcast
#:   nardolillofh.com/obituary/Herbert-Fried            an obituary
#:   seismosoc.org/member-login/                        a society login
NOT_A_UNIVERSITY_RE = re.compile(
    r"(myworkdayjobs|workday|taleo|icims|greenhouse\.io|lever\.co|"
    r"jobvite|smartrecruiters|bamboohr|successfactors)|"
    r"(soundcloud|spotify|podbean|buzzsprout|vimeo|eventbrite|"
    r"meetup|slideshare|medium\.com|substack|wordpress\.com/news)|"
    r"(funeral|obitu|legacy\.com|dignitymemorial)", re.I)

#: /people/<something>, and nothing after it.
A_PROFILE = re.compile(
    r"/(people|faculty|profile|profiles|directory|person|staff|bio)/"
    r"([^/]+?)/?$", re.I)

_ROSTER_WORD = frozenset({
    "index", "default", "home", "all", "list", "members", "member",
    "team", "group", "people", "faculty", "students", "staff",
    "current", "roster", "everyone",
})


def _is_name_shaped(seg: str) -> bool:
    """Does this path segment look like one person's name?

    ray-chen and yejin-choi do. index.php, members and
    current-members do not, and nor does anything carrying a digit or
    a query -- a profile system's id is not a name we should read as
    one either way, but a roster page must not be mistaken for it.
    """
    base = _EXT.sub("", (seg or "").strip().lower())
    if not base or base in _ROSTER_WORD:
        return False
    toks = [t for t in re.split(r"[-_.]+", base) if t]
    if not 2 <= len(toks) <= 3:
        return False
    return all(t.isalpha() and len(t) >= 2 for t in toks)


_EXT = re.compile(r"\.(html?|php|aspx?|jsp|cfm)$", re.I)


#: A QUERY STRING THAT IS A DIRECTORY SEARCH. 156 of the 1,772 tested
#: rows were one Penn State page -- secure.gradsch.psu.edu/gpms/index.cfm
#: -- called once per graduate programme:
#:
#:   index.cfm?searchType=fac&prog=BME     38 members, 34.2%
#:   index.cfm?searchType=fac&prog=BUSAD   13 members, 38.5%
#:
#: These are NOT duplicates, which is why the query may not simply be
#: stripped: each one is a different programme's faculty. They are a
#: graduate programme's professors, which is a department measurement
#: and not a principal investigator's group.
DIRECTORY_QUERY = re.compile(
    r"(?:^|&)(searchtype=fac|view=faculty|type=faculty|"
    r"category=faculty|group_id=|block_id=)", re.I)


def host_of(url: str) -> str:
    return urlparse(url or "").netloc.lower().removeprefix("www.")


def canonical(url: str) -> str:
    """One address per page, for counting.

    THE FRAGMENT IS NEVER A DIFFERENT PAGE, and 46 of the tested rows
    were the same page reached through its own in-page navigation:
    chemistry.brown.edu/people/faculty, then #menu, #flyout_search and
    #page_main_content. Counting those four as four groups inflates the
    denominator the correction is computed over.

    The QUERY IS KEPT, because ?prog=BME and ?prog=BUSAD are different
    programmes at Penn State and collapsing them would merge sixty
    distinct rosters into one.
    """
    #: THE SCHEME AND A LEADING www. ARE NOT A DIFFERENT PAGE EITHER.
    #: http://www.jiang-lab.net/members.html and
    #: https://www.jiang-lab.net/members.html both reached the published
    #: table in the same run -- one lab, printed twice, at 73.3% of 60.
    p = urlparse(url or "")
    path = p.path.rstrip("/") or "/"
    q = f"?{p.query}" if p.query else ""
    return f"{p.netloc.lower().removeprefix('www.')}{path}{q}"


def _segments(url: str) -> list:
    path = urlparse(url or "").path
    out = []
    for seg in path.split("/"):
        seg = _EXT.sub("", seg.strip().lower())
        if seg:
            out.append(seg)
    return out


#: A DOCUMENT IS NOT A PAGE. retry_failed_rosters re-reads any address
#: that gave nothing, with a looser reader than the crawler used, and it
#: recovered web.njit.edu/~cs638/paper/phased_MIMO.pdf as a roster:
#: 7 of 14, from a paper's author list.
A_DOCUMENT = re.compile(r"\.(pdf|docx?|pptx?|xlsx?|csv|txt)$", re.I)

#: THE ADDRESS OR THE TITLE HAS TO SAY THE PAGE LISTS PEOPLE.
#:
#: This is the one positive requirement here, and it exists because a
#: PROFESSOR'S HOMEPAGE IS NOT A ROSTER. lab_overrides already records
#: the failure for one of them -- "The extractor read this site's
#: PUBLICATION CO-AUTHORS, not its roster" -- and the published table
#: held four more of the same shape:
#:
#:   j-min.io/              "Jaemin Cho"               68 of 172
#:   xiongyexiao.com/       "Xiongye Xiao | AI for..." 11 of 18
#:   sites.nd.edu/jiahong-wu/  "Jiahong Wu's Web Page" 14 of 31
#:   sites.google.com/view/yujunyan  "Yujun Yan"        9 of 13
#:
#: 172 names on a personal homepage is a bibliography. The crawler's
#: own discovery stage already required the page to say lab or group;
#: the retry pass does not, so the requirement moves here where both
#: are judged.
#:
#: The TITLE counts, not only the address, because two real rosters
#: have neither word in the URL:
#:   glycobio.wixsite.com/wangglycan/about  "People | wangglycan"
#:   muratkocaoglu.com/CausalML/            "CausalML Lab -"
#: NOT "~". A tilde says WHOSE site this is, not that the page lists
#: anyone, and admitting it was the hole every remaining bibliography
#: came through. Measured on the labelled pages:
#:
#:   eecis.udel.edu/~ruizhang/        5 role words,  37 venue words
#:   pages.mtu.edu/~shene/NSF-2/      3 role words,  67 venue words
#:   graphics.stanford.edu/~maneesh   2 role words, 167 venue words
#:   cs.princeton.edu/~zhuangl        4 role words,   6 venue words
#:   cs.princeton.edu/~ravian         5 role words,   4 venue words
#:   cs.princeton.edu/~funk           5 role words,   4 venue words
#:
#: and ROLE AND VENUE COUNTS CANNOT SEPARATE THOSE from a lab page that
#: also lists its papers -- ~ravian and ~funk sit at 5 roles and 4
#: venues, while the real covert.stanford.edu/people has 0 and 0. That
#: is worth stating as a negative result instead of tuning a threshold
#: until it fits six examples.
#:
#: What separates them is structural: A TEAM PAGE'S JOB IS THE TEAM. A
#: professor's homepage is not, even when it mentions his students, and
#: the tilde pages that ARE rosters say so --
#: ~dey/students.html, ~jchen70/People/People.html,
#: ~fringer/group.html, ~lekheng/work/people.html, ~jianfeng/group.htm.
LISTS_PEOPLE = re.compile(
    r"(lab|laborator|group|team|members?|people|personnel|roster|"
    r"students?|staff|who[-_ ]?we[-_ ]?are|our[-_ ]?(team|group))", re.I)

#: A DEPARTMENT'S RESEARCH PAGE, which is about subjects and lists the
#: professors working on them. Eleven of these arrived through the
#: retry pass:
#:   matse.illinois.edu/research/electronics-comms       5 of 12
#:   math.purdue.edu/research/applied-mathematics-...   12 of 23
#:   unr.edu/me/research                                 5 of 12
#: A laboratory's own site puts its roster under /people or /team, so
#: those are allowed through even below a /research segment.
DEPARTMENT_RESEARCH = re.compile(r"/research(/|$)", re.I)
ROSTER_PATH = re.compile(r"/(people|members?|team|group|roster|staff)",
                         re.I)

#: A DEGREE COHORT NAMES THE DEGREE. A laboratory's roster page says
#: "members", "team", "people" or "students"; it does not say "graduate
#: students", because everyone in the group is one and there is nothing
#: to distinguish. A department has to say it, and does:
#:
#:   stat.umd.edu/people/current-statistics-graduate-students.html
#:     "Current Graduate Students in Statistics"        15 of 33
#:
#: which the segment rules missed, because "current" is followed by
#: "statistics" rather than by "students". So the test is the pair of
#: words in one segment, not their order.
A_DEGREE_COHORT = re.compile(
    r"(?=[^/]*\b(graduate|grad|phd|doctoral|masters|postgraduate)\b)"
    r"[^/]*\bstudents?\b", re.I)

#: Department indexes the segment rules do not reach, each measured.
DEPARTMENT_INDEX = re.compile(
    r"(faculty[-_]expertise|directory/researchers?|"
    r"students?[-_]by[-_]year|postdoc\w*|courtesy\w*|"
    r"^https?://profiles\.)", re.I)


def is_a_research_group(url: str, title: str = "") -> tuple[bool, str]:
    """(keep, why not) for one candidate page.

    `title` is the page's own <title>, which the stored rows carry. It
    is consulted only for the positive requirement, never to override
    an exclusion: a department page that calls itself a lab is still a
    department page.
    """
    host = host_of(url)
    if host in NOT_A_UNIVERSITY:
        return False, f"{host} is not a university"
    if NOT_A_UNIVERSITY_RE.search(url or ""):
        return False, f"{host} is not a university"
    #: A NEWS SUBDOMAIN. news.engineering.asu.edu/welcome/<name> is a
    #: post about one new hire; the extractor read the bylines.
    if host.startswith("news."):
        return False, f"{host} is a news site"
    if A_DOCUMENT.search(urlparse(url or "").path):
        return False, "a document, not a page"
    if DEPARTMENT_INDEX.search(url or ""):
        return False, "a department index, not a group"
    #: WHOSE COHORT IT IS. "phd-students" under a DEPARTMENT is the
    #: department's whole cohort; under a PERSON it is that professor's
    #: own students, which is a roster.
    #:
    #:   isye.gatech.edu/people/phd-students              173, a cohort
    #:   stat.umd.edu/people/current-statistics-grad...    33, a cohort
    #:   uva.theopenscholar.com/weiqiang-wang/phd-students 26, his own
    #:
    #: The author supplied the third. A name-shaped segment earlier in
    #: the path is what tells them apart, and no department page has
    #: one -- "people", "faculty" and "industrial" are not names.
    segs = _segments(url)
    owned_by_a_person = any(_is_name_shaped(sg) for sg in segs[:-1])
    if not owned_by_a_person:
        for seg in segs:
            flat = seg.replace("-", " ").replace("_", " ")
            if A_DEGREE_COHORT.search(flat) or COHORT_SEGMENT.fullmatch(seg):
                return False, "a degree cohort, not a group"
    if (DEPARTMENT_RESEARCH.search(urlparse(url or "").path)
            and host.endswith(".edu")
            and not ROSTER_PATH.search(urlparse(url or "").path)):
        return False, "a department's research page, not a group"
    #: ONE PERSON IS NOT A TEAM. /people/<name>, /faculty/<name>,
    #: /profile/<name> is a profile page. Two were in the published
    #: table: mrc.utexas.edu/people/faculty/ray-chen, whose "roster"
    #: was the whole Microelectronics Research Center faculty, and
    #: profiles.stanford.edu/yejin-choi.
    #:
    #: The final segment has to look like a NAME, so a lab's own
    #: /people/index.php and /members/index.php come through --
    #: sc.edu/.../research_groups/wang_hui/members/index.php is a real
    #: roster and ends in a segment under a /members/ directory.
    m = A_PROFILE.search(urlparse(url or "").path)
    if m and _is_name_shaped(m.group(2)):
        return False, "a profile page, not a team"
    if DIRECTORY_QUERY.search(urlparse(url or "").query):
        return False, "a graduate programme's faculty list, not a group"
    if (not segs or segs == ["index"]) and \
            host.startswith(GENERIC_HOST_PREFIX):
        return False, f"{host} is a general web host, not a group site"
    for i, seg in enumerate(segs):
        base = seg.split("?")[0]
        if SEGMENT_PATTERNS.fullmatch(base):
            return False, f"the address says {base!r}"
        if i == len(segs) - 1 and base in SEGMENT_EXACT_TAIL:
            return False, f"the page is {base!r}"
        if (i == len(segs) - 1 and base in STUDENTS
                and host.endswith(".edu")
                and not host.startswith(PERSONAL_HOST)
                and not any(sg.startswith("~") for sg in segs)):
            return False, "the university's own students page"
    if not (LISTS_PEOPLE.search(url or "")
            or LISTS_PEOPLE.search(title or "")):
        return False, "neither the address nor the title says it lists people"
    return True, ""
