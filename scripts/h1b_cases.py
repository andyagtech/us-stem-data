#!/usr/bin/env python3
"""The cases the H-1B explorer leads with, declared once.

WHY A DECLARATION

Each case is a claim about the federal record, and each is only interesting
if the number behind it is real. So a case names the dataset and the exact
field, and the builder resolves it at render time. A case whose evidence
stops resolving fails the build.

WHAT BELONGS HERE

Filings that a reader would not predict. H-1B is understood as a visa for
software engineers and professors, and most of it is. These are the parts
that are not, and they are in the government's own disclosure files.

NONE OF THIS IS AN ACCUSATION. A certified application is permission to
employ, not proof of hiring, and nothing on this page says any employer broke
a rule. Several of these jobs are perfectly ordinary things for a visa to
cover. They are here because they are the opposite of what the program is
usually described as doing.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Case:
    title: str
    #: One sentence. What the record shows.
    finding: str
    #: Why a reader should not have expected it.
    why_odd: str
    #: (label, dataset file under site/data, dotted path, format)
    evidence: tuple = field(default_factory=tuple)
    href: str = ""
    caveat: str = ""
    #: The group key to drill into, and which H-1B file names the employers.
    #: Nationality always comes from perm_by_industry, because no H-1B file
    #: records one below the national total. A case with no group gets no
    #: drill-down and says why.
    group: str = ""
    h1b_source: str = ""        # "industry" | "occupation" | ""



CASES: tuple[Case, ...] = (
    Case(
        title="Gas stations",
        group="gas_stations",
        h1b_source="industry",
        finding=("Certified labor condition applications filed by gas "
                 "stations and convenience retail, across hundreds of "
                 "separate employers."),
        why_odd=("H-1B is a visa for a speciality occupation requiring at "
                 "least a bachelor's degree. These are filed under the "
                 "industry code for filling stations."),
        evidence=(("certified applications", "h1b_by_industry.json",
                   "groups.gas_stations.filings", "n"),
                  ("distinct employers", "h1b_by_industry.json",
                   "groups.gas_stations.employers", "n"),
                  ("median wage offered", "h1b_by_industry.json",
                   "groups.gas_stations.median_wage", "usd")),
        caveat=("The industry code is the employer's own answer. A firm that "
                "owns stations and does something else too files under one "
                "code for all of it."),
    ),
    Case(
        title="Building cleaning and maintenance",
        group="custodial",
        h1b_source="occupation",
        finding=("Applications in the occupation group that covers janitors, "
                 "cleaners and groundskeeping."),
        why_odd=("This is the occupational classification itself, not an "
                 "industry: the employer named a cleaning or maintenance "
                 "occupation on the form."),
        evidence=(("certified applications", "h1b_by_occupation.json",
                   "groups.custodial.filings", "n"),
                  ("distinct employers", "h1b_by_occupation.json",
                   "groups.custodial.employers", "n"),
                  ("median wage offered", "h1b_by_occupation.json",
                   "groups.custodial.median_wage", "usd")),
    ),
    Case(
        title="Food preparation and serving",
        group="food_service",
        h1b_source="occupation",
        finding=("Applications in the occupation group covering cooks, food "
                 "service managers and serving staff. Panda Express is among "
                 "the employers in the wider record."),
        why_odd=("Restaurant work is the standard example of what a "
                 "speciality-occupation visa is not for."),
        evidence=(("certified applications", "h1b_by_occupation.json",
                   "groups.food_service.filings", "n"),
                  ("distinct employers", "h1b_by_occupation.json",
                   "groups.food_service.employers", "n"),
                  ("median wage offered", "h1b_by_occupation.json",
                   "groups.food_service.median_wage", "usd")),
    ),
    Case(
        title="Personal care and service",
        group="personal_care",
        h1b_source="occupation",
        finding=("Applications in the group covering personal care aides, "
                 "childcare and related work. The lowest median wage of any "
                 "occupation group measured here."),
        why_odd=("A wage at this level is below what the program's critics "
                 "and defenders both assume is the floor."),
        evidence=(("certified applications", "h1b_by_occupation.json",
                   "groups.personal_care.filings", "n"),
                  ("median wage offered", "h1b_by_occupation.json",
                   "groups.personal_care.median_wage", "usd"),
                  ("against the postsecondary teaching median",
                   "h1b_by_occupation.json",
                   "groups.teachers_post.median_wage", "usd")),
    ),
    Case(
        title="Farming, fishing and forestry",
        group="farming",
        h1b_source="occupation",
        finding=("Applications in the agricultural occupation group, filed "
                 "on H-1B rather than on the agricultural visa built for it."),
        why_odd=("H-2A exists for seasonal agricultural labor and has its "
                 "own wage rules. These filings did not use it."),
        evidence=(("certified applications", "h1b_by_occupation.json",
                   "groups.farming.filings", "n"),
                  ("distinct employers", "h1b_by_occupation.json",
                   "groups.farming.employers", "n"),
                  ("median wage offered", "h1b_by_occupation.json",
                   "groups.farming.median_wage", "usd")),
    ),
    Case(
        title="Sponsored while holding a tourist visa",
        finding=("Permanent-residence filings where the worker held "
                 "something that is not work authorisation when the employer "
                 "filed: a B-2 visitor visa, temporary protected status, "
                 "parole, or no inspection at all."),
        why_odd=("The ordinary path runs H-1B then permanent residence. "
                 "These filings start somewhere else entirely."),
        evidence=(("public-sector filings flagged",
                   "public_employer_perm.json",
                   "anomaly_totals.sponsored_while_not_work_authorised", "n"),),
        href="/public-sector-visas#anomalies",
        caveat=("Lawful in itself. An employer may petition for someone in "
                "any of these positions, and the filing says nothing about "
                "how the person came to be in it."),
    ),
    Case(
        title="US citizens on permanent-residence filings",
        finding=("Filings that record the worker as a United States citizen, "
                 "including some born in the United States."),
        why_odd=("A US citizen cannot need a labor certification. The field "
                 "is almost certainly mis-keyed, which makes this a defect in "
                 "a federal disclosure file that nobody had looked for."),
        evidence=(("filings naming a US citizen", "public_employer_perm.json",
                   "anomaly_totals.a_us_citizen_named_on_the_filing", "n"),),
        href="/public-sector-visas#anomalies",
    ),
    Case(
        title="A state motor-vehicle agency",
        finding=("The Washington State Department of Licensing sponsored an "
                 "IT applications specialist for permanent residence in "
                 "FY2021. The worker was a citizen of Hong Kong, born in "
                 "Hong Kong. The state Attorney General's office sponsored "
                 "an Assistant Attorney General the same way in FY2023."),
        why_odd=("These are posts inside the machinery of a state "
                 "government, and both are published with the worker's "
                 "citizenship, the wage and the case number."),
        evidence=(("state-agency filings nationally, all published whole",
                   "public_employer_perm.json",
                   "sectors.state_agencies.filings", "n"),),
        href="/public-sector-visas#state-WASHINGTON",
    ),
    Case(
        title="One school district, one role, one country",
        finding=("Dallas Independent School District's largest single role "
                 "is Elementary Bilingual Teacher. The great majority of "
                 "those filings name Mexican citizens."),
        why_odd=("A single employer, a single job title, and a nationality "
                 "distribution that is nothing like the national one. Open "
                 "the employer on the public-sector page to see every role "
                 "and who filled it."),
        evidence=(("school-district filings nationally",
                   "public_employer_perm.json",
                   "sectors.school_districts.filings", "n"),
                  ("largest citizenship among them, nationally",
                   "public_employer_perm.json",
                   "sectors.school_districts.citizenship.Philippines", "n")),
        href="/public-sector-visas#school_districts",
    ),
    Case(
        title="Elementary and secondary schools",
        group="schools_k12",
        h1b_source="industry",
        finding=("Certified applications filed by K-12 schools and "
                 "districts, from thousands of separate employers."),
        why_odd=("The H-1B debate is conducted almost entirely about "
                 "technology companies. Public schools are one of the "
                 "largest filing sectors in the country."),
        evidence=(("certified applications", "h1b_by_industry.json",
                   "groups.schools_k12.filings", "n"),
                  ("distinct employers", "h1b_by_industry.json",
                   "groups.schools_k12.employers", "n"),
                  ("median wage offered", "h1b_by_industry.json",
                   "groups.schools_k12.median_wage", "usd")),
        href="/public-sector-visas#school_districts",
    ),
)
