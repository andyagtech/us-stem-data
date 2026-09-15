"""The data catalog: what each derived artifact is, what builds it, what it needs.

WHY THIS EXISTS

`PIPELINE.md` documents the seven formal steps thoroughly, and those steps run
the dissertation corpus from harvest to deploy. But they are only half the
system. The other half -- acquiring federal data and turning it into the derived
artifacts the site and the assistant read -- lives in `scripts/`, where roughly
thirty files are called by nothing. Knowing which to run, in what order, after a
source updates was tribal knowledge. This module writes it down in a form that
can be checked against disk rather than trusted.

WHAT IT IS NOT

It is not a build system and it does not replace the pipeline. It answers three
questions and stops:

    what produces this file?          -> `produces`
    what does that need first?        -> `consumes`
    is it out of date?                -> compare mtimes

DECLARING TRUTHFULLY

Every path here is checked. `python3 -m pipeline datasets` reports any entry
whose declared inputs or outputs are missing, and lists scripts in `scripts/`
that no entry claims -- so the catalog's own coverage is visible instead of
assumed. An entry that lies shows up as a broken entry, not as silence.

Paths are repo-relative. A dataset with no `consumes` is a leaf: its input is a
file downloaded from an agency, and re-running it re-reads whatever is on disk.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Dataset:
    key: str
    script: str                       # builder under scripts/, no extension
    produces: tuple[str, ...]
    summary: str
    source: str                       # issuing agency, or "derived"
    consumes: tuple[str, ...] = ()
    cadence: str = "on source update"
    notes: str = ""
    args: str = ""                    # how to invoke, if not bare
    archived_at: str = ""             # where the source lives when not on disk
    source_url: str = ""              # where a reader goes to get it themselves

    def offloaded(self) -> tuple[str, ...]:
        """Consumed paths that are archived rather than kept locally.

        Some sources are large, rebuildable and needed only when their step is
        re-run -- the 4 GB of DOL disclosure files behind `lca`, for one. They
        are pushed to S3 and deleted locally, which is fine right up until a
        check that asserts every catalogued path exists starts failing.
        Recording WHERE the data went keeps that check honest: a path may be
        absent only if the catalogue says where to get it back.
        """
        if not self.archived_at:
            return ()
        return tuple(p for p in self.consumes if not (ROOT / p).exists())

    def script_path(self) -> Path | None:
        """Where this entry's builder lives. Most are Python; a few are shell."""
        for ext in (".py", ".sh"):
            cand = ROOT / "scripts" / f"{self.script}{ext}"
            if cand.exists():
                return cand
        return None

    def script_rel(self) -> str:
        """Display path, falling back to .py for an entry pointing at nothing."""
        sp = self.script_path()
        return str(sp.relative_to(ROOT)) if sp else f"scripts/{self.script}.py"

    def out_paths(self) -> list[Path]:
        return [ROOT / p for p in self.produces]

    def in_paths(self) -> list[Path]:
        return [ROOT / p for p in self.consumes]

    def missing_outputs(self) -> list[str]:
        return [p for p in self.produces if not (ROOT / p).exists()]

    def missing_inputs(self) -> list[str]:
        return [p for p in self.consumes if not (ROOT / p).exists()]

    def is_priority(self) -> bool:
        """Refreshing this matters more than the mtime alone suggests."""
        return "HIGHEST-PRIORITY" in (self.notes or "")

    def stale(self) -> bool:
        """True when any declared input is newer than the oldest output.

        A declared input may be a directory -- cloud/chat/knowledge is one --
        in which case the newest file inside it counts. Without that, editing
        a knowledge file would leave the curated answers looking current while
        the assistant had already moved on.
        """
        outs = [p for p in self.out_paths() if p.exists()]
        if not outs:
            return False
        newest_in = 0.0
        for p in self.in_paths():
            if p.is_dir():
                for child in p.rglob("*"):
                    if child.is_file():
                        newest_in = max(newest_in, child.stat().st_mtime)
            elif p.exists():
                newest_in = max(newest_in, p.stat().st_mtime)
        if not newest_in:
            return False
        return newest_in > min(p.stat().st_mtime for p in outs)


# ---------------------------------------------------------------------------
# The catalog. Ordered by dependency: an entry may only consume what an earlier
# entry produces.
# ---------------------------------------------------------------------------

