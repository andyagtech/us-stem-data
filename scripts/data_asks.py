#!/usr/bin/env python3
"""The data asks, declared once.

WHY A DECLARATION AND NOT A PAGE

This replaces report/data_requests.html, which was a hand-written memo holding
eight requests. The memo's structure was right and is kept: who holds it, what
form collects it, what is published now, the smallest extract that would
answer the question, and what that would settle. What was wrong was that its
figures were typed in, which is the one thing this repo does not allow
anywhere else. An ask here names the dataset that demonstrates the gap and the
builder resolves the figure at render time, so an ask cannot outlive its
evidence.

The eight originals are the first eight below, in their original order and
substantially in their original words. The rest were met while building
something else on this site since.

HOW TO WRITE ONE

  * Name what is NOT published, not what you wish were true.
  * Ask for the SMALLEST extract that answers the question. A request for
    everything is a request a disclosure officer cannot grant.
  * Counts only, at the agency's own suppression thresholds. Never a
    person-level record. Where a cell falls below the threshold, the
    suppressed cell is itself a useful answer.
  * Say whether the agency already holds it. That is the question that decides
    who you are talking to, and it is usually yes.

EFFORT separates a disclosure decision from a budget request. They go to
different people and they should not be mixed on one page without a label.
"""
from __future__ import annotations

from dataclasses import dataclass, field

EFFORT = {
    "collected": ("No new collection",
                  "The agency holds this today, on a form or survey it "
                  "already processes. Publishing it is a disclosure "
                  "decision."),
    "restore": ("Published before, then stopped",
                "This was public and is not any more. The collection has not "
                "changed; only the release has."),
    "aggregate": ("A tabulation would do it",
                  "The record-level data is sensitive or suppressed, but a "
                  "tabulation at the agency's own thresholds would answer the "
                  "question without releasing it."),
    "new": ("Needs a new collection",
            "Nobody holds this. It is a real cost and belongs in a different "
            "conversation from the rest of this page."),
}


@dataclass(frozen=True)
class Ask:
    title: str
    held_by: str
    collected_on: str
    published_now: str
    request: str
    would_settle: str
    effort: str
    #: (label, dataset file under site/data, dotted path, format)
    evidence: tuple = field(default_factory=tuple)
    note: str = ""

    def __post_init__(self):
        if self.effort not in EFFORT:
            raise ValueError(f"unknown effort {self.effort!r} on {self.title!r}")


