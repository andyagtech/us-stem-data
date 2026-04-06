# Data Index

Machine-readable catalog of all data files in this project. For use by AI agents and programmatic access.

Last updated: 2026-04-05

## Quick Reference
- Total datasets: ~85 distinct dataset families (1,200+ individual files)
- Countries covered: 200+ (all visa-issuing nations; deep focus on China, India, South Korea, Taiwan, Iran, Saudi Arabia)
- Time range: 1958-2026
- Key agencies: NCES/IPEDS, NSF/NCSES, DHS/ICE/SEVP, USCIS, State Dept, DOL, HESA (UK), IRCC (Canada)

## Table of Contents
1. [Student Enrollment (SEVIS, IPEDS)](#1-student-enrollment)
2. [PhD Production (NSF SED, IPEDS Completions)](#2-phd-production)
3. [Work Authorization (OPT, CPT, H-1B, LCA, PERM)](#3-work-authorization)
4. [Visa Issuances (State Dept NIV, Immigrant Visas)](#4-visa-issuances)
5. [Green Cards & Naturalization (EB, DHS Yearbook)](#5-green-cards--naturalization)
6. [University Research (HERD Funding)](#6-university-research)
7. [International (Canada, UK, EU, India, China, Mexico)](#7-international-comparisons)
8. [Medical Education (AAMC, NRMP, ECFMG)](#8-medical-education)
9. [VWP & Overstay](#9-vwp--overstay)
10. [NSF Workforce Surveys (SDR, NSCG, GSS)](#10-nsf-workforce-surveys)
11. [Dissertation Harvest (ETDs)](#11-dissertation-harvest)
12. [Pipeline / Processed Data](#12-pipeline--processed-data)
13. [Analysis Outputs](#13-analysis-outputs)
14. [Site Data (Generated for Web)](#14-site-data)
15. [Reference & Taxonomy](#15-reference--taxonomy)
16. [Financial (IPEDS Finance, FSA, SHEF, USASpending)](#16-financial)

---

## 1. Student Enrollment

### SEVP / SEVIS Data Mapping (Monthly Snapshots)

Active F/M student records by country of citizenship, gender, education level, and U.S. state.

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/sevp/sevis_data_mapping_jan2024.csv` | CSV | Active students by country, gender, level, state | country x state x level x gender | Jan 2024 | DHS/ICE SEVP |
| `data/sevp/sevis_data_mapping_jan2024_stem.csv` | CSV | Active STEM students by country, gender, level, state | country x state x level x gender | Jan 2024 | DHS/ICE SEVP |
| `data/sevp/sevis_data_mapping_dec2024.csv` | CSV | Active students snapshot | country x state x level x gender | Dec 2024 | DHS/ICE SEVP |
| `data/sevp/sevis_data_mapping_dec2024_stem.csv` | CSV | Active STEM students snapshot | country x state x level x gender | Dec 2024 | DHS/ICE SEVP |
| `data/sevp/sevis_data_mapping_aug2025.csv` | CSV | Active students snapshot | country x state x level x gender | Aug 2025 | DHS/ICE SEVP |
| `data/sevp/sevis_data_mapping_aug2025_stem.csv` | CSV | Active STEM students snapshot | country x state x level x gender | Aug 2025 | DHS/ICE SEVP |
| `data/sevp/sevis_data_mapping_jan2026.csv` | CSV | Active students snapshot | country x state x level x gender | Jan 2026 | DHS/ICE SEVP |
| `data/sevp/sevis_data_mapping_jan2026_stem.csv` | CSV | Active STEM students snapshot | country x state x level x gender | Jan 2026 | DHS/ICE SEVP |
| `data/sevp/sevis_data_mapping_feb2026.csv` | CSV | Active students snapshot | country x state x level x gender | Feb 2026 | DHS/ICE SEVP |
| `data/sevp/sevis_data_mapping_feb2026_stem.csv` | CSV | Active STEM students snapshot | country x state x level x gender | Feb 2026 | DHS/ICE SEVP |
| `data/sevp/sevis_data_mapping_mar2026.csv` | CSV | Active students snapshot | country x state x level x gender | Mar 2026 | DHS/ICE SEVP |
| `data/sevp/sevis_data_mapping_mar2026_stem.csv` | CSV | Active STEM students snapshot | country x state x level x gender | Mar 2026 | DHS/ICE SEVP |
| `data/sevp/sevis_data_mapping_dec2025.csv` | CSV | Active students snapshot | country x state x level x gender | Dec 2025 | DHS/ICE SEVP |

Key fields: `Country of Citizenship, Continent, Region, Active Students, Male, Female, Associate, Bachelors, Doctorate, Masters, [state columns AK..WY]`

STEM variant key fields: `State, Abbrv, Student Education Level, CoC, Sex, Count of Active STEM Students`

### SEVP Reports (PDF)

| File | Format | Description | Coverage | Source |
|------|--------|-------------|----------|--------|
| `data/sevp/2022_sevis_by_the_numbers.pdf` | PDF | Annual SEVIS statistics overview | 2022 | DHS/ICE SEVP |
| `data/sevp/2023_sevis_by_the_numbers.pdf` | PDF | Annual SEVIS statistics overview | 2023 | DHS/ICE SEVP |
| `data/sevp/2024_sevis_by_the_numbers.pdf` | PDF | Annual SEVIS statistics overview | 2024 | DHS/ICE SEVP |
| `data/sevp/2022_all_students_by_coc.pdf` | PDF | Students by country of citizenship | 2022 | DHS/ICE SEVP |
| `data/sevp/2023_all_students_by_coc.pdf` | PDF | Students by country of citizenship | 2023 | DHS/ICE SEVP |
| `data/sevp/2024_all_countries_active_records.pdf` | PDF | All countries active student records | 2024 | DHS/ICE SEVP |
| `data/sevp/2024_all_countries_stemopt.pdf` | PDF | STEM OPT by country | 2024 | DHS/ICE SEVP |
| `data/sevp/2024_top100_schools_stemopt.pdf` | PDF | Top 100 schools by STEM OPT count | 2024 | DHS/ICE SEVP |
| `data/sevp/2024_top200_employers_opt_stemopt.pdf` | PDF | Top 200 OPT/STEM OPT employers | 2024 | DHS/ICE SEVP |
| `data/sevp/2024_total_sevis_records_opt_cpt_stemopt.pdf` | PDF | Total SEVIS records with OPT/CPT/STEM OPT | 2024 | DHS/ICE SEVP |
| `data/sevp/2024_stem_designated_degree_list.pdf` | PDF | STEM-designated CIP code list | 2024 | DHS/ICE SEVP |
| `data/sevp/opt_growth_2007_2022.pdf` | PDF | OPT program growth over time | 2007-2022 | DHS/ICE SEVP |
| `data/sevp/opt_stemopt_cpt_authorizations_2007_2024.pdf` | PDF | OPT/STEM OPT/CPT authorization counts | 2007-2024 | DHS/ICE SEVP |
| `data/sevp/sevp_certified_school_list.pdf` | PDF | SEVP-certified school list | 2024 | DHS/ICE SEVP |

### IPEDS Enrollment

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/ipeds/enrollment/ef2023a.csv` | CSV | Fall enrollment by race/ethnicity, gender, level, attendance | institution x race x gender x level | Fall 2023 | NCES/IPEDS |
| `data/ipeds/enrollment/ef2022a.csv` | CSV | Fall enrollment (original) | institution x race x gender x level | Fall 2022 | NCES/IPEDS |
| `data/ipeds/enrollment/ef2022a_rv.csv` | CSV | Fall enrollment (revised) | institution x race x gender x level | Fall 2022 | NCES/IPEDS |
| `data/ipeds/enrollment/grad_enrollment_demographics_2022.csv` | CSV | Graduate enrollment demographics | institution x race x gender | Fall 2022 | NCES/IPEDS |
| `data/ipeds/enrollment_major/ef2023d.csv` | CSV | Fall enrollment by major field (CIP) | institution x CIP x race x level | Fall 2023 | NCES/IPEDS |
| `data/ipeds/enrollment_major/ef2022d.csv` | CSV | Fall enrollment by major field | institution x CIP x race x level | Fall 2022 | NCES/IPEDS |
| `data/ipeds/enrollment_major/ef2022d_rv.csv` | CSV | Fall enrollment by major field (revised) | institution x CIP x race x level | Fall 2022 | NCES/IPEDS |

Key fields: `UNITID, EFALEVEL, LINE, SECTION, LSTUDY, EFTOTLT, EFAIANT, EFASIAT, EFBKAAT, EFHISPT, EFNHPIT, EFWHITT, EF2MORT, EFUNKNT, EFNRALT` (race/ethnicity enrollment counts including nonresident alien)

### IPEDS Institutional Characteristics

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/ipeds/HD2024.csv` | CSV | Institution directory (names, addresses, sectors, Carnegie class) | institution | 2024 | NCES/IPEDS |
| `data/ipeds/hd2002.csv` - `HD2023.csv` | CSV | Institution directory (23 annual files, 2002-2024) | institution x year | 2002-2024 | NCES/IPEDS |
| `data/ipeds/ic1980.csv` - `ic2001_ay.csv` | CSV | Early institutional characteristics | institution | 1980-2001 | NCES/IPEDS |
| `data/ipeds/dictionaries/C2023_a_dict.xlsx` | XLSX | Completions data dictionary | n/a | 2023 | NCES/IPEDS |
| `data/ipeds/dictionaries/HD2023_dict.xlsx` | XLSX | Institution directory data dictionary | n/a | 2023 | NCES/IPEDS |

Key fields (HD): `UNITID, INSTNM, CITY, STABBR, SECTOR, ICLEVEL, CONTROL, HLOFFER, C21BASIC (Carnegie), HBCU, MEDICAL, TRIBAL, LOCALE`

---

## 2. PhD Production

### IPEDS Completions (Raw)

Annual degree completions by institution, CIP code, award level, race/ethnicity, and gender.

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/ipeds/C2024_a.csv` | CSV | Completions by CIP, race, gender, award level | institution x CIP x race x gender x award | 2023-24 | NCES/IPEDS |
| `data/ipeds/c1984_cip.csv` - `c1994_cip.csv` | CSV | Early completions (10 files, 1984-1994) | institution x CIP | 1984-1994 | NCES/IPEDS |
| `data/ipeds/c9596_a.csv` - `c9899_a.csv` | CSV | Mid-era completions (4 files, 1995-1999) | institution x CIP x race | 1995-1999 | NCES/IPEDS |
| `data/ipeds/c2000_a.csv` - `C2023_a.csv` | CSV | Modern completions (48 files incl. _rv revisions, 2000-2023) | institution x CIP x race x gender x award | 2000-2023 | NCES/IPEDS |

Key fields: `UNITID, CIPCODE, MAJORNUM, AWLEVEL, CTOTALT, CTOTALM, CTOTALW, CAIANT, CASIAT, CBKAAT, CHISPT, CNHPIT, CWHITT, C2MORT, CUNKNT, CNRALT` (CNRALT = nonresident alien)

### IPEDS Completions (Filtered/Processed)

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/ipeds/filtered/ipeds_stem_phd_1984.csv` - `ipeds_stem_phd_2024.csv` | CSV | STEM PhD completions only (37 annual files) | institution x STEM field | 1984-2024 | NCES/IPEDS (filtered) |
| `data/ipeds/ipeds_stem_phd_all_years.csv` | CSV | Consolidated STEM PhD completions across all years | institution x STEM field x year | 1984-2024 | NCES/IPEDS (filtered) |
| `data/ipeds/ipeds_stem_phd_demographics_by_year.csv` | CSV | National STEM PhD demographics time series | year x race/ethnicity | 1984-2024 | NCES/IPEDS (aggregated) |
| `data/ipeds/ipeds_stem_phd_programs.csv` | CSV | List of institutions with STEM PhD programs | institution x STEM discipline | current | NCES/IPEDS (derived) |

Key fields (filtered): `Year, UNITID, State, University, City, STEM_Discipline, Category, CIP_2Digit, CIP_Codes_Detail, Institution_URL`

Key fields (demographics): `Year, Total_Men, Total_Women, Total, White, Asian, NonresAlien_International, Hispanic, Black, [pct columns]`

### NSF Survey of Earned Doctorates (SED)

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/nsf_sed/tables/nsf25349-tab*.xlsx` | XLSX | Raw SED tables (97 files, tables 1-1 through 9-19) | varies by table | 1958-2024 | NSF/NCSES |
| `data/nsf_sed/tables/_index.txt` | TXT | Table descriptions index | n/a | n/a | NSF/NCSES |
| `data/nsf_sed/parsed/table_1_6_broad_field_citizenship_1979_2024.csv` | CSV | PhD recipients by broad field and citizenship status | field x citizenship | 1979-2024 | NSF/NCSES (parsed) |
| `data/nsf_sed/parsed/table_1_7_major_field_citizenship_2014_2024.csv` | CSV | PhD recipients by major field and citizenship | field x citizenship | 2014-2024 | NSF/NCSES (parsed) |
| `data/nsf_sed/parsed/table_2_8_temp_visa_intending_stay_by_country.csv` | CSV | Temp visa holders intending to stay, by country | country x year | 2018-2024 | NSF/NCSES (parsed) |
| `data/nsf_sed/parsed/table_4_1_financial_support_by_field.csv` | CSV | Primary financial support source by field, sex, citizenship, race | field x support_source x demographics | 2024 | NSF/NCSES (parsed) |
| `data/nsf_sed/parsed/table_7_5_top_institutions_temp_visa.csv` | CSV | Top institutions awarding PhDs to temp visa holders | institution (ranked) | 2024 | NSF/NCSES (parsed) |
| `data/nsf_sed/parsed/table_7_7_top_countries_by_field.csv` | CSV | Top countries of citizenship by field | country x field | 2024 | NSF/NCSES (parsed) |
| `data/nsf_sed/parsed/table_7_8_top_countries_2024.csv` | CSV | Top countries of citizenship overall | country (ranked) | 2024 | NSF/NCSES (parsed) |
| `data/nsf_sed/sed_citizenship_by_field.csv` | CSV | PhD recipients by citizenship and field | field x citizenship | multi-year | NSF/NCSES (parsed) |
| `data/nsf_sed/sed_top_institutions_temp_visa.csv` | CSV | Top institutions for temp visa PhDs | institution (ranked) | multi-year | NSF/NCSES (parsed) |
| `data/nsf_sed/sed_top10_countries_by_year.csv` | CSV | Top 10 countries of PhD recipients by year | country x year | multi-year | NSF/NCSES (parsed) |

Key fields (table_2_8): `region_country, total_2018_2024_number, total_2018_2024_pct_staying, [year]_number, [year]_pct_staying`

### NSF Graduate Students & Postdoctorates (GSS)

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/nsf_gss/gss2023adjusted_institutions.xlsx` | XLSX | GSS institutional-level data | institution x field | 2023 | NSF/NCSES GSS |
| `data/nsf_gss/gss2024_Code.xlsx` | XLSX | GSS survey codebook | n/a | 2024 | NSF/NCSES GSS |
| `data/nsf_gss/nsf_gss_stem_phd_programs.csv` | CSV | STEM PhD programs from GSS | institution x field | 2024 | NSF/NCSES GSS (derived) |
| `data/nsf_gss/parsed/gss_enrollment_by_institution.csv` | CSV | Graduate enrollment by institution and field | institution x field x enrollment type | 2024 | NSF/NCSES GSS (parsed) |
| `data/nsf_gss/parsed/gss_enrollment_summary.csv` | CSV | Graduate enrollment summary statistics | field | 2024 | NSF/NCSES GSS (parsed) |
| `data/nsf_gss/2023_GSS_Adjusted_Institutions_User_Guide.pdf` | PDF | GSS user guide | n/a | 2023 | NSF/NCSES GSS |
| `data/nsf_gss/gss-2023-puf-user-guide.pdf` | PDF | Public use file user guide | n/a | 2023 | NSF/NCSES GSS |

Key fields (enrollment_by_institution): `institution_id, unitid, year, institution_name, state, hbcu_flag, field_name, broad_field, is_stem, total_enrolled, total_ft, total_pt, total_foreign, total_us_domestic, masters_enrolled, doctoral_enrolled, firsttime_ft_total, firsttime_ft_foreign`

---

## 3. Work Authorization

### H-1B Employer Data Hub

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/h1b/h1b_datahub_fy2010.csv` - `h1b_datahub_fy2026.csv` | CSV | H-1B petition decisions by employer (17 files + checkthis variants) | employer x fiscal year | FY2010-FY2026 | USCIS |

Key fields: `Fiscal Year, Employer (Petitioner) Name, Tax ID, Industry (NAICS) Code, Petitioner City, Petitioner State, New Employment Approval, New Employment Denial, Continuation Approval, Continuation Denial, Change of Employer Approval, Amended Approval` (UTF-16LE encoded)

### H-1B Aggregated by University

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/h1b/h1b_by_university.json` | JSON | H-1B petition data aggregated per university | university | multi-year | USCIS (derived) |

### LCA (Labor Condition Applications)

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/h1b/lca/lca_FY2013.xlsx` - `lca_FY2026_Q1.xlsx` | XLSX | Raw LCA disclosure data (33 files, quarterly + annual) | application-level | FY2013-FY2026 Q1 | DOL/OFLC |
| `data/h1b/LCA_Disclosure_Data_FY2024_Q4.xlsx` | XLSX | LCA disclosure (top-level copy) | application-level | FY2024 Q4 | DOL/OFLC |
| `data/h1b/LCA_Disclosure_Data_FY2025_Q1.xlsx` | XLSX | LCA disclosure (top-level copy) | application-level | FY2025 Q1 | DOL/OFLC |
| `data/h1b/lca_by_university.json` | JSON | LCA filings aggregated per university | university | multi-year | DOL/OFLC (derived) |

### PERM (Permanent Labor Certification)

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/h1b/perm_fy2024_q4.xlsx` | XLSX | PERM disclosure data | application-level | FY2024 Q4 | DOL/OFLC |
| `data/h1b/perm_by_university.json` | JSON | PERM filings aggregated per university | university | multi-year | DOL/OFLC (derived) |

### OPT / STEM OPT / CPT

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/h1b/national_opt_trends.json` | JSON | National OPT/STEM OPT/CPT authorization counts by year | year x authorization type | 2007-2024 | DHS/ICE SEVP (derived) |
| `data/h1b/opt_by_university.json` | JSON | OPT participation aggregated per university | university | multi-year | DHS/ICE SEVP (derived) |
| `data/h1b/opt_by_school.json` | JSON | OPT/STEM OPT counts by school for select years | school x year | 2019, 2022 | DHS/ICE SEVP (derived) |
| `data/h1b/TotalNumberAnnualOPT_STEM_OPT_CPT_AuthorizationsWithEmpStartDatesDuringIndicatedCY2007_2024.pdf` | PDF | Total annual OPT/STEM OPT/CPT authorizations | year | 2007-2024 | DHS/ICE SEVP |

### SEVP OPT School Rankings (PDF)

| File | Format | Description | Coverage | Source |
|------|--------|-------------|----------|--------|
| `data/h1b/17_0623_hsi_sevp-sevis-btn-2017-top100-prepost-opt-schools.pdf` | PDF | Top 100 schools pre/post OPT | 2017 | DHS/ICE SEVP |
| `data/h1b/17_0623_hsi_sevp-sevis-btn-2017-top100-stem-opt-schools.pdf` | PDF | Top 100 schools STEM OPT | 2017 | DHS/ICE SEVP |
| `data/h1b/*_top100_*opt*.pdf` | PDF | Annual top-100 OPT/STEM OPT school PDFs (14 files, 2017-2024) | annual | 2017-2024 | DHS/ICE SEVP |
| `data/h1b/2024_Top200_Schools_OPT_STEM_OPT_Students.pdf` | PDF | Top 200 schools OPT/STEM OPT | 2024 | DHS/ICE SEVP |
| `data/h1b/sevis_btn_2024.pdf` | PDF | SEVIS by the numbers 2024 | 2024 | DHS/ICE SEVP |

### J-1 Exchange Visitor

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/h1b/j1_participation_cy2015_2025.xlsx` | XLSX | J-1 participation by category and year | category x year | CY2015-2025 | State Dept |

---

## 4. Visa Issuances

### State Department NIV (Nonimmigrant Visas)

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/h1b/state_dept/FYs97-24_NIVDetailTable.xlsx` | XLSX | NIV issuances by visa class and nationality | country x visa class x year | FY1997-2024 | State Dept |
| `data/h1b/state_dept/niv_by_country_fy2024.csv` | CSV | NIV issuances by country for FY2024 | country x visa class | FY2024 | State Dept |
| `data/h1b/state_dept/niv_timeseries_key_countries.csv` | CSV | F-1, H-1B, J-1 issuances time series for key countries | country x visa type x year | 2010-2024 | State Dept (derived) |
| `data/h1b/state_dept/FY2024AnnualReport_TableXVB_NIVbyClass.pdf` | PDF | NIV issuances by class | visa class | FY2024 | State Dept |
| `data/h1b/national_visa_trends.json` | JSON | National visa issuance trends (F-1, J-1, H-1B, O-1, L-1 + petitions) | visa type x year/country | multi-year | State Dept (derived) |

Key fields (niv_timeseries): `fiscal_year, country, F1_issuances, H1B_issuances, J1_issuances`

### B-Visa Refusal Rates

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/h1b/state_dept/b_visa_refusal_rates_fy23.csv` - `fy25.csv` | CSV | B-visa refusal rates by country (3 files) | country | FY2023-2025 | State Dept |
| `data/h1b/state_dept/refusal_rates_FY19.pdf` - `FY25.pdf` | PDF | Visa refusal rate reports (7 files) | country | FY2019-2025 | State Dept |

Key fields: `country, refusal_rate_pct`

### Immigrant Visas

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/h1b/state_dept/immigrant_visas_by_country_fy2015_2024.csv` | CSV | Total immigrant visa issuances by country | country x year | FY2015-2024 | State Dept |
| `data/h1b/state_dept/eb_visas_by_country_fy2024.csv` | CSV | Employment-based (EB) visa issuances by preference category | country x EB category | FY2024 | State Dept |
| `data/h1b/state_dept/FY2024_TableV_IV_by_preference.pdf` | PDF | Immigrant visas by preference category | preference x country | FY2024 | State Dept |
| `data/h1b/state_dept/FY2024AnnualReport_TableXIII_IVbyChargeability.pdf` | PDF | Immigrant visas by chargeability | country | FY2024 | State Dept |

Key fields (eb_visas): `country, EB1, EB2, EB3, EB3_other_workers, EB3_total, EB4, EB4_religious, EB4_total`

Key fields (immigrant_visas): `country, FY2015, FY2016, ..., FY2024`

---

## 5. Green Cards & Naturalization

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/vwp/dhs_lpr_fy2023.xlsx` | XLSX | Lawful permanent resident (green card) statistics | country x category | FY2023 | DHS Yearbook |
| `data/vwp/dhs_naturalizations_fy2023.xlsx` | XLSX | Naturalization statistics | country | FY2023 | DHS Yearbook |
| `data/vwp/dhs_naturalizations_fy2023.pdf` | PDF | Naturalization statistics report | country | FY2023 | DHS Yearbook |
| `data/vwp/dhs_nonimmigrants_fy2023.xlsx` | XLSX | Nonimmigrant admissions | country x visa class | FY2023 | DHS Yearbook |

---

## 6. University Research

### HERD (Higher Education R&D Survey)

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/herd/herd_fy2024_table13.xlsx` | XLSX | R&D expenditures by institution and funding source | institution x funding source | FY2024 | NSF/NCSES HERD |
| `data/herd/herd_fy2024_table14.xlsx` | XLSX | R&D expenditures by institution and field | institution x field | FY2024 | NSF/NCSES HERD |
| `data/herd/funding_by_university.json` | JSON | HERD funding aggregated per university (keyed by university slug) | university | FY2024 | NSF/NCSES HERD (derived) |

### USASpending

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/usaspending/top_university_grants.csv` | CSV | Top universities by federal grant funding | university | multi-year | USASpending.gov |

Key fields: `name, uei, total_grants`

---

## 7. International Comparisons

### Canada

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/canada/study_permits_by_citizenship.csv` | CSV | Study permit holders by citizenship (monthly) | country x month | 2015-2025 | IRCC |
| `data/canada/study_permits_by_citizenship.xlsx` | XLSX | Study permit holders by citizenship | country | multi-year | IRCC |
| `data/canada/study_permits_yearend_by_citizenship.xlsx` | XLSX | Year-end study permit holders by citizenship | country x year | multi-year | IRCC |
| `data/canada/study_permits_by_province_gender.xlsx` | XLSX | Study permits by province and gender | province x gender | multi-year | IRCC |
| `data/canada/study_permits_by_province_study_level.xlsx` | XLSX | Study permits by province and study level | province x level | multi-year | IRCC |
| `data/canada/study_permits_yearend_by_province_study_level.xlsx` | XLSX | Year-end study permits by province and level | province x level x year | multi-year | IRCC |
| `data/canada/imp_by_citizenship.csv` | CSV | International Mobility Program by citizenship | country | multi-year | IRCC |
| `data/canada/imp_yearend_by_citizenship.xlsx` | XLSX | IMP year-end by citizenship | country x year | multi-year | IRCC |
| `data/canada/pgwp_by_province_csd.csv` | CSV | Post-Graduation Work Permit by province/CSD | province/CSD | multi-year | IRCC |
| `data/canada/pgwp_by_province_cma.xlsx` | XLSX | PGWP by province/CMA | province/CMA | multi-year | IRCC |
| `data/canada/pgwp_yearend_by_province_cma.xlsx` | XLSX | PGWP year-end by province/CMA | province/CMA x year | multi-year | IRCC |

Key fields (study_permits CSV): `EN_YEAR, EN_QUARTER, EN_MONTH, EN_COUNTRY_OF_CITIZENSHIP, TOTAL`

### United Kingdom

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/uk/education-visas-datasets-sep-2025.xlsx` | XLSX | UK education visa grants (study, graduate route) | country x visa type x year | to Sep 2025 | UK Home Office |
| `data/uk/uk_student_trends.json` | JSON | UK student enrollment, student visas, graduate route trends | series x year | multi-year | HESA / UK Home Office |
| `data/uk/uk_visa_grants.json` | JSON | UK visa grant data | visa type x country x year | multi-year | UK Home Office |

### European Union / Germany

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/eu/eu_student_trends.json` | JSON | Germany and EU international student trends (total, by country, by field) | country x year x field | 2017-2025 | DAAD / Eurostat / DESTATIS |

Keys: `germany_total_international_students, germany_bildungsauslaender_only, germany_top_countries_*, germany_field_of_study, eu_total_international_students, eu_top_destination_countries_2023`

### China Outbound

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/china_outbound/china_students_abroad.json` | JSON | Chinese students studying abroad by destination country | destination country x year | multi-year | MOE China / various |

Keys: `overview, united_states, united_kingdom, canada, australia, japan, south_korea, germany, france`

### India Outbound

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/india_outbound/india_students_abroad.json` | JSON | Indian students studying abroad by destination | destination x year | multi-year | MEA India / various |

Keys: `overview, destinations`

### Mexico

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/mexico/mexico_student_trends.json` | JSON | Mexican students in U.S. (Open Doors, SEVIS, by level/state/field) and abroad | multiple series | multi-year | IIE / SEVP / SEP Mexico |

Keys: `mexican_students_in_us_open_doors, mexican_students_in_us_sevis, mexican_students_in_us_by_level, mexican_students_in_us_by_state, mexican_stem_students_in_us, mexican_students_abroad_all_destinations`

---

## 8. Medical Education

| File | Format | Description | Coverage | Source |
|------|--------|-------------|----------|--------|
| `data/medical/aamc_A1_applications_by_school_state_gender.xlsx` | XLSX | Medical school applications by school, state, gender | multi-year | AAMC |
| `data/medical/aamc_A12_applicants_by_race_ethnicity.xlsx` | XLSX | Applicants by race/ethnicity | multi-year | AAMC |
| `data/medical/aamc_A25_daca_status_2018-2026.xlsx` | XLSX | DACA applicants/matriculants | 2018-2026 | AAMC |
| `data/medical/aamc_B1_2_enrollment_by_school_2021-2026.xlsx` | XLSX | Medical school enrollment by school | 2021-2026 | AAMC |
| `data/medical/aamc_B3_enrollment_by_race_gender.xlsx` | XLSX | Enrollment by race and gender | multi-year | AAMC |
| `data/medical/aamc_chart4_enrollment_history.xlsx` | XLSX | Historical enrollment trends | multi-year | AAMC |
| `data/medical/aamc_table1_summary_2016-2026.xlsx` | XLSX | Summary statistics for applicants/matriculants/enrollees | 2016-2026 | AAMC |
| `data/medical/aamc_graduation_rates_attrition.pdf` | PDF | Graduation and attrition rates | multi-year | AAMC |
| `data/medical/nrmp_2025_advance.pdf` | PDF | NRMP Match advance data | 2025 | NRMP |
| `data/medical/Match2026Infographic.pdf` | PDF | 2026 Match results infographic | 2026 | NRMP |
| `data/medical/charting_outcomes_img_2024.pdf` | PDF | Match outcomes for IMGs | 2024 | NRMP |
| `data/medical/CertsbyYear2000-2024.pdf` | PDF | ECFMG certifications by year | 2000-2024 | ECFMG |
| `data/medical/Top5CitizenshipCountries2000-2024.pdf` | PDF | Top 5 ECFMG certification countries | 2000-2024 | ECFMG |
| `data/medical/EVSP-Physicians-Country-2025.pdf` | PDF | Exchange visitor physicians by country | 2025 | ECFMG/EVSP |
| `data/medical/EVSP-Physicians-States-2025.pdf` | PDF | Exchange visitor physicians by state | 2025 | ECFMG/EVSP |
| `data/medical/EVSP-Specialties-Physicians-2025.pdf` | PDF | Exchange visitor physicians by specialty | 2025 | ECFMG/EVSP |
| `data/medical/EVSP-Specialties-Table-2025.pdf` | PDF | Exchange visitor specialty details | 2025 | ECFMG/EVSP |
| `data/medical/EVSP-Sponsorship-2015-2025.pdf` | PDF | EVSP sponsorship trends | 2015-2025 | ECFMG/EVSP |
| `data/medical/FAIMER-MedicalSchoolGrowith_ByRegion.pdf` | PDF | Global medical school growth by region | multi-year | FAIMER |
| `data/medical/FAIMER-MedicalSchoolGrowith_Country.pdf` | PDF | Global medical school growth by country | multi-year | FAIMER |
| `data/medical/FAIMER-MedicalSchoolGrowth_TotalWorldwide.pdf` | PDF | Total worldwide medical schools | multi-year | FAIMER |
| `data/medical/J-1_US_Infographic.pdf` | PDF | J-1 physician program infographic | current | ECFMG |

---

## 9. VWP & Overstay

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/vwp/dhs_overstay_fy2023.pdf` | PDF | Visa overstay report | country x visa class | FY2023 | DHS |
| `data/vwp/dhs_overstay_fy2024.pdf` | PDF | Visa overstay report | country x visa class | FY2024 | DHS |
| `data/vwp/dhs_overstay_fy2025.pdf` | PDF | Visa overstay report | country x visa class | FY2025 | DHS |
| `data/vwp/sevis_2024_all_countries.pdf` | PDF | SEVIS all countries (copy) | country | 2024 | DHS/ICE SEVP |
| `data/vwp/sevis_2024_stem_opt.pdf` | PDF | SEVIS STEM OPT (copy) | country | 2024 | DHS/ICE SEVP |

---

## 10. NSF Workforce Surveys

### Survey of Doctorate Recipients (SDR) - Microdata

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/nsf_workforce/sdr_2023/psd23Public/epsd23.csv` | CSV | SDR 2023 public-use microdata (80,143 records) | individual | 2023 | NSF/NCSES SDR |
| `data/nsf_workforce/sdr_2023/psd23Public/Dpsd23.xlsx` | XLSX | SDR 2023 data dictionary | n/a | 2023 | NSF/NCSES SDR |
| `data/nsf_workforce/sdr_2023/psd23Public/Ppsd23.pdf` | PDF | SDR 2023 variable codebook | n/a | 2023 | NSF/NCSES SDR |
| `data/nsf_workforce/sdr_2023/psd23Public/psd23_Annotated.pdf` | PDF | SDR 2023 annotated survey instrument | n/a | 2023 | NSF/NCSES SDR |
| `data/nsf_workforce/sdr_2021/psd21Public/` | various | SDR 2021 (same structure as 2023) | individual | 2021 | NSF/NCSES SDR |
| `data/nsf_workforce/psd23Public/epsd23.csv` | CSV | SDR 2023 (alternate location copy) | individual | 2023 | NSF/NCSES SDR |
| `data/nsf_workforce/psd23Public/Dpsd23.xlsx` | XLSX | SDR 2023 data dictionary (alternate) | n/a | 2023 | NSF/NCSES SDR |

Key SDR variables: `BTHUS (born in US), CTZN (citizenship), CTZFOR (foreign citizenship), CTZUSIN (naturalized), CTZN_DRF (citizenship at doctorate)`

### SDR Summary Tables

| File | Format | Description | Coverage | Source |
|------|--------|-------------|----------|--------|
| `data/nsf_workforce/sdr_2023_tables/nsf25321-tab*.xlsx` | XLSX | SDR 2023 detailed tables (78+ files, tables 1-1 through 78) | 2023 | NSF/NCSES SDR |
| `data/nsf_workforce/sdr_2023_tables/_index.txt` | TXT | Table descriptions | n/a | NSF/NCSES SDR |
| `data/nsf_workforce/sdr_citizenship_findings.json` | JSON | Key citizenship/foreign-born findings from SDR | summary | 2023 | NSF/NCSES SDR (derived) |

### National Survey of College Graduates (NSCG) - Microdata

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/nsf_workforce/nscg_2023/pcg23Public/epcg23.csv` | CSV | NSCG 2023 public-use microdata (94,606 records) | individual | 2023 | NSF/NCSES NSCG |
| `data/nsf_workforce/nscg_2023/pcg23Public/Dpcg23.xlsx` | XLSX | NSCG 2023 data dictionary | n/a | 2023 | NSF/NCSES NSCG |
| `data/nsf_workforce/nscg_2023/pcg23Public/Ppcg23.pdf` | PDF | NSCG 2023 variable codebook | n/a | 2023 | NSF/NCSES NSCG |
| `data/nsf_workforce/nscg_2023/pcg23Public/TOGA_crosswalk_NSCG23_20250116.xlsx` | XLSX | TOGA crosswalk for occupation/field coding | n/a | 2023 | NSF/NCSES NSCG |
| `data/nsf_workforce/nscg_2021/pcg21Public/` | various | NSCG 2021 (same structure) | individual | 2021 | NSF/NCSES NSCG |

### NSB Foreign-Born STEM Workers

| File | Format | Description | Coverage | Source |
|------|--------|-------------|----------|--------|
| `data/nsf_workforce/nsb_foreign_born_stem/nsb20245-tabslbr-*.xlsx` | XLSX | Foreign-born STEM workforce tables (28 numbered + 4 lettered = 32 files) | 2021 | NSB/NCSES |
| `data/nsf_workforce/nsb_foreign_born_stem/nsb20245-supplemental-tables.pdf` | PDF | Supplemental tables for foreign-born STEM | 2021 | NSB/NCSES |
| `data/nsf_workforce/nsb_foreign_born_stem/_index.txt` | TXT | Table descriptions | n/a | NSB/NCSES |

Key tables: SLBR-25 (foreign-born STEM by citizenship), SLBR-26 (top countries of birth), SLBR-27 (citizenship by STEM category), SLBR-28 (stay rates by field and country)

### NSB Indicators: Talent Report Tables

| File | Format | Description | Coverage | Source |
|------|--------|-------------|----------|--------|
| `data/nsf_workforce/nsb20261_report_tables/nsb20261-tabtal-*.xlsx` | XLSX | S&E Indicators talent tables (19 files) | 2023 | NSB/NCSES |
| `data/nsf_workforce/nsb20261_report_tables/_index.txt` | TXT | Table descriptions | n/a | NSB/NCSES |

Key tables: TAL-4/5/6 (foreign-born workers), TAL-17/18 (stay rates), TAL-19 (internationally mobile students)

### NSB Indicators: STEM Labor Supplemental Tables

| File | Format | Description | Coverage | Source |
|------|--------|-------------|----------|--------|
| `data/nsf_workforce/nsb20261_stem_labor/nsb20261-tabstal-*.xlsx` | XLSX | STEM labor market supplemental tables (24 files) | 2023 | NSB/NCSES |
| `data/nsf_workforce/nsb20261_stem_labor/nsb20261-supplemental-tables.pdf` | PDF | Supplemental tables PDF | 2023 | NSB/NCSES |
| `data/nsf_workforce/nsb20261_stem_labor/_index.txt` | TXT | Table descriptions | n/a | NSB/NCSES |

Key tables: STAL-1/4/12 (workers by origin, occupational group, industry)

### Census / ACS

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/census_acs/acs_2022_summary.json` | JSON | ACS doctorate holders, foreign-born population, citizenship | national | 2022 | Census/ACS |

Keys: `total_doctorate_holders, total_population, native_born, foreign_born, naturalized_citizens, non_citizens, foreign_born_grad_degree`

---

## 11. Dissertation Harvest

### Raw ETD Scrapes

108 university ETD (electronic thesis/dissertation) files in `data/western_us_dissertations/`, totaling ~1.4M rows. Each university has `{slug}_etds.csv` and `{slug}_checkpoint.json`.

| File Pattern | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/western_us_dissertations/{univ}_etds.csv` | CSV | Harvested dissertation metadata (~108 universities) | individual dissertation | varies (1990s-2025) | University repositories (OAI-PMH) |
| `data/western_us_dissertations/{univ}_checkpoint.json` | JSON | Harvest progress checkpoints | n/a | n/a | Pipeline |

Key fields: `repo, university, identifier, title, creator, contributor, date, subject, description, type, format, language, oai_set, url, degree_type`

Notable variants: `njit_theses.csv`, `missouri_st_masters.csv`, `stony_brook_dspace_etds.csv`, `purdue_figshare_etds.csv`, `utdallas_gradschool_etds.csv`

### Additional Dissertation Collections

| File | Format | Description | Coverage | Source |
|------|--------|-------------|----------|--------|
| `data/caltech_dissertations/caltech_theses_metadata.csv` | CSV | Caltech thesis metadata | multi-decade | Caltech CODA |
| `data/caltech_dissertations/{dept}_alumni.csv` | CSV | Caltech alumni by department (cms, ee, galcit, mce, mede) | multi-decade | Caltech |
| `data/caltech_dissertations/caltech_dept_alumni_combined.csv` | CSV | Combined Caltech department alumni | multi-decade | Caltech |
| `data/stanford_dissertations/stanford_dissertations_metadata.csv` | CSV | Stanford dissertation metadata | multi-decade | Stanford SearchWorks |
| `data/uc_dissertations/uc_dissertations_metadata.csv` | CSV | UC system dissertations | multi-decade | eScholarship |
| `data/uc_dissertations/uc_stem_dissertations.csv` | CSV | UC STEM dissertations (filtered) | multi-decade | eScholarship |
| `data/uw_dissertations/uw_dissertations_metadata.csv` | CSV | UW dissertations | multi-decade | UW ResearchWorks |
| `data/uw_dissertations/uw_etd_metadata.csv` | CSV | UW ETD metadata | multi-decade | UW |
| `data/or_wa_dissertations/pdxscholar_dissertations.csv` | CSV | Portland State dissertations | multi-decade | PDXScholar |
| `data/or_wa_dissertations/pdxscholar_enriched.csv` | CSV | Portland State enriched (with classifications) | multi-decade | PDXScholar |
| `data/or_wa_dissertations/uoregon_dissertations.csv` | CSV | U of Oregon dissertations | multi-decade | Scholars' Bank |
| `data/or_wa_dissertations/wsu_dissertations.csv` | CSV | WSU dissertations | multi-decade | WSU Research Exchange |
| `data/stevens_crossref_dissertations.csv` | CSV | Stevens Institute dissertations (Crossref) | multi-decade | Crossref |
| `data/stevens_phd_recipients.csv` | CSV | Stevens PhD recipients | multi-decade | Stevens |

### Finished (Cleaned) ETD Data

16 cleaned/enriched datasets from the pipeline, totaling 285,544 rows.

| File | Format | Description | Coverage | Source |
|------|--------|-------------|----------|--------|
| `data/finished_data/oai_*.csv` | CSV | Cleaned ETD data from OAI-PMH harvests (14 files) | varies | Pipeline output |
| `data/finished_data/api_stanford.csv` | CSV | Stanford API harvest (cleaned) | multi-decade | Pipeline output |
| `data/finished_data/html_caltech.csv` | CSV | Caltech HTML scrape (cleaned) | multi-decade | Pipeline output |
| `data/finished_data/MANIFEST.txt` | TXT | Manifest of finished datasets with row counts | n/a | Pipeline |

---

## 12. Pipeline / Processed Data

### Processed University JSON (Per-University)

101 universities, each with STEM and non-STEM JSON files. Generated by the pipeline (step 2 process + step 3 enrich).

| File Pattern | Format | Description | Granularity | Source |
|------|--------|-------------|-------------|--------|
| `data/processed/stem/{slug}.json` | JSON | STEM dissertation records per university (101 files) | individual record | Pipeline output |
| `data/processed/nonstem/{slug}.json` | JSON | Non-STEM dissertation records per university (101 files) | individual record | Pipeline output |
| `data/processed/stem_records.parquet` | Parquet | All STEM records consolidated | individual record | Pipeline output |
| `data/processed/nonstem_records.parquet` | Parquet | All non-STEM records consolidated | individual record | Pipeline output |

Key fields per record: `key, name, nra, count, records, stats`

### Quality Assurance

| File | Format | Description | Source |
|------|--------|-------------|--------|
| `data/qa_report.csv` | CSV | QA metrics per university (NRA pct, record counts, degree labeling, year coverage) | Pipeline |

Key fields: `key, name, nra, stem_records, nonstem_records, total_records, phd_count, ms_count, unlabeled_degree, degree_label_pct, dept_count, year_min, year_max, has_2024, issues`

---

## 13. Analysis Outputs

Pre-computed analysis JSONs for charts and dashboards, stored in `data/analyses/`.

| File | Format | Description | Granularity | Source |
|------|--------|-------------|-------------|--------|
| `data/analyses/china_vs_india_timeseries.json` | JSON | China vs India comparison across multiple metrics over time | country x year | Derived (multi-source) |
| `data/analyses/eb_bottleneck.json` | JSON | Employment-based green card backlog analysis (EB breakdown, ratios) | country x EB category | Derived (State Dept + USCIS) |
| `data/analyses/national_pipeline_indexed.json` | JSON | National talent pipeline indexed to base year | metric x year | Derived (multi-source) |
| `data/analyses/pipeline_by_country.json` | JSON | Talent pipeline stages by country (enrollment -> PhD -> OPT -> H-1B -> EB) | country x pipeline stage | Derived (multi-source) |
| `data/analyses/stay_rate_vs_refusal.json` | JSON | PhD stay rate vs visa refusal rate correlation | country | Derived (NSF SED + State Dept) |
| `data/analyses/stem_country_state_matrix.json` | JSON | STEM students by country and U.S. state (matrix) | country x state | Derived (SEVP) |

Structure: Each file contains `_metadata, labels, datasets, chartConfig` for rendering.

---

## 14. Site Data

Generated JSON files served by the static website. Located in `site/data/`.

| File Pattern | Format | Description | Granularity | Source |
|------|--------|-------------|-------------|--------|
| `site/data/stem/{slug}.json` | JSON | Per-university STEM dashboard data (102 files) | university | Pipeline output |
| `site/data/nonstem/{slug}.json` | JSON | Per-university non-STEM dashboard data (102 files) | university | Pipeline output |
| `site/data/stem/_search.json` | JSON | STEM university search index | all universities | Pipeline output |
| `site/data/nonstem/_search.json` | JSON | Non-STEM university search index | all universities | Pipeline output |
| `site/data/taxonomy.json` | JSON | STEM/Non-STEM field classification taxonomy | field -> category | Pipeline |

Key fields per university: `key, name, nra, records, h1b, opt, lca, perm, enrollment, enrollment_ipeds`

---

## 15. Reference & Taxonomy

| File | Format | Description | Source |
|------|--------|-------------|--------|
| `data/taxonomy.json` | JSON | STEM/Non-STEM field classification (CIP-based) | Project-defined |
| `data/taxonomy_lookup.json` | JSON | Fast lookup version of taxonomy | Project-defined |
| `data/dept_links.json` | JSON | University department URL links | Project-curated |
| `data/dept_links_additional.json` | JSON | Additional department links | Project-curated |
| `data/master_stem_phd_institutions.csv` | CSV | Master list of STEM PhD-granting institutions (IPEDS + GSS merged) | NCES/NSF (derived) |
| `data/university_repositories.md` | MD | University ETD repository URLs and harvest methods | Project documentation |
| `data/DATA_DICTIONARY.md` | MD | Data dictionary for pipeline fields | Project documentation |
| `data/utdallas_doctoral_degrees.json` | JSON | UT Dallas doctoral degree program listings | UT Dallas |
| `data/gemini_exported_sheet.csv` / `.xlsx` | CSV/XLSX | Research university listing by state | Manual curation |

### Department Classification Reports

| File | Format | Description | Source |
|------|--------|-------------|--------|
| `data/department_classification_reports/department_data.json` | JSON | Department classification data for all universities | Pipeline |
| `data/department_classification_reports/department_summary.json` | JSON | Summary of department classifications | Pipeline |
| `data/department_classification_reports/{univ}_department_report.txt` | TXT | Per-university department classification reports (8 files) | Pipeline |
| `data/department_classification_reports/{univ}_name_lists.txt` | TXT | Name lists by department (7 files) | Pipeline |

---

## 16. Financial

### IPEDS Finance

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/ipeds_finance/f1415_f1a.csv` - `f2223_f1a.csv` | CSV | IPEDS Finance Survey (Form F1A) institutional revenues/expenditures (9 annual files) | institution | AY2014-15 to AY2022-23 | NCES/IPEDS |
| `data/ipeds_finance/f2223_f1a.xlsx` | XLSX | Most recent finance survey (Excel) | institution | AY2022-23 | NCES/IPEDS |

### IPEDS Tuition

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/ipeds/ic_tuition/grad_tuition_2023.csv` | CSV | Graduate tuition and fees | institution | 2023 | NCES/IPEDS |
| `data/ipeds/ic_tuition/ic2022_ay.csv` - `ic2023_ay.csv` | CSV | Institutional characteristics (tuition/fees) | institution | 2022-2023 | NCES/IPEDS |

### IPEDS Student Financial Aid

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/ipeds/sfa/sfa2122.csv` - `sfa2223.csv` | CSV | Student financial aid data | institution | 2021-2023 | NCES/IPEDS |
| `data/ipeds/sfa/grad_aid_2223.csv` | CSV | Graduate student aid data | institution | 2022-23 | NCES/IPEDS |

### IPEDS Human Resources

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/ipeds/hr/faculty_demographics_2022.csv` | CSV | Faculty demographics | institution x rank x race x gender | 2022 | NCES/IPEDS |
| `data/ipeds/hr/s2022_is.csv` / `s2022_is_rv.csv` | CSV | Fall staff (instructional) | institution | 2022 | NCES/IPEDS |
| `data/ipeds/hr/s2022_sis.csv` / `s2022_sis_rv.csv` | CSV | Fall staff (non-instructional) | institution | 2022 | NCES/IPEDS |
| `data/ipeds/hr/sal2022_is.csv` / `sal2022_is_rv.csv` | CSV | Faculty salaries | institution x rank | 2022 | NCES/IPEDS |

### Federal Student Aid (FSA)

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/fsa/AidRecipientsSummary.xls` | XLS | Aid recipients summary | national | multi-year | ED/FSA |
| `data/fsa/AidRecipientsSummary_dataed.xls` | XLS | Aid recipients (data.ed.gov version) | national | multi-year | ED/FSA |
| `data/fsa/DLEnteringDefaults.xls` | XLS | Direct Loan entering default | national/institution | multi-year | ED/FSA |
| `data/fsa/DLPortfolio-by-Location.xls` | XLS | Direct Loan portfolio by location | state | current | ED/FSA |
| `data/fsa/DLPortfolio-by-School-Type.xls` | XLS | Direct Loan portfolio by school type | school type | current | ED/FSA |
| `data/fsa/Portfolio-by-Location.xls` | XLS | Federal student loan portfolio by state | state | current | ED/FSA |
| `data/fsa/PortfoliobyLoanStatus.xls` | XLS | Portfolio by loan status | status | current | ED/FSA |
| `data/fsa/PortfoliobyLoanType.xls` | XLS | Portfolio by loan type | type | current | ED/FSA |
| `data/fsa/PortfolioSummary.xls` | XLS | Federal student loan portfolio summary | national | current | ED/FSA |

### SHEF (State Higher Education Finance)

| File | Format | Description | Granularity | Coverage | Source |
|------|--------|-------------|-------------|----------|--------|
| `data/shef/SHEEO_SHEF_FY24_Report_Data.xlsx` | XLSX | State higher education finance (appropriations, tuition, enrollment) | state x year | FY2024 | SHEEO |

---

## Miscellaneous / Ad-hoc Files

| File | Format | Description |
|------|--------|-------------|
| `data/dashboard_data.json` | JSON | Legacy dashboard data |
| `data/njit_chinese_qa.csv` / `.txt` | CSV/TXT | NJIT Chinese student QA analysis |
| `data/njit_stem_all_students_by_field.csv` | CSV | NJIT STEM students by field |
| `data/phd_institutions_*.txt` | TXT | Regional PhD institution lists (7 files) |
| `data/demographics_by_field.txt` / `_yearly.txt` | TXT | Demographics analysis text reports |
| `data/ipeds_breakdown.txt` | TXT | IPEDS data breakdown notes |
| `data/ipeds_nra_asian_ranking.txt` | TXT | NRA/Asian ranking analysis |
| `data/high_nra_classification_report.txt` / `_v2.txt` | TXT | High-NRA institution classification reports |
| `data/stem_name_classification_report.txt` | TXT | Name-based STEM classification report |
| `data/name_classification_review.txt` | TXT | Name classification review |
| `data/name_demographics_report.txt` | TXT | Name demographics analysis |
| `data/stem_classification_dashboard.html` | HTML | STEM classification dashboard (standalone) |
| `data/student_directory_audit.md` | MD | Student directory audit notes |
| `data/visa_correlation_analysis.md` | MD | Visa correlation analysis notes |
| `data/caltech_dissertations/dashboard_data.json` | JSON | Caltech-specific dashboard data |
| `data/caltech_dissertations/ipeds_field_demographics.json` | JSON | Caltech IPEDS field demographics |
| `data/caltech_dissertations/option_mapping.json` | JSON | Caltech academic option mapping |
