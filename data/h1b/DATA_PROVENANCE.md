# Immigration & Work Authorization Data Provenance

## Pipeline: PhD Production → Work Authorization → Employment

This document tracks the official US government data sources used to analyze the pipeline
from PhD completion at US universities to work authorization and employment.

---

## Stage 1: PhD Production (Thesis/Dissertation Data)
**Source:** University institutional repositories via OAI-PMH
**Files:** `data/western_us_dissertations/*.csv`
**Coverage:** 105 R1 research universities, 2016-2026
**What it shows:** Who is completing PhDs and Master's, in which departments

## Stage 2: International Student Enrollment
**Source:** NSF Graduate Students and Postdoctorates Survey (GSS)
**Agency:** National Science Foundation / National Center for Science and Engineering Statistics
**URL:** https://ncses.nsf.gov/surveys/graduate-students-postdoctorates-in-science-and-engineering/
**Files:** `data/gss/*.csv`
**What it shows:** How many international graduate students are enrolled at each university

**Source:** IPEDS Fall Enrollment
**Agency:** US Department of Education, National Center for Education Statistics
**URL:** https://nces.ed.gov/ipeds/
**Files:** `data/ipeds/ef*_d.csv`
**What it shows:** Total enrollment including nonresident aliens, by institution

## Stage 3: OPT (Optional Practical Training)
**Source:** SEVP SEVIS By the Numbers Reports
**Agency:** US Department of Homeland Security, Immigration & Customs Enforcement (ICE)
**URL:** https://studyinthestates.dhs.gov/sevis-by-the-numbers/sevis-by-the-numbers-data
**Files:**
- `data/h1b/sevis_btn_2024.pdf` — 2024 annual report (national aggregates)
- `data/h1b/23_0425_hsi_sevp-sevis-btn-2022-top100-prepost-opt-schools.pdf` — Top 100 schools, pre/post-completion OPT, CY2022
- `data/h1b/23_0425_hsi_sevp-sevis-btn-2022-top100-stem-opt-schools.pdf` — Top 100 schools, STEM OPT extensions, CY2022
- `data/h1b/20_0903_hsi_sevp-sevis-btn-2019-top100-stem-opt-schools.pdf` — Top 100 schools, STEM OPT, CY2019
- `data/h1b/20_0903_hsi_sevp-sevis-btn-2019-top100-prepost-opt-schools.pdf` — Top 100 schools, OPT, CY2019
**What it shows:** Which universities have the most students on OPT/STEM OPT work authorization
**Limitation:** PDF only, not machine-readable. Top 100/200 schools only.
**Key stat:** 194,554 OPT students with EADs in CY2024 (21% increase from CY2023)

## Stage 4: H-1B Visa (University as Employer)
**Source:** USCIS H-1B Employer Data Hub
**Agency:** US Citizenship and Immigration Services (USCIS), Department of Homeland Security
**URL:** https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub
**Files:** `data/h1b/h1b_datahub_fy{2010-2026}.csv` — 17 fiscal years, FY2010 through FY2026
**Processed:** `data/h1b/h1b_by_university.json` — 97 universities matched
**What it shows:** How many H-1B petitions each university files as an employer (cap-exempt)
**Fields:** Fiscal Year, Employer, Initial/Continuing Approvals/Denials, NAICS, State, City

**FORMAT CHANGE AT FY2024 — this breaks naive parsers.** FY2010-FY2023 are
plain UTF-8 CSV. FY2024 onward are **UTF-16 little-endian, TAB-separated**
crosstab exports. Reading them as UTF-8 CSV yields garbage, not an error.
`pipeline/step3_parse_federal.py` sniffs the byte-order mark and switches
readers; anything new that touches these files must do the same. That step also
checks the first bytes for an HTML anti-bot page, because a failed download
arrives looking like a successful one.

**FY2026 is partial** (24,362 rows against ~62,000 for a full year) because the
fiscal year is still running. Treat it as year-to-date, never as an annual total.

**Housekeeping:** `h1b_datahub_fy2024-checkthis.csv` and
`h1b_datahub_fy2025-checkthis.csv` are byte-identical copies of the real files
(~29 MB of duplication); the parser skips any filename containing `checkthis`.
`h1b_datahub_fy2026-2.csv` is a 30-byte failed download with no rows.

