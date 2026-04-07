# Florida – State University System (SUS) Operating Budget

## Sources

- **Florida Board of Governors**: https://www.flbog.edu/
- **Operating Budget Summaries** (annual):
  https://www.flbog.edu/finance/university-budget-information/operating-budget-summaries/

Each year's "SUS Operating Budget Summary Book" is a single PDF that
contains individual Summary Schedule I reports for each of the 12 public
universities in the State University System of Florida.

## Downloaded files

11 years of Operating Budget Summary Books:

| Fiscal year | File |
|-------------|------|
| 2015-16 | `sus_operating_budget_2015-16.pdf` |
| 2016-17 | `sus_operating_budget_2016-17.pdf` |
| 2017-18 | `sus_operating_budget_2017-18.pdf` |
| 2018-19 | `sus_operating_budget_2018-19.pdf` |
| 2019-20 | `sus_operating_budget_2019-20.pdf` |
| 2020-21 | `sus_operating_budget_2020-21.pdf` |
| 2021-22 | `sus_operating_budget_2021-22.pdf` |
| 2022-23 | `sus_operating_budget_2022-23.pdf` |
| 2023-24 | `sus_operating_budget_2023-24.pdf` |
| 2024-25 | `sus_operating_budget_2024-25.pdf` |
| 2025-26 | `sus_operating_budget_2025-26.pdf` |

Plus `uf_operating_budget.pdf` - a one-off 2025-26 UF operating budget
supplemental.

## Extracted JSON

`florida_sus_general_revenue_timeseries.json` – indexed by fiscal year
then by university key, with three line items per record:

- `general_revenue` – State general revenue funds (E&G budget, main
  campus column only — excludes IFAS, HSC, FAMU-FSU Joint CoE,
  Lastinger Center, USF Cybersecurity Resiliency, UCF Community School
  Grant line items which are reported separately within each schedule)
- `lottery` – Educational Enhancement Trust Fund (Lottery) appropriation
- `student_tuition` – Student tuition revenue (E&G)

Note: for FY 2015-16 through 2018-19, the number of target universities
matched may be 11 (out of 12) because older layouts used slightly
different section headers for one school; the 7 universities we care
about (UF, FSU, USF, UCF, FIU, FAU, FAMU) are all present in every year.

## Coverage in unified JSON

Matched to our 101-university keys:

| Key   | FL SUS institution              | Years |
|-------|----------------------------------|-------|
| uf    | University of Florida            | 11    |
| fsu   | Florida State University         | 11    |
| usf   | University of South Florida      | 11    |
| ucf   | University of Central Florida    | 11    |
| fiu   | Florida International University | 11    |
| fau   | Florida Atlantic University      | 11    |
| famu  | Florida A&M University           | 11    |

## Sample

University of Florida main-campus General Revenue time series
(rounded, millions USD):

| FY | GR |
|----|-----|
| 2015-16 | 348.2 |
| 2016-17 | 365.9 |
| 2017-18 | 431.2 |
| 2018-19 | 446.0 |
| 2019-20 | 429.9 |
| 2020-21 | 462.7 |
| 2021-22 | 545.8 |
| 2022-23 | 505.9 |
| 2023-24 | 624.4 |
| 2024-25 | 784.4 |
| 2025-26 | 715.2 |
