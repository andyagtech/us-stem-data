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
)