CATALOG: tuple[Dataset, ...] = (
    Dataset(
        key="nra_index",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        script="build_nra_index",
        source="NCES IPEDS Completions (C{year}_A.csv)",
        produces=("data/ipeds/nra_index.csv.gz",
                  "data/ipeds/nra_index_meta.json",
                  "data/ipeds/cip_titles.csv"),
        summary=("Non-resident and total research doctorates by year, institution "
                 "and CIP code. The ground truth every headline share derives from."),
        cadence="annually, when IPEDS releases a new completions year",
        notes=("Research doctorates only -- award level 17 from 2010, legacy 9 "
               "before. Master's (level 7) is NOT in this index; scripts that "
               "need it read the raw completions files directly."),
    ),
    Dataset(
        key="nra_shares",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        script="compute_nra_shares",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",),
        produces=("pipeline/universities.json",),
        summary="Each university's headline NRA share, written into the registry.",
        args="--write",
        cadence="after nra_index changes",
        notes=("Pinned basis: CIP families 11,14,15,26,27,30,40,42; years "
               "2015-2022; award level 17. Changing any one changes every "
               "published share. Also rewrites the duplicate `nra` values in "
               "scripts/generate_name_lists.py, which holds its own copy."),
    ),
    Dataset(
        key="f1_series",
        source_url="https://travel.state.gov/content/travel/en/legal/visa-law0/visa-statistics/nonimmigrant-visa-statistics.html",
        script="build_f1_series",
        source="US Department of State, NIV detail tables",
        consumes=("data/h1b/state_dept/FYs97-24_NIVDetailTable.xlsx",),
        produces=(),                  # prints; --json writes where asked
        summary="F-1 student visa issuance by fiscal year, with China and India.",
        args="--json PATH",
        cadence="annually, when State publishes the new fiscal year",
        notes=("Two silent traps: sheets mix country rows with regional and grand "
               "totals (a naive sum triple-counts), and the column name changes "
               "from 'F-1' to 'F1' at FY2022. FY2015 = 644,233 is pinned as a "
               "verification anchor and the script warns if a change moves it."),
    ),
    Dataset(
        key="federal_support",
        source_url="https://ncses.nsf.gov/surveys/federal-support-survey/",
        script="build_federal_support_json",
        source="NSF NCSES federal S&E support tables",
        consumes=("data/federal_support/nsf25339-tab017.xlsx",),
        produces=("data/federal_support/federal_support_by_university.json",),
        summary="Federal science and engineering obligations per institution.",
    ),
    Dataset(
        key="doctorate_origins",
        script="build_doctorate_origins",
        source="NSF NCSES, Survey of Earned Doctorates 2024, tables 7-8 and 5-5",
        source_url="https://ncses.nsf.gov/pubs/nsf25349/data-tables",
        consumes=("data/sed/",),
        produces=("site/data/doctorate_origins.json",),
        summary=("The 40 largest countries of origin of temporary-visa "
                 "doctorate recipients, and parental education by citizenship."),
        cadence="annual, with the SED",
        notes=("'Non-resident' was one undifferentiated block everywhere except "
               "the retention page, which named countries the degree pages "
               "could not. China is 35.9% of temporary-visa doctorates and "
               "India 14.1%; the top five are 61%, across 159 countries in "
               "total. COUNTS ARE ALL FIELDS, not core-STEM only, so they are "
               "not directly comparable to the IPEDS core-STEM figures used "
               "elsewhere. Ranks are checked against the counts, so a shifted "
               "column is reported rather than published."),
    ),
    Dataset(
        key="grad_support",
        script="build_grad_support",
        source="NSF NCSES, Survey of Graduate Students and Postdoctorates, 2024",
        source_url="https://ncses.nsf.gov/surveys/graduate-students-postdoctorates-s-e/",
        consumes=("data/nsf_gss/graduate_students_postdocs_2024.zip",),
        produces=("site/data/grad_support.json",),
        summary=("Full-time doctoral support by mechanism and, within federal "
                 "support, by funding agency -- whose money pays for graduate "
                 "study, across 653 institutions."),
        cadence="annual, with GSS",
        notes=("Answers the question the SED leaves open. The SED says a "
               "recipient was funded by an assistantship; this says federal "
               "money reaches doctoral students overwhelmingly through "
               "RESEARCH assistantships (52,428 of 67,936 federally supported "
               "students) while teaching assistantships are almost entirely "
               "institutional (1,041 federal against 63,425 non-federal). NIH "
               "and NSF together fund 62%. COUNTS ARE STUDENTS, NOT DOLLARS. "
               "It does NOT close the citizenship link: GSS reports support by "
               "agency and enrolment by citizenship but never together, so no "
               "published field says which agency funded a foreign national. "
               "TRAP: the token 'forgn' means different things in the two "
               "sheets. In Race it is the student's citizenship; in Support "
               "it is a FOREIGN SOURCE OF FUNDS, a sibling of 'inst' and "
               "'othus' -- dr_ft_ra_nfed_forgn_v is 1,313, far too small to "
               "be foreign students on assistantships. Reading the Support "
               "one as citizenship would manufacture exactly the crossing "
               "this note says does not exist."),
    ),
    Dataset(
        key="working_conditions",
        script="build_working_conditions",
        source="NSF NCSES, Survey of Doctorate Recipients 2023 public-use file",
        source_url="https://ncses.nsf.gov/surveys/doctorate-recipients/",
        consumes=("data/nsf_workforce/doctorate_recipients_2023.zip",),
        produces=("site/data/working_conditions.json",),
        summary=("Hours worked and reported satisfaction by CURRENT "
                 "citizenship status -- whether visa dependence shows up in "
                 "what people work and report, not only in the statute."),
        cadence="biennial, with the SDR",
        notes=("Built to test the leverage argument empirically. IT SPLITS. "
               "Visa holders report much more dissatisfaction with JOB "
               "SECURITY (21.8% against 13.7% of native citizens) and salary "
               "(27.0% against 19.2%), which supports it. They are LESS "
               "likely to work more than 40 hours a week -- 32.8% against "
               "48.0%, and still lower within recent cohorts (28.4% against "
               "46.9% for 2010-14) -- which does NOT. But the hours measure "
               "CANNOT TEST the usual claim: the public file topcodes HRSWKP "
               "at 'more than 40', so 41 hours and 80 hours are one value, "
               "and the claim is about the distance above forty. Treat the "
               "hours result as UNABLE TO SETTLE the question rather than as "
               "refuting it -- and note both measures are self-reported to a "
               "federal survey by people whose stay depends on an employer. "
               "POPULATION MATTERS: this is DOCTORATE HOLDERS, many of them "
               "academic postdocs, and is not the H-1B population the "
               "argument is usually about, most of whom hold a bachelor's or "
               "master's. Grouped by status NOW (CTZN), unlike everything "
               "else here, because leverage attaches to current status. "
               "Hours are a BANDED self-report ('more than 40'), not a count. "
               "Read within cohort: visa holders are much younger."),
    ),
    Dataset(
        key="lpr_adjustments",
        script="build_lpr_adjustments",
        source="DHS Office of Homeland Security Statistics, Yearbook of "
               "Immigration Statistics, table 6",
        source_url="https://ohss.dhs.gov/topics/immigration/yearbook",
        consumes=("data/dhs_yearbook/lpr_fy2023.xlsx",),
        produces=("site/data/lpr_adjustments.json",),
        summary=("Permanent residence by class and by type -- adjustment of "
                 "status against new arrival. How many green cards go to "
                 "people already in the country on a temporary visa."),
        cadence="annual, with the DHS Yearbook",
        notes=("The non-immigrant-to-immigrant route measured for the whole "
               "system rather than one survey population. EMPLOYMENT-BASED "
               "GREEN CARDS ARE OVERWHELMINGLY ADJUSTMENTS: 74.6% in FY2023, "
               "85.6% in FY2014 -- the recipient was already here. The "
               "contrast is the point: family-sponsored is 5.4% and the "
               "diversity lottery 1.4%, so this is specific to the "
               "employment route, not typical of immigration. AN ADJUSTMENT "
               "DOES NOT NAME THE PRIOR STATUS: the table shows the person "
               "was already in the country, NOT which visa brought them and "
               "NOT that they studied here. Counts are persons, rounded by "
               "DHS to the nearest ten, so parts need not sum exactly; the "
               "builder checks adjustments plus new arrivals against the "
               "published total and reports any class that fails."),
    ),
    Dataset(
        key="enrolment_and_funding",
        script="join_enrolment_and_funding",
        source="NSF NCSES GSS 2024 and HERD FY2024 table 14",
        source_url="https://ncses.nsf.gov/surveys/higher-education-research-development/",
        consumes=("site/data/gss_institution_ranking.json",
                  "data/herd/herd_fy2024_table14.xlsx",
                  "data/ipeds/hd2024.csv"),
        produces=("site/data/enrolment_and_funding.json",),
        summary=("Temporary-visa share of graduate enrolment joined to "
                 "federal R&D expenditure -- whether the public money and the "
                 "foreign enrolment sit in the same institutions."),
        cadence="annual, with GSS and HERD",
        notes=("THEY DO SIT TOGETHER. By quartile of federal R&D the doctoral "
               "visa share runs 20.5% in the lowest against 43.6% in the "
               "highest, and the top quartile holds 167,396 doctoral students "
               "against 7,631 in the bottom; master's runs 32.9% to 50.3%. "
               "REPORTED AT THREE LEVELS -- doctoral, master's and the two "
               "pooled -- because the unit of interest is the institution and "
               "its graduate operation in bulk. Majority-foreign institutions "
               "hold $12.5bn of federal R&D counted at doctoral level, "
               "$24.1bn at master's, and $19.4bn (32.9% of matched, 210,870 "
               "students across 108 institutions) counted on graduate study "
               "as a whole. HERD records expenditure AT THE INSTITUTION and "
               "never at a student, so none of this traces a grant to a "
               "person -- the claim is about institutions, which is what the "
               "data measures. "
               "KEEP ONE NUANCE: the very highest master's SHARES are at "
               "institutions with almost no federal R&D -- Harrisburg and "
               "Central Missouri are not in HERD at all -- so 'highest share' "
               "and 'most federal money' name different institutions even "
               "though the overall relationship is positive. MATCHING: HERD "
               "abbreviates and campus-qualifies names, and fourteen GSS "
               "names cover more than one campus, so matching on the GSS name "
               "collapsed Ann Arbor, Dearborn and Flint into one record and "
               "reported the wrong one (Michigan showed 90.3%). The join now "
               "goes through the GSS UNITID to the IPEDS campus name. 477 of "
               "649 matched; UNMATCHED IS NOT ZERO -- it may mean absent from "
               "HERD or an unrecovered spelling. HERD is R&D EXPENDITURE, not "
               "all federal money and not student support."),
    ),
    Dataset(
        key="agency_grants",
        script="",                    # fetched by data/state_funding/*/fetch_*.py
        source="NIH RePORTER v2 API and NSF Awards API",
        source_url="https://reporter.nih.gov/exporter",
        consumes=("data/state_funding/nih_reporter/nih_by_university.json",
                  "data/state_funding/nsf_awards/nsf_by_university.json"),
        produces=(),
        summary=("Grant dollars and counts per university per year from NIH "
                 "RePORTER (FY2020-24, 105 institutions) and NSF Awards "
                 "(2020-25, 102 institutions)."),
        cadence="on demand, via each agency's API",
        notes=("Fetched by data/state_funding/nih_reporter/fetch_nih.py and "
               "the NSF equivalent, which live beside their output rather "
               "than in scripts/. HELD AND DOCUMENTED, NOT YET BUILT INTO "
               "ANYTHING. Finer than "
               "HERD, which reports total R&D expenditure per institution: "
               "these are individual agencies at grant level, by year. The "
               "marginal value over the HERD join in enrolment_and_funding is "
               "agency attribution -- whether NIH-heavy and NSF-heavy "
               "institutions differ in foreign enrolment share -- and a "
               "shorter but more current window. COVERS ONLY THE ~100 "
               "UNIVERSITIES THIS PROJECT TRACKS, not the 694 in HERD, so it "
               "cannot replace the HERD join and would bias any ranking "
               "toward large research universities. Organisation names are "
               "matched by each fetcher's own variant list, recorded in "
               "org_name_variants and appears_as."),
    ),
    Dataset(
        key="h1b_approvals",
        script="build_h1b_approvals",
        source="USCIS H-1B Employer Data Hub",
        source_url="https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub",
        consumes=("data/uscis_hub/",),
        produces=("site/data/h1b_approvals.json",),
        summary=("H-1B petitions approved and denied by employer, FY2009-2023 "
                 "-- what USCIS actually granted, between what employers "
                 "asked for and what enforcement later found."),
        cadence="quarterly, with USCIS hub releases",
        notes=("The middle term the project lacked: LCA is what was "
               "requested, WHISARD what was found, this is what was GRANTED. "
               "INITIAL AND CONTINUING ARE KEPT APART -- an initial approval "
               "is a new worker, a continuing one an extension for someone "
               "already here, so summing them counts a person repeatedly "
               "across years. Wipro leads on initial approvals and files "
               "90.0% at wage Level I or II; TCS 86.2%. DENIAL RATES ARE A "
               "POLICY SERIES: 2.2% in FY2022 against 24.3% in FY2018, which "
               "tracks adjudication policy rather than employers. USCIS "
               "renamed the columns in FY2020 from plural to singular, which "
               "scored eleven years at zero before it was caught. FY2023 IS "
               "INCOMPLETE -- 38,315 initial approvals against a median of "
               "114,863 -- and is flagged in the output. NAME FRAGMENTATION "
               "IS MATERIAL: Cognizant files under 18 spellings totalling "
               "50,994 against 22,287 for its largest, so every employer "
               "total is a floor; the name_variants block lists each spelling "
               "with its own count rather than merging them silently."),
    ),
    Dataset(
        key="state_funding_and_enrolment",
        script="build_state_funding_and_enrolment",
        source="SHEEO State Higher Education Finance FY2024, and NCES IPEDS Fall Enrolment",
        source_url="https://shef.sheeo.org/data-downloads/",
        consumes=("data/shef/SHEEO_SHEF_FY24_Report_Data.xlsx",
                  "data/ipeds_enrollment/", "data/ipeds/hd2024.csv"),
        produces=("site/data/state_funding_and_enrolment.json",),
        summary=("State appropriations per FTE against the non-resident share "
                 "of graduate enrolment at public institutions, by state, "
                 "2010-2023 -- a test of why the tuition finding exists."),
        cadence="annual, with SHEF and IPEDS",
        notes=("Built to test the explanation this project had been asserting "
               "for the tuition findings -- that states withdrew support so "
               "universities recruited full-fare foreign students. THE PANEL "
               "DOES NOT SUPPORT IT, AND POINTS THE OTHER WAY: states in the "
               "half that cut most saw the foreign share rise 3.74 points, "
               "those that cut least 4.96 points. Louisiana cut 22.4% in real "
               "terms and its foreign share FELL 2.6 points; Illinois raised "
               "funding 54.7% and its share rose 12.5. Only 13 of 50 states "
               "cut in real terms at all over the period. THE BASELINE IS "
               "DOING WORK: 2010 is a post-crash trough. The median state "
               "fell 11.1% from 2008 to 2010 and was still 5.7% below 2008 "
               "in 2023, so from a 2008 baseline 'most states raised funding' "
               "reverses. The enrolment series cannot start earlier, so the "
               "window stays and the limitation is declared. The tuition "
               "stands; the causal story for it does not, and should not be "
               "repeated. HECA IS AN INDEX, NOT A MULTIPLIER -- nominal "
               "dollars are DIVIDED by it; multiplying instead put Alabama "
               "2010 at $3,811 against a published $7,686 and turned a "
               "recovery into an apparent doubling. Public institutions only; "
               "enrolment is ALL FIELDS. No coefficient is published: fifty "
               "states share a strong common trend."),
    ),
    Dataset(
        key="repo_datasets",
        script="publish_repo_datasets",
        source="Derived: copies of analysis files built elsewhere in the repo",
        source_url="",
        consumes=("data/h1b/", "data/cap_exempt/", "data/federal_support/",
                  "data/nsf_workforce/", "data/buildfellowship/"),
        produces=("site/data/repo_datasets.json",),
        summary=("Publishes eighteen analysis files that their own builders "
                 "write beside their inputs rather than into site/data/."),
        cadence="rebuild after any of the source builders",
        notes=("Closes a publishing gap, not an analysis one: OPT by "
               "university, the cap-exempt sponsor ranking, PERM by status "
               "held when filed, the nonprofit filings, EB-2 NIW and the "
               "Build Fellowship projects were all built, catalogued and "
               "tested but unreachable from outside the repository. THEY ARE "
               "COPIES: the path under data/ stays what the builder writes "
               "and what other scripts read, because changing it to fix a "
               "publishing problem would break the pipeline. Regenerated on "
               "every run. PLUMBING IS DELIBERATELY EXCLUDED -- the "
               "assistant's bundle, curated answers, social images, IPEDS "
               "index metadata and the university configuration are not "
               "findings and publishing them would invite them to be read as "
               "such. 3.8 MB across eighteen files."),
    ),
    Dataset(
        key="wage_level_trend",
        script="build_wage_level_trend",
        source="US DOL OFLC, H-1B LCA disclosure archive FY2017-2026",
        source_url="https://www.dol.gov/agencies/eta/foreign-labor/performance",
        consumes=("data/h1b/lca_archive_manifest.json",),
        archived_at="s3://phd-demographics-raw-data/data/h1b/lca/",
        produces=("site/data/wage_level_trend.json",),
        summary=("Share of certified H-1B filings at each prevailing-wage "
                 "level, by fiscal year -- whether employers have moved "
                 "toward the bottom of the legal range or away from it."),
        cadence="quarterly, with OFLC releases",
        notes=("THE TREND RUNS THE OTHER WAY FROM WHAT TWO YEARS IMPLIED and "
               "this must be said wherever the level figures appear: the "
               "Level I or II share FELL from 80.5% in FY2017 to 62.7% in "
               "FY2025, and Level I alone from 44.4% to 20.8%. Employers file "
               "HIGHER on the scale than they did, not lower. The break is "
               "between FY2017 and FY2018, where Level I drops 44.4% to "
               "17.9%; both files use the same column and the same visa-class "
               "field, so it is a real reading, and it coincides with the "
               "April 2017 executive order that put Level I filings under "
               "scrutiny -- a coincidence in time, not a demonstrated cause. "
               "FY2018 SHIPS TWO OVERLAPPING ANNUAL FILES and summing them "
               "doubled the year to 939,820 against a true 576,359; the "
               "larger is kept and the other recorded in "
               "superseded_duplicates. Pre-FY2017 files carry no wage-level "
               "column at all, so the series cannot start earlier. FY2026 is "
               "partial. This is the LEVEL MIX and is a separate question "
               "from whether the wage clears a local median, which "
               "local_wage_comparison answers and where the picture is worse."),
    ),
    Dataset(
        key="local_wage_comparison",
        script="build_local_wage_comparison",
        source="BLS OEWS state file and US DOL OFLC LCA disclosure data",
        source_url="https://www.bls.gov/oes/tables.htm",
        consumes=("data/bls_oes/", "data/h1b/lca_archive_manifest.json",
                  "site/data/occupational_wages.json"),
        archived_at="s3://phd-demographics-raw-data/data/h1b/lca/",
        produces=("site/data/local_wage_comparison.json",),
        summary=("The below-median finding measured against the median for "
                 "the occupation in the worksite state, not the national one."),
        cadence="quarterly, with OFLC and annually with OEWS",
        notes=("THE NATIONAL COMPARISON UNDERSTATES AND THIS IS THE FIGURE TO "
               "QUOTE: on the same 565,966 filings, 70.8% fall below the "
               "national median for their occupation and 78.7% below the "
               "median in their own state. Filings concentrate in high-wage "
               "states, so a national yardstick flatters them. CALIFORNIA IS "
               "THE EXTREME: 37.7% below national against 70.3% below local, "
               "a 32.6-point swing; Washington +27.1, New York +21.2. "
               "Low-wage states move the other way -- Florida -7.8, Georgia "
               "-2.9. METROPOLITAN IS SHARPER STILL AND IS THE FIGURE TO "
               "QUOTE: 84.0% on the 517,103 filings whose county resolves to "
               "a metro area, against 70.0% national on the same subset. The "
               "chain is deterministic -- worksite COUNTY through the Census "
               "delineation file to a CBSA, so no city name or postcode is "
               "guessed. The 9% with no metro match keep the state figure "
               "rather than being dropped. By level, Level III is the "
               "striking one: 53.1% below "
               "national but 72.9% below local, so the nominally experienced "
               "rate is under the local median for nearly three in four "
               "filings. STATE, NOT METRO: the application records a worksite "
               "state reliably and a metro only by city and postcode, which "
               "would need a crosswalk introducing its own error. Filings "
               "whose occupation has no published state median are counted "
               "unmatched (60,558) rather than given the national figure. "
               "What was PROMISED, not paid; filing low is lawful."),
    ),
    Dataset(
        key="occupational_wages",
        script="build_occupational_wages",
        source="BLS Occupational Employment and Wage Statistics, national files 2019-2024",
        source_url="https://www.bls.gov/oes/tables.htm",
        consumes=("data/bls_oes/",),
        produces=("site/data/occupational_wages.json",),
        summary=("Annual wage percentiles by detailed occupation -- the "
                 "denominator that prices the H-1B wage levels in dollars."),
        cadence="annual, with the OEWS release",
        notes=("SAYS NOTHING ABOUT VISAS ON ITS OWN. It is the wage "
               "distribution for everyone in an occupation and exists to give "
               "lca_wage_levels a denominator. OEWS suppresses cells as '*' "
               "and tops wages out at $239,200 as '#'; both are stored null "
               "rather than guessed, so a high-wage occupation can have a "
               "missing p90. Detailed six-digit SOC rows only, so rows do not "
               "sum to national employment. RETRIEVAL: bls.gov returns 403 to "
               "a user agent containing a parenthetical, which made this look "
               "unreachable across two sessions; a plain token works and the "
               "bulk files need no key. The public API accepts OEWS series "
               "IDs but returns no data for them, so the bulk files are the "
               "route."),
    ),
    Dataset(
        key="tuition_and_appropriations",
        script="build_tuition_and_appropriations",
        source="NCES IPEDS Institutional Characteristics, SHEEO SHEF, and BLS CPI-U",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        consumes=("data/ipeds_tuition/", "data/shef/SHEEO_SHEF_FY24_Report_Data.xlsx",
                  "data/bls_cpi/", "data/ipeds/hd2024.csv"),
        produces=("site/data/tuition_and_appropriations.json",),
        summary=("Published in-state tuition at public institutions beside "
                 "state appropriations per FTE, 2000-2023, in constant "
                 "dollars -- what students were charged as states changed "
                 "what they put in."),
        cadence="annual, with IPEDS and SHEF",
        notes=("The substitution, at institution and state level and long "
               "enough to see the whole arc. WASHINGTON IS THE CLEAREST CASE "
               "and validates the build against a known policy event: "
               "University of Washington in-state undergraduate tuition and "
               "fees rose 70.7% in real terms between 2008 and 2012 while "
               "state appropriations per FTE fell 35.8%, and both reversed "
               "after the 2015 College Affordability Program cut resident "
               "tuition. In 2008 the state put in more than students paid "
               "($10,378 against $9,910); by 2012 students paid $16,919 and "
               "the state $6,659. THE BASELINE MATTERS ELSEWHERE: the median "
               "state fell 11.1% from 2008 to 2010, so any series starting in "
               "2010 opens at a trough -- which qualifies "
               "state_funding_and_enrolment. THE PERIOD DECIDES THE STORY: "
               "the substitution is a 2008-2012 event, and across 2011-2023 "
               "it runs the OTHER WAY -- median appropriations per FTE +11.2% "
               "real, median in-state sticker +2.5%, median NET PRICE -6.6% "
               "with 35 of 51 states down. Always give the window. Net price "
               "(IPEDS SFA, 1,857 institutions, 2011-2023) is the better "
               "measure of what is actually paid but is a different "
               "population and basis from the sticker: first-time full-time "
               "undergraduates on aid, cost of attendance including living "
               "costs, minus grants. Out-of-state rates are carried too -- "
               "Washington charges 3.3x its in-state rate, which is the "
               "differential that makes a non-resident valuable. TUITION IS A "
               "PUBLISHED RATE, the "
               "sticker before discount, waiver or aid, so it is what a "
               "student is quoted and not what the average student pays. Two "
               "series moving apart is a PATTERN, NOT A DEMONSTRATED CAUSE: "
               "legislatures set one and boards the other. Tuition is "
               "deflated by CPI-U from the BLS API; appropriations by SHEEO's "
               "HECA index, which DIVIDES. Public institutions only."),
    ),
    Dataset(
        key="tuition_dependence",
        script="build_tuition_dependence",
        source="NCES IPEDS Finance FY2023-24, and NSF NCSES GSS 2024",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        consumes=("data/ipeds_finance/f2324_f1a.csv",
                  "data/ipeds_finance/f2324_f2.csv",
                  "site/data/gss_institution_ranking.json"),
        produces=("site/data/tuition_dependence.json",),
        summary=("Tuition as a share of institutional revenue against the "
                 "foreign share of graduate enrolment, public and private "
                 "reported separately."),
        cadence="annual, with IPEDS Finance",
        notes=("THE ANSWER SPLITS BY SECTOR AND SHOULD BE QUOTED THAT WAY. "
               "Among 389 PUBLIC institutions the more tuition-dependent half "
               "runs a higher foreign graduate share (50.4% against 40.7%); "
               "among 234 PRIVATE institutions it runs LOWER (40.9% against "
               "50.2%). The likely reason is composition -- highly "
               "tuition-dependent privates are small teaching colleges, while "
               "research privates look un-dependent because endowment and "
               "grants are large -- so neither half supports a causal read "
               "and the opposite signs are themselves the argument against "
               "one. PUBLIC AND PRIVATE ARE NEVER POOLED: GASB and FASB "
               "forms, non-interchangeable line items, public tuition net of "
               "discounts and the private total including investment return. "
               "TUITION IS FROM EVERY STUDENT, not from foreign students -- "
               "IPEDS does not report revenue by citizenship. Shares are "
               "pooled from raw counts; weighting percentages and scaling by "
               "100 again produced shares above 4,000%."),
    ),
    Dataset(
        key="lca_wage_levels",
        script="build_lca_wage_levels",
        source="US DOL Office of Foreign Labor Certification, H-1B LCA disclosure data",
        source_url="https://www.dol.gov/agencies/eta/foreign-labor/performance",
        consumes=("data/h1b/lca_archive_manifest.json",),
        archived_at="s3://phd-demographics-raw-data/data/h1b/lca/",
        produces=("site/data/lca_wage_levels.json",),
        summary=("Prevailing-wage level promised on certified H-1B filings, by "
                 "employer, FY2019 and FY2023 -- what was promised, beside "
                 "what enforcement later found."),
        cadence="quarterly, with OFLC disclosure releases",
        notes=("64.6% of certified H-1B filings name Level I or II, the bottom "
               "two of four. Among the largest filers TCS is 86.2%, Infosys "
               "71.2%, Amazon 70.6%. THIS IS WHAT WAS PROMISED, not paid, and "
               "filing at a low level is LAWFUL -- it is the cheapest legal "
               "way to fill a role, not a violation. THE ENFORCEMENT CROSSING "
               "IS INCONCLUSIVE: only six employers match, because the "
               "published enforcement extract carries only its largest cases, "
               "so absence from it is not evidence of no findings and six "
               "cases cannot support a correlation. Enforcement is also not "
               "random -- large employers and staffing firms are investigated "
               "more and both skew low-level. THREE SCHEMA CHANGES bite here: "
               "the column is PW_WAGE_LEVEL_1 through FY2019 and "
               "PW_WAGE_LEVEL after; values are 'Level II' then bare 'II'; "
               "and VISA_CLASS must be matched EXACTLY because 'H-1B1 Chile' "
               "contains 'H-1B'. Each one silently zeroed a year before it "
               "was caught. The 4.3 GB archive is processed one file at a "
               "time against 5 GB of free disk."),
    ),
    Dataset(
        key="h1b_enforcement",
        script="build_h1b_enforcement",
        source="US DOL Wage and Hour Division enforcement database (WHISARD)",
        source_url="https://enforcedata.dol.gov/views/data_catalogs.php",
        consumes=("data/WHD_enforcement.zip",),
        produces=("site/data/h1b_enforcement.json",),
        summary=("H-1B wage violations found by the Department of Labor, "
                 "2000-2026: cases, back wages, employees and employers."),
        cadence="periodic, with DOL enforcement releases",
        notes=("The ONLY source in this project that reaches the H-1B "
               "population itself. Every survey used elsewhere covers "
               "doctorate holders; most H-1B workers hold a bachelor's or "
               "master's and work in industry, and this records findings "
               "against their employers. 2,887 cases, $123.4m back wages "
               "agreed, 13,640 employees, $9,049 each. Enforcement INTENSITY "
               "fell elevenfold: 26.2 cases per 10,000 H-1B issuances in 2009 "
               "against 2.37 in 2024. IT IS A FLOOR, NEVER A RATE -- these "
               "are violations FOUND, which requires a complaint or an "
               "investigation, so a low figure is NOT evidence of compliance "
               "and is equally consistent with nobody complaining, which is "
               "what employer dependence would predict. The data cannot "
               "settle which, and saying so is part of using it. BACK WAGES "
               "ARE 'AGREED TO PAY', a finding, not money proven collected. "
               "Dated by FINDINGS_END_DATE though an investigation may cover "
               "earlier years. Employers are grouped on the filed legal name "
               "with case and whitespace normalised ONLY -- nothing is "
               "fuzzy-matched, so two spellings stay two rows and a company "
               "total is a floor."),
    ),
    Dataset(
        key="visa_bulletin",
        script="build_visa_bulletin",
        source="US Department of State, Visa Bulletin historical final action dates",
        source_url="https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html",
        consumes=("data/state_visas/bulletin/",),
        produces=("site/data/visa_bulletin.json",),
        summary=("Employment-based final action dates FY1992-2023 for India, "
                 "China, the Philippines and all other countries -- the "
                 "employer-dependence argument in years."),
        cadence="monthly, with the Visa Bulletin",
        notes=("Puts a number on the dependence every other leverage figure "
               "only describes. INDIA EB-2 IS 12.7 YEARS AND EB-3 14.7 at the "
               "last dated month, against 1.2 and 3.3 for all other "
               "countries. It is not static: India EB-2 was CURRENT through "
               "2004, 3.4 years by 2007, 5.2 by 2013 and over ten by 2016. "
               "WAIT_YEARS IS THE WAIT ALREADY SERVED by the person reaching "
               "the front, NOT a forecast for a new filer -- where the queue "
               "grows, the eventual wait is longer than this shows. 'C' means "
               "CURRENT and 'U' means UNAVAILABLE, a wait of unknown length "
               "and NOT zero; both are stored as a status with a null wait so "
               "they cannot be averaged in. A single month can also read C "
               "when unused numbers spill over, as September 2022 does, so "
               "read the run rather than one month. Only the 1st, 2nd and 3rd "
               "preference columns are parsed because their order is stable "
               "across every era of the chart. Retrieved by hand: "
               "travel.state.gov refuses automated requests from this "
               "project, including a headless browser."),
    ),
    Dataset(
        key="nativity_labour",
        script="build_nativity_labour",
        source="BLS Current Population Survey, foreign-born workers news release",
        source_url="https://www.bls.gov/news.release/forbrn.nr0.htm",
        consumes=("data/bls_nativity/",
                  "data/bls_nativity/archives/"),
        produces=("site/data/nativity_labour.json",),
        summary=("Employment by occupation and median weekly earnings, split "
                 "by nativity -- the domestic side of the ledger."),
        cadence="annual, with the BLS foreign-born release",
        notes=("Occupation by nativity is a series from 2007, parsed from "
               "Table 4 of nineteen archived releases: the foreign-born share of "
               "computer and mathematical occupations rose from 21.6% to 26.8% "
               "over 2011-2019, within one occupational classification. It "
               "breaks at 2011 and 2020 and the 2025 annual figure is an "
               "11-month average, so the rise to 29.0% in 2025 crosses two "
               "comparability breaks and is not a one-year trend. "
               "Closes the structural gap the audit named: every other "
               "dataset here measured the foreign population and none "
               "measured the workers already present, which made the "
               "displacement argument one-sided. Foreign-born workers are "
               "19.2% of all employment but 29.0% of computer and "
               "mathematical occupations, 21.9% of life, physical and social "
               "science, 21.2% of architecture and engineering. Median usual "
               "weekly earnings $1,059 against $1,236, or 85.7%. NATIVITY IS "
               "NOT VISA STATUS: 'foreign born' pools naturalised citizens, "
               "permanent residents and temporary-visa holders; 'native born' "
               "includes anyone born here whatever their parentage. Far "
               "broader than the visa categories used elsewhere and NOT the "
               "same population. THE EARNINGS GAP IS NOT LIKE-FOR-LIKE -- age, "
               "education, occupation, region and language are uncontrolled, "
               "so it describes two populations and not what an employer pays "
               "for the same work. TWO PARSING TRAPS: the native-born total is "
               "the FOURTH column, not the second, and every occupation row is "
               "a PERCENT OF ITS OWN GROUP rather than a headcount -- taken "
               "literally, computer occupations read 61.4% foreign-born "
               "instead of 29.0%."),
    ),
    Dataset(
        key="humanitarian_admissions",
        script="build_humanitarian_admissions",
        source="DHS Yearbook of Immigration Statistics, refugee and asylee tables",
        source_url="https://ohss.dhs.gov/topics/immigration/yearbook",
        consumes=("data/dhs_yearbook/refugees_fy2023.xlsx",
                  "data/dhs_yearbook/asylees_fy2023.xlsx"),
        produces=("site/data/humanitarian_admissions.json",),
        summary=("Refugee arrivals 1980-2023 and asylum grants by "
                 "nationality -- the humanitarian route, for scale against "
                 "the study and work routes."),
        cadence="annual, with the DHS Yearbook",
        notes=("Held so the employment and study figures can be read against "
               "the whole rather than in isolation. REFUGEE ADMISSION IS A "
               "POLICY CEILING set each year by presidential determination, "
               "so the series tracks decisions in Washington and a fall must "
               "NOT be read as fewer people seeking admission: 207,120 in "
               "1980, 11,450 at the low, 60,050 in 2023. REFUGEES AND ASYLEES "
               "ARE COUNTED AT DIFFERENT MOMENTS and are never summed -- a "
               "refugee is admitted from abroad after approval, an asylee is "
               "already here when the grant is made. Different law, different "
               "caps, different process from everything else in this "
               "project."),
    ),
    Dataset(
        key="origin_vs_residence",
        script="build_origin_vs_residence",
        source="DHS Yearbook of Immigration Statistics, tables 2 and 3",
        source_url="https://ohss.dhs.gov/topics/immigration/yearbook",
        consumes=("data/dhs_yearbook/lpr_fy2023.xlsx",),
        produces=("site/data/origin_vs_residence.json",),
        summary=("Permanent residents by country of last residence against "
                 "country of birth -- which countries are waypoints rather "
                 "than sources."),
        cadence="annual, with the DHS Yearbook",
        notes=("CANADA IS A MEASURABLE WAYPOINT: 18,590 people obtained US "
               "permanent residence from Canada in FY2023 against 11,870 born "
               "there, so 36.1% of arrivals from Canada were born elsewhere, "
               "and the share has sat near a third for a decade. The UAE runs "
               "61.7%. On the other side Mexico, the Philippines and India "
               "show more births than residences. THE TWO TABLES ARE SEPARATE "
               "TOTALS, NOT A CROSS-TABULATION: no individual is traced, so a "
               "surplus in one country CANNOT BE ATTRIBUTED to any particular "
               "origin however well the deficits appear to match. IT DOES NOT "
               "REACH TEMPORARY VISAS AT ALL -- TN, H-1B, F-1 and L-1 are "
               "published by CITIZENSHIP ONLY and country of birth is not "
               "published for any nonimmigrant classification, so a "
               "naturalised citizen cannot be distinguished from a "
               "native-born one anywhere in the visa data. THE COMPOSITION "
               "REFINES THE HEADLINE AND SHOULD BE QUOTED WITH IT: Canada's "
               "surplus is 55% immediate relatives of US citizens and 23% "
               "family-sponsored against only 17% employment-based, and ZERO "
               "in refugees and asylees. It is predominantly a family route, "
               "not a skilled-worker one and not a humanitarian one, which "
               "the total alone cannot show. Countries below "
               "3,000 are excluded as noise."),
    ),
    Dataset(
        key="nonimmigrant_admissions",
        script="build_nonimmigrant_admissions",
        source="DHS Yearbook of Immigration Statistics, nonimmigrant tables",
        source_url="https://ohss.dhs.gov/topics/immigration/yearbook",
        consumes=("data/dhs_yearbook/nonimmigrants_fy2023.xlsx",),
        produces=("site/data/nonimmigrant_admissions.json",),
        summary=("Admissions by class of admission and year, FY2014-2023, "
                 "with destination state -- the closest substitute for the "
                 "L-1 and O-1 employer data that is not published."),
        cadence="annual, with the DHS Yearbook",
        notes=("Built because L-1 AND O-1 HAVE NO EMPLOYER-LEVEL DATA AT ALL: "
               "neither requires a labour condition application, so DOL never "
               "sees them, and USCIS publishes an employer hub for H-1B, H-2A "
               "and H-2B but not for these. This is a substitute for that "
               "question and NOT AN ANSWER TO IT. AN ADMISSION IS AN ENTRY AT "
               "A PORT -- one worker travelling four times is four admissions "
               "-- so these figures far exceed the issuance series and the "
               "two MUST NOT BE MIXED: issuances count documents, admissions "
               "count arrivals, neither counts workers. L-1 admissions FELL "
               "15% between 2014 and 2023 (591,730 to 503,490) while H-1B "
               "rose 48% and TN 69%. Destination state is what the traveller "
               "declared on arrival, usually the office being joined; L-1 "
               "concentrates in Texas, California, New York and Michigan, O-1 "
               "in New York and California. It is a location, not an "
               "employer. DHS rounds every figure."),
    ),
    Dataset(
        key="employer_profiles",
        script="build_employer_profiles",
        source="Joined from h1b_approvals, lca_wage_levels and h1b_enforcement",
        source_url="https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub",
        consumes=("site/data/h1b_approvals.json",
                  "site/data/lca_wage_levels.json",
                  "site/data/h1b_enforcement.json"),
        produces=("site/data/employer_profiles.json",),
        summary=("One row per employer: H-1B petitions requested, granted and "
                 "denied, the wage level promised, and any enforcement "
                 "findings."),
        cadence="rebuild when any input changes",
        notes=("The three H-1B files joined for the first time. Cognizant "
               "50,940 initial approvals against 43,264 certified LCAs at "
               "51% Level I or II; TCS 43,756 and 86%; Wipro 28,460 and 90%; "
               "Tech Mahindra 100%. NAMES ARE THE WHOLE DIFFICULTY: the "
               "agencies share no identifier and each employer files under "
               "several spellings. Normalisation covers case, punctuation, "
               "legal suffixes and a SHORT EXPLICIT ABBREVIATION TABLE "
               "(solns->solutions, svcs->services, tech->technology); nothing "
               "is fuzzy-matched and every row lists the spellings it "
               "absorbed so the join can be audited. 'Infosys' and 'Infosys "
               "Technologies' stay separate because merging them would need a "
               "rule that also merges unrelated firms. TOTALS ARE FLOORS. "
               "ABSENCE IS NULL, NOT ZERO -- the inputs are top-N extracts, "
               "so a missing value means 'not in that list', which absent_from "
               "records. NO EQUIVALENT EXISTS FOR L-1 OR O-1: neither needs a "
               "labour condition application and USCIS publishes no employer "
               "hub for either, so the question cannot be asked of them."),
    ),
    Dataset(
        key="university_foreign_students",
        script="build_university_foreign_students",
        source="NCES IPEDS Fall Enrolment and DHS SEVP top-campus tables",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        consumes=("data/ipeds_enrollment/", "data/ipeds/hd2024.csv",
                  "data/sevp/2024_top100_schools_stemopt.pdf"),
        produces=("site/data/university_foreign_students.json",),
        summary=("Non-resident enrolment by institution, with SEVP's top "
                 "campuses by STEM OPT authorisation beside it."),
        cadence="annual, with IPEDS and SEVP",
        notes=("F-1 ISSUANCE BY UNIVERSITY IS NOT PUBLISHED -- State reports "
               "visas by consulate and nationality, never by school, and SEVP "
               "publishes school-level figures only for OPT. This answers who "
               "ENROLS foreign students, which is a different question. NYU "
               "leads on non-resident headcount (19,373), then Columbia, USC "
               "and Georgia Tech. Nationally 17.1% of graduate and 2.8% of "
               "undergraduate enrolment. THREE MEASURES, THREE POPULATIONS: "
               "IPEDS counts everyone enrolled in a fall term at every level "
               "and field; SEVP counts graduates already working on STEM OPT; "
               "the GSS ranking covers S&E&H graduate students only. They "
               "rank institutions differently and are reported side by side, "
               "never blended. Ranked by COUNT because share rankings here "
               "are dominated by tiny institutions. Non-resident is a visa "
               "category, so permanent residents count as domestic and every "
               "share is a floor."),
    ),
    Dataset(
        key="expansion_phases",
        script="build_expansion_phases",
        source="Derived from graduate_balance and visa_issuances",
        source_url="",
        consumes=("site/data/graduate_balance.json",
                  "site/data/visa_issuances.json"),
        produces=("site/data/expansion_phases.json",),
        summary=("Non-resident graduate degrees and visa issuances on one "
                 "time axis, in named windows -- when each part of the "
                 "pipeline expanded, and in what order."),
        cadence="rebuild when either input changes",
        notes=("THE WINDOWS: post-9/11 contraction 1998-2003 (F-1 falls to "
               "215,695); the long student expansion 2003-2015 (F-1 +199% to "
               "an all-time 644,233); the master's expansion 2007-2017 "
               "(non-resident master's +216%, share 25.7% to 43.2%), starting "
               "about three years into the student expansion; 2015-2019 F-1 "
               "falls 44% while degrees hold; consular closure 2019-2021 "
               "(H-1B -67%); and the second surge 2022-2025, master's +139% "
               "with H-1B peaking at 265,777 in 2023. PHASE BOUNDARIES ARE A "
               "JUDGMENT and each carries its reason so a reader can move "
               "them. THE LAG IS TESTED ON DIFFERENCED SERIES with 2020-21 "
               "excluded: it peaks at three years (r=0.56, n=19) and is near "
               "zero at lag zero, the shape a mechanical lag gives rather "
               "than a shared trend -- but it is still a correlation on "
               "nineteen observations, consistent with the mechanics of a "
               "two-year degree rather than proof. A window ending below its "
               "own peak reports both, because first-to-last read +7% for a "
               "window containing the H-1B record."),
    ),
    Dataset(
        key="visa_issuances",
        script="build_visa_issuances",
        source="US Department of State, Nonimmigrant Visa Detail Tables, FY1997-2024",
        source_url="https://travel.state.gov/content/travel/en/legal/visa-law0/visa-statistics/nonimmigrant-visa-statistics.html",
        consumes=("data/state_visas/1997-2024_NIVDetailTable.xlsx",),
        produces=("site/data/visa_issuances.json",),
        summary=("Nonimmigrant visa issuances by class and nationality, "
                 "1997-2024 -- the entry point, counted at the consulate."),
        cadence="annual, with the State Department detail tables",
        notes=("The only series here measured OUTSIDE the country, and the "
               "most current: State publishes through the last fiscal year "
               "while IPEDS and the SED run one to two years behind. H-1B "
               "issuances 80,547 to 219,659; O-1 3,345 to 19,457 (+482%), "
               "which is the uncapped route. INDIA IS 68.6% OF H-1B "
               "ISSUANCES and 21.5% of F-1. AN ISSUANCE IS NOT A PERSON AND "
               "NOT AN ARRIVAL -- one person may be issued several visas over "
               "the years, and a visa is permission to travel and seek "
               "admission, not admission itself. Class codes are hyphenated "
               "in the early sheets and not in the later ones; without "
               "normalising them every series silently starts around 2010. "
               "OVERREPRESENTATION IS AT THE WORK STAGE, NOT THE STUDENT "
               "STAGE: India and China take nearly identical F-1 shares "
               "(21.5% and 20.6%, both about 1.2x their share of world "
               "population), but India is 68.6% of H-1B issuances (3.8x) "
               "while China is 14.4% (0.8x, under its population share). The "
               "population denominator is one defensible choice among "
               "several and is labelled as such. THE MECHANISM: India issues "
               "1.75 H-1B visas per F-1 visa in 2024 -- more people arrive on "
               "the work visa than on the student visa, which the US student "
               "pipeline cannot account for -- against 0.38 for China and "
               "0.24-0.37 for everyone else. CONFOUND TO RAISE FIRST: visas "
               "are re-stamped for travel, so the H-1B numerator counts some "
               "workers more than once and the ratio is not a conversion "
               "rate. "
               "Retrieved manually: travel.state.gov returns 403 to automated "
               "requests including a headless browser."),
    ),
    Dataset(
        key="summary",
        script="build_summary",
        source="Derived from this project's own published datasets",
        source_url=None,
        consumes=("site/data/graduate_balance.json",
                  "site/data/gss_citizenship_trend.json",
                  "site/data/institution_profiles.json",
                  "site/data/enrolment_and_funding.json",
                  "site/data/local_wage_comparison.json",
                  "site/data/lpr_adjustments.json",
                  "site/data/nativity_labour.json"),
        produces=("site/data/summary.json",),
        summary=("The headline figure from every finding, in one file, each "
                 "with the dataset and path it was read from and the limit on "
                 "how it may be read."),
        cadence="rebuild whenever any source dataset is rebuilt",
        notes=("14 figures. Every value is pulled from a declared path at "
               "build time and never typed, so this file cannot preserve a "
               "number the data no longer says; a path that stops resolving is "
               "reported as missing and --check exits non-zero. Every entry "
               "carries a required 'limit' field, checked at build time, "
               "because a summary is where caveats go to die -- the number "
               "survives the trip and the qualification does not. Holds one "
               "number per finding and nothing conditional: anything by year, "
               "state, institution or occupation needs the dataset named on "
               "the figure."),
    ),
    Dataset(
        key="visa_schools",
        script="build_visa_schools",
        source=("NCES IPEDS Fall Enrollment 2022-2024, Institutional Characteristics "
                "directory 2024 and Student Financial Aid 2022-23; IRS Form 990 "
                "e-file returns"),
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        consumes=("data/ipeds/HD2024.csv",
                  "data/ipeds/enrollment/EF2022A.zip",
                  "data/ipeds/enrollment/EF2023A.zip",
                  "data/ipeds/enrollment/EF2024A.zip",
                  "data/ipeds/sfa/SFA2223.zip",
                  "data/irs990/recruitment_990.json"),
        produces=("site/data/visa_schools.json",),
        summary=("Every US institution with 100+ graduate students where "
                 "non-residents are half or more of them: 57 in fall 2024, up "
                 "from 43 in 2022, with their federal student aid and the "
                 "recruitment payments the nonprofits report to the IRS."),
        cadence="annual, with IPEDS Fall Enrolment and the IRS 990 release",
        notes=("THE FEDERAL AID IS UNDERGRADUATE. IPEDS Student Financial Aid "
               "reports Pell and federal loans for undergraduates only, so a "
               "graduate-heavy school's federal money is UNDERSTATED here; "
               "graduate borrowing lives in the Education Department's Title IV "
               "programme volume reports, which this does not yet read. Foreign "
               "students cannot receive Pell or federal loans: these dollars are "
               "the school's, awarded to its eligible students and paid to the "
               "institution against tuition. Recruitment payments are two "
               "different bases that must never be summed -- named contractors "
               "from Form 990 Part VII Section B, and Part IX expense lines "
               "naming recruitment, which can contain the same money. A return "
               "filed under a parent's EIN (Trine's regional record, the two "
               "Northeastern entries, Longy under Bard) is flagged rather than "
               "attributed to the campus."),
    ),
    Dataset(
        key="visa_substitution",
        script="build_visa_substitution",
        source=("US Department of State Nonimmigrant Visa Detail Tables; DHS SEVP "
                "OPT/STEM OPT/CPT; USCIS H-1B Employer Data Hub; Federal Register"),
        source_url="https://travel.state.gov/content/travel/en/legal/visa-law0/visa-statistics/nonimmigrant-visa-statistics.html",
        consumes=("site/data/visa_issuances.json",
                  "site/data/opt_national.json",
                  "site/data/h1b_approvals.json",
                  "data/policy/visa_policy_events.json"),
        produces=("site/data/visa_substitution.json",),
        summary=("Visa issuance by class, student work authorisations and the "
                 "H-1B denial rate on one timeline, 2007-2024, with the dated "
                 "federal actions that restricted or expanded each."),
        cadence="annual",
        notes=("TIMING, NOT CAUSE. Visa issuance and USCIS decisions are FISCAL "
               "years; OPT, STEM OPT and CPT are CALENDAR years, three months "
               "apart. FY2020-21 issuance fell in every class while consulates "
               "were shut for the pandemic, so the June 2020 entry suspension is "
               "not the only explanation for that drop. TN is open only to "
               "Canadians and Mexicans and E-3 only to Australians, so neither "
               "is a route for the graduates this site tracks -- TN is carried "
               "in the data and kept out of the chart for that reason. An "
               "issuance is not a person: visas are re-stamped for travel."),
    ),
    Dataset(
        key="institution_profiles",
        script="build_institution_profiles",
        source=("IPEDS Completions, Fall Enrollment, Institutional "
                "Characteristics and Directory; NSF HERD FY2024; NSF Federal "
                "Support Survey FY2023; NSF GSS 2024"),
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        consumes=("data/ipeds/",
                  "data/ipeds/enrollment/EF2023A.zip",
                  "data/ipeds_tuition/ic2023_ay.csv",
                  "data/herd/herd_fy2024_table14.xlsx",
                  "data/federal_support/nsf25339-tab017.xlsx",
                  "pipeline/ncses_crosswalk.json",
                  "site/data/gss_institution_ranking.json",
                  "site/data/tuition_dependence.json"),
        produces=("site/data/institution_profiles.json",),
        summary=("One row per institution on a single UNITID key -- core-STEM "
                 "master's and doctorates with their non-resident shares, "
                 "graduate enrolment, federal R&D and obligations, tuition -- "
                 "with national rankings on each measure and a rollup to "
                 "states."),
        cadence="annual, with IPEDS completions",
        notes=("2,290 institutions, 1,021 of them with federal money "
               "attached. Joins the two NCSES surveys, which publish "
               "institution names and no identifier, onto UNITID by exact "
               "normalised match plus a hand-verified crosswalk; 1.7% of "
               "HERD dollars and 3.1% of Federal Support dollars stay "
               "unmatched, and every one of those is a research institute "
               "with no IPEDS unit (Scripps, Woods Hole, Cold Spring "
               "Harbor). Subset matching was tried and rejected: it maps "
               "Florida A&M onto the University of Florida. "
               "federal_per_doctorate reproduces the basis published on the "
               "funding page -- Missouri S&T comes out at $107,334 either "
               "way -- and is an intensity ratio, not a price: the national "
               "median over 262 institutions is $821,054. The top of that "
               "ranking is medical schools, which is why every row also "
               "carries doctorates across all fields and professional "
               "doctorates, so a partial denominator is visible rather than "
               "asserted."),
    ),
    Dataset(
        key="gss_institution_ranking",
        script="build_gss_institution_ranking",
        source="NSF NCSES, Survey of Graduate Students and Postdoctorates, 2024",
        source_url="https://ncses.nsf.gov/surveys/graduate-students-postdoctorates-s-e/",
        consumes=("data/nsf_gss/graduate_students_postdocs_2024.zip",),
        produces=("site/data/gss_institution_ranking.json",),
        summary=("Full-time S&E&H graduate enrolment by institution and the "
                 "temporary-visa share of it, master's and doctoral, ranked."),
        cadence="annual, with GSS",
        notes=("Nationally 46.8% of full-time master's and 44.5% of doctoral "
               "S&E&H enrolment is temporary-visa. The master's ranking is "
               "the striking one -- several institutions above 90%, "
               "Harrisburg University 96.4% and Central Missouri 92.7% on "
               "2,862 students. THE GSS REPORTS ONE ROW PER ORGANISATIONAL "
               "UNIT, not per institution, so rows must be summed to the "
               "institution or a large university is ranked as several small "
               "departments. Uses the Race sheet, where 'forgn' is the "
               "STUDENT'S CITIZENSHIP; in the Support sheet the same token "
               "means a foreign SOURCE OF FUNDS. Share rankings apply an "
               "enrolment floor because small programmes give meaningless "
               "percentages. ENROLMENTS, NOT DEGREES, on an S&E&H field "
               "basis: not comparable with the IPEDS core-STEM degree "
               "rankings elsewhere. Single year."),
    ),
    Dataset(
        key="gss_citizenship_trend",
        script="build_gss_citizenship_trend",
        source="NSF NCSES, Survey of Graduate Students and Postdoctorates, table 1-7",
        source_url="https://ncses.nsf.gov/surveys/graduate-students-postdoctorates-s-e/",
        consumes=("data/nsf_gss/tables/nsf26307-tab001-007.xlsx",),
        produces=("site/data/gss_citizenship_trend.json",),
        summary=("Forty years of science, engineering and health graduate and "
                 "postdoctoral enrolment by citizenship, 1980-2024 -- the "
                 "long STEM-specific view."),
        cadence="annual, with GSS",
        notes=("The best enrolment series in the project: STEM-restricted and "
               "back to 1980, where graduate_enrollment is all-fields and "
               "starts in 2010. Graduate students 13.7% to 38.5% temporary "
               "visa (peak 39.4% in 2023); POSTDOCS 35.4% to 58.3%, a clear "
               "majority. Citizen counts rose too -- graduate +59%, postdoc "
               "+145% -- so this is a share shift, not a domestic collapse. "
               "COUNTS ARE STUDENTS ENROLLED in S&E&H units; graduate_balance "
               "counts DEGREES CONFERRED in eight core-STEM CIP families from "
               "IPEDS. Different population, field definition and collection: "
               "they corroborate in direction and their LEVELS ARE NOT "
               "INTERCHANGEABLE. Permanent residents are grouped with "
               "citizens throughout. The builder checks the published parts "
               "and percentages against the published totals."),
    ),
    Dataset(
        key="graduate_enrollment",
        script="build_graduate_enrollment",
        source="NCES IPEDS Fall Enrolment (EF), 2010-2023",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        consumes=("data/ipeds_enrollment/",),
        produces=("site/data/graduate_enrollment.json",),
        summary=("Non-resident share of graduate enrolment, all fields, "
                 "2010-2023 -- an independent read on the degree series."),
        cadence="annual, with IPEDS Fall Enrolment",
        notes=("ALL FIELDS, NOT CORE STEM. IPEDS publishes enrolment by "
               "institution and level but not by field, so these figures are "
               "NOT comparable with the core-STEM degree counts in "
               "graduate_balance and must never be quoted beside them as if "
               "they were. Enrolment also runs about two years behind "
               "completions, so it CORROBORATES the degree series rather "
               "than leading it -- it is not the early-warning indicator it "
               "looks like. Full-time graduate 14.5% to 23.1%, all graduate "
               "10.4% to 17.1%. EFALEVEL 12 is all graduate, 32 full-time "
               "and 52 part-time; 22 and 42 are the UNDERGRADUATE codes and "
               "using them puts twelve million undergraduates into the "
               "series, which the full-time-plus-part-time reconciliation "
               "catches."),
    ),
    Dataset(
        key="graduate_balance",
        script="build_graduate_balance",
        source="NCES IPEDS Completions, 1995-2025",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        consumes=("data/ipeds/",),
        produces=("site/data/graduate_balance.json",),
        summary=("Non-resident share of core-STEM degrees at master's level, "
                 "doctorate level and the two combined, across thirty years -- "
                 "where in graduate education the balance actually shifted."),
        cadence="annual, with IPEDS Completions",
        notes=("THE SHIFT IS AT MASTER'S LEVEL, not the doctorate: 24.4% to "
               "45.9% between 1995 and 2025 (+21.5 points) against 32.7% to "
               "37.5% (+4.8 points) for the doctorate, which peaked at 40.1% "
               "in 2021 and has fallen since. Combined graduate 26.4% to "
               "44.8%. Domestic counts rose at both levels throughout -- "
               "master's +189%, doctorate +74% -- so this is a change in "
               "share, not a domestic decline. Handles two schema breaks: "
               "residency columns renamed in 2008 (legacy CRACE01/02 over "
               "CRACE15/16), and doctorate award level 9 to 17 in 2010 with "
               "institutions migrating across 2008-09, which must SUM both "
               "codings. Column names are lowercase before 2008. Validated "
               "against long_series: the doctorate line reproduces that "
               "independent index within 0.3% in every overlapping year. NRA "
               "IS A VISA CATEGORY, NOT AN IMMIGRATION OUTCOME -- permanent "
               "residents are counted under their race and appear as domestic "
               "here; see doctorate_outcomes for where visa holders end up. "
               "COUNTS ARE DEGREES, NOT PEOPLE."),
    ),
    Dataset(
        key="support_trend",
        script="build_support_trend",
        source="NSF NCSES, Survey of Earned Doctorates, primary-source-of-support table, 2018-2024 releases",
        source_url="https://ncses.nsf.gov/surveys/earned-doctorates/",
        consumes=("data/sed/nsf20301-tab035.xlsx",
                  "data/sed/nsf21308-tab035.xlsx",
                  "data/sed/nsf22300-tab035.xlsx",
                  "data/sed/nsf23300-tab004-001.xlsx",
                  "data/sed/nsf24300-tab004-001.xlsx",
                  "data/sed/nsf24336-tab004-001.xlsx",
                  "data/sed/nsf25349-tab004-001.xlsx"),
        produces=("site/data/support_trend.json",),
        summary=("Seven years of primary source of doctoral support by "
                 "citizenship, 2018-2024 -- how long the assistantship gap "
                 "has held, and which way it is moving."),
        cadence="annual, with each SED release",
        notes=("Built because one year cannot distinguish a new gap from an "
               "entrenched one. THE GAP IS ENTRENCHED: research assistantships "
               "fund 46-49% of visa holders against 26-29% of citizens in "
               "every one of the seven years, never below 19.3 points. The "
               "visa share rises across the period (46.4% to 48.9%) and the "
               "population grows -- visa holders on an RA up 16.7%, now 47.2% "
               "of everyone on one. The GAP ITSELF is roughly level, because "
               "both shares rise together; report the rising share and the "
               "headcount rather than calling the gap widening. Runs on ALL "
               "FIELDS because NCSES revised the field "
               "taxonomy in the 2023 release, so a science-and-engineering "
               "series would cross a definitional break; the S&E rollup is "
               "carried separately for the four releases that publish it. "
               "Inherits the grad_support caveat: the SED never records which "
               "award paid, so the RA row is a proxy for federal funding, not "
               "a measurement of it. Releases before 2021 publish no separate "
               "reporting base, so reconstructed headcounts for those years "
               "are scaled off all recipients and run a few percent high on "
               "both sides -- which is why headcount is reported as a share."),
    ),
    Dataset(
        key="doctorate_outcomes",
        script="build_doctorate_outcomes",
        source="NSF NCSES, Survey of Doctorate Recipients 2023 public-use file",
        source_url="https://ncses.nsf.gov/surveys/doctorate-recipients/",
        consumes=("data/nsf_workforce/doctorate_recipients_2023.zip",),
        produces=("site/data/doctorate_outcomes.json",),
        summary=("What US-trained doctorate holders earn and where they work, "
                 "by citizenship AT THE DOCTORATE, and what became of those on "
                 "a temporary visa."),
        cadence="biennial, with the SDR",
        notes=("Completes the retention stage: stay rates say people remain, "
               "this says what they do and earn. GROUPS ARE BY STATUS AT THE "
               "DEGREE (CTZN_DRF), not current status. Splitting on current "
               "status counts everyone who naturalised as a citizen, which "
               "leaves the non-citizen group in older cohorts a residue of "
               "those who never did and produced $80,000 gaps that described "
               "selection rather than pay. WEIGHTS ARE NOT OPTIONAL: the SDR "
               "is a stratified sample and WTSURVY is the population weight. "
               "Salary differences are NOT like-for-like -- field, years since "
               "doctorate and sector are uncontrolled, which is why the figures "
               "are also broken out within doctorate cohort."),
    ),
    Dataset(
        key="stay_rates",
        source_url="https://ncses.nsf.gov/pubs/nsf25325",
        script="build_stay_rates",
        source="NCSES NSF 25-325, Table 1",
        consumes=("data/stay_rates/nsf25325_tab001.xlsx",),
        produces=("site/data/stay_rates.json",),
        summary=("Where temporary-visa S&E doctorate recipients actually live "
                 "years after graduating: 73% of the 2017-19 cohort were still "
                 "in the US in 2023."),
        cadence="when NCSES republishes",
        notes=("MEASURED, NOT INTENDED. This project separately holds SED "
               "Table 2-8, which records what recipients SAID they planned to "
               "do before graduating. The two are different quantities and "
               "must not be quoted interchangeably -- an intention is a survey "
               "answer, this is administrative residence. Rows are accepted "
               "only when the US and non-US counts account for the stated "
               "total, so a shifted column is caught rather than published."),
    ),
    Dataset(
        key="stem_earnings",
        source_url="https://collegescorecard.ed.gov/data/",
        script="build_stem_earnings",
        source="U.S. Department of Education, College Scorecard field of study file",
        consumes=("data/scorecard/field_of_study.zip",),
        produces=("site/data/stem_earnings.json",),
        summary=("Median earnings and debt one year after completion, by "
                 "4-digit CIP and credential level -- the only federal source "
                 "that prices a STEM degree by field AND level."),
        cadence="annual, with the Scorecard release",
        notes=("Built to test why domestic doctorate conversion is falling. "
               "NOT A RETURN TO THE DEGREE: each figure is measured one year "
               "after that credential finishes, so a bachelor's cohort is "
               "about 23 and a doctoral cohort about 29, and the bachelor's "
               "holder has six years of earnings the comparison does not "
               "count. DO NOT COMPARE THE POOLED MEDIANS ACROSS LEVELS: "
               "suppression leaves 208 doctoral programmes against 7,121 "
               "bachelor's and they are a different mix of fields, which is "
               "why the pooled doctoral figure falls below the pooled "
               "master's while only 3 of 27 fields do so within the field. "
               "Compare within a field."),
    ),
    Dataset(
        key="domestic_pipeline",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        script="build_domestic_pipeline",
        source="NCES IPEDS Completions",
        consumes=("data/ipeds/",),
        produces=("site/data/domestic_pipeline.json",),
        summary=("Domestic core-STEM completions by level 2011-2025, and the "
                 "rate at which a bachelor's cohort is followed by graduate "
                 "degrees."),
        cadence="annual, with IPEDS",
        notes=("Built to test the claim that America is not producing STEM "
               "graduates. It is not: domestic completions ROSE at every level "
               "-- bachelor's +56%, master's +82%, doctorates +35%. The finding "
               "that survives is about CONVERSION. Domestic bachelor's to "
               "master's rose from 23.9% to 26.6%; bachelor's to doctorate FELL "
               "from 5.4% to 4.7%. The cohort lag (6 years to a doctorate, 2 to "
               "a master's) is a modelling choice, stated in the output, with "
               "raw counts published so another can be applied. IPEDS counts "
               "DEGREES, NOT PEOPLE: this is a ratio between two populations, "
               "not a tracked cohort, and it cannot say whether someone chose "
               "industry, was not admitted, or was not funded."),
    ),
    Dataset(
        key="cap_exempt_directory",
        source_url="https://www.ellis.com/visa-sponsors/cap-exempt",
        script="scrape_cap_exempt_directory",
        source="ellis.com/visa-sponsors/cap-exempt",
        consumes=("data/cap_exempt/pages/",),
        produces=("data/cap_exempt/directory.json",
                  "data/cap_exempt/proxy_comparison.json",
                  "data/cap_exempt/merged_employers.json",
                  "data/cap_exempt/sponsor_ranking.json"),
        summary=("A third-party list of 2,388 employers treated as cap-exempt, "
                 "compared against NAICS 61 in the USCIS Employer Data Hub."),
        cadence="on demand",
        notes=("NOT AUTHORITATIVE. USCIS records cap status on the I-129 and "
               "does not publish it, so every public cap-exempt list is an "
               "inference from employer type. Use this to CHOOSE which "
               "employers to look up and publish USCIS's own figures. The "
               "comparison is the useful part: NAICS codes are self-reported "
               "and often describe something other than the institution -- "
               "Washington University in St Louis files as Manufacturing, the "
               "University of Colorado Denver as Information -- so neither "
               "proxy is a substitute for the unpublished field. Four public "
               "sources were examined and two collected: ellis.com and two "
               "job boards all permit it in robots.txt. myvisajobs.com names "
               "ClaudeBot in a Disallow rule and h1bgrader.com returns 403 "
               "from its edge protection even to a real browser, so neither "
               "is included. The job boards list OPENINGS rather than "
               "employers and add only about fifteen institutions after "
               "filtering job titles and section headings out."),
    ),
    Dataset(
        key="build_fellowship_projects",
        source_url="https://hub.buildfellowship.com/projects",
        script="scrape_buildfellowship_hub",
        source="hub.buildfellowship.com/projects",
        consumes=("data/buildfellowship/projects/",),
        produces=("data/buildfellowship/projects.json",
                  "data/buildfellowship/project_links.json"),
        summary=("All 243 published Build Fellowship projects: title, area, "
                 "level, schedule, application timeline, and the fellow "
                 "leading each with their role, bio and employer."),
        cadence="on demand; the cache makes a re-run cheap",
        notes=("robots.txt disallows /admin and /survey; /projects is "
               "permitted. The pages look server-rendered -- curl returns the "
               "text -- but it sits in Next.js flight pushes rather than "
               "markup, and long strings are stored by reference as '$1a' and "
               "defined separately with a hex length prefix, so both have to "
               "be decoded. THESE PAGES RECORD NO VISA STATUS: a listing says "
               "a named person leads a project at a named company, nothing "
               "more. `organization` is the published field and is almost "
               "always the nonprofit itself; `employers_from_bio` is extracted "
               "from prose, is a best effort, and is absent for 88 projects. "
               "Spelling variants are grouped case-insensitively but distinct "
               "names are never merged."),
    ),
    Dataset(
        key="build_fellowship_partners",
        source_url="https://www.buildfellowship.com/impact",
        script="build_fellowship_partners",
        source="buildfellowship.com/impact, joined to NCES IPEDS",
        consumes=("data/h1b/build_fellowship_partners_raw.json",),
        produces=("data/h1b/build_fellowship_partners.json",),
        summary=("The 54 university partners the Build Fellowship publishes, "
                 "with each one's graduate STEM completions and non-resident "
                 "share from IPEDS."),
        cadence="when the organisation updates its impact page",
        notes=("Open Avenues Foundation runs the Build Fellowship and is the "
               "clearest public example of the cap-exempt affiliated-nonprofit "
               "route. A PARTNERSHIP IS THE ORGANISATION'S OWN CLAIM that it "
               "trains students at that institution. It does not mean the "
               "university sponsors anyone, employs a fellow, or is party to "
               "any petition -- the affiliation conferring cap exemption is the "
               "nonprofit's, and no source records cap status against a named "
               "employer. The IPEDS columns are independent of the partner "
               "list. Student counts below ten are published only as '< 10'."),
    ),
    Dataset(
        key="perm_pipeline",
        source_url="https://www.dol.gov/agencies/eta/foreign-labor/performance",
        script="build_perm_pipeline",
        source="US DOL Office of Foreign Labor Certification, PERM disclosure data",
        consumes=("data/h1b/perm_fy2024_q4.xlsx",),
        produces=("data/h1b/perm_pipeline.json",),
        summary=("PERM labour certifications by the status held when filed, by "
                 "country and by occupation -- the last published step before a "
                 "green card."),
        cadence="quarterly, when DOL publishes",
        notes=("CLASS_OF_ADMISSION is the reason to read this file: it is the "
               "one published field showing which visa people hold when they "
               "seek permanent residence, and it is a genuine piece of the "
               "pipeline linkage the briefing asks for. It cannot follow a "
               "person across datasets. A certification is NOT a green card -- "
               "USCIS must still approve an I-140 and a visa number must be "
               "available, which for India and China takes years. Counts are "
               "APPLICATIONS, not people; one person may appear more than once, "
               "and CERTIFIED-EXPIRED means the certification lapsed unused."),
    ),
    Dataset(
        key="j1_scholars",
        source_url="https://j1visa.state.gov/basics/facts-and-figures/",
        script="build_j1_scholars",
        source="BridgeUSA participants by calendar year of program begin date",
        consumes=("data/h1b/national_visa_trends.json",),
        produces=("data/h1b/j1_scholars.json",),
        summary=("J-1 academic exchange categories 2015-2024 -- the uncapped "
                 "route into a university lab that is shrinking while the others "
                 "grow."),
        cadence="annual",
        notes=("J-1 research scholar needs no cap, no labour condition "
               "application and no wage floor, which makes its decline the "
               "counter-example to every other route here. THE PARTIAL YEAR IS "
               "THE TRAP: the source carries CY2025 as data through about March. "
               "Comparing 2015 with 2025 puts a full year against a quarter and "
               "reports a 51% fall in research scholars; the fall to the last "
               "complete year is 33%. The builder refuses to compute a change "
               "into a year marked partial."),
    ),
    Dataset(
        key="eb2_niw",
        source_url="https://www.uscis.gov/sites/default/files/document/reports/stem_related_petition_trends_eb2_and_o1a_categories_factsheet_fy23.pdf",
        script="build_eb2_niw",
        source="USCIS, STEM-Related Petition Trends: EB-2 and O-1A Categories, Table 1",
        consumes=("data/h1b/uscis_reports/",),
        produces=("data/h1b/eb2_niw.json",),
        summary=("EB-2 immigrant petitions with and without a National Interest "
                 "Waiver, FY2018-FY2023 -- the immigrant-visa counterpart to the "
                 "O-1 route."),
        cadence="when USCIS updates the fact sheet",
        notes=("An EB-2 normally needs an employer and a labour certification; "
               "the NIW removes both and the beneficiary self-petitions. USCIS "
               "clarified the STEM criteria in January 2022. Receipts are "
               "FILINGS, not people, and an approval is not an admission -- a "
               "visa number must still be available, which is where the "
               "country backlogs bite. USCIS rounds every figure to the nearest "
               "10, so the two parts need not sum exactly to the printed total; "
               "rows reconcile within 10 and are dropped otherwise. Only Table 1 "
               "(all job types) is read: Table 2 repeats the row shape for STEM "
               "categories only, and reading past the heading mixes them."),
    ),
    Dataset(
        key="nonprofit_990s",
        source_url="https://projects.propublica.org/nonprofits/api",
        script="build_nonprofit_990s",
        source="IRS Form 990 via the ProPublica Nonprofit Explorer API",
        consumes=(),
        produces=("data/h1b/nonprofit_990s.json",),
        summary=("Revenue and expenses of the nonprofits that appear in the H-1B "
                 "data describing university-affiliated cap-exempt sponsorship."),
        cadence="annual, as filings are posted",
        notes=("The USCIS report counts affiliated-nonprofit petitions without "
               "naming an organisation, and the Employer Data Hub names "
               "employers without recording cap status. A 990 is the one public "
               "record that sizes a named filer. Revenue is NOT a count of "
               "sponsorships and a 990 records no cap status. employees_w3 is "
               "frequently 0 in the source even where staff are reported, so a "
               "zero there is unreported rather than none. Each EIN is an "
               "assertion that the filer is the organisation seen in the H-1B "
               "data; add one only after confirming the match."),
    ),
    Dataset(
        key="fica_exposure",
        source_url="https://www.irs.gov/individuals/international-taxpayers/foreign-student-liability-for-social-security-and-medicare-taxes",
        script="build_fica_exposure",
        source="IRC 3121(b)(19) and IRS guidance; DHS SEVP authorisation counts",
        consumes=("data/h1b/opt_national.json",),
        produces=("data/h1b/fica_exposure.json",
                  "site/data/fica_exposure.json"),
        summary=("The employer-side payroll-tax differential on OPT employment, "
                 "as a rate and as a labelled scenario grid."),
        cadence="on statute change or a new SEVP release",
        notes=("Students in F-1 or J-1 status are exempt from Social Security "
               "and Medicare tax on authorised employment, and IRS guidance "
               "lists practical training, so OPT and STEM OPT are covered. The "
               "RATES are statutory and the AUTHORISATION COUNTS are published; "
               "the WAGES are assumptions. No agency publishes OPT wages, so "
               "there is deliberately NO national total here -- only a "
               "per-$100,000 figure and a scenario grid. Do not quote a "
               "scenario as a measurement. Authorisations are not FTE-years, so "
               "applying an annual wage to a count overstates a single year."),
    ),
    Dataset(
        key="h1b_cap_exempt",
        source_url="https://www.uscis.gov/tools/reports-and-studies",
        script="download_h1b_cap_exempt",
        source="USCIS annual Report on H-1B Petitions to Congress, Section 2.2",
        consumes=("data/h1b/uscis_reports/",),
        produces=("data/h1b/h1b_cap_exempt.json",),
        summary=("H-1B petitions from cap-exempt employer types -- universities, "
                 "nonprofits affiliated with them, and research organisations -- "
                 "FY2018 to FY2025."),
        cadence="annual, when USCIS reports to Congress",
        notes=("Neither source already here can answer this: the DOL LCA form "
               "never asks about the cap, and the USCIS Employer Data Hub has no "
               "cap flag. USCIS publishes the counts as ACWIA FEE exemptions, "
               "and the first three employer rows are the same categories that "
               "are cap-exempt under INA 214(g)(5). Fee exemption is BROADER "
               "than cap exemption -- the same table counts primary and "
               "secondary schools, which are not cap-exempt, and procedural "
               "exemptions that say nothing about employers. The report's own "
               "footnote warns a petition may appear in several rows, so the "
               "rows must never be summed to a total. FY2018-FY2019 are scans: "
               "figures are accepted only when the four quarters reconcile "
               "against the printed annual total, after a repair pass for the "
               "separator artefacts."),
    ),
    Dataset(
        key="opt",
        source_url="https://www.ice.gov/sevis/whats-new",
        script="parse_opt_reports",
        source="DHS Student and Exchange Visitor Program (SEVP) published reports",
        consumes=("data/sevp/", "data/h1b/"),
        produces=("data/h1b/opt_by_university.json",
                  "data/h1b/opt_national.json",
                  "data/h1b/opt_employers.json"),
        summary=("Optional Practical Training: the national OPT / STEM OPT / CPT "
                 "series 2007-2024, the Top 100 school tables 2017-2024 in both "
                 "flavours, and the 2024 Top 200 employers."),
        cadence="annual, when SEVP publishes",
        notes=("Two DIFFERENT kinds of number live here and must not be mixed. "
               "opt_national.json is a complete national count. The per-school "
               "and per-employer tables are TOP-N RANKINGS: a school missing "
               "from a year placed outside the top 100 that year, it did not "
               "have zero OPT students. Summing schools therefore gives a floor, "
               "not a total, and a school entering or leaving the list between "
               "years may only reflect the cutoff moving. Use the national table "
               "for anything published as a total. `opt` is pre- plus "
               "post-completion OPT; `stem_opt` is the 24-month STEM extension. "
               "In the employer table a student on both programmes is counted "
               "once in total but in both columns, so the columns do not sum."),
    ),
    Dataset(
        key="lca",
        source_url="https://www.dol.gov/agencies/eta/foreign-labor/performance",
        script="aws_lca_rebuild",
        source="US DOL Office of Foreign Labor Certification, LCA disclosure files",
        consumes=("data/h1b/lca/",),
        archived_at="s3://phd-demographics-raw-data/data/h1b/lca/",
        produces=("data/h1b/lca_by_university.json",),
        summary=("H-1B Labor Condition Applications aggregated per university: "
                 "volume, job titles, SOC codes and wage quartiles. Feeds every "
                 "university page."),
        cadence="quarterly, when DOL publishes a new disclosure file",
        notes=("Rows are deduplicated on CASE_NUMBER (LCA_CASE_NUMBER in FY2013). "
               "DOL's quarterly files overlap inconsistently -- some are a single "
               "quarter, some are cumulative to an arbitrary date -- so ADD every "
               "file DOL publishes and NEVER delete one that looks superseded. "
               "Dedup makes a redundant file free; a deleted one may be "
               "unrecoverable. The intermediate csv_cache/ is ~6 GB and derived: "
               "never back it up, delete it whenever space is needed. When it "
               "will not fit locally, scripts/aws_lca_rebuild.sh runs the "
               "pipeline's own aggregation on EC2. The source .xlsx are NOT "
               "kept locally either: they are archived to the prefix in "
               "archived_at and listed in data/h1b/lca_archive_manifest.json. "
               "Restore them before re-running. See data/h1b/LCA_ARCHIVE.md."),
    ),
    Dataset(
        key="workforce",
        source_url="https://ncses.nsf.gov/surveys/national-survey-college-graduates/",
        script="build_workforce_data",
        source="NSF Survey of Doctorate Recipients",
        produces=("data/nsf_workforce/workforce_dashboard.json",),
        summary="Foreign-born share of the US doctoral workforce, for /workforce.html.",
        notes=("The SDR public-use file has NO state: geography is suppressed for "
               "confidentiality, so nothing here can answer a state-level question."),
    ),
    Dataset(
        key="live_bundle",
        script="build_live_bundle",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",
                  "data/h1b/state_dept/FYs97-24_NIVDetailTable.xlsx"),
        produces=("site/data/live_bundle.json",),
        summary=("Everything the live voice dashboard renders, in one ~9 KB file "
                 "so no chart update touches the network."),
        cadence="after nra_index or f1_series changes",
        notes=("Reads the raw IPEDS completions files directly for master's "
               "(award level 7), which nra_index does not carry."),
    ),
    Dataset(
        key="site_map",
        script="build_site_map",
        source="derived",
        produces=("site/data/chat/site_map.json",),
        summary=("Every page, title, description and anchor, walked from the "
                 "actual HTML so the assistant's page list cannot drift."),
        cadence="after any page is added, renamed or re-sectioned",
    ),
    Dataset(
        key="chat_facts",
        script="build_chat_facts",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",),
        produces=("cloud/chat/chat_data/universities_compact.json",
                  "cloud/chat/chat_data/national_series.json",
                  "cloud/chat/chat_data/nra_index.csv.gz"),
        summary="The data the chat Lambda ships with, in-zip. Nothing fetched at runtime.",
        cadence="before any chat deploy",
    ),
    Dataset(
        key="parquet_exports",
        script="build_parquet_from_site",
        source="derived",
        produces=("site/data/exports/stem_records.parquet",
                  "site/data/exports/nonstem_records.parquet"),
        summary="The whole record corpus as Parquet, for people who would rather compute.",
        cadence="after generate/build_pages",
        notes=("Requires duckdb. build_pages swallows the ImportError and still "
               "reports OK, which is how these silently served an April snapshot "
               "for four months. Check the row counts, not the exit code."),
    ),
    Dataset(
        key="concentration_cases",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        script="build_concentration_cases",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",),
        produces=("site/data/concentration_cases.json",),
        summary=("The 49 institution-and-field cells that are sustainedly "
                 "majority non-resident. Drives the landing-page hero."),
        cadence="after nra_index changes",
        notes=("Thresholds are deliberately conservative -- 80+ doctorates in "
               "the window, 70%+ in at least 6 of 8 years. Loosening them "
               "produces a longer list that is easier to attack. The payload "
               "carries the national context (domestic doctorates +32% against "
               "a total +33%) alongside the cases, so the page cannot show one "
               "without the other."),
    ),
    Dataset(
        key="taxpayer_cost",
        source_url="https://ncses.nsf.gov/surveys/federal-support-survey/",
        script="build_taxpayer_cost",
        source="derived (NSF NCSES Federal Support Survey + IPEDS)",
        consumes=("data/ipeds/nra_index.csv.gz",
                  "data/federal_support/federal_support_by_university.json"),
        produces=("site/data/taxpayer_cost.json",),
        summary=("Federal obligations per STEM research doctorate, against "
                 "non-resident share. Quantifies the public-investment claim."),
        cadence="after nra_index or federal_support changes",
        notes=("Research DOCTORATES only. Doctoral students are largely funded "
               "on federal grants; master's students mostly pay tuition, so "
               "combining the levels overstates the federal subsidy attached to "
               "master's degrees. The per-doctorate figure is an INTENSITY "
               "RATIO, not a cost of production -- federal obligations buy "
               "research, not degrees, and a campus with a national lab ranks "
               "high for unrelated reasons."),
    ),
    Dataset(
        key="long_series",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        script="build_long_series",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",),
        produces=("site/data/long_series.json",),
        summary=("Core-STEM doctorates 1995-2025: totals, non-resident and "
                 "domestic counts, share, and the by-field breakdown."),
        cadence="after nra_index changes",
        notes=("Sums BOTH award-level bases across 2008-09. Institutions "
               "migrated from level 9 to 17 one at a time and each reports "
               "exactly one -- verified zero report both -- so taking a single "
               "basis there drops ~20% of those years and puts a false trough "
               "in the middle of the series. Use models.bases_for(year), never "
               "award_level_basis(), for anything crossing the transition."),
    ),
    Dataset(
        key="level_rankings",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        script="build_level_rankings",
        source="derived",
        consumes=("data/ipeds/",),
        produces=("site/data/level_rankings.json",),
        summary=("Non-resident share rankings at BOTH master's and doctoral "
                 "level: by institution, by 4-digit CIP, fastest risers, "
                 "largest cohorts, and the within-institution contrast."),
        cadence="after a new Completions year lands",
        notes=("Every ranking is a ratio, so every one carries a cohort floor "
               "and publishes how many units cleared it -- a programme with 4 "
               "degrees all to non-residents reads 100% and means nothing. "
               "Floors differ by level because master's cohorts are far larger. "
               "The within-institution contrast is the strongest cut here: it "
               "holds the institution fixed, so it cannot be answered with "
               "'that university is internationally oriented'. The OPT/H-1B "
               "reading of that contrast is a READING and is labelled as one on "
               "the page; IPEDS records awards, not admissions or intent."),
    ),
    Dataset(
        key="tuition",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        script="build_tuition_revenue",
        source="derived",
        consumes=("data/ipeds_tuition/", "data/ipeds_finance/", "data/ipeds/"),
        produces=("site/data/tuition.json",),
        summary=("What the core-STEM master's expansion is worth in tuition: "
                 "published out-of-state graduate rates against non-resident "
                 "master's degrees conferred, with the audited sector total "
                 "alongside, in constant 2024 dollars."),
        cadence="annually, when IPEDS IC and finance files are released",
        notes=("The billings figure is an ESTIMATE and must always be published "
               "as one: a published sticker rate multiplied by a degree count, "
               "not receipts and not net of waivers. It is defensible at "
               "master's level only because NSF GSS 2024 puts master's "
               "assistantship rates at 7.0% RA / 6.9% TA, so ~86% hold neither "
               "and therefore carry no tuition waiver; the same method would be "
               "wrong for undergraduates. Never add it to, or subtract it from, "
               "the F1B01/F2D01 finance series -- that series is net and covers "
               "every level, so the two are different quantities. Inputs come "
               "from BOTH NCES mirrors: complete-data-files lacks IC2014_AY, "
               "datacenter/data lacks the newest year."),
    ),
    Dataset(
        key="university_distribution",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        script="build_university_distribution",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",),
        produces=("site/data/university_distribution.json",),
        summary=("Per-university department distributions: every 4-digit CIP "
                 "programme with 15+ doctorates, 2015-2022, with its share."),
        cadence="after nra_index changes",
        notes=("4-digit grain deliberately. At 2-digit, 'Engineering' at Purdue "
               "collapses sixteen programmes running 30-82% into one bar, which "
               "is the averaging this chart exists to undo. A single headline "
               "share per university misleads: MIT runs 15.8% to 73.2% and the "
               "average describes none of its departments."),
    ),
    Dataset(
        key="distribution",
        source_url="https://nces.ed.gov/ipeds/use-the-data",
        script="build_distribution",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",),
        produces=("site/data/distribution.json",),
        summary=("National department histogram by non-resident share, "
                 "2010/2015/2020/2025, at 4-digit CIP."),
        cadence="after nra_index changes",
    ),
    Dataset(
        key="support_by_citizenship",
        source_url="https://ncses.nsf.gov/surveys/earned-doctorates/",
        script="build_support_by_citizenship",
        source="NSF Survey of Earned Doctorates, Table 4-1",
        produces=("site/data/support_by_citizenship.json",),
        summary=("Primary source of support by citizenship. The allocation "
                 "evidence: 76.0% of international S&E doctorate recipients are "
                 "on assistantships against 53.1% of citizens."),
        cadence="annually, when SED publishes",
        notes=("SED gives citizenship but not whether an assistantship is "
               "federal or institutional; GSS gives the federal split but not "
               "citizenship. The two CANNOT be multiplied - doing so assumes "
               "the federal share is identical for both groups, which nothing "
               "measures."),
    ),
    Dataset(
        key="curated_answers",
        script="curated_answers",
        args="--export cloud/chat/curated_answers.yaml",
        source="derived (the live assistant)",
        consumes=(
            # The answers are only as current as the knowledge the assistant had
            # when they were exported. Any of these moving makes them stale.
            "cloud/chat/knowledge",
            "site/data/concentration_cases.json",
            "site/data/taxpayer_cost.json",
            "site/data/support_by_citizenship.json",
            "site/data/distribution.json",
            "site/data/programme_shares.json",
        ),
        produces=("cloud/chat/curated_answers.yaml",),
        summary=("The assistant's answers to the 31 most-asked questions, "
                 "exported for hand-editing and then seeded into the cache."),
        cadence="after ANY change to the knowledge base or the published data",
        notes=("HIGHEST-PRIORITY REFRESH. These answers are what most visitors "
               "actually read -- they are served from cache, so a stale one is "
               "repeated verbatim to everyone who asks. They go stale silently: "
               "the assistant improves, the data updates, and the cached answer "
               "keeps saying what it said in the old world. `datasets` reports "
               "this as STALE whenever a knowledge file or a published dataset "
               "is newer than the export. Re-export, re-edit the voice, --check, "
               "--seed."),
    ),
    Dataset(
        key="og_cards",
        script="build_og_cards",
        source="derived",
        produces=("site/og",),
        summary="237 OpenGraph share cards, one per page and per university.",
        cadence="after any published share changes",
        notes=("Cards must use the NARROW 8-family STEM basis, matching the page "
               "headline. Rendering them on the broad 16-family set makes a card "
               "contradict the page it represents."),
    ),
)

