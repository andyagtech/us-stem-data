# State Taxpayer Funding of US Universities — Additional Data Sources

Research compiled 2026-04-05. Goal: extend the PhD Demographics project beyond IPEDS Finance, NSF HERD, FSA, and USASpending with additional state-level taxpayer-funding data sources.

---

## TIER 1 — HIGHEST VALUE, READY TO INGEST

### 1. SHEEO SHEF — State Higher Education Finance Report
- **URL:** https://shef.sheeo.org/ | Data: https://shef.sheeo.org/data-downloads/
- **What:** Education appropriations, state+local support, net tuition revenue, FTE enrollment, state financial aid, capital appropriations, federal stimulus, performance-based funding allocations.
- **Granularity:** State-level and sector-level (public 2yr / 4yr / research). Sector determined per institution via Carnegie. NOT institution-level in the main tables, but sector is aggregated from institution data. **SHEF Expansion Dashboard** combines with IPEDS for institution-level exploration.
- **Time coverage:** FY1980–FY2024 (most tables); capital appropriations FY2020–FY2024; stimulus FY2009–FY2024.
- **Format:** XLSX downloads for all tables; PDF report.
- **Downloadable:** Yes, direct (no scraping). Open in Safari per their instructions.
- **Value-add over IPEDS:** SHEF normalizes across states, adjusts for tuition offsets, HEPI inflation, and cost-of-living. Provides state-effort and capacity metrics. Includes the **Grapevine** preliminary data (next-FY estimates published in January) — IPEDS lags 18–24 months.
- **Key tables:**
  - Table 1.1–1.4: Sources and uses of state funding
  - Tables 2.x, 3.x: Revenue and enrollment distribution
  - Tables 4.x: Tuition revenue
  - Capital Appropriations dataset (separate)

### 2. SHEEO Grapevine Report
- **URL:** https://shef.sheeo.org/grapevine/
- **What:** Earliest available state tax appropriations for higher ed, published each January for the current FY.
- **Granularity:** State-level, 50 states + DC.
- **Time coverage:** 1980–present (FY2025 initial estimates available).
- **Format:** Interactive tables + XLSX.
- **Value-add:** ~18-month lead on IPEDS finance data. Originally from Illinois State University Center for the Study of Education Policy, now consolidated into SHEF.

### 3. NIH RePORTER / ExPORTER
- **URL:** https://reporter.nih.gov/ | API: https://api.reporter.nih.gov/ | Bulk: https://exporter.nih.gov/
- **What:** All NIH grants (~$45B/yr) by project, PI, institution, department, fiscal year, dollar amount, publications, clinical studies, patents.
- **Granularity:** Project-level, PI-level, institution-level, department-level (often). FY1985–present, ~2.6M projects.
- **Format:** JSON via API v2; weekly CSV/XML bulk files via ExPORTER.
- **Downloadable:** Yes. API has 10K-record limit per query → must page or use weekly ExPORTER dumps (no limit).
- **Value-add:** IPEDS bundles federal grants as aggregate; RePORTER breaks it to grant level with PI names, project abstracts, and department — invaluable for cross-referencing researcher demographics and research topics (e.g., dual-use, China collaboration indicators).

### 4. NSF Award Search
- **URL:** https://www.nsf.gov/awardsearch/ | Bulk: https://www.nsf.gov/awardsearch/download.jsp | API: https://api.nsf.gov/services/v1/awards
- **What:** All NSF grants (~$9B/yr) by award, PI, institution, directorate, amount.
- **Granularity:** Award-level, institution-level. 2007–present via API; historical downloads back to FY1959.
- **Format:** As of Jan 2025, **bulk downloads converted from XML to JSON**; CSV/Excel/XML exports for <3000 results from the web UI.
- **Downloadable:** Yes, zipped annual dumps + API.
- **Value-add:** Parallels NIH RePORTER for the other major federal science agency. Include abstract text for classification.

### 5. InformEd States Datasets
- **URL:** https://informedstates.org/data
- **What:** (a) State Funding Mechanisms dataset — how states allocate funding (formulas, base-plus, performance). (b) Workforce-Oriented Performance-Based Funding dataset.
- **Granularity:** State-by-sector level (FY2004–FY2020 for mechanisms).
- **Format:** XLSX with data dictionary tab.
- **Value-add:** Explains the *method* by which state dollars flow to institutions — critical for interpreting SHEF numbers. The only longitudinal dataset of funding-mechanism details.

