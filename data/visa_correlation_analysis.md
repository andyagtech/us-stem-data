# Visa & Student Data Correlation Analysis

## Data Inventory

### 1. SEVIS/SEVP - International Student Enrollment (DHS/ICE)

**Files:** `data/sevp/sevis_data_mapping_{month}{year}.csv` (8 snapshots)
- **Granularity:** Country x Degree Level x US State x Gender
- **Time coverage:** Jan 2024, Dec 2024, Aug 2025, Dec 2025, Jan-Mar 2026
- **228 countries, ~70 columns per file**
- **Columns:** Country of Citizenship, Continent, Region, Active Students, Male, Female, Associate through Secondary degree levels, plus distribution across all 50 US states + territories
- **Key stats (Mar 2026):** China = 229,463 active students; India = 350,237; total all countries approx 1.5M

**Files:** `data/sevp/sevis_data_mapping_{month}{year}_stem.csv` (6 snapshots)
- **Granularity:** US State x Degree Level x Country x Gender x Student Count
- **~28,000 rows per file** (micro-level: individual state-degree-country-gender combinations)
- **Time coverage:** Jan 2024, Dec 2024, Aug 2025, Jan-Mar 2026
- **Columns:** State, Abbrv, Student Education Level, CoC (Country of Citizenship), Sex, Count of Active STEM Students

### 2. NSF Survey of Earned Doctorates (NSF/NCSES)

**Files:** `data/nsf_sed/parsed/*.csv` (7 parsed tables) + 90+ raw XLSX tables

| File | Rows | Granularity | Coverage |
|------|------|-------------|----------|
| `table_1_6_broad_field_citizenship_1979_2024.csv` | 68 | Broad field x Citizenship status | 1979-2024 (decennial) |
| `table_1_7_major_field_citizenship_2014_2024.csv` | 234 | Major field x Citizenship status | 2014-2024 (annual) |
| `table_2_8_temp_visa_intending_stay_by_country.csv` | 101 | Country x Region | 2018-2024, includes % intending to stay |
| `table_4_1_financial_support_by_field.csv` | 114 | Field x Support source x Citizenship | 2024 |
| `table_7_5_top_institutions_temp_visa.csv` | 20 | Top 20 institutions | 2024 |
| `table_7_7_top_countries_by_field.csv` | 30 | Top 10 countries x S&E vs non-S&E | 2014-2024 |
| `table_7_8_top_countries_2024.csv` | 40 | Top 40 countries | 2024 |
| `sed_top10_countries_by_year.csv` | 328 | Country x Field category | 2014-2024 |
| `sed_citizenship_by_field.csv` | 680 | Field x Citizenship status | 1979-2024 |

- **Key insight:** China = 6,756 PhDs in 2024 (79.3% intend to stay in US); India = 2,649 (88.4% stay)
- **PhD production is the pipeline's starting point** -- people who later need OPT, H-1B, EB green cards

### 3. H-1B Employer Data Hub (USCIS)

**Files:** `data/h1b/h1b_datahub_fy{2010-2026}.csv`
- **Granularity:** Employer x Fiscal Year x Approval/Denial counts
- **Note: NO country-of-birth field** -- this is employer-level only
- **Processed:** `data/h1b/h1b_by_university.json` (97 universities matched)
- **Columns:** Fiscal Year, Employer, Initial/Continuing Approvals/Denials, NAICS, Tax ID, State, City, ZIP

### 4. DOL LCA Disclosure Data

**Files:** `data/h1b/lca/*.xlsx` (FY2013-2026, quarterly)
- **Granularity:** Individual petition-level: Employer x Job Title x SOC Code x Wage x Location
- **Processed:** `data/h1b/lca_by_university.json` (78 universities)
- **Also:** `data/h1b/LCA_Disclosure_Data_FY2025_Q1.xlsx` (1M+ rows, 97 columns)
- **Note: NO country-of-birth field** -- but has job titles, wages, and SOC codes

