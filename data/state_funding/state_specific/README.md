# Tier 3: State-Specific University Funding Data

This directory contains state-specific appropriations data for the three
U.S. states with the most universities in the PhD Demographics project:
California, Texas, and Florida.

## Layout

```
state_specific/
├── ca/   California – UC Office of the President budget docs
├── tx/   Texas – LBB Fiscal Size-Up and related
├── fl/   Florida – Board of Governors SUS Operating Budgets
├── extract.py                                         # PDF parser
└── state_specific_funding_by_university.json          # unified time series
```

## Unified output

`state_specific_funding_by_university.json` maps 21 of our 101 university
keys to per-year state funding figures where available:

| State | Universities covered | Temporal coverage |
|-------|---------------------|-------------------|
| CA    | ucberkeley, ucla, ucsd, ucsf, ucdavis, ucirvine, ucsb, ucsc, ucriverside, ucmerced | FY 2019-20 through 2025-26 (systemwide only) |
| TX    | utaustin, utdallas, utarlington, uhouston, ttu | 2026-27 biennium snapshot |
| FL    | uf, fsu, usf, ucf, fiu, fau, famu | FY 2015-16 through 2025-26 (11 years) |

## Per-state notes

See `ca/README.md`, `tx/README.md`, `fl/README.md` for source details,
data limitations, and methodology.

## Running the extractor

```bash
cd /Users/andy/usds_china/data/state_funding/state_specific
python3 extract.py
```

Requires `pdftotext` (poppler). Regenerates the three per-state JSONs and
the unified `state_specific_funding_by_university.json`.
