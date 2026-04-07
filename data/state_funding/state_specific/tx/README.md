# Texas – Higher Education Appropriations

## Sources

- **Texas Legislative Budget Board (LBB)**: https://www.lbb.texas.gov/
  - Fiscal Size-Up 2026-27 Biennium (December 2025):
    `https://lbb.texas.gov/Documents/Publications/Fiscal_SizeUp/Fiscal_SizeUp.pdf`
  - General Appropriations Act 2026-27:
    `https://lbb.texas.gov/Documents/GAA/General_Appropriations_Act_2026_2027.pdf`
  - 88R Senate-recommended HE appropriations (prior biennium):
    `https://www.lbb.texas.gov/Documents/Appropriations_Bills/88/LBB_Recommended_Senate/LBE_Senate_Program_III_HE_88R.pdf`
  - HE Issue Docket (88R / 2024-25):
    `https://www.lbb.texas.gov/Documents/Appropriations_Bills/88/Adopted_Decision_Documents/Article03(HE)_IssueDoc.pdf`
  - Financing Public Higher Ed primer:
    `https://www.lbb.texas.gov/Documents/Publications/Primer/4909_Financing_Public_Higher_Ed.pdf`

## Downloaded files

| File | Description |
|------|-------------|
| `tx_fiscal_sizeup_2026-27.pdf` | LBB Fiscal Size-Up, 2026-27 biennium – contains per-institution All Funds and GR formula funding tables |
| `tx_gaa_2026-27.pdf` | Full General Appropriations Act, 2026-27 biennium |
| `tx_lbb_88R_HE_recommendations.pdf` | 88R Senate-recommended HE program appropriations |
| `tx_lbb_HE_issue_docket_2024-25.pdf` | HE decision document, 2024-25 biennium |
| `tx_lbb_financing_public_HE.pdf` | LBB primer on financing Texas public higher ed |

## Extracted JSON

`texas_appropriations_2026-27_biennium.json`

Contains two breakdowns from the LBB Fiscal Size-Up (Figures 193 and 194):

1. **All Funds Appropriations** for the 2026-27 biennium (in $ millions)
2. **GR I&O + Infrastructure Formula Funding** for the 2026-27 biennium (in $ millions)

For each of our 5 target TX universities (UT Austin, UT Dallas, UT
Arlington, University of Houston, Texas Tech).

Sample:
```json
{
  "all_funds_2026_27_biennium_millions": {
    "utaustin": 1023.4,
    "utdallas": 471.1,
    "utarlington": 464.4,
    "uhouston": 552.6,
    "ttu": 599.1
  },
  "gr_formula_2026_27_biennium_millions": {
    "utaustin": 476.5,
    "utdallas": 194.1,
    "utarlington": 208.3,
    "uhouston": 307.5,
    "ttu": 353.1
  }
}
```

## Limitations

- The extracted per-institution figures are only for the **2026-27
  biennium** (so each year in the biennium is ~half these totals). LBB
  publishes the Fiscal Size-Up once per biennium; earlier Size-Ups
  (e.g., 2024-25, 2022-23) are available on the LBB site and could be
  added for a time series, but are not included here.
- The 88R HE Recommendations and Issue Docket PDFs contain detailed
  per-strategy line items but require more complex parsing than the
  Fiscal Size-Up tables and are included only as primary-source archives.
- THECB (Texas Higher Education Coordinating Board, highered.texas.gov)
  offers a Legislative Appropriations Request (LAR) portal at
  `txhighereddata.org`, but the detailed breakdowns were not machine-
  readable downloads at the time of collection.