---

## TIER 2 — HIGH VALUE, STATE-LEVEL AGGREGATES

### 6. NASBO State Expenditure Report
- **URL:** https://www.nasbo.org/reports-data/state-expenditure-report | Archive: https://www.nasbo.org/reports-data/state-expenditure-report/state-expenditure-archives
- **Latest PDF:** 2024 Report (FY2022–FY2024): https://higherlogicdownload.s3.amazonaws.com/NASBO/9d2d2db1-c943-4f1b-b750-0fca152d64c2/UploadedImages/SER%20Archive/2024_SER/2024_State_Expenditure_Report_S.pdf
- **Higher Ed section (2024):** https://higherlogicdownload.s3.amazonaws.com/NASBO/9d2d2db1-c943-4f1b-b750-0fca152d64c2/UploadedImages/SER%20Archive/2024_SER/Higher_Education_-_2024_State_Expenditure.pdf
- **What:** Higher-ed expenditures by state funds vs federal pass-through vs bonds, as % of state total, annual % change.
- **Granularity:** State-level.
- **Time coverage:** Annual since 1987.
- **Format:** PDF only (will require tabula-py or pdfplumber extraction).
- **Value-add:** Unlike SHEF which focuses on *appropriations to institutions*, NASBO captures total state *expenditures on* higher ed, including federal pass-through dollars. Also shows higher ed's share of state budget vs Medicaid, K-12, corrections etc.

### 7. NSF NCSES Survey of Federal Funds for R&D
- **URL:** https://ncses.nsf.gov/surveys/federal-funds-research-development
- **What:** Federal obligations/outlays for R&D at universities, by agency and performer.
- **Granularity:** Agency × state × performer type. Complements HERD (which is institution-level self-reported) with agency-side obligations.
- **Time coverage:** Annual, FY1951+.
- **Format:** Tables + downloadable data.
- **Value-add:** Cross-check HERD numbers from the funder side; captures obligated-but-not-yet-expended funds.

### 8. Census Bureau Annual Survey of State Government Finances (ASFIN)
- **URL:** https://www.census.gov/programs-surveys/state.html
- **What:** Revenue, expenditure, debt, assets by function — including "state institutions of higher education" line item.
- **Granularity:** State-level.
- **Time coverage:** Annual since 1952.
- **Format:** Downloadable CSV/Excel via Census data portal.
- **Value-add:** Independent audit-quality crosscheck on SHEEO and NASBO. Consistent methodology across 70+ years.

### 9. Urban Institute — State and Local Finance Initiative
- **URL:** https://www.urban.org/policy-centers/cross-center-initiatives/state-and-local-finance-initiative/state-and-local-backgrounders/higher-education-expenditures
- **Interactive tool:** https://apps.urban.org/features/higher-education/ — "Financing Public Higher Education"
- **What:** Analytical reports + interactive tool examining how state appropriations per student have declined and tuition compensated.
- **Granularity:** State-level, per-FTE.
- **Value-add:** Pre-processed analysis and time-series charting. Good for framing, not primary data source.

### 10. Education Commission of the States — 50-State Comparison
- **URL:** https://www.ecs.org/50-state-comparison-postsecondary-education-funding-2025/
- **What:** How each state determines funding levels — formulas, base-plus, institutional request, performance factors.
- **Granularity:** State-level policy descriptions.
- **Format:** HTML tables (scrape) + narrative profiles.
- **Value-add:** Policy context layer. Partnership with NCHEMS.

---

## TIER 3 — INSTITUTION-LEVEL, STATE-SPECIFIC

### 11. California LAO — Legislative Analyst's Office
- **URL:** https://lao.ca.gov/ | EdBudget: https://lao.ca.gov/EdBudget
- **What:** Line-item UC/CSU/CCC appropriations, per-student GF support, tuition revenue.
- **Granularity:** Institution (UC and CSU systems get breakdowns; sometimes campus level).
- **Format:** PDF + XLSX tables on EdBudget.
- **Downloadable:** Yes.
- **Value-add:** For UC San Diego, UC Berkeley, UCSF — dollar-level detail beyond IPEDS.

