# SHEEO / Grapevine / InformEd States — State Funding Data

Downloaded 2026-04-05 for the PhD Demographics project (101 universities).

## What's here

### SHEEO SHEF (State Higher Education Finance)

Source: https://shef.sheeo.org/data-downloads/

| File | Coverage | Description |
|---|---|---|
| `SHEEO_SHEF_FY24_Report_Data.xlsx` | FY1980–2024 | Main SHEF report. Unadjusted (nominal) state-level metrics: total state support, education appropriations, net tuition, FTE enrollment, student share, RAM carve-outs, etc. |
| `SHEEO_SHEF_FY24_Sector_Data.xlsx` | FY2019–2024 | State × sector (two-year / four-year) breakouts. This is the closest SHEEO publishes to institution-level data — **no institution-level data is publicly released**. |
| `SHEEO_SHEF_FY23_State_Effort_Capacity.xlsx` | FY1980–2023 | Revenue, tax effort, per-capita funding capacity by state. |
| `SHEEO_SHEF_FY24_Data_Adjustments.xlsx` | — | COLI (cost of living), EMI (enrollment mix), HECA / CPI (inflation) adjustment factors. |
| `SHEEO_SHEF_FY24_Capital_Appropriations_Data.xlsx` | FY2020–2024 | State capital (facilities) appropriations, separate from operating. |
| `SHEEO_SHEF_FY24_Federal_Stimulus_Funding_Data.xlsx` | FY2009–2024 | ARRA + CARES/CRRSA/ARP stimulus used to backfill state support. |
| `SHEEO_SHEF_FY24_PBF_Data.xlsx` | FY2020–2024 | Share of state funding distributed via performance-based formulas. |
| `SHEEO_SHEF_FY24_Residency_Data.xlsx` | FY2020–2024 | In-state vs out-of-state FTE enrollment shares. |

### SHEEO Grapevine (early FY estimates)

Source: https://shef.sheeo.org/grapevine/ (project moved from Illinois State University to SHEEO; illinoisstate.edu URLs redirect)

| File | Coverage |
|---|---|
| `SHEEO_Grapevine_FY26_Data_Download.xlsx` | FY1980–2026 full historical data download |
| `SHEEO_Grapevine_FY26_All-Tables.xlsx` | Summary tables for FY2026 (latest annual release) |
| `SHEEO_Grapevine_FY25_All-Tables.xlsx` | **FY2025 tables (primary request)** |

Grapevine is the earliest available estimate of state tax appropriations for higher ed, released before SHEF data for that fiscal year is finalized.

### InformEd States (`informed_states/` subdirectory)

Source: https://informedstates.org/data — the raw Excel datasets sit behind request forms (`state-funding-mechanisms-dataset-download`, `pbf-funding-policies-dataset-download`, etc.). Writing `info@informedstates.org` is required for bulk dataset access. What is publicly downloadable without a form:

| File | Description |
|---|---|
| `ISBrief_Landscape_Funding_Formulas_2023.pdf` | InformEd States policy brief: "The Landscape of State Funding Formulas for Public Colleges and Universities" (Ortagus, Kelchen, et al.) — typology of base-funding mechanisms. |
| `SHEEO_2022_State_Approaches_Base_Funding.pdf` | SHEEO companion report on state base-funding approaches. |
| `State-Funding-Mechanisms-Readme.pdf` | Data dictionary for the gated State Funding Mechanisms dataset (what columns are in the Excel if you request it). |
| `State-Policies-PBF-Readme.pdf` | Data dictionary for the Performance-Based Funding Policies dataset. |

To acquire the actual InformEd States Excel files, submit the forms at the URLs above or email `info@informedstates.org`.

## Derived JSON outputs (one level up)

- `../sheeo_by_state.json` — state-level time series 2010–2024 for all 52 SHEF reporting entities (50 states + DC + US total-ish; exact roster defined by SHEF). Metrics, for each (state, fiscal year):
  - Nominal $: `total_state_support`, `total_state_local_support`, `federal_stimulus`, `state_local_ex_stimulus`, `education_appropriations`, `ed_approp_ex_stimulus`, `net_tuition_revenue`, `total_education_revenue`, `state_tax_appropriations`, `research_appropriations`, `medical_school_appropriations`
  - Enrollment: `net_fte_enrollment`
  - Ratios: `student_share`, `ed_approp_per_fte`
  - Inflation: `heca_inflation_adj` (HECA multiplier to FY2024)
  - Real (FY2024 constant $): `total_state_support_real24`, `education_appropriations_real24`, `state_tax_appropriations_real24`, `ed_approp_per_fte_real24`
- `../sheeo_by_university.json` — for each of the 101 project universities, the state it lives in (joined via IPEDS HD STABBR + manual overrides for Mines and CUNY Grad Center) plus the full state-level time series as a proxy. **SHEEO does not publish institution-level appropriations publicly**; state-level values are the best available open proxy. For genuine per-institution state appropriations, use IPEDS F1A (state-appropriations line) already in `data/ipeds_finance/`.

## Data dictionary — key SHEF metrics

- **Total State Support** — all state government appropriations to higher ed, including RAM (research/agriculture/medical) carve-outs and independent aid.
- **Education Appropriations** — operating support for the general education of students; **excludes** RAM and independent financial aid. This is the headline number for "state support per student."
- **State Tax Appropriations** — funds appropriated from state tax revenues (a subset of total state support; excludes lottery, tuition trust income, local appropriations).
- **Federal Stimulus** — ARRA (FY2009–FY2011) and COVID-era GEER/HEERF/SFRF (FY2020–FY2024) funds used by states to supplant/backfill higher ed appropriations. The `*_ex_stimulus` variants strip these out for apples-to-apples state-effort comparisons.
- **Net FTE Enrollment** — full-time-equivalent enrollment at public institutions, net of medical students and non-credit.
- **Student Share** — share of total education revenue paid by students (net tuition / (net tuition + education appropriations)).
- **HECA** — Higher Education Cost Adjustment, SHEEO's preferred deflator for converting nominal dollars to real constant dollars. CPI is also provided in the source file for comparison.

## Pipelines / reproducibility

JSON builder: `scripts/build_sheeo_json.py` — reads `SHEEO_SHEF_FY24_Report_Data.xlsx` + IPEDS `HD*.csv` for unitid→state mapping, writes both JSON outputs. Rerun after new SHEF release.
