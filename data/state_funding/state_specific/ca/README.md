# California – UC System State Funding

## Sources

- **UC Office of the President, Budget for Current Operations** (annual)
  - Landing page: https://www.ucop.edu/operating-budget/budgets-and-reports/current-operations-budgets/index.html
  - Summary PDF: `https://www.ucop.edu/operating-budget/_files/rbudget/{FY}-budget-summary.pdf`
  - Detail PDF:  `https://www.ucop.edu/operating-budget/_files/rbudget/{FY}-budget-detail.pdf`

## Downloaded files

| Fiscal year | Files |
|-------------|-------|
| 2019-20 | `uc_budget_2019-20_summary.pdf`, `uc_budget_2019-20_detail.pdf` |
| 2020-21 | `uc_budget_2020-21_summary.pdf`, `uc_budget_2020-21_detail.pdf` |
| 2021-22 | `uc_budget_2021-22_summary.pdf`, `uc_budget_2021-22_detail.pdf` |
| 2022-23 | `uc_budget_2022-23_summary.pdf`, `uc_budget_2022-23_detail.pdf` |
| 2023-24 | `uc_budget_2023-24_summary.pdf`, `uc_budget_2023-24_detail.pdf` |
| 2024-25 | `uc_budget_2024-25_summary.pdf`, `uc_budget_2024-25_detail.pdf` |
| 2025-26 | `uc_budget_2025-26_summary.pdf`, `uc_budget_2025-26_detail.pdf` |

## Extracted JSON

`uc_systemwide_state_funds_timeseries.json` – UC systemwide State
General Fund totals by fiscal year, parsed from the detail PDFs using
the phrase `"State General Fund support for UC totals $X.XX billion in
FY..."`.

## IMPORTANT LIMITATION

**UC Office of the President does not publish per-campus state general
fund appropriations in its annual budget documents.** UCOP receives
state appropriations as a block grant to the system and makes internal
allocations to the 10 campuses based on enrollment, academic programs,
and strategic priorities. The UC budget detail documents show:

- Systemwide State General Fund totals
- Per-campus FTE enrollment, tuition revenue, and expenditure data
- Overall core fund composition

…but NOT per-campus state-fund allocations. Researchers who need
campus-level breakdowns must file CPRA requests with UCOP or use
third-party data sources (e.g., IPEDS, SHEEO, or Cal State Controller's
Office data) which themselves are derived from institutional reporting,
not from the state appropriation itself.

Our unified JSON (`state_specific_funding_by_university.json`) therefore
applies the UC **systemwide** total identically to all 10 campus keys
with a `_note` field explaining this.

## LAO note

California Legislative Analyst's Office (lao.ca.gov) publishes policy
analysis and fiscal outlooks but does not publish a separate per-campus
UC appropriation dataset — they cite the UC Budget for Current
Operations documents as their source.
