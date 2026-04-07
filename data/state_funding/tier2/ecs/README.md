# ECS 50-State Comparison — Postsecondary Education Funding (Tier 2)

**Source:** Education Commission of the States (ECS)
**Publication:** "50-State Comparison: Postsecondary Education Funding" (July 2025)
**Authors:** Chris Duncombe, Erin Whinnery, Shytance Wren, Tom Keily
**Landing page:** https://www.ecs.org/50-state-comparison-postsecondary-education-funding-2025/
**Interactive comparison:** https://reports.ecs.org/comparisons/postsecondary-education-funding-2025
**State profiles:** https://www.ecs.org/postsecondary-education-funding-state-profiles-2025/

## Files

- `ECS_Postsecondary_Funding_2025.pdf` — consolidated 50-state comparison PDF exported from the ECS reports system (https://reports.ecs.org/comparisons/pdf/1144)

## Data format

**PDF only.** ECS does not publish a downloadable CSV/Excel for this comparison. The interactive report (`reports.ecs.org/comparisons/postsecondary-education-funding-2025`) is populated from a proprietary CMS database; the only public export is the PDF.

## Scope

ECS is a **policy database**, not a funding-amount dataset. The 50-state comparison covers categorical policy features rather than dollar appropriations:

- **Budget process** — who submits the postsecondary budget request (coordinating/governing board vs. individual institutions)
- **Funding models** — Base Plus / Funding Formula / Institutional Request / Combination
- **Enrollment factors** — headcount vs. FTE vs. weighted categories
- **Staffing & facility factors** — how staff and square footage enter the formula
- **Performance factors** — outcome metrics (credit hours, degrees/certificates, completion, workforce outcomes)

Broken out separately for 2-year and 4-year institutions.

**Key stat from the 2025 report:** 44 states + DC (2-year) and 42 states + DC (4-year) use coordinating/governing boards to submit budget requests rather than institutions directly.

## Complementary source

For actual dollar funding levels by state, ECS points users to the State Higher Education Finance (SHEF) report from SHEEO:
- https://shef.sheeo.org/

SHEF is not downloaded in this tier but is the natural companion dataset (it provides state appropriations per FTE, state support, net tuition revenue, and higher-education funding effort by state, in dollars).

## Extraction still needed

- Parse the PDF into a structured JSON keyed by state with fields for each policy dimension (budget_process_2yr, budget_process_4yr, funding_model_2yr, funding_model_4yr, performance_metrics, etc.). Recommended approach: `pdfplumber` on the tabular pages, followed by manual schema cleanup.
- No numerical funding data will result from this source — it is a **policy / categorical** complement to the NASBO + ASFIN + NSF dollar data in the sibling directories.