### 5. DOL PERM (Green Card Labor Certification)

**Files:** `data/h1b/perm_fy2024_q4.xlsx`
- **Granularity:** Individual employer x Job x Country of citizenship
- **Processed:** `data/h1b/perm_by_university.json`
- **PERM data DOES include country of citizenship** -- critical join key

### 6. State Dept - Nonimmigrant Visa Issuances by Country (NEW)

**Files:** `data/h1b/state_dept/FYs97-24_NIVDetailTable.xlsx`
- **Granularity:** Country x Visa Class (80 visa types including F-1, H-1B, J-1, O-1, L-1)
- **Time coverage:** FY1997-2024 (28 fiscal years)
- **208 countries per year**
- **Extracted CSVs:**
  - `niv_by_country_fy2024.csv` -- All 208 countries with F-1, H-1B, J-1, O-1, L-1, Grand Total
  - `niv_timeseries_key_countries.csv` -- 10 key countries, F-1/H-1B/J-1, FY2010-2024

**Key FY2024 numbers (visa stamps issued at consulates):**

| Country | F-1 | H-1B | J-1 |
|---------|-----|------|-----|
| China (mainland) | 82,654 | 31,735 | 14,297 |
| India | 86,067 | 150,647 | 12,080 |
| South Korea | 11,424 | 3,972 | 12,523 |
| Iran | 4,780 | 191 | 1,084 |
| Bangladesh | 18,723 | 3,125 | 813 |

### 7. State Dept - Immigrant Visa Issuances by Country (NEW)

**Files:** `data/h1b/state_dept/immigrant_visas_by_country_fy2015_2024.csv`
- **Granularity:** Country x Fiscal Year (all immigrant visa categories combined)
- **Time coverage:** FY2015-2024
- **234 countries/regions**
- **Source PDF:** `FY2024AnnualReport_TableXIII_IVbyChargeability.pdf`

### 8. State Dept - Employment-Based (EB) Visas by Country (NEW)

**Files:** `data/h1b/state_dept/eb_visas_by_country_fy2024.csv`
- **Granularity:** Country x EB category (EB-1, EB-2, EB-3, EB-4)
- **Time coverage:** FY2024 only
- **Source PDF:** `FY2024_TableV_IV_by_preference.pdf` (28 pages, also has EB-5 and family preferences)

**Key FY2024 EB numbers:**

| Country | EB-1 | EB-2 | EB-3 (total) | EB-4 (total) | EB Total |
|---------|------|------|--------------|--------------|----------|
| China (mainland) | 6,952 | 6,556 | 6,141 | 78 | 19,727 |
| India | 8,809 | 3,916 | 3,655 | 428 | 16,808 |
| South Korea | 1,321 | 1,139 | 1,125 | 12 | 3,597 |
| Iran | 268 | 1,873 | 170 | 0 | 2,311 |
| Nigeria | 427 | 1,548 | 533 | 175 | 2,683 |
| **Grand Total** | **47,462** | **46,314** | **47,290** | **11,672** | **152,738** |

### 9. State Dept - B-Visa Refusal Rates by Nationality (NEW)

**Files:** `data/h1b/state_dept/b_visa_refusal_rates_{fy23,fy24,fy25}.csv`
- **Granularity:** Country x Fiscal Year
- **199 countries per year**
- **Source PDFs:** `refusal_rates_FY{19-25}.pdf` (7 years downloaded)

**Key refusal rates:**

| Country | FY23 | FY24 | FY25 |
|---------|------|------|------|
| China | 26.6% | 25.4% | 20.2% |
| India | 11.0% | 16.3% | 22.0% |
| Iran | 53.3% | 55.5% | 62.4% |
| Bangladesh | 43.7% | 46.1% | 61.5% |
| Nigeria | 29.2% | 46.5% | 57.0% |
| Brazil | 11.9% | 15.5% | 14.9% |

### 10. Other Supporting Data

