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
    #: A DEPARTMENT'S WHOLE COHORT. The worst of these, because it
    #: looks the most like a finding: 254 people at 36.6% is a real
    #: measurement of a department, not of anyone's hiring.
    r"(?:graduate|grad|phd|doctoral|masters|current|prospective|"
    r"incoming|former)[-_]?students?(?:[-_]\w+)*",
    r"undergrad\w*(?:[-_]\w+)*", r"reu(?:[-_]\w+)*",
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
)), re.I)

#: Segments that are only disqualifying as the WHOLE page, because the
#: word is ordinary inside a lab's own address. "labs" ends a
#: department's list of laboratories; "mylab/labs/photos" does not.
SEGMENT_EXACT_TAIL = frozenset({
    "academics", "directory", "news", "labs", "lab-directory",
    "centers", "center",
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

_EXT = re.compile(r"\.(html?|php|aspx?|jsp|cfm)$", re.I)


def host_of(url: str) -> str:
    return urlparse(url or "").netloc.lower().removeprefix("www.")


def _segments(url: str) -> list:
    path = urlparse(url or "").path
    out = []
    for seg in path.split("/"):
        seg = _EXT.sub("", seg.strip().lower())
        if seg:
            out.append(seg)
    return out


def is_a_research_group(url: str) -> tuple[bool, str]:
    """(keep, why not) for one candidate address."""
    host = host_of(url)
    if host in NOT_A_UNIVERSITY:
        return False, f"{host} is not a university"
    #: A NEWS SUBDOMAIN. news.engineering.asu.edu/welcome/<name> is a
    #: post about one new hire; the extractor read the bylines.
    if host.startswith("news."):
        return False, f"{host} is a news site"
    segs = _segments(url)
    for i, seg in enumerate(segs):
        base = seg.split("?")[0]
        if SEGMENT_PATTERNS.fullmatch(base):
            return False, f"the address says {base!r}"
        if i == len(segs) - 1 and base in SEGMENT_EXACT_TAIL:
            return False, f"the page is {base!r}"
        if (i == len(segs) - 1 and base in STUDENTS
                and host.endswith(".edu")
                and not any(sg.startswith("~") for sg in segs)):
            return False, "the university's own students page"
    return True, ""