**Source:** DOL LCA Disclosure Data
**Agency:** US Department of Labor, Office of Foreign Labor Certification (OFLC)
**URL:** https://www.dol.gov/agencies/eta/foreign-labor/performance
**Files:** `data/h1b/lca/*.xlsx` — 32 files, 3.5 GB, covering FY2013 and
FY2015-FY2026. FY2013 and FY2015-FY2019 are annual/end-of-year releases;
FY2020-FY2025 are complete quarterly sets (Q1-Q4); FY2026 currently holds Q3
only, the fiscal year being in progress.
**Processed:** `data/h1b/lca_by_university.json` — 78 universities matched

**These quarterly files are cumulative, not incremental.** A Q3 file contains
the year to date, not the third quarter alone — FY2026 Q3 carries received
dates running back years, because a case received earlier can be decided in the
current period. That is why superseded earlier quarters of the same fiscal year
can be archived without data loss. FY2026 Q1 was moved to
`s3://phd-demographics-raw-data/backups/2026-08-18/h1b/lca/superseded/` on that
basis; retrieve it from there rather than re-downloading if it is ever needed.
**What it shows:** Individual job titles, SOC codes, and salaries for H-1B positions at universities
**Fields:** Employer Name, Job Title, SOC Code, Wage Rate, Visa Class, Case Status, Worksite

## Stage 5: Green Card Sponsorship
**Source:** DOL PERM Disclosure Data
**Agency:** US Department of Labor, OFLC
**URL:** https://www.dol.gov/agencies/eta/foreign-labor/performance
**Files:** `data/h1b/perm_fy2024_q4.xlsx`
**What it shows:** Which universities are sponsoring employees for permanent residency (green cards)

## Stage 6: Research Funding
**Source:** NSF HERD Survey (Higher Education Research and Development)
**Agency:** National Science Foundation
**URL:** https://ncses.nsf.gov/surveys/higher-education-research-development/
**Files:** `data/herd/*.xlsx`, `data/herd/funding_by_university.json`
**What it shows:** R&D expenditures by university — correlates with international researcher hiring

## Additional Context: J-1 Exchange Visitors
**Source:** Exchange Visitor Program Participation Data
**Agency:** US Department of State, Bureau of Educational and Cultural Affairs
**URL:** https://j1visa.state.gov/basics/facts-and-figures/
**Files:** `data/h1b/j1_participation_cy2015_2025.xlsx`
**What it shows:** National aggregates of J-1 exchange visitors by category (Research Scholar, Professor, etc.)
**Limitation:** No per-university breakdown in public data

## Additional Context: O-1 Extraordinary Ability Visa
**Source:** USCIS I-129 Nonimmigrant Worker Petition Reports
**Agency:** USCIS
**URL:** https://www.uscis.gov/tools/reports-and-studies/immigration-and-citizenship-data
**What it shows:** National aggregate O-1 approval/denial counts (~10K/year)
**Limitation:** No per-employer breakdown. PDF/aggregate only.

---

## Data Pipeline Summary

```
PhD Production (OAI-PMH) ──┐
                            ├── University-Level Analysis
Enrollment (IPEDS/GSS) ────┤
                            ├── Work Authorization Pipeline
OPT (SEVIS reports) ───────┤   PhD → OPT → H-1B → PERM/Green Card
                            │
H-1B (USCIS Hub + DOL LCA)─┤
                            │
PERM (DOL) ────────────────┤
                            │
Funding (HERD) ────────────┘
```

All data sources are official US government publications from:
- Department of Homeland Security (USCIS, ICE/SEVP)
- Department of Labor (OFLC)
- Department of Education (NCES/IPEDS)
- National Science Foundation (NCSES)
- Department of State (J-1 program)

---

## Verifying this document

Coverage lines drift as files are added. To re-derive them:

```bash
ls data/h1b/h1b_datahub_*.csv                 # USCIS fiscal years on disk
ls data/h1b/lca/*.xlsx                        # DOL LCA files and quarters
file data/h1b/h1b_datahub_fy2024.csv          # confirm the UTF-16 boundary
```

Everything here was downloaded directly from the issuing agency — USCIS, DOL
OFLC, DHS/ICE SEVP, NCES/IPEDS and NSF NCSES. No third-party aggregator,
scraper or reseller sits between those agencies and this repository.

Last verified: 2026-08-19.
