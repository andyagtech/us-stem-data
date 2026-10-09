#!/usr/bin/env python3
"""Where each knowledge file's numbers come from.

WHY THIS EXISTS. knowledge_figures.py pins individual figures by re-deriving
them, which is exact and expensive: one resolver per figure. The knowledge base
states about 1,300 figures, so pinning every one by hand would mean 1,300
hand-written resolvers -- and a hand-written resolver is one more thing that can
be wrong.

This takes the cheaper half of the problem. Every figure in a knowledge file
must be FINDABLE in a dataset that file draws on. That does not prove a figure
is the right one, but it proves the number exists in the data and is not
invented, mistyped or left over from a build two quarters ago. It caught, in
its first run, a pair of 2008 enrolment counts matching no dataset in the repo.

Pair the two: this says "the number is in the data", knowledge_figures says
"the number is still current". Volatile figures deserve both; a stable
historical series needs only this.

HOW A FILE DECLARES ITS SOURCES. Most name their dataset in prose ("Data:
/data/x.json"), and that is read automatically. SOURCES below is for the files
that draw on a dataset without naming it, and for the second and third dataset
a file quotes from.
"""
from __future__ import annotations

#: file -> the datasets it draws figures from, by site/data/<name>.json stem.
#: Only needed where the prose does not already name the file. A name prefixed
#: "pipeline:" is a build input under pipeline/ rather than a published
#: dataset -- real provenance, just not shipped to the site.
SOURCES: dict[str, tuple[str, ...]] = {
    "01-central-finding.md": ("distribution", "national_series"),
    "02-definitions.md": ("distribution", "universities_index"),
    "03-limitations.md": ("universities_index", "pipeline:universities"),
    "10-funding-argument.md": ("support_by_citizenship", "taxpayer_cost",
                               "federal_support", "grad_support",
                               "gss_institution_ranking"),
    "11-distributions.md": ("distribution", "programme_shares",
                            "university_distribution"),
    "12-masters-expansion.md": ("graduate_balance", "concentration_cases",
                                "expansion_phases"),
    "13-the-work-pipeline.md": ("opt_national", "visa_issuances",
                                "h1b_approvals", "visa_substitution",
                                "h1b_cap_exempt"),
    "14-the-domestic-pipeline.md": ("domestic_pipeline", "graduate_balance",
                                   "grad_support", "scorecard_earnings"),
    "15-how-long-the-gap-has-held.md": ("support_trend", "support_by_citizenship"),
    "16-equal-pay-is-not-equal-cost.md": ("fica_exposure", "visa_substitution"),
    "17-where-the-balance-shifted.md": ("graduate_balance",),
    "18-route-revenue-leverage.md": ("lpr_adjustments", "visa_issuances",
                                     "enrolment_and_funding"),
    "27-tuition-and-state-support.md": ("tuition_and_appropriations", "tuition"),
    "29-who-requests-and-enrols.md": ("employer_profiles", "h1b_approvals"),
    "30-l1-o1-and-admissions.md": ("nonimmigrant_admissions", "visa_issuances"),
    "17-where-the-balance-shifted.md": ("graduate_balance", "expansion_phases"),
    "04-sources.md": ("universities_index", "pipeline:universities"),
    "19-enrolment-and-leverage.md": ("gss_citizenship_trend",
                                     "gss_institution_ranking"),
    "24-enforcement.md": ("h1b_enforcement", "visa_issuances"),
    "32-local-wages-and-domestic-series.md": ("local_wage_comparison",
                                              "nativity_labour"),
    "33-wage-level-trend.md": ("wage_level_trend", "local_wage_comparison"),
    "34-comparing-institutions.md": ("institution_profiles", "summary"),
    "35-looking-figures-up.md": ("summary", "universities_index"),
    "36-the-argument.md": ("taxpayer_cost", "support_by_citizenship",
                           "visa_schools", "opt_national", "visa_substitution",
                           "distribution"),
    "37-the-body-shops.md": ("visa_bodyshops", "visa_staffing"),
    "38-critical-industries.md": ("critical_industries", "grid_capacity"),
    "39-the-public-sector.md": ("public_employer_perm",),
    "40-postdocs.md": ("postdoc_citizenship", "gss_institution_ranking"),
    "41-the-name-lists.md": ("name_lists", "repository_index"),
}

#: Figures that legitimately have no dataset behind them, with the reason.
#: A statutory rate, a legal citation, a figure quoted from a published federal
#: document this project does not parse. Keyed by the literal string as it
#: appears in the prose. Anything here is exempt from the scan; nothing here
#: should be a figure this project computes.
EXTERNAL: dict[str, str] = {
    "7.65": "Statutory employer FICA rate, 26 USC 3111 (6.2 + 1.45).",
    "6.2": "Statutory Social Security rate, 26 USC 3101(a)/3111(a).",
    "1.45": "Statutory Medicare rate, 26 USC 3101(b)/3111(b).",
    "15.3": "Both halves of FICA, the statutory rates added.",
    "3121": "Statutory citation, 26 USC 3121(b)(19).",
    "214.2": "Regulatory citation, 8 CFR 214.2(f)(10).",
    "120.62": "Regulatory citation, 22 CFR 120.62 (ITAR U.S. person).",
    "73.56": "Regulatory citation, 10 CFR 73.56 (NRC access authorisation).",
    "12968": "Executive Order 12968 (access to classified information).",
    "1324": "Statutory citation, 8 USC 1324b(a)(3).",
    "1182": "Statutory citation, 8 USC 1182(n)(3) (H-1B dependency).",
    "655": "Regulatory citation, 20 CFR 655 (OFLC debarment).",
    "656": "Regulatory citation, 20 CFR 656.31(f) (PERM debarment).",
    "90": "Days of unemployment permitted on post-completion OPT, 8 CFR 214.2.",
    "150": "Days of unemployment permitted across the STEM extension, 8 CFR 214.2.",
    "24": "Months of the STEM OPT extension, 2016 DHS final rule.",
    "17": "Months of the superseded STEM OPT extension, 2008 interim rule.",
    "12": "Months of standard post-completion OPT, 8 CFR 214.2(f)(10).",
    "65000": "Statutory H-1B cap, 8 USC 1184(g)(1)(A).",
    "20000": "Statutory H-1B master's exemption, 8 USC 1184(g)(5)(C).",
    "140000": "Statutory annual employment-based immigrant limit, 8 USC 1151(d).",
}


def sources_for(name: str) -> tuple[str, ...]:
    return SOURCES.get(name, ())
