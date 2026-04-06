# Mexico International Student Data Sources

Last updated: 2026-04-05

## 1. Mexican Students in the United States

### IIE Open Doors (Primary Source)
- **URL:** https://opendoorsdata.org/data/international-students/
- **Coverage:** Annual academic year enrollment, 1949-present
- **Key data points (from CSIS, ICEF, Hispanic Outlook):**
  - 2014/15: ~17,052 (historical peak)
  - 2018/19: 15,229
  - 2019/20: 14,348
  - 2020/21: COVID dip (numbers not yet confirmed)
  - 2022/23: 14,541
  - 2023/24: 15,474 (rank: 11th among sending countries)
- **Notes:**
  - Mexico comprised 5% of all international students when tracking began in 1949 (4th largest sender)
  - Now represents ~1% (11th largest sender)
  - 49% of Mexican students attend institutions in the four US-Mexico border states
  - More than half enrolled in undergraduate programs
  - For full time series, download from opendoorsdata.org (requires clicking through data tables)

### SEVP/SEVIS Data (DHS) -- Already in Project
- **Location:** `/data/sevp/sevis_data_mapping_*.csv`
- **Key data (March 2026 snapshot):**
  - Total active Mexican students (F-1/M-1): **17,851**
  - Male: 9,059 | Female: 8,792
  - By level: Bachelors 7,034, Masters 3,361, Doctorate 1,841, Associate 1,661, Language Training 1,281, High School 1,558 (incl. Primary/Secondary), Flight School 127, Other/Vocational 490
  - STEM students (March 2026): **8,104**
- **Top US states for Mexican students:** TX (4,953), CA (1,979), NY (1,348), MA (979), FL (928), AZ (723), IL (713), UT (713)
- **Time series from SEVIS snapshots:**
  - Jan 2024: 17,423
  - Dec 2024: 18,016
  - Aug 2025: 16,294 (summer dip)
  - Dec 2025: 17,917
  - Mar 2026: 17,851
- **Note:** SEVIS counts active records (higher than Open Doors enrollment because it includes OPT, language training, K-12)

### Field of Study (Open Doors 2022/23)
- Business and Management: 19.5%
- Engineering: 13.5% (below global avg of 19.2%)
- Physical and Life Sciences: 11.4%
- Math and Computer Sciences: 7.1% (below global avg of 23%)

## 2. Mexican Students Abroad (All Destinations)

### UNESCO UIS
- **URL:** https://databrowser.uis.unesco.org/
- **Key data:** 36,922 Mexican students enrolled in higher education abroad (2022)
- **Top destinations (from ICEF Monitor, Feb 2025):**
  - Canada: 16,980 study-permit holders (2023, +14%)
  - United States: ~15,400 in higher education (2023, +7%)
  - Spain: 5,540 (2022/23, +13%)
  - Australia: 3,620 (2024, stable)
  - Germany: 3,600 (2023)
  - United Kingdom: ~1,500 (2022, -18% from 2019)

### IIE Project Atlas
- **URL:** https://www.iie.org/research-initiatives/project-atlas/explore-data/mexico-2/
- **Notes:** Contains outbound mobility data for Mexico but the page returned 404; may need to check updated URL

## 3. International Students Studying IN Mexico (Inbound)

### ANUIES Patlani Survey
- **URL:** https://repositoriointernacional.anuies.mx/
- **Latest report:** https://repositoriointernacional.anuies.mx/wp-content/uploads/2024/06/Reporte_Mov_2023_Junio-20-2024-vfinal.pdf
- **Key data (2014/15, most recent publicly available breakdown):**
  - 7,142 international students pursuing degree programs (45.8% of inbound mobility)
  - 7,010 in temporary mobility with curricular value (44.9%)
  - Total inbound mobility: ~15,600
- **Limitations:** Patlani is survey-based (not a census), relies on institutional reporting, and newer data may exist behind login at patlani.anuies.mx
- **Note:** Mexico does not report inbound student data to OECD, making Patlani the primary source