BY_KEY = {d.key: d for d in CATALOG}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def uncatalogued() -> list[str]:
    """Scripts in scripts/ that no catalog entry claims."""
    claimed = {d.script for d in CATALOG}
    out = []
    scripts_dir = ROOT / "scripts"
    if not scripts_dir.is_dir():
        return out
    for name in sorted(os.listdir(scripts_dir)):
        if not name.endswith(".py") or name.startswith("_"):
            continue
        stem = name[:-3]
        if stem not in claimed:
            out.append(stem)
    return out


def report(verbose: bool = False) -> int:
    """Print catalog status. Returns the number of problems found."""
    problems = 0
    print(f"Data catalog — {len(CATALOG)} datasets\n")
    width = max(len(d.key) for d in CATALOG) + 2

    for d in CATALOG:
        missing_out = d.missing_outputs()
        missing_in = d.missing_inputs()
        if missing_in:
            flag, note = "INPUT MISSING", ", ".join(missing_in)
            problems += 1
        elif missing_out and d.produces:
            flag, note = "NOT BUILT", ", ".join(missing_out)
            problems += 1
        elif d.stale():
            flag = "STALE (priority)" if d.is_priority() else "STALE"
            note = ("what most visitors actually read; a stale answer is "
                    "repeated verbatim" if d.is_priority()
                    else "input newer than output")
            problems += 1
        elif not d.produces:
            flag, note = "ok", "writes only where told (--json)"
        else:
            flag, note = "ok", ""
        print(f"  {d.key:<{width}}{flag:<15}{note}")
        if verbose:
            print(f"  {'':<{width}}  script:  {d.script_rel()} {d.args}".rstrip())
            print(f"  {'':<{width}}  source:  {d.source}")
            print(f"  {'':<{width}}  {d.summary}")
            if d.notes:
                print(f"  {'':<{width}}  NOTE: {d.notes}")
            print()

    priority_stale = [d for d in CATALOG if d.is_priority() and d.stale()]
    if priority_stale:
        print("  ATTENTION")
        for d in priority_stale:
            print(f"    {d.key} is stale and is high priority: {d.summary}")
            runner = "" if d.script_rel().endswith(".sh") else "python3 "
            print(f"    rebuild: {runner}{d.script_rel()} {d.args}".rstrip())
        print()

    extra = uncatalogued()
    print(f"\n{len(extra)} scripts not in the catalog "
          f"({len(CATALOG)} of {len(CATALOG) + len(extra)} catalogued):")
    for name in extra:
        print(f"  scripts/{name}.py")
    print("\nThese are one-off analyses, downloaders and helpers. A script "
          "belongs in the\ncatalog when something published depends on its "
          "output.")
    return problems


def order_for(keys: list[str] | None = None) -> list[Dataset]:
    """Catalog order, filtered. The catalog is declared in dependency order,
    so this is the order to re-run in."""
    if not keys:
        return list(CATALOG)
    want = set(keys)
    # pull in anything a requested dataset consumes
    for d in CATALOG:
        if d.key in want:
            for other in CATALOG:
                if set(other.produces) & set(d.consumes):
                    want.add(other.key)
    return [d for d in CATALOG if d.key in want]
