# Data Dictionary -- PhD Demographics Project

Last updated: 2026-03-31

This document describes every data source in the repository, including field definitions,
coverage periods, source agencies, and known limitations.

---

## Table of Contents

1. [Key Terminology](#key-terminology)
2. [Citizenship Field Definitions by Source](#citizenship-field-definitions-by-source)
3. [IPEDS Completions](#ipeds-completions)
4. [IPEDS Enrollment](#ipeds-enrollment)
5. [IPEDS Enrollment Major / Graduation Rates (EF-D)](#ipeds-enrollment-major--graduation-rates-ef-d)
6. [IPEDS Student Financial Aid (SFA)](#ipeds-student-financial-aid-sfa)
7. [IPEDS Institutional Characteristics / Tuition (IC)](#ipeds-institutional-characteristics--tuition-ic)
8. [IPEDS Human Resources / Faculty (HR)](#ipeds-human-resources--faculty-hr)
9. [IPEDS Finance](#ipeds-finance)
10. [IPEDS Institutional Directory (HD)](#ipeds-institutional-directory-hd)
11. [NSF HERD (R&D Funding)](#nsf-herd-rd-funding)
12. [NSF Survey of Earned Doctorates (SED)](#nsf-survey-of-earned-doctorates-sed)
13. [NSF Graduate Student Survey (GSS)](#nsf-graduate-student-survey-gss)
14. [NSF Workforce Surveys (SDR, NSCG, NSB Reports)](#nsf-workforce-surveys-sdr-nscg-nsb-reports)
15. [DOL H-1B Disclosure Data](#dol-h-1b-disclosure-data)
16. [ICE SEVP / SEVIS Data](#ice-sevp--sevis-data)
17. [USAspending Federal Grants](#usaspending-federal-grants)
18. [Census American Community Survey (ACS)](#census-american-community-survey-acs)
19. [Dissertation Metadata (Scraped)](#dissertation-metadata-scraped)
20. [Finished Data Archive](#finished-data-archive)
21. [Site Data (Generated Per-University JSONs)](#site-data-generated-per-university-jsons)

---

## Key Terminology

**NRA (Non-Resident Alien):** IPEDS category for students on temporary visas (F-1, J-1, etc.).
Does NOT include permanent residents (green card holders). This is the only category in IPEDS
that isolates foreign nationals; all other race/ethnicity categories include both citizens and
permanent residents.

**Temporary Visa vs. Permanent Resident vs. Naturalized Citizen:**
- *Temporary visa holder* -- F-1 (student), J-1 (exchange visitor), H-1B (specialty worker), etc. Not a permanent resident.
- *Permanent resident (green card holder)* -- Legally authorized to live and work in the US permanently. Classified as "domestic" by IPEDS (grouped with citizens).
- *Naturalized citizen* -- Foreign-born individual who became a US citizen. Also classified as "domestic" by IPEDS.

**STEM CIP Codes:** Classification of Instructional Programs codes used by NCES/DHS to
designate STEM fields. Two-digit CIP codes 01, 03, 04, 10, 11, 14, 15, 26, 27, 29, 40, 41,
42, 45 (select), 51 (select) are commonly included. The DHS STEM Designated Degree Program
List (in `data/sevp/`) is the authoritative list for OPT purposes. This project primarily
uses 2-digit CIP groupings: Engineering (14), Computer Science (11), Biological Sciences (26),
Physical Sciences (40), Mathematics (27), and related fields.

**Carnegie R1/R2 Classification:** Carnegie Classification of Institutions of Higher Education.
R1 = "Very High Research Activity" (approximately 146 institutions). R2 = "High Research
Activity." These designations come from the HD (institutional directory) files via the
C18BASIC or C21BASIC field. R1 institutions produce the vast majority of STEM PhDs.

**OAI-PMH Harvesting:** Open Archives Initiative Protocol for Metadata Harvesting. A standard
protocol used by university digital repositories (DSpace, eScholarship, etc.) to expose
dissertation/thesis metadata. The project harvests metadata via OAI-PMH ListRecords requests
to each university's repository endpoint. Records include title, author, date, subject,
department, and degree type.

---

## Citizenship Field Definitions by Source

### IPEDS (all surveys)
- **NRA (CNRALT, EFNRALT, HRNRALT):** Temporary visa holders ONLY.
- **Race/ethnicity categories (Asian, White, Black, Hispanic, etc.):** Include BOTH US citizens AND permanent residents. There is NO way to separate citizens from green card holders in IPEDS data.
- **Unknown (CUNKNT, EFUNKNT, HRUNKNT):** Race/ethnicity unknown or not reported.

### NSF Survey of Earned Doctorates (SED)
- Groups doctorate recipients as "US citizen or permanent resident" vs. "temporary visa holder."
- Same limitation as IPEDS: citizens and permanent residents are combined.
- Does NOT provide country-of-birth for citizens/permanent residents.

### NSF Survey of Doctorate Recipients (SDR)
- **CTZN field** separates citizenship into five categories:
  - 1 = US citizen, native (born in US)
  - 2 = US citizen, naturalized (foreign-born, became citizen)
  - 3 = US permanent resident (green card holder)
  - 4 = Temporary visa holder
  - 5 = Living outside the US
- **BTHUS:** Born in US (Y/N)
- **CTZN_DRF:** Citizenship status at time of doctorate
- **CTZFOR:** Country of foreign citizenship
- Key finding: 28.1% of the "domestic" PhD workforce (those IPEDS calls "US citizen or permanent resident") are actually foreign-born: 17.9% naturalized citizens + 7.0% permanent residents. Only 63.5% are native-born Americans.

### NSF National Survey of College Graduates (NSCG)
- **CTZN:** Same citizenship categories as SDR (1-5).
- **BTHUS:** Born in US (Y/N)
- **BTHST_TOGA:** Birth state/country TOGA code -- enables identification of specific birth country (e.g., China, India). This field is unique to NSCG and critical for country-specific analysis.
- **BTHRGN:** Birth region (broader geographic grouping)
- **CTZDUAL:** Dual citizenship indicator
- NSCG has the most granular birth-country data of any federal survey.

---

## IPEDS Completions

**Directory:** `data/ipeds/`

**What it is:** Completions survey (C component) from the Integrated Postsecondary Education
Data System. Counts degrees awarded by institution, CIP code, award level, and race/ethnicity.

**Source:** NCES / U.S. Department of Education
- URL: https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx

**Date range:** 1984-2024 (academic years)

**Files:**
- `c1984_cip.csv` through `c1994_cip.csv` -- Early format (fewer demographic columns)
- `c2000_a.csv` through `c2024_a.csv` -- Modern format (full demographic breakdown)
- `c20XX_a_rv.csv` -- Revised/final versions (preferred over preliminary)
- `ipeds_stem_phd_all_years.csv` -- Pre-built aggregate of STEM PhD completions across all years

**Key fields (modern format, e.g., C2024_a.csv):**
| Field | Definition |
|-------|-----------|
| UNITID | Unique institution identifier (6-digit integer) |
| CIPCODE | 6-digit Classification of Instructional Programs code |
| MAJORNUM | Major number (1 = first major, 2 = second major) |
| AWLEVEL | Award level: 7 = Master's, 9 = Doctor's - research/scholarship, 10 = Doctor's - professional practice, 11 = Doctor's - other |
| CTOTALT / CTOTALM / CTOTALW | Total completions / Male / Female |
| CAIANT / CASIAT / CBKAAT / CHISPT / CNHPIT / CWHITT / C2MORT | American Indian / Asian / Black / Hispanic / Native Hawaiian-Pacific / White / Two or more races |
| CUNKNT | Race/ethnicity unknown |
| CNRALT / CNRALM / CNRALW | Non-resident alien total / male / female |
| X-prefixed fields (e.g., XCTOTALT) | Imputation flags |

**Key fields (early format, e.g., c1984_cip.csv):**
| Field | Definition |
|-------|-----------|
| unitid | Institution ID |
| cipcode | CIP code |
| awlevel | Award level |
| crace15 | Total completions |
| crace16 | Non-resident alien |

**Pre-built aggregate (ipeds_stem_phd_all_years.csv):**
| Field | Definition |
|-------|-----------|
| Year | Academic year |
| UNITID | Institution ID |
| State | State abbreviation |
| University | Institution name |
| City | City |
| STEM_Discipline | Discipline grouping (Engineering, Computer Science, etc.) |
| Category | STEM category |
| CIP_2Digit | 2-digit CIP code |
| CIP_Codes_Detail | Specific CIP codes included |
| Institution_URL | Website |

**Size:** ~2.8 GB total for all completions files

**How it's used:** Primary source for tracking NRA PhD share over time by field and institution.
The `ipeds_stem_phd_all_years.csv` aggregate powers the IPEDS dashboard.

**Known limitations:**
- Cannot separate US citizens from permanent residents within domestic categories
- Pre-2008 data uses different race/ethnicity categories (no "two or more races")
- Pre-2000 files have fewer demographic fields
- Some institutions report with a 1-year lag; revised (_rv) files are more accurate

---

## IPEDS Enrollment

**Directory:** `data/ipeds/enrollment/`

**What it is:** Fall Enrollment survey (EF-A component). Counts enrolled students by level
of study, race/ethnicity, and attendance status.

**Source:** NCES / U.S. Department of Education

**Date range:** 2022-2024

**Files:**
- `ef2022a.csv`, `ef2022a_rv.csv` -- Fall 2022 enrollment (preliminary and revised)
- `ef2023a.csv` -- Fall 2023 enrollment
- `EF2024A.zip` -- Fall 2024 enrollment (zipped)
- `grad_enrollment_demographics_2022.csv` -- Pre-built graduate enrollment summary

**Key fields (e.g., ef2023a.csv):**
| Field | Definition |
|-------|-----------|
| UNITID | Institution ID |
| EFALEVEL | Level of student (graduate, undergraduate, etc.) |
| LINE | Detail line within level |
| SECTION | Reporting section |
| LSTUDY | Level of study |
| EFTOTLT / EFTOTLM / EFTOTLW | Total enrolled / Male / Female |
| EFAIANT / EFASIAT / EFBKAAT / EFHISPT / EFNHPIT / EFWHITT / EF2MORT | Race/ethnicity counts (same categories as completions) |
| EFUNKNT | Unknown race/ethnicity |
| EFNRALT / EFNRALM / EFNRALW | Non-resident alien total / male / female |
| EFGNDRUN / EFGNDRAN / EFGNDRUA / EFGNDRKN | Gender unknown/another/unknown-another/known |

**Pre-built summary (grad_enrollment_demographics_2022.csv):**
| Field | Definition |
|-------|-----------|
| unitid | Institution ID |
| name | Institution name |
| carnegie | Carnegie classification |
| total_grad | Total graduate enrollment |
| nra | Non-resident alien count |
| nra_pct | NRA percentage |
| asian / white / black / hispanic | Domestic race/ethnicity counts |

**Size:** ~800 MB (includes ZIPs)

**How it's used:** Provides current enrollment snapshot; used to calculate NRA share of
graduate enrollment at R1 institutions.

**Known limitations:**
- Same citizen/permanent-resident conflation as all IPEDS data
- EF-A does not break down by field of study (see EF-D for that, but EF-D lacks demographics)

---

## IPEDS Enrollment Major / Graduation Rates (EF-D)

**Directory:** `data/ipeds/enrollment_major/`

**What it is:** The EF-D files in this directory contain graduation rate and retention data
(GRS component), NOT enrollment by major with demographics. Despite the directory name,
these are cohort tracking files.

**Files:**
- `ef2022d.csv`, `ef2022d_rv.csv` -- 2022 graduation/retention rates
- `ef2023d.csv` -- 2023 graduation/retention rates

**Key fields:**
| Field | Definition |
|-------|-----------|
| UNITID | Institution ID |
| GRCOHRT | Graduation rate cohort size |
| UGENTERN | Undergraduate entering class |
| PGRCOHRT | Pell Grant recipient cohort |
| RRFTCT | Full-time graduation rate count |
| RRFTEX | Full-time exclusions |
| RRFTIN | Full-time inclusions |
| RET_NMF / RET_PCF | Full-time retention number / percentage |
| STUFACR | Student-to-faculty ratio |

**Known limitations:**
- These files do NOT contain enrollment by CIP/major with demographics
- The IPEDS EF-D enrollment-by-major survey exists but is not downloaded here

---

## IPEDS Student Financial Aid (SFA)

**Directory:** `data/ipeds/sfa/` (combined with enrollment_major directory)

**What it is:** Student Financial Aid survey. Reports grant, loan, and aid data by institution.

**Files:**
- `sfa2122.csv`, `sfa2122_rv.csv` -- AY 2021-22 (preliminary and revised)
- `sfa2223.csv` -- AY 2022-23
- `grad_aid_2223.csv` -- Pre-built graduate aid summary

**Key fields (sfa2223.csv, selected from 500+ columns):**
| Field | Definition |
|-------|-----------|
| UNITID | Institution ID |
| SCUGRAD | Total graduate students |
| SCUGDGSK | Graduate degree-seeking |
| SCUGFFN / SCUGFFP | First-time full-time graduate number / percentage |
| UPGRNTN / UPGRNTP / UPGRNTT / UPGRNTA | Pell Grant recipients: number / pct / total / average |
| UFLOANN / UFLOANP / UFLOANT / UFLOANA | Federal loan recipients: number / pct / total / average |
| GIS4* fields | Graduate institutional scholarships/grants by income level |
| GRN4* fields | Graduate grant aid by income level |
| NPT* fields | Net price by income level |

**Pre-built summary (grad_aid_2223.csv):**
| Field | Definition |
|-------|-----------|
| unitid | Institution ID |
| name | Institution name |
| grad_students | Total graduate students |
| receiving_grants_n | Number receiving grants |
| grant_total_amount | Total grant dollars |
| grant_avg_amount | Average grant amount |
| receiving_fed_grants_n | Number receiving federal grants |
| fed_grant_total | Total federal grant dollars |

**How it's used:** Context for understanding financial support of NRA graduate students.

---

## IPEDS Institutional Characteristics / Tuition (IC)

**Directory:** `data/ipeds/ic_tuition/`

**What it is:** Institutional Characteristics survey, tuition and fees component.

**Files:**
- `ic2023_ay.csv` -- Full IC survey for AY 2023 (200+ tuition/fee fields)
- `ic2022_rv.csv` -- Revised 2022 data
- `grad_tuition_2023.csv` -- Pre-built graduate tuition summary

**Key fields (grad_tuition_2023.csv):**
| Field | Definition |
|-------|-----------|
| unitid | Institution ID |
| name | Institution name |
| grad_instate_tuition | Graduate in-state tuition |
| grad_instate_fees | Graduate in-state fees |
| grad_outstate_tuition | Graduate out-of-state tuition |
| grad_outstate_fees | Graduate out-of-state fees |

**Key fields (ic2023_ay.csv, selected):**
| Field | Definition |
|-------|-----------|
| TUITION1-7 | Tuition charges by program type (1=in-district, 2=in-state, 3=out-of-state, 5-7=graduate equivalents) |
| FEE1-7 | Required fees by program type |
| ISPROF1-9 / OSPROF1-9 | In-state/out-of-state professional program tuition |
| CHG*AT/AF/AY fields | Comprehensive charges (tuition, fees, room and board) |

**How it's used:** Estimating the taxpayer cost of training NRA students at public universities
(NRA students typically pay out-of-state tuition, but many receive RA/TA waivers).

---

## IPEDS Human Resources / Faculty (HR)

**Directory:** `data/ipeds/hr/` (combined with enrollment_major and sfa)

**What it is:** IPEDS Human Resources survey -- staff demographics, including faculty counts
by race/ethnicity and rank.

**Files:**
- `s2022_is.csv`, `s2022_is_rv.csv` -- Fall Staff survey 2022 (instructional staff)
- `s2022_sis.csv`, `s2022_sis_rv.csv` -- Fall Staff survey 2022 (support/institutional staff)
- `sal2022_is.csv`, `sal2022_is_rv.csv` -- Faculty salary data 2022
- `faculty_demographics_2022.csv` -- Pre-built faculty demographics summary

**Key fields (s2022_is.csv):**
| Field | Definition |
|-------|-----------|
| UNITID | Institution ID |
| SISCAT | Staff category |
| FACSTAT | Faculty status |
| ARANK | Academic rank (1=Professor, 2=Associate, 3=Assistant, 4=Instructor, 5=Lecturer, 6=No rank, 7=Grad assistants) |
| HRTOTLT / HRTOTLM / HRTOTLW | Total staff / Male / Female |
| HRASIAT | Asian staff count |
| HRWHITT | White staff count |
| HRNRALT / HRNRALM / HRNRALW | Non-resident alien staff total / male / female |

**Pre-built summary (faculty_demographics_2022.csv):**
| Field | Definition |
|-------|-----------|
| unitid | Institution ID |
| name | Institution name |
| faculty_total | Total faculty |
| faculty_nra | NRA faculty count |
| faculty_asian / faculty_white / faculty_black / faculty_hispanic | Faculty by race/ethnicity |

**Key fields (sal2022_is.csv):**
| Field | Definition |
|-------|-----------|
| UNITID | Institution ID |
| ARANK | Academic rank |
| SAINSTT / SAINSTM / SAINSTW | Number on 9/10-month contract total / male / female |
| SATOTLT / SATOTLM / SATOTLW | Total salary expenditures |
| SA09MCT-SA12MCT | Number of staff at various month lengths |
| SAOUTLT / SAOUTLM / SAOUTLW | Outlays for equated 9-month contracts |

**How it's used:** Tracking NRA representation in faculty and graduate assistant roles.

---

## IPEDS Finance

**Directory:** `data/ipeds_finance/`

**What it is:** IPEDS Finance survey (F1A -- FASB reporting standards for private institutions
and public institutions using FASB). Reports revenues, expenses, assets, and liabilities.

**Source:** NCES / U.S. Department of Education

**Date range:** AY 2014-15 through AY 2022-23

**Files:**
- `f1415_f1a.csv` through `f2223_f1a.csv` -- Annual finance data
- `f2223_f1a.xlsx` -- Excel version of most recent year
- `F2223_F1A.zip`, `F2223_F1A_Dict.zip` -- Source ZIP files with data dictionary

**Key fields (selected from 300+ columns):**
| Field | Definition |
|-------|-----------|
| UNITID | Institution ID |
| F1A01 | Total current fund revenues |
| F1B01-F1B27 | Revenue by source (tuition, federal, state, local, etc.) |
| F1C011-F1C192 | Endowment and investment income |
| F1D01-F1D06 | Scholarships and fellowships |
| F1E01-F1E172 | Expenditures by functional category (instruction, research, public service, etc.) |
| F1H01-F1H03D | Revenue from tuition and fees |
| F1N01-F1N07 | Net assets / fund balances |

**Size:** ~23 MB

**How it's used:** Calculating research expenditure per NRA student; estimating how much
federal revenue flows to institutions training large NRA cohorts.

---

## IPEDS Institutional Directory (HD)

**Directory:** `data/ipeds/`

**What it is:** Institutional directory header files providing identifying information for
every IPEDS institution.

**Files:**
- `hd2018.csv`, `hd2019.csv`, `HD2023.csv`, `HD2024.csv`

**Key fields:**
| Field | Definition |
|-------|-----------|
| UNITID | Unique institution identifier |
| INSTNM | Institution name |
| ADDR / CITY / STABBR / ZIP | Address fields |
| FIPS | FIPS state code |
| OBEREG | Bureau of Economic Analysis region |
| C18BASIC / C21BASIC | Carnegie Classification (2018/2021 edition) |
| INSTCAT | Institutional category |
| HLOFFER | Highest level of offering |
| UGOFFER / GROFFER | Undergraduate / graduate offering flags |
| CONTROL | Control (1=Public, 2=Private non-profit, 3=Private for-profit) |

**How it's used:** Joining UNITID across all IPEDS surveys to institution names and
Carnegie classifications. Filtering to R1/R2 doctoral universities.

---

## NSF HERD (R&D Funding)

**Directory:** `data/herd/`

**What it is:** Higher Education Research and Development Survey. Reports total R&D
expenditures by institution, source of funds, and field.

**Source:** NSF National Center for Science and Engineering Statistics (NCSES)
- URL: https://ncses.nsf.gov/surveys/higher-education-research-development/

**Date range:** FY 2024

**Files:**
- `herd_fy2024_table13.xlsx` -- R&D expenditures by institution and source (federal, state, etc.)
- `herd_fy2024_table14.xlsx` -- R&D expenditures by institution and field
- `funding_by_university.json` -- Pre-built per-university funding summary (keyed by slug)

**funding_by_university.json structure:**
Dictionary keyed by university slug (e.g., "caltech", "njit"). Each entry contains
R&D expenditure totals by source and field.

**Size:** ~400 KB

**How it's used:** Contextualizing universities by their federal research funding levels;
showing how much R&D money flows to universities with high NRA concentrations.

---

## NSF Survey of Earned Doctorates (SED)

**Directory:** `data/nsf_sed/` and `data/nsf_sed/parsed/`

**What it is:** Annual census of all research doctorate recipients from US institutions.
Conducted by NORC for NSF/NCSES. Every PhD recipient fills out the SED at graduation.

**Source:** NSF NCSES
- URL: https://ncses.nsf.gov/surveys/earned-doctorates/
- Tables: https://ncses.nsf.gov/pubs/nsf25300/

**Date range:** 1979-2024 (varies by table)

**Raw files (`data/nsf_sed/`):**
- `all-tables.zip` -- All published SED tables
- `tables/` -- Extracted table files
- `sed_citizenship_by_field.csv` -- Long-format: Field, Citizenship, Year, Count
- `sed_top_institutions_temp_visa.csv` -- Top institutions by temp visa PhDs
- `sed_top10_countries_by_year.csv` -- Top 10 source countries over time

**Parsed files (`data/nsf_sed/parsed/`):**

| File | Description | Key Fields |
|------|-------------|------------|
| `table_1_6_broad_field_citizenship_1979_2024.csv` | Doctorates by broad field and citizenship, 1979-2024 | field_and_citizenship_status, yearly counts (1979-2024) |
| `table_1_7_major_field_citizenship_2014_2024.csv` | Doctorates by major field and citizenship, 2014-2024 | field_and_citizenship_status, yearly counts, pct_change_2014_2024 |
| `table_2_8_temp_visa_intending_stay_by_country.csv` | Temp visa holders intending to stay by country, 2018-2024 | region_country, total_2018_2024_number, total_2018_2024_pct_staying, yearly number/pct pairs |
| `table_4_1_financial_support_by_field.csv` | Primary financial support by field | field_and_support_source, total, male, female, us_citizen_or_permanent_resident, temporary_visa_holder, race/ethnicity columns |
| `table_7_5_top_institutions_temp_visa.csv` | Top institutions for temp visa PhDs (2024) | institution, rank, temp_visa_phds_2024 |
| `table_7_7_top_countries_by_field.csv` | Top source countries by field, 2014-2024 | country_and_field, yearly counts |
| `table_7_8_top_countries_2024.csv` | Top countries for 2024 | country, total, se, non_se |

**Size:** ~2.7 MB

**How it's used:** Primary source for national doctorate trends, foreign PhD share by field,
stay rate analysis, and source country identification. Powers the "National Overview" dashboard.

**Known limitations:**
- Citizenship categories match IPEDS: "US citizen or permanent resident" vs "temporary visa holder"
- Cannot identify country of birth for citizens/permanent residents
- Small numbers suppressed (shown as "D" or "S" in original tables)
- 2020-2021 data affected by COVID disruptions

---

## NSF Graduate Student Survey (GSS)

**Directory:** `data/nsf_gss/` and `data/nsf_gss/parsed/`

**What it is:** Survey of Graduate Students and Postdoctorates in Science and Engineering.
Institution-reported data on enrollment, financial support, and demographics of graduate
students in S&E departments.

**Source:** NSF NCSES
- URL: https://ncses.nsf.gov/surveys/graduate-students-postdoctorates-in-science-and-engineering/

**Date range:** 2023-2024

**Raw files (`data/nsf_gss/`):**
- `gss2024_code.sas7bdat` / `gss2024_Code.xlsx` -- 2024 codebook
- `gss2023adjusted_institutions.sas7bdat` / `.xlsx` -- 2023 adjusted institution data
- `graduate_students_postdocs_2024.zip` -- 2024 survey data
- `nsf_gss_stem_phd_programs.csv` -- STEM PhD program listing
- PDF user guides

**Parsed files (`data/nsf_gss/parsed/`):**

| File | Description |
|------|-------------|
| `gss_enrollment_by_institution.csv` | Enrollment by institution, field, and demographics |
| `gss_enrollment_summary.csv` | Summary enrollment statistics |

**Key fields (gss_enrollment_by_institution.csv):**
| Field | Definition |
|-------|-----------|
| institution_id | GSS institution ID |
| unitid | IPEDS UNITID (for joining) |
| year | Survey year |
| institution_name | Institution name |
| state | State |
| hbcu_flag | HBCU indicator |
| gss_code / hdg_code | GSS field codes |
| field_name / broad_field | Field of study |
| is_stem | STEM indicator |
| total_enrolled / total_ft / total_pt | Total / full-time / part-time enrollment |
| total_foreign | Foreign (temporary visa) students |
| total_us_domestic | US citizens and permanent residents |
| masters_enrolled / doctoral_enrolled | Enrollment by degree level |
| masters_foreign / doctoral_foreign | Foreign students by degree level |
| firsttime_ft_total / firsttime_ft_foreign | First-time full-time students |
| us_white / us_asian / us_black / us_hispanic / us_multirace / us_unknown_race | Domestic demographics |

**Key fields (nsf_gss_stem_phd_programs.csv):**
| Field | Definition |
|-------|-----------|
| Institution_Name | Institution name |
| State | State |
| UNITID | IPEDS UNITID |
| GSS_Code | GSS field code |
| GSS_Field | Field name |
| Broad_Field | Broad field grouping |
| STEM_Discipline | STEM discipline category |
| Category | Core STEM vs. STEM-related |

**Size:** ~92 MB (includes SAS files and ZIPs)

**How it's used:** Provides field-level enrollment data with foreign/domestic separation at
the institution level. More granular than IPEDS enrollment for S&E fields.

**Known limitations:**
- S&E fields only (no humanities, education, business)
- "Foreign" = temporary visa holders (same conflation as IPEDS for domestic categories)
- Adjusted institution data may differ from raw survey responses

---

## NSF Workforce Surveys (SDR, NSCG, NSB Reports)

**Directory:** `data/nsf_workforce/`

**What it is:** A collection of NSF/NCSES workforce surveys and reports that provide the
most granular citizenship and country-of-birth data available for the US PhD/STEM workforce.

**Source:** NSF NCSES
- SDR: https://ncses.nsf.gov/explore-data/microdata/doctorate-recipients
- NSCG: https://ncses.nsf.gov/explore-data/microdata/national-survey-college-graduates

### Survey of Doctorate Recipients (SDR) 2023

**Directory:** `data/nsf_workforce/sdr_2023/psd23Public/`

Public-use microdata file with 80,143 records of PhD holders in the US.

**Key files:**
- `epsd23.csv` -- CSV microdata (80,143 records)
- `Dpsd23.xlsx` -- Data dictionary
- `Ppsd23.pdf` -- Variable codebook

**Key citizenship/origin variables:**
| Variable | Definition |
|----------|-----------|
| CTZN | Citizenship: 1=native citizen, 2=naturalized, 3=permanent resident, 4=temp visa, 5=outside US |
| CTZN_DRF | Citizenship at time of doctorate receipt |
| BTHUS | Born in US (Y/N) |
| CTZFOR | Country of foreign citizenship |
| CTZUS | US citizenship (Y/N) |
| CTZUSIN | Naturalized US citizen (Y/N) |
| MGRNAT | Marital partner nativity |
| SPNAT | Spouse nativity |

**SDR 2021:** Also available in `sdr_2021/` with same structure.

**SDR 2023 Data Tables:** `sdr_2023_tables/` contains 67+ pre-built Excel tables
(nsf25321-tab*.xlsx) covering employment, salary, and demographics by citizenship.

**SDR Citizenship Findings:** `data/nsf_workforce/sdr_citizenship_findings.json` -- Pre-computed summary:
- 63.5% native-born citizens
- 17.9% naturalized citizens (foreign-born)
- 7.0% permanent residents
- 3.1% temporary visa holders
- 8.6% living outside US

### National Survey of College Graduates (NSCG) 2023

**Directory:** `data/nsf_workforce/nscg_2023/pcg23Public/`

Public-use microdata file with 94,606 records of college graduates.

**Key files:**
- `epcg23.csv` -- CSV microdata (94,606 records)
- `Dpcg23.xlsx` -- Data dictionary

**Key citizenship/origin variables (unique to NSCG):**
| Variable | Definition |
|----------|-----------|
| CTZN | Citizenship (same coding as SDR) |
| BTHUS | Born in US |
| BTHST_TOGA | Birth state/country TOGA code (specific country identification) |
| BTHRGN | Birth region |
| CTZDUAL | Dual citizenship |
| CTZFOR | Foreign citizenship |

**NSCG 2021:** Also available in `nscg_2021/`.

### NSB Reports

**NSB 2024 STEM Labor Force (`nsb_foreign_born_stem/`):**
8 Excel tables + supplemental PDF from Science & Engineering Indicators 2024.
Key tables: SLBR-25 (foreign-born STEM workers by citizenship), SLBR-26 (top birth countries),
SLBR-28 (postgrad plans by country of origin).

**NSB 2026 STEM Talent (`nsb20261_report_tables/` and `nsb20261_stem_labor/`):**
19+ tables from S&E Indicators 2026. Key tables: TAL-4 (workers by birth region),
TAL-5 (foreign-born by country), TAL-17 (stay rates by country, 2012-2023).

**Size:** ~1.2 GB total (includes microdata files)

**How it's used:** Critical for disaggregating the IPEDS "domestic" category. The SDR finding
that 28% of "domestic" PhDs are foreign-born is a core finding of this project. NSCG provides
country-level birth data (BTHST_TOGA) that no other federal survey offers.

---

## Degree-level coverage — read this before quoting a master's/doctoral split

Degree level (`phd` / `masters`) comes from each institution's OAI feed. Only
seven repositories have a metadata prefix that exposes it, so coverage varies
enormously — and until 2026-08-20 nothing recorded that.

`degree_label_coverage` is now written into every `site/data/{stem,nonstem}/
<key>.json` and into `pipeline/universities.json`, as a number so a check can
assert on it. Regenerate with `scripts/label_degree_coverage.py --write`.

**Lowest coverage (of 207 corpora; 10 sit below 50%):**

| university | STEM | non-STEM |
|---|---|---|
| montana_state | 24.3% | 18.2% |
| bu | 32.2% | 39.5% |
| gmu | 38.1% | 51.6% |
| cornell | 41.8% | 47.5% |
| mit | 47.8% | 41.9% |
| utk | 49.8% | 56.5% |
| ucf | 76.9% | 55.0% |
| ttu | 55.0% | 57.6% |
| rice | 56.3% | 65.3% |

A master's/doctoral split for these institutions describes only the labelled
share, not the whole corpus. Montana State at 18.2% is the extreme, but MIT and
Cornell are also under 50%, which is easy to miss because they are otherwise
well covered.

**This is a source limitation, not a defect.** The feeds for the remainder do
not publish degree level. Three full repository walks (gmu, uoregon, cmu)
returned zero additional records. Montana State has no degree-enrichment entry
at all — adding one means identifying which prefix its repository exposes
degree level under, which is new configuration rather than a fix.

## DOL H-1B Disclosure Data

**Directory:** `data/h1b/`

**What it is:** Labor Condition Application (LCA) disclosure data for H-1B visa petitions.
Every H-1B employer must file an LCA with the Department of Labor.

**Source:** U.S. Department of Labor, Office of Foreign Labor Certification
- URL: https://www.dol.gov/agencies/eta/foreign-labor/performance

**Files:**
- `LCA_Disclosure_Data_FY2024_Q4.xlsx` -- FY2024 Q4 (598,831 rows, 97 columns)
- `LCA_Disclosure_Data_FY2025_Q1.xlsx` -- FY2025 Q1 (1,042,871 rows, 97 columns)
- `README_DATA_SUMMARY.md` -- Detailed column documentation

**Backup and local footprint.** The 32 `.xlsx` source files (3.5 GiB) are the
only thing here worth preserving, and all 32 are mirrored byte-for-byte at
`s3://phd-demographics-raw-data/data/h1b/lca/` (verified 2026-08-20: 32 of 32,
zero size mismatches).

`data/h1b/lca/csv_cache/` is **DERIVED and must never be backed up**. It is a
one-time XLSX-to-CSV conversion built by `pipeline/step3_parse_federal.py` so
DuckDB can query the LCA data; the code checks `if not csv_path.exists()` and
rebuilds any missing file automatically. It reached 5.9 GB, which is larger
than the source it is derived from, and an earlier plan to upload it to S3 was
abandoned as pure waste. It was deleted on 2026-08-20 to relieve a disk that
had reached 100% full. Delete it again whenever space is needed: the cost is
one conversion pass, and the inputs are both local and on S3.

**Key fields (97 total, selected):**
| Field | Definition |
|-------|-----------|
| CASE_NUMBER | Unique case identifier |
| CASE_STATUS | Certified, Certified-Withdrawn, Withdrawn, Denied |
| VISA_CLASS | H-1B, E-3 Australian, H-1B1 Chile/Singapore |
| JOB_TITLE | Specific job title |
| SOC_CODE / SOC_TITLE | Standard Occupational Classification |
| EMPLOYER_NAME | Petitioning employer |
| EMPLOYER_CITY / STATE | Employer location |
| NAICS_CODE | Industry classification |
| WAGE_RATE_OF_PAY_FROM / TO | Offered wage range |
| WAGE_UNIT_OF_PAY | Year, Hour, Week, etc. |
| PREVAILING_WAGE / PW_WAGE_LEVEL | Prevailing wage and level (I-IV) |
| WORKSITE_CITY / STATE | Work location |
| H-1B_DEPENDENT | Employer H-1B dependency flag |
| TOTAL_WORKER_POSITIONS | Number of workers requested |

**Size:** ~176 MB

**How it's used:** Tracking post-graduation employment pipeline from PhD to H-1B.
Cross-referencing employers hiring PhDs with university NRA concentrations.

**Known limitations:**
- LCA data covers applications, not actual visa grants
- Does not include country of origin for the worker
- One LCA can cover multiple worker positions
- Includes all H-1B, not just PhD-level positions

---

## ICE SEVP / SEVIS Data

**Directory:** `data/sevp/`

**What it is:** Student and Exchange Visitor Information System data from DHS/ICE.
Tracks all F-1 and M-1 visa holders in the US.

**Source:** DHS Student and Exchange Visitor Program (SEVP)
- URL: https://studyinthestates.dhs.gov/sevis-data-mapping-tool

**CSV files -- Country-Level Summary (monthly snapshots, ~229 rows, 72 columns each):**
- `sevis_data_mapping_jan2024.csv` through `sevis_data_mapping_mar2026.csv`

**CSV schema:**
| Field | Definition |
|-------|-----------|
| Country of Citizenship | Country name |
| Continent | Continent |
| Region | Sub-region |
| Active Students | Total active F-1/M-1 records |
| Male / Female | Gender counts |
| Associate through Secondary | Counts by education level (Associate, Bachelors, Doctorate, Flight School, High School, Language Training, Masters, Other, Other Vocational School, Primary, Secondary) |
| AK through WY | Counts by US state (55 columns including DC, GU, MP, PR, VI) |

**CSV files -- STEM School-Level (monthly, ~28,000+ rows, 6 columns):**
- `sevis_data_mapping_jan2024_stem.csv` through `sevis_data_mapping_mar2026_stem.csv`

**STEM CSV schema:**
| Field | Definition |
|-------|-----------|
| State | Full state name |
| Abbrv | State abbreviation |
| Student Education Level | Degree level |
| CoC | Country of Citizenship |
| Sex | Male/Female |
| Count of Active STEM Students | Count |

**PDF reports:** Annual "SEVIS By The Numbers" reports (2022-2024), OPT/STEM OPT/CPT
authorization time series, top employers, top schools, certified school list.

**Size:** ~15 MB

**How it's used:** Current snapshot of international student population by country and
education level. China data point: 229,463 active Chinese students as of March 2026.
STEM breakdowns show concentration in doctoral programs.

---

## USAspending Federal Grants

**Directory:** `data/usaspending/`

**What it is:** Federal grant awards to universities, sourced from USAspending.gov.

**Source:** U.S. Department of the Treasury / USAspending.gov
- URL: https://www.usaspending.gov/

**Files:**
- `top_university_grants.csv`

**Fields:**
| Field | Definition |
|-------|-----------|
| name | University name |
| uei | Unique Entity Identifier (federal contractor ID) |
| total_grants | Total federal grant dollars |

**Size:** ~8 KB

**How it's used:** Ranking universities by federal funding to contextualize which
high-NRA institutions receive the most taxpayer dollars.

---

## Census American Community Survey (ACS)

**Directory:** `data/census_acs/`

**What it is:** Pre-built summary of ACS data on doctorate holders in the US population.

**Source:** U.S. Census Bureau, American Community Survey 2022
- URL: https://data.census.gov/

**Files:**
- `acs_2022_summary.json`

**Fields (JSON keys):**
| Key | Definition |
|-----|-----------|
| total_doctorate_holders | Total PhD holders in US |
| total_population | Reference population |
| native_born | Native-born PhD holders |
| foreign_born | Foreign-born PhD holders |
| naturalized_citizens | Foreign-born who became citizens |
| non_citizens | Foreign-born non-citizens |
| foreign_born_grad_degree | Foreign-born with graduate degrees |

**Size:** ~4 KB

**How it's used:** Provides population-level context for foreign-born PhD concentration.

---

## Dissertation Metadata (Scraped)

### Western US Dissertations (and National Universities)

**Directory:** `data/western_us_dissertations/`

**What it is:** Dissertation/thesis metadata harvested via OAI-PMH from university
digital repositories (101 tracked in `pipeline/universities.json`, 104 configured in
`scripts/scrape_oai_etds.py`). Despite the directory name, covers universities nationally
(Cornell, Yale, CMU, Columbia, WVU, Clemson, etc.).

**Files:** 110 CSV files (one per repository config) + JSON checkpoint files. ~1.4 million total rows.
Examples: `cornell_etds.csv`, `yale_etds.csv`, `cmu_etds.csv`, `bu_etds.csv`, `clemson_etds.csv`

**Common fields:**
| Field | Definition |
|-------|-----------|
| repo | Repository identifier |
| university | University name |
| identifier | OAI record identifier |
| title | Dissertation/thesis title |
| creator | Author name |
| contributor | Advisor(s) |
| date | Completion date |
| subject | Subject keywords |
| description | Abstract |
| type | Document type (thesis, dissertation) |
| format | File format |
| language | Language |
| oai_set | OAI set membership |
| url | Full-text URL |

**Size:** ~981 MB

### UW Dissertations

**Directory:** `data/uw_dissertations/`

**What it is:** University of Washington Seattle dissertations, scraped from ResearchWorks.

**Files:** `uw_etd_metadata.csv`, `uw_dissertations_metadata.csv`

**Fields:**
| Field | Definition |
|-------|-----------|
| uuid | Unique record ID |
| url | Repository URL |
| department | Academic department |
| title | Dissertation title |
| author | Author name |
| date | Completion date |
| keywords | Subject keywords |
| description | Abstract |
| degree_type | PhD, MS, etc. |

### UC Dissertations

**Directory:** `data/uc_dissertations/`

**What it is:** University of California system dissertations from eScholarship.

**Files:** `uc_dissertations_metadata.csv`, `uc_stem_dissertations.csv`

**Fields:**
| Field | Definition |
|-------|-----------|
| campus_set | UC campus OAI set |
| campus_name | Campus name (Berkeley, UCLA, etc.) |
| identifier | Record ID |
| title | Dissertation title |
| creator | Author name |
| contributor | Advisor(s) |
| date | Completion date |
| subject | Subject keywords |
| escholarship_url | eScholarship page URL |
| pdf_url | PDF download URL |
| degree_type | PhD, EdD, etc. |

### Stanford Dissertations

**Directory:** `data/stanford_dissertations/`

**What it is:** Stanford University dissertations from Stanford Digital Repository (SDR API).

**Files:** `stanford_dissertations_metadata.csv` (15,822 records)

**Fields:**
| Field | Definition |
|-------|-----------|
| druid | Stanford Digital Repository unique ID |
| purl | Persistent URL |
| title | Dissertation title |
| author | Author name |
| advisor | Advisor name |
| date | Completion date |
| genre | Document genre |
| subject | Subject keywords |
| department | Department |
| degree | Degree type |
| description | Abstract |

### Caltech Dissertations

**Directory:** `data/caltech_dissertations/`

**What it is:** Caltech theses plus department alumni lists.

**Files:** `caltech_theses_metadata.csv` (12,387 records), department alumni CSVs
(`cms_alumni.csv`, `ee_alumni.csv`, `galcit_alumni.csv`, `mce_alumni.csv`, `mede_alumni.csv`),
`caltech_dept_alumni_combined.csv`, dashboard/classification JSONs.

### Oregon/Washington Dissertations

**Directory:** `data/or_wa_dissertations/`

**What it is:** Dissertations from Portland State, University of Oregon, and Washington State.

**Files:** `pdxscholar_dissertations.csv`, `pdxscholar_enriched.csv`, `uoregon_dissertations.csv`,
`wsu_dissertations.csv`

**Fields (wsu_dissertations.csv):**
| Field | Definition |
|-------|-----------|
| id | Record ID |
| url | Repository URL |
| repo | Repository name |
| title | Dissertation title |
| author | Author name |
| date | Completion date |
| keywords | Subject keywords |
| language | Language |
| description | Abstract |
| institution | University name |
| doi | DOI if available |
| pdf_url | PDF URL |
| type | Document type |

**How scraped data is used:** Author names are classified using ML/rule-based name
origin classifiers to estimate the national origin composition of PhD recipients,
particularly identifying Chinese-origin names. This supplements IPEDS data which only
reports "NRA" without country specificity.

**Known limitations of scraped data:**
- Name-based classification is probabilistic, not determinitive
- Repositories vary in completeness (some have all theses, others only recent ones)
- Not all theses are doctoral dissertations (includes masters theses)
- Metadata quality varies (missing dates, departments, or degree types)
- No citizenship information -- only author name as a proxy

---

## Finished Data Archive

**Directory:** `data/finished_data/`

**What it is:** Immutable archive copies of completed scrape outputs. If a working copy
is lost or corrupted, restore from here.

**Files:** 16 datasets, 285,544 total rows (see MANIFEST.txt for checksums).
Includes UC all campuses (80,617 rows), Stanford (15,822), Caltech (12,387),
Portland State, Arizona, BYU, Utah State, and more.

Each file has SHA-256 checksums recorded in `MANIFEST.txt`.

**Size:** ~200 MB

---

## Site Data (Generated Per-University JSONs)

**Directory:** `site/data/stem/` and `site/data/nonstem/`

**What it is:** Pre-computed JSON files (one per university) powering the site's
name-list viewer pages. Generated by classification scripts from scraped dissertation data.

**Files:** 102 JSON files in each directory (stem/ and nonstem/).
Includes `_search.json` (search index) plus one file per university
(e.g., `binghamton.json`, `boise_state.json`, `cornell.json`).

**How it's used:** Loaded by `stem.html` and `non_stem.html` to display classified
name lists with department, year, and origin estimates.

---

## Additional Files

| File | Location | Description |
|------|----------|-------------|
| `master_stem_phd_institutions.csv` | `data/` | Master list of STEM PhD-granting institutions |
| `dashboard_data.json` | `data/` and `site/` | Pre-built dashboard data for site |
| `gemini_exported_sheet.csv/.xlsx` | `data/` | Exported analysis sheet |
| `njit_chinese_qa.csv/.txt` | `data/` | NJIT-specific QA data |
| `stevens_phd_recipients.csv` | `data/` | Stevens Institute PhD data |
| `qa_report.csv` | `data/` | Quality assurance report |
| Various `*_report.txt` files | `data/` | Classification and analysis reports |
| `university_repositories.md` | `data/` | List of university OAI-PMH endpoints |

