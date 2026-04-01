# SEVP / SEVIS Data Summary

Downloaded: 2026-03-31
Source: DHS Student and Exchange Visitor Program (SEVP) / ICE

## CSV Data: SEVIS Data Mapping Tool (Monthly Snapshots)

Extracted from HTML tables at studyinthestates.dhs.gov. Two types:

### Country-Level Summary CSVs (~229 rows each, 72 columns)
- `sevis_data_mapping_mar2026.csv` - March 2026
- `sevis_data_mapping_feb2026.csv` - February 2026
- `sevis_data_mapping_jan2026.csv` - January 2026
- `sevis_data_mapping_dec2025.csv` - December 2025
- `sevis_data_mapping_aug2025.csv` - August 2025
- `sevis_data_mapping_dec2024.csv` - December 2024
- `sevis_data_mapping_jan2024.csv` - January 2024

**Schema:** Country of Citizenship, Continent, Region, Active Students, Male, Female,
then education levels (Associate, Bachelors, Doctorate, Flight School, High School,
Language Training, Masters, Other, Other Vocational School, Primary, Secondary),
then counts by US state (AK through WY, 55 columns including DC/GU/MP/PR/VI).

Key data point (March 2026): China has 229,463 active students (118,244 male, 111,219 female).

### STEM School-Level CSVs (~28,000+ rows each, 6 columns)
- `sevis_data_mapping_mar2026_stem.csv`
- `sevis_data_mapping_feb2026_stem.csv`
- `sevis_data_mapping_jan2026_stem.csv`
- `sevis_data_mapping_aug2025_stem.csv`
- `sevis_data_mapping_dec2024_stem.csv`
- `sevis_data_mapping_jan2024_stem.csv`

**Schema:** State, Abbrv, Student Education Level, CoC (Country of Citizenship), Sex, Count of Active STEM Students

These provide school-state-level granularity: counts of active STEM students by state, education level, country of citizenship, and sex.

## PDF Reports: Annual SEVIS By The Numbers

- `2024_sevis_by_the_numbers.pdf` (1.3 MB) - CY2024 annual report, 1,582,808 active F-1/M-1 records
- `2023_sevis_by_the_numbers.pdf` (889 KB) - CY2023 annual report
- `2022_sevis_by_the_numbers.pdf` (660 KB) - CY2022 annual report, 1,362,157 active records

## PDF Reports: Country of Citizenship Breakdowns

- `2024_all_countries_active_records.pdf` - All countries by total active SEVIS records (2024)
- `2024_all_countries_stemopt.pdf` - All countries with STEM OPT authorizations (2024)
- `2023_all_students_by_coc.pdf` - All students by country of citizenship (2023)
- `2022_all_students_by_coc.pdf` - All students by country of citizenship (2022)

## PDF Reports: OPT / Practical Training Data

- `opt_stemopt_cpt_authorizations_2007_2024.pdf` - Annual OPT, STEM OPT, and CPT authorizations time series (2007-2024)
- `opt_growth_2007_2022.pdf` - Annual growth in OPT, STEM OPT and CPT (2007-2022)
- `2024_total_sevis_records_opt_cpt_stemopt.pdf` - Total SEVIS records with OPT/CPT/STEM OPT auth (2024)

## PDF Reports: Employer and School Rankings

- `2024_top200_employers_opt_stemopt.pdf` (472 KB) - Top 200 employers for OPT and STEM OPT students (2024)
- `2024_top100_schools_stemopt.pdf` (173 KB) - Top 100 school campuses with STEM OPT authorization (2024)

## Other

- `sevp_certified_school_list.pdf` (3.3 MB) - SEVP-certified schools (as of April 2021, 315 pages)
- `2024_stem_designated_degree_list.pdf` (419 KB) - DHS STEM designated degree program list (2024)

## Notes

- The country-level CSVs are the most analytically useful -- they can be loaded directly into pandas/R for analysis.
- The STEM CSVs provide school-level granularity with ~28K rows per month.
- The PDF reports contain additional context, charts, and narrative but require extraction for quantitative analysis.
- The studyinthestates.dhs.gov site blocks automated fetching (403) but curl with a browser User-Agent works for HTML pages.
- Data covers F-1 (academic students) and M-1 (vocational students) visa holders.
- OPT data covers post-graduation work authorization (critical for understanding Chinese STEM workforce pipeline).
