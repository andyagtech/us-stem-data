# India Outbound Student Mobility: Data Sources

Last updated: 2026-04-05

## Overview

This directory contains statistics on Indian students studying abroad, compiled from
government data (India, US, Canada, UK, Australia, Germany, New Zealand), international
organizations (UNESCO, IIE), and project-local SEVIS/IRCC datasets.

---

## 1. India Government Sources

### Ministry of External Affairs (MEA)
- **What it covers**: Stock of Indian students registered with Indian missions abroad, by country
- **Key data**: 1,335,878 Indian students abroad in 2024; 1,318,955 in 2023; 907,404 in 2022
- **Lok Sabha Question No. 894**: [MEA Lok Sabha response](https://www.mea.gov.in/lok-sabha.htm?dtl%2F38014%2FQUESTION+No894+INDIAN+STUDENTS+STUDYING+ABROAD=)
- **Coverage**: ~108 countries. Based on voluntary registration with missions + host govt coordination.
- **Media coverage**:
  - [The PIE News: Over 1.3 million Indian students studying abroad in 2024](https://thepienews.com/over-1-3-million-indian-students-studying-abroad-in-2024/)
  - [Business Standard: Over 1.3mn Indian students abroad](https://www.business-standard.com/external-affairs-defence-security/news/over-1-3-mn-indian-students-pursuing-higher-studies-abroad-in-2024-govt-124080101441_1.html)
  - [EDMAT: Government reports over 1.3 million](https://www.edmat.org/blog/government-reports-over-1-3-million-indian-students-studying-abroad-in-2024)
- **Limitation**: Voluntary registration means actual numbers likely higher. Different missions may count differently.

### Bureau of Immigration (BoI)
- **What it covers**: Annual outbound departures from India on student visas
- **Key data**: 760,073 departures in 2024; 894,783 in 2023 (peak); 752,111 in 2022; 260,363 in 2020
- **Source**: [Y-Axis / BoI data summary](https://www.y-axis.com/news/indian-students-abroad-hit-new-high-with-760000-in-2024/)
- **Limitation**: Counts departures, not stock. A student already abroad from prior year is not recounted.

### National Medical Commission (NMC) / FMGE
- **What it covers**: Foreign Medical Graduate Examination — required for Indian citizens with foreign medical degrees to practice in India
- **Key data**: 61,616 total FMGE candidates in 2024; 10,269 passed (16.7% overall pass rate)
- **Country-wise pass rates**: Georgia (35.65%), Russia (29.54%), Philippines (24%), Kazakhstan (18.5%), China (19.2%)
- **China specifically**: 13,427 candidates from Chinese universities, 2,580 passed
- **Sources**:
  - [CareerMarg: FMGE 2024 Country-Wise Success Rates](https://www.careermarg.com/article/fmge-2024-country-wise-success-rates-top-universities-for-indian-students)
  - [Careers360: Top Performing Countries in FMGE 2024](https://studyabroad.careers360.com/articles/top-performing-countries-in-fmge-2024)
  - [University World News: 25,000 go abroad yearly to study medicine](https://www.universityworldnews.com/post.php?story=20240822135849204)

---

## 2. United States Sources

### IIE Open Doors Report
- **What it covers**: Annual census of international students enrolled at US higher education institutions
- **Key data**: 363,019 Indian students in 2024/25; 331,602 in 2023/24; 268,923 in 2022/23
- **Historical**: Time series from 2009/10 (~104,897) through 2024/25 (363,019)
- **URLs**:
  - [Open Doors main page](https://opendoorsdata.org/annual-release/international-students/)
  - [All Places of Origin](https://opendoorsdata.org/data/international-students/all-places-of-origin/)
  - [IIE Open Doors 2025 Press Release](https://www.iie.org/news/open-doors-2025-press-release/)
- **India surpassed China** as #1 origin country in 2023/24 for first time since 2009
- **Media**:
  - [ThePrint: 17% drop in new international students in US](https://theprint.in/india/education/17-drop-in-new-international-students-in-us-in-fall-2025-indians-remain-largest-cohort-open-doors/2785710/)
  - [WENR: Slowing Growth and Uncertainty](https://wenr.wes.org/2024/12/slowing-growth-and-uncertainty-a-look-at-iies-open-doors-report-2024-and-what-the-future-might-hold)

### SEVP/ICE SEVIS Data (Local Files)
- **What it covers**: Point-in-time snapshots of active F/M student visa records by country
- **Local path**: `/Users/andy/usds_china/data/sevp/`
- **Key India data points** (active students):
  - Jan 2024: 337,478
  - Dec 2024: 370,846 (peak)
  - Dec 2025: 353,737
  - Mar 2026: 350,237
- **STEM students from India**:
  - Jan 2024: 308,252
  - Dec 2024: 340,699
  - Mar 2026: 321,546
- **Note**: SEVIS counts are higher than Open Doors because they include OPT, language training, flight school, etc. ~91% of Indian SEVIS records are STEM-designated.

---

## 3. Canada Source

### IRCC Study Permits (Local File)
- **What it covers**: Study permit holders with valid permit on December 31, by citizenship
- **Local path**: `/Users/andy/usds_china/data/canada/study_permits_yearend_by_citizenship.xlsx`
- **Key India data**: 392,810 valid permits on Dec 31 2024; 426,195 in 2023 (peak); 318,225 in 2022
- **Historical**: Full series from 2000 (2,210) through 2024 (392,810)
- **Note**: India was #1 source for Canadian study permits from ~2018 onward. Sharp decline in new permits in 2025 (71% rejection rate).
- **Media**: [ICEF Monitor: Indian students abroad fell in 2025](https://monitor.icef.com/2025/12/the-number-of-indian-students-abroad-fell-in-2025/)

---

## 4. United Kingdom Source

### Home Office Immigration Statistics + HESA (Local File)
- **What it covers**: Student visa grants + HESA enrollment data
- **Local path**: `/Users/andy/usds_china/data/uk/uk_student_trends.json`
- **HESA enrollment 2023/24**: 166,310 Indian students (down 15% YoY)
- **Visa grants by year**: From 18,027 in 2018 to peak of 138,157 in 2022, down to 88,610 in 2024
- **Graduate Route**: Indian nationals = 46% of all Graduate Route visa grants
- **Source URLs**:
  - [HESA](https://www.hesa.ac.uk/data-and-analysis/students/where-from)
  - [Home Office statistics](https://www.gov.uk/government/statistical-data-sets/immigration-system-statistics-data-tables)

---

## 5. Australia Source

### Dept of Education + MEA
- **Key data**: ~122,202 Indian students in 2024 (MEA); 139,720 Jan-Sep 2025 (Dept of Education)
- **India is 2nd largest source** (17% of international students, behind China at 23%)
- **Source**: [Australian Dept of Education International Student Data](https://www.education.gov.au/international-education-data-and-research/international-student-monthly-summary-and-data-tables)
- **Media**: [ICEF Monitor](https://monitor.icef.com/2025/12/the-number-of-indian-students-abroad-fell-in-2025/)

---

## 6. Germany Source

### DAAD / Destatis
- **Key data**: 59,419 Indian students in winter semester 2024/25; 49,483 in 2023/24; 28,905 in 2020/21
- **India surpassed China** as #1 origin country for international students in Germany
- **Source**: [DAAD India](https://www.daad.in/en/2025/09/22/indian-students-in-germany-at-an-all-time-high/)
- **PDF report**: [Indian student numbers in Germany (DAAD)](https://www.daad.in/files/2024/09/Indian-student-numbers-in-Germany.pdf)

---

## 7. New Zealand Source

### Education New Zealand (ENZ)
- **Key data**: ~12,000 Indian students in 2025; 10,640 in Jan-Aug 2024; 7,930 in 2023
- **2nd largest source** country after China
- **Source**: [Education New Zealand India Insights](https://www.enz.govt.nz/news-and-research/ed-news/india-insights-snapshot)

---

## 8. UNESCO UIS

- **What it covers**: Global count of outbound internationally mobile tertiary students from India
- **Key data**: 622,000 in 2022; 508,000 in 2021
- **Source**: [UNESCO UIS Data Browser](https://databrowser.uis.unesco.org/browser/EDUCATION/UIS-EducationOPRI/int-stud)
- **Limitation**: UNESCO figures lag 2-3 years. 2023/24 data not yet published as of April 2026.

---

## 9. Aggregate Analysis Sources

- [WENR/WES: India's Moment](https://wenr.wes.org/2025/02/indias-moment-an-examination-of-student-mobility-from-and-to-a-key-player) — comprehensive analysis with Big Four destination data
- [Wikipedia: Indian students abroad](https://en.wikipedia.org/wiki/Indian_students_abroad) — useful compilation of MEA, BoI, and destination country data
- [ICEF Monitor: Indian students abroad fell in 2025](https://monitor.icef.com/2025/12/the-number-of-indian-students-abroad-fell-in-2025/) — multi-country 2025 analysis with Canada, US, Australia, Germany, UK data

---

## Data Quality Notes

1. **MEA stock vs BoI flow**: MEA counts total Indians registered abroad (stock); BoI counts annual departures (flow). These measure different things.
2. **Open Doors vs SEVIS**: Open Doors counts enrolled higher-ed students in a given academic year. SEVIS counts all active visa records at a point in time (includes OPT workers, language students).
3. **Canada IRCC vs MEA**: IRCC counts valid permits on Dec 31. MEA counts from mission registrations. Numbers differ by ~30k.
4. **HESA vs Home Office**: HESA counts enrolled students. Home Office counts new visa grants. Stock vs flow difference.
5. **Medical students**: FMGE candidacy data is the best proxy for Indian medical students who studied abroad and returned. Not all foreign medical graduates sit FMGE in the same year they graduate.
