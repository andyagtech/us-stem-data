# EU / Germany International Student Data Sources

Last updated: 2026-04-05

## 1. Germany: International Students (Wissenschaft weltoffen / DAAD)

### Primary Source: Wissenschaft weltoffen
- **URL:** https://www.wissenschaft-weltoffen.de/en/
- **Interactive tool:** https://www.wissenschaft-weltoffen.de/en/interactive/foreign-students-in-germany-by-country-of-origin/
- **Full 2024 report PDF:** https://www.wissenschaft-weltoffen.de/content/uploads/2024/11/WWO_2024_EN_aktualisiert_BF.pdf
- **Compact flyer:** https://www.wissenschaft-weltoffen.de/content/uploads/2024/04/Kompaktflyer_WWO_en_barrierefrei.pdf
- **Published by:** DAAD (German Academic Exchange Service) + DZHW (German Centre for Higher Education Research and Science Studies)
- **Note:** Interactive tool requires browser; data is dynamically rendered, not easily scraped

### Total International Students in Germany (Winter Semester)

| Year | Total Foreign | International (Bildungsauslaender) | Resident Foreign (Bildungsinlaender) |
|------|--------------|-------------------------------------|--------------------------------------|
| 2010/11 | ~250,000 | 184,960 | ~65,000 |
| 2013/14 | 301,350 | ~210,000 | ~91,000 |
| 2015/16 | 340,305 | ~249,000 | ~91,000 |
| 2016/17 | 358,895 | ~267,000 | ~92,000 |
| 2017/18 | 374,583 | ~282,000 | ~92,000 |
| 2018/19 | 394,665 | 302,157 | 92,508 |
| 2019/20 | 411,601 | 319,902 | 91,699 |
| 2020/21 | 416,437 | 324,729 | 91,708 |
| 2021/22 | 440,564 | 349,438 | 91,126 |
| 2022/23 | 458,210 | 367,578 | 90,632 |
| 2023/24 | 469,485 | 379,939 | 89,546 |
| 2024/25 | 402,083* | ~402,000 | n/a |

*Note: The 2024/25 figure of 402,083 appears to count only Bildungsauslaender (international students who obtained their HE entrance qualification outside Germany). The total including Bildungsinlaender would be ~490,000.

**Key distinction:** Germany separates foreign students into:
- **Bildungsauslaender** (international students): obtained HE entrance qualification abroad
- **Bildungsinlaender** (resident foreign students): foreign citizenship but educated in Germany (many are Turkish-origin)

### Top Countries of Origin (2023/24 Winter Semester)

| Rank | Country | Students |
|------|---------|----------|
| 1 | India | 49,008 |
| 2 | China | 38,687 |
| 3 | Turkey | 18,084 |
| 4 | Austria | 15,379 |
| 5 | Iran | 15,159 |
| 6 | Syria | 13,379 |
| 7 | Russia | 10,593 |
| 8 | Italy | 10,154 |
| 9 | Ukraine | 9,914 |
| 10 | Pakistan | 9,873 |

### Top Countries of Origin (2024/25 Winter Semester, preliminary)

| Rank | Country | Students | Change |
|------|---------|----------|--------|
| 1 | India | ~59,000 | +20% |
| 2 | China | ~38,600 | declining |
| 3 | Turkey | ~20,900 | +15.5% |
| 4 | Iran | ~17,248 | +14% |

### India vs China Time Series in Germany

| Year | India | China | Notes |
|------|-------|-------|-------|
| 2016 | 13,537 | ~38,000 | China > 2x India |
| 2018/19 | ~20,000 | ~39,900 | India rising fast |
| 2020/21 | ~25,000 | ~41,000 | |
| 2021/22 | ~34,000 | ~40,000 | India catching up |
| 2022/23 | ~42,600 | ~39,700 | India surpasses China |
| 2023/24 | 49,008 | 38,687 | India #1, China declining |
| 2024/25 | ~59,000 | ~38,600 | India +262% since 2016 |

### Field of Study (International Students)
- Engineering: 43% of international students
- Economics, law, social sciences: 25%
- International share of Master's programs: 26%
- International share of Doctoral programs: 28%

### Secondary Source: studying-in-germany.org
- **URL:** https://www.studying-in-germany.org/germany-international-student-statistics/
- Aggregates Destatis and DAAD data with good time series

## 2. EU-Wide: Eurostat

### Primary Source: Eurostat Learning Mobility Statistics
- **URL:** https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Learning_mobility_statistics
- **Data browser:** https://ec.europa.eu/eurostat/databrowser/view/educ_uoe_mobs01/default/table
- **News release (Aug 2025):** https://ec.europa.eu/eurostat/web/products-eurostat-news/w/ddn-20250822-1

### EU Total International Students (2023)
- **1.76 million** students from abroad in EU tertiary education
- Represents **8.4%** of all tertiary students

### Top EU Destination Countries (2023)

| Country | International Students | Share of EU Total |
|---------|----------------------|-------------------|
| Germany | 423,200 | 24.1% |
| France | 276,200 | 15.7% |
| Netherlands | 169,500 | 9.6% |

### Highest Share of Foreign Students Within Country (2023)
- Luxembourg: 52.3%
- Malta: 29.6%
- Cyprus: 22.3%

### Student Origins (2023)
- Europe: 43%
- Asia: 25%
- Africa: 17%
- Caribbean/Central-South America: 2%
- North America: <2%
- Oceania: <1%
- Top single country of origin: China (incl. Hong Kong) at 5.6%

### Distribution by Education Level (2023)
- Bachelor's: 44.0%
- Master's: 44.8%
- Doctoral: 9.0%
- Short-cycle tertiary: 2.2%

## 3. EU Countries in US SEVIS Data (March 2026)

From project data (`/data/sevp/sevis_data_mapping_mar2026.csv`):

| Country | Active Students in US |
|---------|----------------------|
| United Kingdom | 12,856 |
| Spain | 10,812 |
| France | 9,396 |
| Germany | 9,034 |
| Italy | 7,770 |
| Sweden | 2,883 |
| Netherlands | 2,575 |
| Poland | 2,439 |

## 4. Data Gaps and Next Steps

1. **Wissenschaft weltoffen full PDF**: The 2024 full report (WWO_2024_EN) has detailed time series tables -- need to extract data from the PDF
2. **Eurostat data browser**: Download full time series (2013-2023) of mobile students by EU country from educ_uoe_mobs01 table
3. **Country-of-origin breakdowns for EU**: Eurostat should have China, India, etc. as source countries for each EU destination
4. **Germany by country time series**: The Wissenschaft weltoffen interactive tool has full country-by-country time series -- need to manually extract or find API
5. **France**: Campus France publishes "Chiffres cles" with detailed breakdown of international students in France
6. **Netherlands**: Nuffic publishes annual "Incoming student mobility in Dutch higher education" reports
7. **Erasmus+ mobility data**: Separate from degree-seeking students -- covers EU intra-mobility exchanges