ASKS: tuple[Ask, ...] = (
    # ======================================================= the original eight
    Ask(
        title="H-1B cap-exempt status by employer",
        held_by="USCIS",
        collected_on=("Form I-129, which records whether a petition is "
                      "cap-exempt and on what ground."),
        published_now=("National totals by exemption category in the Report "
                       "to Congress. The H-1B Employer Data Hub names every "
                       "employer and carries no cap field."),
        request=("The Employer Data Hub extract with two added fields, "
                 "cap-exempt yes or no and the exemption ground, by employer "
                 "and fiscal year, with approvals and denials."),
        would_settle=("Which employers use the exemption, at what scale, and "
                      "whether use is concentrated. Today the petitions filed "
                      "under the affiliated-nonprofit ground cannot be "
                      "attributed to any organization."),
        effort="collected",
        evidence=(("employers on a cap-exempt list built by inference, not by "
                   "record", "cap_exempt_directory.json", "captured_total",
                   "n"),),
    ),
    Ask(
        title="Federal graduate support by citizenship",
        held_by="NSF National Center for Science and Engineering Statistics",
        collected_on=("Survey of Graduate Students and Postdoctorates, which "
                      "records support by mechanism and agency and enrolment "
                      "by citizenship. Survey of Earned Doctorates, which "
                      "records primary support by citizenship."),
        published_now=("Support by agency, and enrolment by citizenship, "
                       "never together. The SED records the assistantship but "
                       "not which award paid for it."),
        request=("A tabulation of graduate students with federal support, by "
                 "citizenship status and by field, from existing returns. If "
                 "the returns do not link the two, a statement saying so, "
                 "which would itself settle whether the figure exists."),
        would_settle=("What federal research funding spends per doctoral "
                      "student by citizenship. It would turn a proxy into a "
                      "measurement."),
        effort="collected",
    ),
    Ask(
        title="Citizens and permanent residents separated at conferral",
        held_by="NSF National Center for Science and Engineering Statistics",
        collected_on=("Survey of Earned Doctorates, which records citizenship "
                      "status at conferral in three categories."),
        published_now=("Two categories: citizens and permanent residents "
                       "combined, and temporary visa holders. The Survey of "
                       "Doctorate Recipients separates them after graduation "
                       "but not at the degree."),
        request=("SED doctorate counts by field and year with US citizens and "
                 "permanent residents shown separately."),
        would_settle=("The citizen share of US graduate STEM doctorates, "
                      "which no published source reports."),
        effort="collected",
        note=("Master's degrees would need a change to IPEDS and are a "
              "separate ask, below."),
    ),
    Ask(
        title="OPT and STEM OPT for every institution",
        held_by="DHS Student and Exchange Visitor Program",
        collected_on="SEVIS.",
        published_now=("A Top 100 ranking of schools. A school outside it is "
                       "absent rather than zero, so school totals are a floor "
                       "and year-to-year movement may only reflect the cutoff "
                       "moving."),
        request=("OPT and STEM OPT authorisation counts for every certified "
                 "school, by calendar year, on the same basis as the "
                 "published national table."),
        would_settle=("Work-authorisation participation for every "
                      "institution, not just the hundred largest."),
        effort="collected",
    ),
    Ask(
        title="Graduate applications and admissions",
        held_by=("No federal agency. The natural home is the National Center "
                 "for Education Statistics."),
        collected_on=("Nothing. The IPEDS Admissions component covers "
                      "first-time undergraduates only."),
        published_now=("Degrees conferred. No federal collection records who "
                       "applied to a graduate program, who was admitted, or "
                       "who was offered funding."),
        request=("A graduate admissions component in IPEDS: applications, "
                 "admissions and funded offers by broad field and residency "
                 "status."),
        would_settle=("Whether domestic applicants are declining, being "
                      "declined, or not applying. That is the question behind "
                      "this whole project and the one it cannot answer."),
        effort="new",
    ),
    Ask(
        title="L-1 and O-1 petitions by employer",
        held_by="USCIS",
        collected_on=("Form I-129, the same form and system that produce the "
                      "published H-1B Employer Data Hub."),
        published_now=("Nothing by employer. Neither classification requires "
                       "a labor condition application, so the Labor "
                       "Department never sees them, and USCIS publishes "
                       "employer hubs for H-1B, H-2A and H-2B only."),
        request=("Petitioner name and address for L-1A, L-1B, O-1A and O-1B, "
                 "aggregated by petitioner and fiscal year, with approvals "
                 "and denials. The H-1B hub's extract, run for four more "
                 "classifications."),
        would_settle=("Which companies transfer the most staff into the "
                      "United States without a wage test, and whether O-1 "
                      "growth sits in the industries most constrained by the "
                      "H-1B cap."),
        effort="collected",
    ),
    Ask(
        title="F-1 students by institution",
        held_by=("DHS Student and Exchange Visitor Program; the State "
                 "Department for visa issuance"),
        collected_on=("SEVIS, which records every F-1 student against a "
                      "certified school."),
        published_now=("State reports issuance by consulate and nationality, "
                       "never by school. SEVP publishes school-level figures "
                       "for OPT alone. IPEDS reports non-resident enrolment, "
                       "a residency category rather than a visa count."),
        request=("Active F-1 student records by certified school and year, "
                 "split by education level."),
        would_settle=("Where the student pipeline enters. That is the first "
                      "stage of everything else on this page."),
        effort="collected",
    ),
    Ask(
        title="Country of birth for nonimmigrant classes",
        held_by="State Department for visa issuance; DHS for admissions",
        collected_on=("The nonimmigrant visa application, which records place "
                      "of birth alongside nationality."),
        published_now=("Every visa and admission series is by nationality. A "
                       "naturalised citizen of one country born in another "
                       "cannot be distinguished from a native-born citizen "
                       "anywhere in the published data."),
        request=("Nonimmigrant visa issuances by visa class, fiscal year, "
                 "nationality and country of birth. For classes admitted "
                 "without a visa, the equivalent from DHS admission records "
                 "if they carry birthplace."),
        would_settle=("How far a nationality series reflects the country "
                      "people actually come from. In the one dataset that "
                      "publishes both fields, the two disagree often enough "
                      "to matter, and the largest single citizenship among "
                      "the mismatches is Canada."),
        effort="collected",
        evidence=(("filings where citizenship and birth country differ, where "
                   "both are published", "public_employer_perm.json",
                   "anomaly_totals.citizenship_differs_from_birth_country",
                   "n"),),
    ),

    # ===================================================== met since the memo
    Ask(
        title="Restore the worker fields to the PERM disclosure file",
        held_by="Department of Labor, Office of Foreign Labor Certification",
        collected_on=("Form ETA-9089, on which the employer still answers all "
                      "three questions."),
        published_now=("Nothing. Country of citizenship, country of birth and "
                       "class of admission were all published through FY2024 "
                       "and all three were removed at once in FY2025, when "
                       "the file went from 155 columns to 137."),
        request=("The three withdrawn columns, restored to the quarterly "
                 "disclosure file on the basis used through FY2024."),
        would_settle=("Every question about who fills a sponsored post. This "
                      "site can say that a Washington state agency sponsored "
                      "a Hong Kong citizen for permanent residence in FY2021. "
                      "It cannot say whether that still happens, and no "
                      "future harvest will tell us, because the field is gone "
                      "rather than empty."),
        effort="restore",
        evidence=(
            ("filings the ended series covers", "public_employer_perm.json",
             "public_rows", "n"),
            ("window, and it cannot be extended", "public_employer_perm.json",
             "window", "raw"),
        ),
        note=("This is the single most consequential item on the page. The "
              "collection did not change. Only the release did."),
    ),
    Ask(
        title="A stable employer identifier in the H-1B Employer Data Hub",
        held_by="USCIS",
        collected_on="Form I-129, which carries the petitioner's FEIN.",
        published_now=("The employer name as filed, and nothing else. There "
                       "is no key that survives a spelling change."),
        request=("Any stable per-employer identifier alongside the name. A "
                 "hashed or truncated FEIN would do. The agency need not "
                 "publish the number itself, only something that is the same "
                 "across filings by the same body."),
        would_settle=("Counting an employer at all. Cognizant files under "
                      "eighteen spellings and the largest accounts for 22,287 "
                      "of 50,994. Every employer total published anywhere, by "
                      "anyone, is a floor, and the error is largest for "
                      "exactly the biggest filers."),
        effort="collected",
    ),
    Ask(
        title="Name the affiliated nonprofits in the Report to Congress",
        held_by="USCIS",
        collected_on="Form I-129.",
        published_now=("A count of petitions from nonprofits related to or "
                       "affiliated with an institution of higher education. "
                       "No organization is named."),
        request=("The same count, broken out by petitioning organization."),
        would_settle=("Sizing the bodies running the cap-exempt route. This "
                      "site reaches for IRS Form 990 to do it, which gives "
                      "revenue and headcount but says nothing about cap "
                      "status, so the two can sit side by side and never "
                      "join."),
        effort="collected",
    ),
    Ask(
        title="A six-digit NAICS code on the labor condition application",
        held_by="Department of Labor, Office of Foreign Labor Certification",
        collected_on="Form ETA-9035, on which the employer reports NAICS.",
        published_now=("Whatever depth the employer chose. The same industry "
                       "appears at two, four, five and six digits in a single "
                       "file."),
        request=("Validation requiring six digits at filing, and the full "
                 "six-digit code in the disclosure file."),
        would_settle=("Separating a staffing firm from a law firm, which is "
                      "the whole basis of the body-shop test. A filing coded "
                      "'6111' is a school and cannot be counted as one, "
                      "because '6111' covers several six-digit industries and "
                      "assigning it would be a guess."),
        effort="collected",
        evidence=(
            ("certified applications read", "h1b_by_industry.json",
             "certified_filings", "n"),
            ("distinct NAICS codes, at mixed depths", "h1b_by_industry.json",
             "distinct_codes", "n"),
        ),
    ),
    Ask(
        title="A published column schema, and a diff when it changes",
        held_by="Department of Labor, Office of Foreign Labor Certification",
        collected_on="Not applicable. This is about the release, not the form.",
        published_now=("Files whose column names change between years without "
                       "notice. H_1B_DEPENDENT became H-1B_DEPENDENT in "
                       "FY2025. FW_INFO_BIRTH_COUNTRY became "
                       "FOREIGN_WORKER_BIRTH_COUNTRY in FY2020."),
        request=("A versioned schema published with each release, and a diff "
                 "against the previous one."),
        would_settle=("A whole category of silent error. A renamed column "
                      "read by its old name returns no value, and a missing "
                      "dependency flag reads as a firm that is never "
                      "dependent. That is a wrong answer rather than a crash, "
                      "and no downstream check can catch it reliably."),
        effort="collected",
        note=("Not a request for data. It would cost close to nothing and it "
              "is the cheapest item here."),
    ),
    Ask(
        title="The complete H-1B enforcement case set",
        held_by="Department of Labor, Wage and Hour Division",
        collected_on="WHISARD case management.",
        published_now=("An extract carrying the largest cases only."),
        request=("All concluded H-1B cases with employer, fiscal year, "
                 "violation type and back wages, at the division's usual "
                 "thresholds."),
        would_settle=("Reading absence. A firm that does not appear may have "
                      "had no findings or may have had small ones, and the "
                      "extract cannot distinguish them. Only a handful of "
                      "employers match between the enforcement file and the "
                      "wage data, so the crossing is inconclusive."),
        effort="aggregate",
        evidence=(("employers matched across both files",
                   "employer_profiles.json", "with_enforcement", "n"),),
    ),
    Ask(
        title="A wage measure for OPT employment",
        held_by="DHS SEVP holds the authorisations; Treasury holds the payroll",
        collected_on=("SEVIS records the authorisation. No federal collection "
                      "records what the job pays."),
        published_now="Nothing.",
        request=("Aggregate earnings for OPT-authorised employment, by year "
                 "and broad field. A tabulation from the employer side of the "
                 "payroll tax would do it without a new survey."),
        would_settle=("Sizing the payroll-tax differential. OPT employment is "
                      "exempt from the employer share of FICA, which is a "
                      "real price difference against an equivalent citizen "
                      "hire. This site publishes no national total for it, "
                      "only a per-$100,000 figure and a scenario grid, "
                      "because the wage base does not exist."),
        effort="new",
    ),
    Ask(
        title="Country of birth crossed against country of residence",
        held_by="DHS Office of Immigration Statistics",
        collected_on="Admission and adjustment records.",
        published_now=("Yearbook tables 2 and 3, which are separate totals "
                       "for the same population."),
        request="The cross-tabulation of the two, at the usual thresholds.",
        would_settle=("Whether a surplus in one country can be attributed to "
                      "a particular origin. No individual is traced across "
                      "the two tables, so however strongly the deficits in "
                      "one line up with the surpluses in another, the "
                      "inference cannot be made, and this site does not make "
                      "it."),
        effort="aggregate",
    ),
    Ask(
        title="State geography on the Survey of Doctorate Recipients",
        held_by="NSF National Center for Science and Engineering Statistics",
        collected_on="The SDR questionnaire, which records location.",
        published_now=("Nothing below national. State is suppressed in the "
                       "public-use file for confidentiality."),
        request=("A state-level tabulation of the core SDR measures with the "
                 "usual cell suppression. Not the microdata."),
        would_settle=("Every state-level question about the doctoral "
                      "workforce. This site publishes a page for each of the "
                      "fifty states and cannot put a single SDR figure on any "
                      "of them."),
        effort="aggregate",
    ),
    Ask(
        title="Hours worked, above the topcode",
        held_by="NSF National Center for Science and Engineering Statistics",
        collected_on="The SDR questionnaire.",
        published_now=("HRSWKP topcoded at more than 40, so 41 hours and 80 "
                       "hours are a single value."),
        request=("Either a higher topcode or a banded distribution above "
                 "forty."),
        would_settle=("The claim people actually make. The argument is about "
                      "the distance above forty, and the variable collapses "
                      "exactly the range the argument is about."),
        effort="aggregate",
    ),
    Ask(
        title="Permanent residents separated from citizens in IPEDS enrolment",
        held_by="National Center for Education Statistics",
        collected_on=("The IPEDS Fall Enrolment component, which collects "
                      "'non-resident alien' as a residency category."),
        published_now=("Two groups, with permanent residents counted as "
                       "domestic and reported under race and ethnicity."),
        request=("A permanent-resident category in Fall Enrolment and "
                 "Completions."),
        would_settle=("Measuring the foreign-born share of a program. Every "
                      "non-resident share on this site is a floor, and the "
                      "gap is largest in exactly the fields where the "
                      "question is asked most."),
        effort="new",
        note=("This is a change to the collection, not only to the release, "
              "which is why it is marked as new. The doctorate version of the "
              "same question needs no new collection and is above."),
    ),
    Ask(
        title="Graduate borrowing in Student Financial Aid",
        held_by="National Center for Education Statistics",
        collected_on=("The IPEDS Student Financial Aid component, which "
                      "covers undergraduates."),
        published_now=("Undergraduate Pell and federal loans. Graduate "
                       "borrowing sits in the Education Department's loan "
                       "systems and not in IPEDS."),
        request=("Graduate federal loan volume by institution and year in "
                 "Student Financial Aid, or a crosswalk to the loan data."),
        would_settle=("Putting a federal dollar figure beside a graduate "
                      "program. A graduate-heavy institution's federal "
                      "money is understated on this site, and the borrowing "
                      "that funds a terminal master's is invisible."),
        effort="collected",
    ),
    Ask(
        title="Raise or remove the OEWS wage topcode",
        held_by="Bureau of Labor Statistics",
        collected_on="The OEWS survey.",
        published_now=("Wages topcoded at $239,200 and published as '#', with "
                       "suppressed cells as '*'."),
        request=("A higher topcode, or the mean above it, for occupations "
                 "where the topcode binds."),
        would_settle=("Comparing a high-wage occupation against its "
                      "prevailing wage. A topcoded occupation has no usable "
                      "90th percentile, so the comparison this site runs on "
                      "every certified filing drops out for the occupations "
                      "where the money is."),
        effort="aggregate",
        evidence=(("filings priced against the local median",
                   "local_wage_comparison.json", "filings_priced", "n"),
                  ("of those, paid below the local median for the occupation",
                   "local_wage_comparison.json", "below_local_median_pct",
                   "pct1")),
    ),
    Ask(
        title="Resume the research-security case compilation",
        held_by="Department of Justice, National Security Division",
        collected_on="Case records.",
        published_now=("Nothing after 19 November 2021. The compilation "
                       "stopped there and the China Initiative ended on "
                       "23 February 2022."),
        request=("Resumed publication on the previous basis, or a statement "
                 "that it has been discontinued."),
        would_settle=("Saying anything about the present. This site publishes "
                      "the register as a frozen record and labels it as one, "
                      "because the alternative is to let a 2021 snapshot read "
                      "as a current picture. Cases have been brought since "
                      "and none is in a public list."),
        effort="restore",
        evidence=(("entries in the frozen register", "security_cases.json",
                   "totals.entries", "n"),
                  ("of them brought after the list stopped",
                   "security_cases.json", "totals.cases_since_list_stopped",
                   "n")),
    ),
    Ask(
        title="Restore the Form 990 e-file years that came off irs.gov",
        held_by="Internal Revenue Service, Tax Exempt and Government Entities",
        collected_on="Form 990, filed electronically.",
        published_now=("Tax years 2019 onward on irs.gov. The 2009 to 2018 "
                       "e-file XML sat on an AWS public bucket that stopped "
                       "updating at the end of 2021, and outside researchers "
                       "report that filings did not survive the move."),
        request=("The full e-file XML archive back to the start of electronic "
                 "filing, hosted by the agency, with an index of what is "
                 "held."),
        would_settle=("Any long-run analysis of a nonprofit. A sponsoring "
                      "organization's growth over fifteen years is the "
                      "question worth asking, and the public record of it now "
                      "depends on third-party mirrors."),
        effort="restore",
        note=("The counts of what went missing come from outside researchers, "
              "not from the IRS, and the agency has published no "
              "reconciliation. A statement of what is held and what is not "
              "would itself be useful."),
    ),
    Ask(
        title="Form 990 employee counts that are populated",
        held_by="Internal Revenue Service, Tax Exempt and Government Entities",
        collected_on="Form 990 Part V, which carries the W-3 employee count.",
        published_now=("The field, frequently as zero even where the filing "
                       "reports staff elsewhere."),
        request=("Either a populated field or a documented explanation of "
                 "when it is left blank."),
        would_settle=("Sizing an organization by people rather than by money. "
                      "Revenue is the only usable measure of a cap-exempt "
                      "sponsor today, and revenue is not a count of "
                      "anything."),
        effort="collected",
    ),
)
