# NASBO State Expenditure Report (Tier 2)

**Source:** National Association of State Budget Officers (NASBO)
**Landing page:** https://www.nasbo.org/reports-data/state-expenditure-report
**Archive:** https://www.nasbo.org/reports-data/state-expenditure-report/state-expenditure-archives

## Files

| File | Publication | Fiscal Years Covered |
|------|-------------|----------------------|
| `2025_NASBO_State_Expenditure_Report.pdf` | Fall 2025 | FY2023 actual, FY2024 actual, FY2025 estimated |
| `2025_Executive_Summary.pdf` | Fall 2025 | Executive summary for the 2025 SER |
| `2024_State_Expenditure_Report.pdf` | Fall 2024 | FY2022 actual, FY2023 actual, FY2024 estimated |
| `2024_Executive_Summary.pdf` | Fall 2024 | Executive summary for the 2024 SER |
| `2023_State_Expenditure_Report.pdf` | Fall 2023 | FY2021, FY2022, FY2023 |
| `2022_State_Expenditure_Report.pdf` | Fall 2022 | FY2020, FY2021, FY2022 |

## Data format

**PDF only.** NASBO does not publish free CSV or Excel versions of the State Expenditure Report on the public web. Historical datasets in machine-readable form are available only behind the NASBO members-only datasets store:
- https://account.nasbo.org/commerce/datasets

## What's inside (higher education chapter)

Each SER contains a dedicated "Higher Education" chapter with tables that break state higher-education spending down by:
- Fund source: General Fund, Federal Funds, Other State Funds, Bonds
- All 50 states (state-by-state table)
- Three fiscal years (prior actual, current actual, current estimated)

Tables typically appear as rendered PDF tables toward the end of the higher-education chapter.

## Extraction still needed

To get structured data for the PhD Demographics project, tables must be extracted from the PDFs. Recommended approach:

1. Use `pdfplumber` or `camelot-py` to pull the state-by-state higher-education expenditure tables.
2. Target pages: search for "Higher Education" chapter + "Table" headings. In the 2025 SER the relevant state-level tables are ~pp. 35-45 (will vary).
3. Normalize into a long-form CSV: `year, state, fund_source, amount_millions`.

No structured JSON summary is included here because the PDFs would need OCR/table extraction first.

## Note on 2025 vs FY2023

The "FY2023 report published late 2024" mentioned in the task brief corresponds to the **2024 SER** (which reports FY2022 actual + FY2023 preliminary). The **2025 SER** (published late 2025) is the most recent edition and covers FY2023-FY2025. Both are included.