### 12. Texas LBB — Legislative Budget Board
- **URL:** https://www.lbb.texas.gov/Higher_Education.aspx
- **Budget docs:** https://www.lbb.texas.gov/ (biennial General Appropriations Act)
- **THECB data:** http://www.txhighereddata.org/
- **What:** Biennial General Appropriations Act with university-by-university line items, funding formulas by sector.
- **Time coverage:** Biennial since 1992+.
- **Format:** PDF (LBB) + downloadable data (THECB).
- **Value-add:** UT Dallas and other Texas publics in the project — direct state-level line items.

### 13. Florida Board of Governors — State University System
- **URL:** https://www.flbog.edu/finance/university-budget-information/operating-budget-summaries/
- **Expenditure:** https://www.flbog.edu/finance/university-budget-information/expenditure-analysis/
- **Dashboards:** https://www.flbog.edu/resources/data-analytics/dashboards/
- **What:** Operating budget summaries per SUS institution + expenditure analysis.
- **Granularity:** Institution-level (UF, FSU, USF, UCF, FIU, etc.).
- **Time coverage:** FY2008-09 through FY2025-26.
- **Format:** PDF summary books + dashboards.
- **Value-add:** Granular per-institution breakdowns of GR appropriations, tuition, contracts & grants.

### 14. GASB Comprehensive Annual Financial Reports (ACFRs / CAFRs)
- **What:** Each public university (and each state) publishes audited financial statements following GASB standards. Include state appropriations received, net position, pension liabilities, OPEB, bond debt.
- **Where:** University's controller/treasurer pages. No central repository.
- **Granularity:** Institution-level, very detailed, audited.
- **Format:** PDF (a few offer XBRL).
- **Downloadable:** Yes, but requires per-institution scraping.
- **Value-add:** Only place you get audited numbers for pension obligations, OPEB, and internal service funds. Reconciles with IPEDS but includes components IPEDS omits.

---

## TIER 4 — SPECIALIZED / ADJACENT

