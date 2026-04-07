# NSF NCSES Federal Funds for R&D (Tier 2)

**Source:** NSF National Center for Science and Engineering Statistics (NCSES)
**Survey:** Survey of Federal Funds for Research and Development (FY2023)
**Landing page:** https://ncses.nsf.gov/surveys/federal-funds-research-development
**Publication:** NSF 25-328 (released March 2025)

## Files

- `nsf25328-data-tables-excels.zip` — full Excel bundle (~1.1 MB, 99 tables)
- `excel_tables/` — unzipped contents, `nsf25328-tab001.xlsx` through `nsf25328-tab099.xlsx`
- `federal_rd_higher_ed_state_fy2023.json` — parsed summary derived from Table 61

## Key table for PhD Demographics project

**Table 61** — "Federal obligations for research and experimental development, by state or location, agency, and performer: FY 2023" (`excel_tables/nsf25328-tab061.xlsx`)

Columns:
- State / Agency
- Total obligations
- Intramural (Federal agencies / FFRDCs)
- Extramural → Businesses, **Higher education**, Nonprofit organizations, State & local governments

Unit: thousands of U.S. dollars.

## Other relevant tables

- Tables 52-57: Research obligations to higher-education performers broken down by research type (basic, applied, development) and field of science
- Table 24: Federal R&D by agency and field
- Tables 1-50: Agency-level obligations (DoD, DoE, HHS/NIH, NASA, NSF, USDA, etc.)

## Parsed summary

`federal_rd_higher_ed_state_fy2023.json` captures, per state, total federal R&D obligations and the portion flowing to higher-education performers in FY2023.

**Top 5 states by federal R&D to higher ed (FY2023, thousands USD):**

| State | Higher Ed R&D |
|-------|---------------|
| California    | $5,773,719 |
| New York      | $3,676,668 |
| Maryland      | $3,018,389 |
| Texas         | $2,654,908 |
| Pennsylvania  | $2,473,571 |

## Extraction still needed

None for the basic state-level totals — Table 61 is parsed. For finer slicing (e.g., "DoD R&D to Texas universities only", "NIH obligations to California universities"), iterate the per-state sub-rows in Table 61 which list each funding agency under each state header, or use Tables 52-57 / the NCSES Table Builder at https://ncsesdata.nsf.gov/builder.
