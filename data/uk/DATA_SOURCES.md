# UK International Student Data Sources

Last updated: 2026-04-05

## Files

| File | Description |
|------|-------------|
| `uk_student_trends.json` | Compiled aggregate statistics for charting: HESA enrollment, visa grants, Graduate Route |
| `uk_visa_grants.json` | Detailed visa grant data extracted from Home Office Excel (by year and nationality) |
| `education-visas-datasets-sep-2025.xlsx` | Raw Home Office data: sponsored study visa grants by quarter, nationality, course level (2018-2025 Q3) |

## Sources

### 1. HESA - Higher Education Student Statistics

- **URL**: https://www.hesa.ac.uk/data-and-analysis/students/where-from
- **Coverage**: Academic years 2014/15 to 2023/24
- **What it provides**: Total international (non-UK domicile) student enrollment in UK higher education institutions, broken down by country of domicile
- **Key table**: Table 28 - Non-UK permanent address students by HE provider and country of permanent address
- **Note**: HESA requires login/subscription for CSV downloads. Numbers in `uk_student_trends.json` were compiled from HESA statistical bulletins and secondary reporting (ICEF Monitor, Wonkhe, StuRents).
- **Published**: March 2025 (for 2023/24 data)

### 2. Home Office - Immigration System Statistics (Student Visas)

- **URL**: https://www.gov.uk/government/statistical-data-sets/immigration-system-statistics-data-tables
- **Direct download**: https://assets.publishing.service.gov.uk/media/699590684222708fdcf8d2f4/education-visas-datasets-sep-2025.xlsx
- **Coverage**: Q1 2018 to Q3 2025 (quarterly)
- **What it provides**: Entry clearance visa applications and grants for sponsored study, broken down by nationality, region, visa type, and course level
- **Note**: Main applicants only in our extracted data. 2025 Q1-Q3 data is provisional. Pre-2018 data approximated from GOV.UK narrative summaries (~200k/yr 2011-2016).
- **Published**: 27 November 2025

### 3. Home Office - Graduate Route Statistics

- **URL**: https://www.gov.uk/government/statistics/immigration-system-statistics-year-ending-september-2025/why-do-people-come-to-the-uk-study
- **Coverage**: July 2021 (launch) to September 2025
- **What it provides**: Graduate Route visa extensions by year, nationality breakdowns
- **Secondary source**: https://migrationobservatory.ox.ac.uk/resources/briefings/student-migration-to-the-uk/
- **Note**: Graduate Route allows 2-year post-study work (3 years for PhD). Top 4 nationalities (India, Nigeria, China, Pakistan) account for 70% of grants.

## Key Findings (as of 2023/24)

- **732,285** international students enrolled in UK HE (HESA 2023/24), down 3.5% from record 758,855 in 2022/23
- **China** is the largest source for visa grants (100,365 in 2024) but **India** leads HESA enrollment (166,310)
- The discrepancy reflects that HESA counts all enrolled students (multi-year), while visa data counts new grants
- Chinese visa grants peaked in 2019 (114,807) and have been declining; 2025 partial-year (83,607) suggests continued fall
- Graduate Route usage growing rapidly: from 66,000 (2022) to 237,452 (2025)
- January 2024 policy change restricting dependants for taught masters drove sharp drop in visa numbers

## Data Limitations

- HESA figures for 2015/16 and 2016/17 are estimates (HESA blocks direct CSV access)
- Home Office visa data starts at 2018; pre-2018 figures are rounded approximations from narrative reports
- India visa grants pre-2022 are approximations (exact figures not in the downloaded Excel which covers main applicants matched to CAS records)
- Graduate Route numbers are year-ending-September, not calendar year
