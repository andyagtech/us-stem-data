#!/usr/bin/env python3
"""Research groups, declared one at a time, with their public roster.

WHAT THIS IS. A department is an administrative unit; a research group
is a person's hiring. The author's question is about the second: who a
named principal investigator actually brings into a federally funded
laboratory. That is a narrower and sharper question than a department
share, and it needs more care, not less.

FOUR RULES, because the unit here is one person's group.

1. TOTALS ONLY. composition() returns counts and shares. No per-person
   label is stored, shown, or written to disk. The roster is archived
   as the page itself so a figure can be rechecked; the arithmetic is
   never attached to an individual student.

2. THE DENOMINATOR IS THE FINDING. A group of twelve is twelve. A high
   share of twelve is one or two people away from an ordinary one, and
   a page that prints a percentage without its denominator beside it is
   making a claim the data cannot carry. Every figure here is written
   "n of m".

3. NAME MARKERS ARE A FLOOR, AND THEY ARE INFERENCE. A classifier
   reading names cannot know a person's citizenship, birthplace or
   nationality, and many Americans have names it marks. The share is
   the proportion of names carrying a marker, which is a lower bound on
   nothing in particular and an upper bound on nothing either. It is a
   prompt to look at the page, which is why the page is linked.

4. ORDINARY EXPLANATIONS EXIST AND BELONG ON THE PAGE. A principal
   investigator recruits from the students who apply, from
   collaborators abroad, from a language they share, from a technique
   taught in a handful of places. None of that is visible in a roster
   and all of it is common. The site shows what the laboratory
   publishes about itself and says so.

THE TAXPAYER CONNECTION IS THE POINT, and it is checkable: a principal
investigator's federal awards are public, with identifiers. That is the
fact the page rests on. The composition is context for it.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Lab:
    #: The group as it names itself.
    name: str
    institution: str
    #: The principal investigator, a named officeholder and grant
    #: recipient acting in a professional capacity.
    pi: str
    #: Where the members are listed, publicly, by the lab itself.
    roster_url: str
    #: The department it sits in, for the field figures.
    department: str = ""
    field: str = ""
    #: Why this one. In the author's voice, not a summary of the data.
    note: str = ""
    #: A lab page is not a roster page. Where the two differ, both.
    home_url: str = ""
    #: The thesis-record key and the words that find this group's own
    #: department in it. The comparison is the department, not the
    #: nation: same admissions, same funding, same applicant pool.
    uni_slug: str = ""
    baseline_words: tuple = ("electrical",)


LABS: tuple[Lab, ...] = (
    Lab(
        name="LIGHT: Laboratory of Integrated Guided-wave "
             "and Hybrid Technologies",
        institution="University of Washington, Seattle",
        pi="Mo Li",
        roster_url="https://sites.google.com/uw.edu/light/members",
        home_url="https://sites.google.com/uw.edu/light/",
        department="Electrical and Computer Engineering",
        field="ee", uni_slug="uw_seattle",
        baseline_words=("electrical",),
    ),
    Lab(
        name="Information Processing Lab",
        institution="University of Washington, Seattle",
        pi="Jenq-Neng Hwang",
        roster_url="https://ipl-uw.github.io/people.html",
        home_url="https://ipl-uw.github.io/",
        department="Electrical and Computer Engineering",
        field="ee", uni_slug="uw_seattle",
        baseline_words=("electrical",),
    ),
    #: UVA, NAMED BY THE AUTHOR on 2026-10-14. The university had never
    #: been searched for a group -- it was one of 30 of the 106 missing
    #: from every target list -- and the engineering school's whole web
    #: estate sits behind a Cloudflare javascript challenge, so the
    #: crawler cannot reach engineering.virginia.edu at all. Both of
    #: these are on the lab's OWN domain, which is how UVA groups
    #: publish, and both answer normally.
    Lab(
        name="Intelligent Sensing Laboratory",
        institution="University of Virginia-Main Campus",
        pi="Kyusang Lee",
        roster_url="https://intellisensinglab.com/sample-page/",
        home_url="https://intellisensinglab.com/",
        department="Electrical and Computer Engineering",
        field="ee", uni_slug="uva",
        baseline_words=("electrical",),
        note="27 members. The largest single origin is 44 per cent and "
             "two thirds of the roster is from outside Europe.",
    ),
    Lab(
        name="Soft Biomatter Laboratory",
        institution="University of Virginia-Main Campus",
        pi="Liheng Cai",
        roster_url="https://softbiomatter.org/members/team/",
        home_url="https://softbiomatter.org/",
        department="Materials Science and Engineering",
        field="battery", uni_slug="uva",
        baseline_words=("material",),
        note="26 members, half of them from one origin.",
    ),
    Lab(
        name="Weiqiang Wang's doctoral students",
        institution="University of Virginia-Main Campus",
        pi="Weiqiang Wang",
        roster_url="https://uva.theopenscholar.com/weiqiang-wang/phd-students",
        home_url="https://uva.theopenscholar.com/weiqiang-wang",
        department="Mathematics",
        field="math", uni_slug="uva",
        baseline_words=("mathematic", "statistic"),
        note="A professor's own list of his doctoral students, past and "
             "present, so it is cumulative rather than a snapshot of a "
             "current group. 26 names once his publication list is "
             "excluded from them: the page interleaves students with "
             "citations, and 'J. Algebra', 'Pacific J. Math' and "
             "'Comm. Math. Phys.' were being counted as people.",
    ),
    #: USF, NAMED BY THE AUTHOR on 2026-10-14, all three from
    #: electrical engineering. Another of the 30 universities that had
    #: never been searched. All three are genuine laboratories and all
    #: three are recorded here; what each MEASURES is in its note,
    #: because two of them are mixed rosters and one is nine people.
    Lab(
        name="Communications, Security and Analytics Laboratory",
        institution="University of South Florida",
        pi="Yao Liu",
        roster_url="https://csalab.site/",
        home_url="https://csalab.site/",
        department="Electrical Engineering",
        field="ee", uni_slug="usf",
        baseline_words=("electrical",),
        note="The sharpest roster on the site at 8 of 9 from one origin, "
             "and BELOW THE MEMBER FLOOR of twelve, so it is recorded "
             "and not tabled. The author rejected an 11-member roster "
             "as too thin to assert on and that floor has not moved "
             "for this one. Two of the nine now hold faculty posts "
             "elsewhere, so the page is cumulative.",
    ),
    Lab(
        name="Xiaomin Lin's group",
        institution="University of South Florida",
        pi="Xiaomin Lin",
        roster_url="http://xiaominlin.github.io/members/",
        home_url="http://xiaominlin.github.io/",
        department="Electrical Engineering",
        field="ee", uni_slug="usf",
        baseline_words=("electrical",),
        note="40 members and visibly mixed: the largest single origin is "
             "27 per cent and under half the roster is from outside "
             "Europe. A large group that is not concentrated.",
    ),
    Lab(
        name="SPS: Smart Grid Power Systems Laboratory",
        institution="University of South Florida",
        pi="Zhixin Miao",
        roster_url="http://power.eng.usf.edu/people.htm",
        home_url="http://power.eng.usf.edu/",
        department="Electrical Engineering",
        field="ee", uni_slug="usf",
        baseline_words=("electrical",),
        note="45 members, largest single origin 27 per cent. The roster "
             "is heavily Gulf-state and South Asian rather than "
             "dominated by any one origin.",
    ),
)
