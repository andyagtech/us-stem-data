# Census Annual Survey of State Government Finances (ASFIN) — Tier 2

**Source:** U.S. Census Bureau, Annual Survey of State Government Finances (ASFIN)
**Landing page:** https://www.census.gov/programs-surveys/state.html
**Data archive root:** https://www2.census.gov/programs-surveys/state/

## Files

### Summary tables (published Excel)
- `2023_ASFIN_State_Totals.xlsx` — FY2023 state totals, all expenditure categories (includes an aggregated "Education" row but not a standalone higher-education row)
- `2022_ASFIN_State_Totals.xlsx` — FY2022 state totals
- `ASFIN_FY2021_2020.xlsx` — combined FY2020-FY2021 state totals

### Flat files (machine-readable, item-code level)
- `23state35.txt`, `22state35.txt`, `21state35.txt` — the item-code flat files (36-character fixed-width records). These contain the full breakdown by government × item code × year, which is where the higher-education-specific codes live. The aggregated summary tables do NOT expose higher-education separately — only these flat files do.

### Documentation / code lists
- `2022_methodology.pdf` — 2022 ASFIN methodology
- `public-use-file-layout.xlsx` — fixed-width field layout for `XXstate35.txt`
- `flat-data-file-layout.csv` — shorter layout reference
- `itemcodes.xlsx` — full item-code dictionary
- `government-ids.xls` — state → 14-character government ID lookup

### Derived
- `higher_ed_state_spending_summary.json` — parsed FY2021 / FY2022 / FY2023 state-level higher-education spending built from the three `state35.txt` flat files.

## Higher-education item codes used

| Code | Description |
|------|-------------|
| E18  | Current operations — Other Higher Education |
| E16  | Current operations — Higher Ed Auxiliary Enterprises |
| F18  | Capital expenditures — Higher Ed, Other (effective 2022; formerly G18/K18) |
| F16  | Capital expenditures — Higher Ed Auxiliary (effective 2022; formerly G16/K16) |
| M18  | Intergovernmental to Local — Higher Education |
| A18  | Charges — Higher Ed, Other (revenue offset) |
| A16  | Charges — Higher Ed Auxiliary Enterprises (revenue offset) |

The JSON summary reports `total_higher_ed_expenditure = E18+E16+F18+F16+M18` per state per year, plus a `net_higher_ed_expenditure_minus_charges` field that nets A18 and A16 (student tuition / auxiliary charges).

**Note:** ASFIN covers 50 state governments only — **Washington, DC is not in ASFIN** (DC is surveyed in the local/District finance file). That is why 50, not 51, states appear in the parsed output.

**FY2023 Top 5 states (total higher-ed expenditure, thousands USD):**

| State | Total Higher Ed Exp |
|-------|---------------------|
| California | $47,226,209 |
| Texas | $32,462,699 |
| Michigan | $11,877,385 |
| New York | $11,721,514 |
| Florida | $11,335,604 |

US total FY2023: $320,652,704 thousand (~$320.7B).

## File layout (XXstate35.txt)

35-character fixed-width:
- Pos 1-14: Government ID (zero-filled; first 2 digits = Census state code)
- Pos 15-17: Item code
- Pos 18-29: Amount in thousands
- Pos 30-31: Survey year
- Pos 32-33: Year of data

## Extraction still needed

None for state-level aggregates — the `state35.txt` files are already parsed into `higher_ed_state_spending_summary.json`. For time series beyond FY2021, additional years (2019, 2020, etc.) are available in sibling directories at `https://www2.census.gov/programs-surveys/state/datasets/{YYYY}/`.