| Dataset | Files | Granularity |
|---------|-------|-------------|
| IPEDS completions | `data/ipeds/c{2000-2024}_a.csv` | Institution x CIP code x Degree level x Race |
| IPEDS enrollment | `data/ipeds/enrollment/ef*.csv` | Institution x Race/ethnicity |
| HERD R&D spending | `data/herd/*.xlsx` | Institution x Funding source |
| J-1 Exchange Visitors | `data/h1b/j1_participation_cy2015_2025.xlsx` | National aggregates by category |
| OPT trends | `data/h1b/national_opt_trends.json` | National OPT/STEM-OPT/CPT by year (2007-2024) |
| National visa trends | `data/h1b/national_visa_trends.json` | F-1/J-1/H-1B/O-1/L-1 issuances by FY |
| OPT by university | `data/h1b/opt_by_university.json` | Top 200 schools, OPT/STEM-OPT counts |

---

## Joinable Dimensions

### Country-Level Joins (the strongest correlation axis)

All of these datasets share **country** as a join key, enabling a full pipeline view:

```
SEVIS enrollment (by country, current snapshot)
    |
NSF SED PhD production (by country, 2014-2024 annual)
    |
State Dept F-1 issuances (by country, FY1997-2024)
    |
State Dept B-visa refusal rates (by country, FY2019-2025)
    |
State Dept H-1B issuances (by country, FY1997-2024)
    |
State Dept EB green card issuances (by country, FY2024)
    |
NSF SED % intending to stay (by country, 2018-2024)
```

**Country name normalization needed:** SEVIS uses "CHINA", NSF uses "Chinaa" (footnote marker), State Dept uses "China - mainland"/"China - mainland born". A mapping table is needed.

### Institution-Level Joins

```
IPEDS completions (by institution, CIP code)
    |
SEVIS STEM enrollment (by state -- not institution-level)
    |
NSF SED top 20 institutions (temp visa PhDs)
    |
H-1B by university (USCIS hub, by employer=university)
    |
LCA by university (DOL, job-level)
    |
PERM by university (DOL, green card sponsorship)
    |
OPT by university (top 200 schools)
    |
HERD R&D spending (by institution)
```

### Field-of-Study Joins

```
NSF SED by major field x citizenship (2014-2024)
    |
IPEDS completions by CIP code x NRA status
    |
LCA data by SOC code (occupational proxy for field)
```

### Time-Series Joins (national trends)

```
F-1 issuances (FY2005-2024)
    |
J-1 participants (CY2015-2025)
    |
OPT/STEM-OPT authorizations (CY2007-2024)
    |
H-1B petitions approved (FY2007-2024)
    |
NSF SED temp visa PhDs (1979-2024, decennial; 2014-2024, annual)
```

---

## Proposed Analyses & Charts

### A. The Full Pipeline by Country (Flagship Analysis)

**Chart: Stacked/grouped bar chart, top 10 countries**
- X-axis: Country
- Bars: (1) SEVIS active students, (2) PhDs produced (SED), (3) F-1 visas issued, (4) H-1B visas issued, (5) EB green cards issued
- Shows the "funnel" from enrollment to permanent residency
- China has 229K students but only 32K H-1Bs and 20K EB visas; India has 350K students and 151K H-1Bs

### B. China vs India Divergence Over Time