### 15. USDA NIFA — Hatch Act / Smith-Lever (Land Grant Funding)
- **URL:** https://www.nifa.usda.gov/grants/programs/capacity-grants
- **Grant Funding Dashboard:** https://www.nifa.usda.gov/data/nifa-dashboards/grant-funding-dashboard
- **Data Gateway:** https://www.nifa.usda.gov/data/data-gateway
- **Reporting Portal:** https://portal.nifa.usda.gov/
- **What:** Capacity grants to 1862/1890/1994 land-grant institutions under Hatch (research) + Smith-Lever (extension).
- **Granularity:** Institution-level, project-level since FY2018.
- **Format:** Dashboard + data gateway; pulls from USAspending monthly.
- **Value-add:** Most land-grant universities (e.g., Missouri, Missouri S&T's sister institutions) receive formula funds that are NOT visible in typical grant searches.

### 16. MSRB EMMA — Municipal Bonds
- **URL:** https://emma.msrb.org/ | Research: https://www.msrb.org/EMMA-Research
- **What:** All municipal bond issuances and disclosures, including university revenue bonds + state GO bonds for university construction.
- **Granularity:** Bond issue (CUSIP) level; issuer detail.
- **Format:** HTML search, PDF official statements, XBRL for some. No clean bulk download — MSRB sells bulk data subscriptions; public site supports search only.
- **Downloadable:** Scraping required. MSRB offers commercial data feeds.
- **Value-add:** Tax-exempt construction financing is a HUGE indirect state subsidy (tax expenditure) never captured in SHEF or IPEDS. University-issued revenue bonds often backed by implicit state guarantee.

### 17. Public Plans Data (Center for Retirement Research, Boston College)
- **URL:** https://publicplansdata.org/
- **What:** 250+ state and local DB pension plans, plan-level data on assets, liabilities, funded ratio, contributions, retiree health.
- **Granularity:** Plan-level (many states have separate university plans — e.g., TRS-Illinois SURS, Texas TRS, CalPERS/CalSTRS, Ohio STRS).
- **Time coverage:** 2001–present.
- **Format:** CSV downloads; API.
- **Value-add:** University employer contributions are a major taxpayer subsidy; pension liabilities often dwarf annual appropriations. Illinois SURS is a particularly well-known case.

### 18. Federal Reserve — State & Local Pension Plans Dataviz
- **URL:** https://www.federalreserve.gov/releases/z1/dataviz/pension/
- **What:** State-level aggregate pension funded status.
- **Granularity:** State aggregate.
- **Format:** Downloadable CSV.
- **Value-add:** Independent source for state-aggregate pension funding.

### 19. Commonfund Higher Education Price Index (HEPI)
- **URL:** https://www.commonfund.org/higher-education-price-index
- **What:** Inflation index specifically for higher-ed costs (faculty salaries, benefits, services, utilities, supplies).
- **Time coverage:** 1961–present; calculated annually since 1983.
- **Format:** PDF annual report (free download).
- **Value-add:** Use instead of CPI for deflating time-series university finance data. SHEF uses HECA (a related index) — HEPI is an alternative.

### 20. USAspending.gov — Bulk Download / API
- **URL:** https://www.usaspending.gov/ | API: https://api.usaspending.gov/
- **Already in project** but noting: bulk download endpoint supports filtering by recipient and date back to FY2001 for custom award data, FY2008 for the Award Data Archive. The /v2/bulk_download/awards endpoint is the recommended path for the recipient-type=Higher Ed filter.

---

## CONSOLIDATED / AGGREGATED SOURCES (what doesn't really exist)

**There is no single "state higher-ed appropriations dashboard"** that combines all these. The closest candidates:

- **SHEEO SHEF Expansion Dashboard** — combines SHEF + IPEDS for institution-level exploration. Best unified view but limited to what IPEDS captures.
- **Urban Institute "Financing Public Higher Education"** interactive — https://apps.urban.org/features/higher-education/ — pre-built visualization but not a raw data source.
- **Chronicle of Higher Education "Almanac"** (paywall) — aggregates many sources for subscribers.

**Think tank coverage:**
- **Brookings:** Publishes occasional reports (e.g., "State Support for Higher Education, Medicaid, and the Business Cycle"; "Designing state funding formulas for public higher education to center equity") but does not maintain a tracker. Uses SHEF data.
- **AEI:** Publishes analytical pieces (e.g., "What More Funding for State Universities Buys Students"). No tracker. Relies on SHEF/IPEDS.
- **Manhattan Institute:** Occasional analyses; no dedicated higher-ed finance database.
- **Reason Foundation:** Public pension debt rankings — https://reason.org/commentary/public-pension-debt-rankings-for-state-and-local-governments/
- **Hoover Institution:** Unfunded pension liabilities reports (Giesecke).

**Conclusion:** SHEEO SHEF + the Grapevine dataset are the closest thing to a canonical, cross-state, longitudinal source. Everything else supplements it.

---

## RECOMMENDED INGESTION PRIORITY

For the PhD Demographics project, the highest marginal-value additions over current sources (IPEDS, HERD, FSA, USASpending):

1. **SHEEO SHEF + Grapevine (XLSX)** — trivial ingest, gives normalized cross-state series + forward-looking data IPEDS lacks.
2. **NIH RePORTER ExPORTER (weekly CSV dumps)** — PI/department granularity; enables joining research dollars to individual demographics already tracked in the project.
3. **NSF Award Search (annual JSON dumps)** — same logic as NIH.
4. **InformEd States funding mechanisms XLSX** — explains the *how* of state funding.
5. **Public Plans Data CSV** — captures pension subsidies that are essentially hidden state funding.
6. **NASBO State Expenditure Report (PDF)** — annual, PDF extraction needed but covers federal pass-through not in SHEF.
7. **State-specific (CA LAO, TX LBB, FL BOG)** — only for universities actually in the project (UC system, UT Dallas, Florida SUS); provides institutional line items.
8. **GASB ACFRs (per-institution scrape)** — last, because per-institution PDF work is expensive.

## NOT RECOMMENDED (for this project's scope)

- **MSRB EMMA municipal bonds** — Important conceptually (tax expenditure) but no bulk download; scraping cost too high relative to marginal insight for a PhD demographics project.
- **NIFA Hatch/Smith-Lever** — Only matters for a handful of land-grant universities; small dollars relative to total funding.
- **HEPI** — Use only as a deflator; not primary data.