### ANUIES Statistical Yearbook
- **URL:** https://www.anuies.mx/informacion-y-servicios/informacion-estadistica-de-educacion-superior/anuario-estadistico-de-educacion-superior
- **Coverage:** School population and teaching personnel at all higher education levels
- **Notes:** Primary focus is domestic enrollment; international student breakdown limited

## 4. CONACYT / CONAHCYT / SECIHTI Scholarships

### Organizational History
- **CONACYT** (Consejo Nacional de Ciencia y Tecnologia): Mexico's science council, est. 1970
- Renamed **CONAHCYT** (2023) to include humanities
- Transformed into **SECIHTI** (2024-25): Ministry of Science, Humanities, Technology and Innovation
- **Key policy shift:** International scholarship awards were almost completely eliminated under CONAHCYT/SECIHTI, with financing redirected toward domestic scholarships

### Scholarship Data
- **Source:** https://www.tandfonline.com/doi/full/10.1080/23322969.2025.2546332
- SECIHTI's 2025 website notes the "low rate of return of previously sponsored graduate students" as justification for cuts
- Central call for full PhD funding abroad in 2025 opened March 17
- Support covers tuition, fees, health insurance, living expenses (max 2 years Masters, 4 years PhD)
- **Historical context:** At peak, CONACYT funded thousands of Mexican graduate students abroad annually; exact numbers need extraction from SECIHTI annual reports

### Proyecta 100,000
- Mexican government initiative supporting short-term study including English language programs
- Launched ~2013, wound down after 2017-2018 administration changes
- Contributed to the 2014/15 peak of Mexican students in the US

## 5. H-1B / OPT / Work Visa Data for Mexican Nationals

### H-1B Datahub (in project: `/data/h1b/h1b_datahub_fy*.csv`)
- **Limitation:** Data is organized by employer, NOT by nationality
- Cannot directly extract Mexico-specific H-1B counts from these files
- Would need LCA disclosure data (which has no nationality field either)

### USCIS H-1B Data by Country of Birth
- **Not yet in project** -- need to download from USCIS
- USCIS publishes H-1B petition approval data by country of birth
- URL: https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub
- Mexico is typically in top 10-15 countries for H-1B approvals

### OPT Data
- SEVP STEM data already captured (8,104 Mexican STEM students as of Mar 2026)
- OPT-specific breakdowns by nationality available in SEVIS BTN PDFs (`/data/sevp/2024_all_countries_stemopt.pdf`)

## 6. Key Statistics Summary

| Metric | Value | Year | Source |
|--------|-------|------|--------|
| Mexican students in US (Open Doors) | 15,474 | 2023/24 | IIE |
| Mexican students in US (SEVIS active) | 17,851 | Mar 2026 | DHS/SEVP |
| Mexican STEM students in US | 8,104 | Mar 2026 | SEVIS |
| Mexican students abroad (all destinations) | 36,922 | 2022 | UNESCO |
| Mexican students in Canada | 16,980 | 2023 | IRCC |
| International students in Mexico | ~15,600 | 2014/15 | ANUIES Patlani |
| Mexico US rank (sending country) | 11th | 2023/24 | IIE |

## 7. Data Gaps and Next Steps

1. **Open Doors full time series**: Need to download the complete Mexico enrollment data from opendoorsdata.org (2000-2024)
2. **ANUIES Patlani 2023**: The June 2024 report may have newer inbound mobility data -- download and extract
3. **USCIS H-1B by country of birth**: Download to get Mexico-specific petition data
4. **CONACYT/SECIHTI annual reports**: Extract historical scholarship counts
5. **UNESCO UIS time series**: Download Mexico inbound/outbound mobility time series from databrowser.uis.unesco.org
6. **Canadian IRCC**: Get full time series of Mexican study permit holders