**Chart: Dual-line time series, FY2010-2024**
- F-1 issuances: China peaked at 274K in FY2015, now at 83K; India peaked at 131K in FY2023
- H-1B issuances: India dominates (151K in FY2024 vs China's 32K)
- PhD production: China stable at ~6,700/year; India growing to 2,649
- Shows complete inversion of the two countries' trajectories

### C. Stay Rate vs Refusal Rate Scatter Plot

**Chart: Scatter plot, one dot per country**
- X-axis: B-visa refusal rate (proxy for visa restrictiveness/risk assessment)
- Y-axis: % of PhD recipients intending to stay in US (from SED table 2-8)
- Size: Number of PhDs produced
- Color: Continent
- Hypothesis: Countries with higher refusal rates may have higher stay rates (people from countries that are harder to return to tend to stay)
- Iran: 55% refusal, very high stay rate; India: 16% refusal, 88% stay rate; China: 25% refusal, 79% stay

### D. EB Green Card Pipeline Bottleneck

**Chart: Ratio chart showing PhD production vs EB visa capacity**
- For each major country: PhDs awarded / EB visas issued = "backlog pressure ratio"
- India: 2,649 new PhDs/year but massive existing H-1B backlog (EB wait times 10+ years)
- China: 6,756 PhDs/year, 19,727 EB visas (but EB-5 is 9,547 of those -- investor visas)
- Highlights countries where the academic pipeline far exceeds green card availability

### E. STEM Concentration by Country Heat Map

**Chart: Heat map, countries x US states**
- Data: SEVIS STEM enrollment data (~28K rows per snapshot)
- Rows: Top 20 countries
- Columns: US states
- Color intensity: Count of STEM students
- Shows geographic clustering (e.g., India concentrated in TX, NJ, CA; China in CA, NY, IL)

### F. Field-of-Study to Work Authorization Flow

**Chart: Sankey/alluvial diagram**
- Left: NSF SED doctoral fields (Engineering, CS, Bio, etc.)
- Middle: % temp visa holders by field
- Right: LCA SOC codes (mapping doctoral fields to actual job categories)
- Shows which fields feed into H-1B employment

### G. National Pipeline Time Series (2007-2024)

**Chart: Multi-line time series**
- Lines: OPT authorizations, STEM-OPT extensions, F-1 issuances, H-1B petitions approved
- All on same chart, indexed to 2007=100
- Shows how OPT/STEM-OPT has grown much faster than H-1B (OPT is now the primary work authorization pathway)
- COVID impact clearly visible in 2020-2021

### H. University-Level Correlation Matrix

**Chart: Scatter plot matrix for top 50 universities**
- Variables: NRA enrollment (IPEDS), PhD completions (IPEDS), OPT students, H-1B petitions filed, PERM applications, R&D spending (HERD)
- Shows correlation between research intensity and foreign worker dependence

---

## Data Gaps

1. **H-1B by country of birth is NOT in USCIS Employer Data Hub.** The USCIS hub only has employer-level data with no nationality/country field. The State Dept NIV detail table provides H-1B *issuances at consulates* by country, which is a close proxy but excludes status changes within the US.

2. **SEVIS STEM data lacks institution-level granularity.** The STEM files break down by State x Country x Degree x Gender, but not by specific university. The non-STEM SEVIS file is country-level only (no state breakdown by degree level).

3. **EB visa data by country is only available for FY2024** (single year from Table V). The multi-year Table XIII has all immigrant visas combined (family + employment + diversity). Historical EB-by-country data would require parsing annual report PDFs for each prior fiscal year.

4. **OPT data by country does not exist in public data.** SEVP publishes OPT by school (top 200) but never breaks down OPT by student nationality. This is a critical gap -- we know 194K people are on OPT but not their country distribution.

5. **No individual-level linkage.** Each dataset is aggregated differently (by country, by institution, by employer, by field). There is no way to track an individual student from SEVIS enrollment through PhD completion to H-1B to green card.

6. **Refusal rates are B-visa only.** The State Dept publishes adjusted refusal rates for B (tourist/business) visas only, not for F-1, H-1B, or other categories. F-1 and H-1B refusal rates by country would be extremely valuable but are not publicly available.

7. **PERM data has country of citizenship** but the processed `perm_by_university.json` may not aggregate by country. Re-processing the raw PERM XLSX to extract country-level patterns would fill a gap.

8. **No data on denied/revoked F-1 or H-1B by country.** We have issuances but not denial rates for work/student visas by nationality. Only B-visa refusal rates are published.
