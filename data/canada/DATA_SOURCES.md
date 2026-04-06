# Canadian International Student Data - IRCC Open Data

**Downloaded:** 2026-04-05
**Source:** Immigration, Refugees and Citizenship Canada (IRCC) Open Data Portal

> Note: Values between 0 and 5 are shown as "--" and all other values are rounded to the nearest multiple of 5. Data are preliminary estimates subject to change.

---

## Study Permit Holders

### 1. study_permits_by_citizenship.csv / .xlsx
- **Description:** Study permit holders by country of citizenship, monthly granularity
- **Source URL:** https://open.canada.ca/data/en/dataset/90115b00-f9b8-49e8-afa3-b4cff8facaee
- **Direct CSV:** https://www.ircc.canada.ca/opendata-donneesouvertes/data/ODP-TR-Study-IS_CITZ.csv
- **Direct XLSX:** https://www.ircc.canada.ca/opendata-donneesouvertes/data/EN_ODP-TR-Study-IS_CITZ_sign_date.xlsx
- **Format:** Tab-separated CSV (9 columns: year, quarter, month, FR equivalents, country EN/FR, total)
- **Coverage:** January 2015 - January 2026 (monthly)
- **Records:** 22,362 rows, 220 unique countries

### 2. study_permits_yearend_by_citizenship.xlsx
- **Description:** Study permit holders with a valid permit on December 31st, by country of citizenship
- **Direct URL:** https://www.ircc.canada.ca/opendata-donneesouvertes/data/EN_ODP_annual-TR-Study-IS_CITZ_year_end.xlsx
- **Format:** XLSX with header rows (country x year matrix, values as formatted strings with commas)
- **Coverage:** 2000 - 2024 (annual Dec 31 snapshots)
- **Records:** ~228 countries

### 3. study_permits_by_province_study_level.xlsx
- **Description:** Study permit holders by province/territory and study level
- **Direct URL:** https://www.ircc.canada.ca/opendata-donneesouvertes/data/EN_ODP-TR-Study-IS_PT_study_level_sign.xlsx
- **Format:** XLSX with multi-level headers (province/study level x year/quarter/month)
- **Coverage:** January 2015 - January 2026

### 4. study_permits_by_province_gender.xlsx
- **Description:** Study permit holders by province/territory and gender
- **Direct URL:** https://www.ircc.canada.ca/opendata-donneesouvertes/data/EN_ODP-TR-Study-IS_PT_gender_sign.xlsx
- **Format:** XLSX with multi-level headers
- **Coverage:** January 2015 - January 2026

### 5. study_permits_yearend_by_province_study_level.xlsx
- **Description:** Year-end (Dec 31) study permit holders by province/territory and study level
- **Direct URL:** https://www.ircc.canada.ca/opendata-donneesouvertes/data/EN_ODP_annual-TR-Study-IS_PT_study_level_year_end.xlsx
- **Coverage:** Annual snapshots

---

## Work Permits - International Mobility Program (IMP)

### 6. imp_by_citizenship.csv
- **Description:** IMP work permit holders by country of citizenship (includes PGWP and other IMP streams)
- **Source URL:** https://open.canada.ca/data/en/dataset/360024f2-17e9-4558-bfc1-3616485d65b9
- **Direct URL:** https://www.ircc.canada.ca/opendata-donneesouvertes/data/ODP-TR-Work-IMP-CITZ.csv
- **Format:** Tab-separated CSV
- **Coverage:** 2015 - 2026

### 7. imp_yearend_by_citizenship.xlsx
- **Description:** All IMP work permit holders on December 31st by country of citizenship (all purposes)
- **Direct URL:** https://www.ircc.canada.ca/opendata-donneesouvertes/data/en_odp_annual-tr-work-imp_citz_year_end_all_purpose.xlsx
- **Coverage:** Annual Dec 31 snapshots

---

## Post-Graduation Work Permits (PGWP)

### 8. pgwp_by_province_cma.xlsx
- **Description:** PGWP holders by province/territory and Census Metropolitan Area (CMA)
- **Direct URL:** https://www.ircc.canada.ca/opendata-donneesouvertes/data/EN_ODP-TR-Work-PGWP_PT_CMA_sign.xlsx
- **Coverage:** Monthly data

### 9. pgwp_by_province_csd.csv
- **Description:** PGWP holders by province/territory, Census Division, and Census Subdivision
- **Direct URL:** https://www.ircc.canada.ca/opendata-donneesouvertes/data/ODP-TR-Work-PGWP-PT_CSD.csv
- **Format:** Tab-separated CSV
- **Coverage:** Monthly data, very granular geography

### 10. pgwp_yearend_by_province_cma.xlsx
- **Description:** PGWP holders on December 31st by province/territory and CMA
- **Direct URL:** https://www.ircc.canada.ca/opendata-donneesouvertes/data/EN_ODP_annual-TR-work-IMP_PT_CMA_year_end.xlsx
- **Coverage:** Annual Dec 31 snapshots

---

## Key Observations

### Scale and Trends
- Canada had **~996,000 international students** on valid study permits as of Dec 31, 2024 (down from peak of ~1,037,000 in 2023)
- Total grew from ~123,000 in 2000 to nearly 1 million in 2024 (8x increase)

### Top Source Countries (Dec 31, 2024 stock)
| Rank | Country | 2024 Stock | 2019 Stock | Change |
|------|---------|-----------|-----------|--------|
| 1 | India | 392,810 | 218,515 | +80% |
| 2 | China | 99,650 | 140,530 | -29% |
| 3 | Nigeria | 45,110 | 11,870 | +280% |
| 4 | Philippines | 43,785 | 7,730 | +466% |
| 5 | France | 25,080 | 23,845 | +5% |
| 6 | Iran | 23,185 | 14,610 | +59% |
| 7 | Nepal | 22,045 | 1,155 | +1,809% |
| 8 | Vietnam | 17,790 | 21,475 | -17% |
| 9 | Algeria | 16,630 | 3,620 | +359% |
| 10 | Bangladesh | 15,185 | 8,375 | +81% |

### China-Specific Trends
- Chinese student stock peaked at ~141,710 in 2018, declined to 99,650 by 2024 (-30%)
- Monthly new permits show steady decline: 87,950 (2019) -> 51,885 (2025)
- China went from #1 source country to #2 (overtaken by India around 2018)

### India-Specific Trends
- India saw explosive growth: 2,210 (2000) -> 392,810 (2024)
- Peak new permits in 2023 (283,690), sharp drop in 2024 (193,090) and 2025 (99,695)
- 2024-2025 decline likely reflects new Canadian study permit caps

### Notable Additional Sources Available (not downloaded)
- TFWP (Temporary Foreign Worker Program) by citizenship, province, occupation (NOC codes)
- IMP by province and program type
- IMP by gender and occupational skill level
- Work permits by NOC 4-digit occupation code
- Humanitarian and compassionate work permits
