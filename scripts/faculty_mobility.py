#!/usr/bin/env python3
"""Faculty who held federally funded US appointments and now work abroad.

WHY THIS IS A LEGITIMATE QUESTION, AND WHAT IT IS NOT. Federal research
money buys two things: the research, and the researcher. The first is
published. The second walks, and when it walks to a strategic competitor
the public has bought expertise it no longer has access to. That is a
question about the return on federal research funding, and it is asked
here with public records only.

IT IS NOT AN ACCUSATION. Changing institutions is legal, ordinary and
common in academia, in both directions. Nothing on this page states or
implies that any person did anything improper, broke any law, or failed
any disclosure obligation. Where no finding exists, the page says so
rather than leaving a space for the reader to fill.

WHAT A CASE MUST HAVE TO APPEAR HERE. All four, or it does not go on the
page:

  1. A documented US faculty appointment.
  2. Federal grants naming them as PI, from the agency's own award
     database, with amounts and dates.
  3. A documented current appointment outside the United States.
  4. An archived copy of every source, because faculty pages vanish --
     the Colorado State page below exists only on the Wayback Machine.

The subject of a case is a professor acting in a professional capacity:
a named grant recipient and a named officeholder. That is a different
thing from a graduate student, and no student appears here.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Appointment:
    institution: str
    role: str
    country: str
    years: str = ""
    url: str = ""
    archived: str = ""


@dataclass(frozen=True)
class Grant:
    agency: str
    award_id: str
    institution: str
    amount: int
    start: str
    title: str


@dataclass(frozen=True)
class Case:
    name: str
    field: str
    #: What the public record shows, in the site's voice. No inference.
    summary: str
    us: tuple[Appointment, ...]
    now: Appointment
    grants: tuple[Grant, ...]
    sources: tuple[tuple[str, str], str | tuple] = ()
    note: str = ""

    @property
    def total(self) -> int:
        return sum(g.amount for g in self.grants)


CASES: tuple[Case, ...] = (
    Case(
        name="Liuqing Yang",
        field="Electrical engineering — wireless communications, "
              "ultra-wideband, connected vehicles",
        summary=(
            "Held faculty appointments at three US public universities over "
            "roughly fifteen years and was principal investigator on ten "
            "National Science Foundation awards across them, including two "
            "CAREER grants — the NSF's award for early-career faculty it "
            "expects to become leaders in their field. Now Chair Professor "
            "and Acting Head of the Intelligent Transportation Thrust at the "
            "Hong Kong University of Science and Technology (Guangzhou)."),
        us=(
            Appointment("University of Florida", "Faculty", "United States",
                        "2006–2009"),
            Appointment("Colorado State University", "Professor",
                        "United States", "2010–2019",
                        url="https://www.engr.colostate.edu/~lqyang/",
                        archived="https://web.archive.org/web/20260313113618/"
                                 "https://www.engr.colostate.edu/~lqyang/"),
            Appointment("University of Minnesota, Twin Cities", "Professor",
                        "United States", "2020–2021"),
        ),
        now=Appointment(
            "Hong Kong University of Science and Technology (Guangzhou)",
            "Chair Professor; Acting Head, Intelligent Transportation Thrust; "
            "Director, Center of Seamless Connectivity and Connected "
            "Intelligence", "China", "current",
            url="https://personal.hkust-gz.edu.cn/lqyang/"),
        grants=(
            Grant("NSF", "2128593", "University of Minnesota-Twin Cities",
                  420000, "2021-08-15",
                  "Collaborative Research: SWIFT: Cognitive spectrum access"),
            Grant("NSF", "2103256", "University of Minnesota-Twin Cities",
                  913956, "2020-10-01",
                  "CPS: Medium: Collaborative Research"),
            Grant("NSF", "2102312", "University of Minnesota-Twin Cities",
                  311000, "2020-10-01",
                  "Hybrid mmWave mMIMO Transceiver Design"),
            Grant("NSF", "1932413", "Colorado State University",
                  958337, "2019-10-01",
                  "CPS: Medium: Collaborative Research"),
            Grant("NSF", "1935915", "Colorado State University",
                  344483, "2019-09-01",
                  "Hybrid mmWave mMIMO Transceiver Design"),
            Grant("NSF", "1343189", "Colorado State University",
                  262400, "2014-01-01",
                  "Collaborative Research: EARS: Large-Scale spectrum"),
            Grant("NSF", "1232305", "Colorado State University",
                  360000, "2012-11-15",
                  "Advancing Phasor Measurement Unit (PMU) technology"),
            Grant("NSF", "1129043", "Colorado State University",
                  400923, "2010-12-01",
                  "CAREER: Acoustic Underwater Sensor Networks"),
            Grant("NSF", "0845722", "University of Florida",
                  165914, "2009-05-01",
                  "CAREER: Acoustic Underwater Sensor Networks"),
            Grant("NSF", "0621879", "University of Florida",
                  240000, "2006-09-01",
                  "Efficient MIMO Transceivers Based on Channel Estimation"),
        ),
        sources=(
            ("NSF Award Search, principal investigator query",
             "https://www.nsf.gov/awardsearch/"),
            ("HKUST (Guangzhou) faculty page",
             "https://personal.hkust-gz.edu.cn/lqyang/"),
            ("Colorado State University faculty page, archived 2026-03-13",
             "https://web.archive.org/web/20260313113618/"
             "https://www.engr.colostate.edu/~lqyang/"),
            ("Wikipedia", "https://en.wikipedia.org/wiki/Liuqing_Yang"),
        ),
        note=("The three US institutions named here are the three the NSF "
              "award record lists as the awardee, and they match the career "
              "sequence given in the public biography, which is how this is "
              "known to be one person rather than a name collision. The "
              "award figures are amounts obligated, taken from the NSF's "
              "own database, and cover only NSF: grants from other federal "
              "agencies are not included and the true federal total is "
              "therefore at least this."),
    ),
)
