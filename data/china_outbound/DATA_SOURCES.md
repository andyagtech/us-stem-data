# China Outbound Student Mobility - Data Sources

Last updated: 2026-04-05

## Primary Sources (with direct data access)

### United States - SEVP/SEVIS (Project Data)
- **Files**: `data/sevp/sevis_data_mapping_*.csv`
- **Description**: Active F/M visa student counts by country, state, and degree level from ICE SEVP snapshots
- **Coverage**: Dec 2024, Jan 2024, Aug 2025, Dec 2025, Jan-Mar 2026 (plus STEM breakdowns)
- **URL**: https://www.ice.gov/sevis/data

### United States - IIE Open Doors
- **Description**: Annual survey of international students at US higher education institutions
- **Coverage**: Academic years 2009/10 through 2024/25
- **Key report**: Open Doors 2025 (released November 2025)
- **URL**: https://opendoorsdata.org/data/international-students/all-places-of-origin/
- **Press release**: https://www.iie.org/news/open-doors-2025-press-release/
- **China fact sheet**: https://opendoorsdata.org/wp-content/uploads/2023/11/OpenDoors_FactSheet_China_2023.pdf

### United Kingdom (Project Data)
- **Files**: `data/uk/uk_student_trends.json`, `data/uk/uk_visa_grants.json`
- **HESA enrollment**: https://www.hesa.ac.uk/data-and-analysis/students/where-from
- **Home Office visa data**: https://www.gov.uk/government/statistical-data-sets/immigration-system-statistics-data-tables
- **Coverage**: HESA 2015/16-2023/24; Visa grants 2018-2025 (2025 partial Q1-Q3)

### Canada (Project Data)
- **Files**: `data/canada/study_permits_by_citizenship.csv`, `data/canada/study_permits_yearend_by_citizenship.xlsx`
- **Source**: Immigration, Refugees and Citizenship Canada (IRCC) via Open Government Portal
- **URL**: https://open.canada.ca/data/en/dataset/90115b00-f9b8-49e8-afa3-b4cff8facaee
- **Coverage**: Monthly data 2015-2026 (2026 partial)

## Secondary Sources (published statistics, not raw data)

### UNESCO UIS - Outbound Mobility
- **Description**: Global count of Chinese degree-seeking students abroad
- **Key figure**: 1,021,303 (2023 record)
- **URL**: https://data.uis.unesco.org/
- **Caveat**: China sends limited data to UNESCO; figures are aggregated from host country reports

### China Ministry of Education (MOE)
- **Description**: Return statistics (haigui), cumulative study-abroad figures
- **Key figures**: 495,000 returned in 2024 (+19.1% YoY); 8.88 million total studied abroad 1978-2024
- **URL**: https://english.www.gov.cn/archive/statistics/202512/11/content_WS693aaa4fc6d00ca5f9a080a6.html
- **Coverage**: https://www.globaltimes.cn/page/202512/1350303.shtml

### Australia - Department of Education
- **Description**: International student enrollment data by country and sector
- **URL**: https://www.education.gov.au/international-education-data-and-research/international-student-monthly-summary-and-data-tables
- **Note**: Data portal allows exploration by month, year, sector, source country

### Japan - JASSO
- **Description**: Annual survey of international students (as of May 1 each year)
- **Key figure**: 123,485 Chinese students in 2024 (+6.9% YoY)
- **URL**: https://www.studyinjapan.go.jp/en/statistics/enrollment/data/2504301000.html
- **PDF**: https://www.studyinjapan.go.jp/en/_mt/2025/04/data2024z_e.pdf

### South Korea - Korean Education Statistics Service
- **Description**: International student enrollment
- **URL**: https://kess.kedi.re.kr (Korean-language)
- **Note**: ~84,000 Chinese students in 2024; share declining from 55% (2022) to ~40% (2023)

### Germany - DAAD / Destatis
- **Description**: International student statistics by nationality
- **Key figure**: ~38,600 Chinese students in 2024/25 (declining ~7% since 2019)
- **URL**: https://www.daad.de/en/the-daad/communication-publications/press/
- **Alt**: https://www.studying-in-germany.org/germany-international-student-statistics/

### France - Campus France
- **Description**: International student enrollment in French higher education
- **URL**: https://www.campusfrance.org/en
- **Note**: ~31,000 Chinese students estimated 2024; France enrolled 430k+ international students total in 2023/24

## Policy Sources

### US Proclamation 10043
- **Wikipedia**: https://en.wikipedia.org/wiki/Proclamation_10043
- **Georgetown CSET analysis**: https://cset.georgetown.edu/publication/assessing-the-scope-of-u-s-visa-restrictions-on-chinese-students/
- **TIME (Rubio 2025 expansion)**: https://time.com/7289945/us-china-trump-rubio-international-student-visa-restrictions-trade-negotiations/

### CCG Annual Report on Chinese Students Abroad
- **Description**: Comprehensive annual report from Center for China and Globalization
- **URL**: http://en.ccg.org.cn/archives/87548
- **Coverage**: 2024-2025 edition

## Data Quality Notes

1. **Open Doors vs SEVIS**: Open Doors counts are academic-year totals including OPT; SEVIS snapshots are point-in-time active records. Numbers will differ.
2. **Canada study permits**: Monthly issuance data summed to annual. Not the same as year-end active holders (year-end holders ~100k for China in 2022).
3. **Australia**: Different sources report different numbers depending on whether they count enrollments, student visa holders, or unique students. Higher education vs all sectors also varies.
4. **UNESCO totals**: Aggregate of host-country reports, not Chinese government data. May not match sum of individual country figures due to coverage gaps and timing differences.
5. **Return rates**: MOE return figures count those who registered with Chinese authorities upon return. Actual returns may be higher (some don't register) or lower (some return temporarily).
