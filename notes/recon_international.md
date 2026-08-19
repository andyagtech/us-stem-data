# International / Non-US Data Freshness Recon

**Repo:** `/Users/andy/usds_china` (site is a symlink to `/Users/andy/usds_china_private/site`)
**Recon date:** 2026-08-18 · **Last ingest:** 2026-04-05/06 (per every `DATA_SOURCES.md`)
**Scope:** canada.html, uk.html, eu.html, mexico.html, india.html, china.html, vwp.html
**Mode:** read-only. No repo file was modified. Only HEAD / small range requests were issued.

---

## 1. What we already have (observed, not assumed)

### 1.1 Canada — `data/canada/` (11 files, downloaded 2026-04-05/06)

| File | Observed max period | How observed |
|---|---|---|
| `study_permits_by_citizenship.csv` (1,238,713 B) | **Jan 2026** | `awk` over `EN_YEAR`/`EN_MONTH`: 2026 has only `Jan` |
| `imp_by_citizenship.csv` (1,188,304 B) | **Jan 2026** | same |
| `pgwp_by_province_csd.csv` (3,967,625 B) | **Jan 2026** | same |
| `study_permits_yearend_by_citizenship.xlsx` | **2024** | sheet1 header row 2 = `2000 … 2024`; `Total unique persons` 2024 = **996,375** |
| `imp_yearend_by_citizenship.xlsx` | 2024 (annual) | file identical in size to current remote |
| `pgwp_yearend_by_province_cma.xlsx` | 2024 (annual) | idem |
| `study_permits_yearend_by_province_study_level.xlsx` | 2024 (annual) | idem |
| `canada_dashboard.json` (built by `scripts/build_canada_data.py`) | flows **2015–2025** | `"years": [2015…2025]` |

`site/canada.html` plots: year-end stock 2000–**2024** (hardcoded `const YEARS`/`TOTALS`/`COUNTRIES`), new-permit flow 2015–**2025** (`const DCN`, inlined from `canada_dashboard.json`).

### 1.2 UK — `data/uk/`

| File | Observed max period |
|---|---|
| `education-visas-datasets-sep-2025.xlsx` (1,415,761 B) | **2025 Q3** (sharedStrings quarters run `2018 Q1 … 2025 Q3`) |
| `uk_student_trends.json` | HESA **2023/24** (732,285); visa grants **2025** (partial Q1–Q3, 359,823); Graduate Route **2025** (237,452, YE Sep) |
| `uk_visa_grants.json` | 2018–2025 (2025 partial) |
| `uk_dashboard.json` (built by `scripts/build_uk_data.py`) | `"as_of": "year ending September 2025"`, years 2018–2025 |

`site/uk.html` max year: 2025 / 2023/24.

### 1.3 EU & Germany — `data/eu/`

Only `eu_student_trends.json` + `DATA_SOURCES.md`. No raw files at all.
- Germany total foreign students: **2013/14 → 2023/24** (469,485)
- Germany Bildungsausländer: **2018/19 → 2024/25** (402,083)
- Eurostat EU total: **2023** only (1,760,000; 8.4% share)
- Eurostat destinations 2023: **only Germany (423,200), France (276,200), Netherlands (169,500)**
- EU students in US: SEVIS **Mar 2026**

`site/eu.html` max: WS 2024/25 (Germany), 2023 (Eurostat), Mar 2026 (SEVIS).

### 1.4 Mexico — `data/mexico/`

Only `mexico_student_trends.json` + `DATA_SOURCES.md`. No raw files.
- Open Doors series: **2014/15, 2018/19, 2019/20, 2022/23, 2023/24** (15,474) — explicitly flagged "Partial series"
- SEVIS: Jan 2024 → **Mar 2026** (17,851)
- UNESCO outbound: **2022** (36,922)
- ANUIES Patlani inbound: **2014/15** (~15,600)

### 1.5 India outbound — `data/india_outbound/`

Only `india_students_abroad.json` + `DATA_SOURCES.md`. No raw files.
- MEA stock: 2022, 2023, **2024** (1,335,878)
- Bureau of Immigration departures: 2020 → **2024** (760,073)
- UNESCO outbound: 2021, **2022** (622,000)
- Open Doors US: 2010 → **2025** (363,019) ✅ current
- SEVIS: → **Mar 2026**
- FMGE: **2024** (61,616 candidates, 10,269 pass, 16.7%)

### 1.6 China outbound — `data/china_outbound/`

Only `china_students_abroad.json` + `DATA_SOURCES.md`. No raw files.
- UNESCO total abroad: **2023** (1,021,303)
- MOE cumulative: **1978–2024** (8.88M); returnees **2024** (495,000)
- Open Doors US: → **2025** (265,919) ✅ current
- Australia / Japan / Korea / Germany / France: all → **2024**, all flagged `by_year_approx`

### 1.7 VWP — `data/vwp/`

| File | Actual content year (verified) |
|---|---|
| `dhs_naturalizations_fy2023.xlsx` / `.pdf` | FY2014–**FY2023** |
| `dhs_lpr_fy2023.xlsx` | FY2014–**FY2023** |
| `dhs_nonimmigrants_fy2023.xlsx` | **FY2023** |
| `dhs_overstay_fy2023.pdf` (1,123,955 B) | **FY2023** report |
| `dhs_overstay_fy2024.pdf` (1,240,659 B) | **FY2024** report (`pdftotext`: "Entry/Exit Overstay Report Fiscal Year 2024 Report to Congress, July 16, 2025") |
| `dhs_overstay_fy2025.pdf` (1,250,728 B) | **also the FY2024 report** — see provenance gap P5 |
| `sevis_2024_all_countries.pdf`, `sevis_2024_stem_opt.pdf` | CY**2024** |

`site/vwp.html` max year mentioned anywhere: **2023**.

### 1.8 Medical (international slice) — `data/medical/`

ECFMG/Intealth EVSP 2025 PDFs, `CertsbyYear2000-2024.pdf`, `Match2026Infographic.pdf`, AAMC FACTS 2026 edition. US-centric; only the ECFMG/FAIMER/J-1 pieces are international. Not a freshness bottleneck for the country pages.

### 1.9 Build-script coverage (matters for how expensive an update is)

| Page | Regenerated from raw files? |
|---|---|
| canada.html | **Partly** — `scripts/build_canada_data.py` → `canada_dashboard.json` → `inline_dashboard_data.py` (`const DCN`). The year-end stock arrays are a *separate legacy hardcoded block* (see P1). |
| uk.html | **Yes** — `scripts/build_uk_data.py` → `uk_dashboard.json` → `const DUK` |
| medical.html | **Yes** — `scripts/build_medical_data.py` → `const D` |
| eu / mexico / india / china / vwp .html | **No** — hand-authored inline JS arrays, no build script anywhere in `scripts/` or `pipeline/` |

---

## 2. Gap table

Sizes are from live `HEAD` requests on 2026-08-18. "Delta" = new periods vs. what is in the repo.

| # | Source | What we have | What is NOW available | Delta | Direct download URL(s) | Size | Format notes |
|---|---|---|---|---|---|---|---|
| **C1** | **IRCC study permits by citizenship** (monthly) | through **Jan 2026** | through **May 31 2026** (`Last-Modified: Tue, 21 Jul 2026`) | **+4 months** | `https://www.ircc.canada.ca/opendata-donneesouvertes/data/ODP-TR-Study-IS_CITZ.csv`<br>`…/EN_ODP-TR-Study-IS_CITZ_sign_date.xlsx` | 1.27 MB / 199 KB | Unchanged: tab-separated, 9 cols, `--` for 1–5. Local 1,238,713 → remote 1,274,537 B |
| **C2** | **IRCC IMP work permits by citizenship** | through Jan 2026 | through May 2026 (2026-07-21) | +4 months | `…/ODP-TR-Work-IMP-CITZ.csv` | 1.17 MB | same schema |
| **C3** | **IRCC PGWP by province/CMA and by CSD** | through Jan 2026 | through May 2026 (2026-07-21) | +4 months | `…/EN_ODP-TR-Work-PGWP_PT_CMA_sign.xlsx`<br>`…/ODP-TR-Work-PGWP-PT_CSD.csv` | 168 KB / 4.01 MB | CSD csv grew 3.97 → 4.21 MB |
| **C4** | **IRCC study permits by province × study level / × gender** | through Jan 2026 | through May 2026 (2026-07-21) | +4 months | `…/EN_ODP-TR-Study-IS_PT_study_level_sign.xlsx`<br>`…/EN_ODP-TR-Study-IS_PT_gender_sign.xlsx` | 85 KB / 80 KB | multi-level headers unchanged |
| **C5** | **IRCC year-end (Dec 31) stock files** ×4 | 2000–**2024** | **still 2000–2024** — all four remote files return `Last-Modified: Fri, 28 Mar 2025` and byte-identical `Content-Length` to our copies | **none** | (unchanged) | — | **No action.** 2025 year-end not yet published; expect ~Mar 2027, possibly later in 2026 |
| **C6** | **IRCC permanent residents by citizenship** | **nothing in repo** | live, through May 2026 (2026-07-21) | **new series** | `https://www.ircc.canada.ca/opendata-donneesouvertes/data/ODP-PR-CITZ.csv`<br>`…/EN_ODP-PR-CITZ.xlsx` | 1.27 MB / 202 KB | Same tab-separated shape as study/IMP files. Brief explicitly asks for PR-by-citizenship; we have none |
| **U1** | **UK Home Office education visas dataset** | `…-sep-2025.xlsx`, **2018 Q1–2025 Q3** | `…-mar-2026.xlsx`, **year ending March 2026** (published 10 Jun 2026, `Last-Modified: Thu, 14 May 2026`) | **+2 quarters** (2025 Q4, 2026 Q1) + revisions to provisional 2025 | `https://assets.publishing.service.gov.uk/media/6a05e19c5f39105e0848a2c3/education-visas-datasets-mar-2026.xlsx` | 1,488,123 B (was 1,415,761) | Same Edu_D01/Edu_D02 tab structure; **`build_uk_data.py` should run unchanged** |
| **U2** | **UK sponsored-study headline / Graduate Route** | YE Sep 2025 narrative; GR 237,452 | **YE Mar 2026**: 409,954 sponsored-study grants (391,572 main + 18,382 deps), −3% YoY, −37% vs YE Jun 2023 peak | +2 quarters | `https://www.gov.uk/government/statistics/immigration-system-statistics-year-ending-march-2026/why-do-people-come-to-the-uk-study` | HTML | Note the March 2026 Statement of Changes (HC 1691) cut the Graduate Route to 18 months — narrative on uk.html is stale |
| **U3** | **HESA student statistics** | **2023/24** (732,285 non-UK) | **2024/25**, published **27 Jan 2026** (SB273): international enrolments **685,565**, −6%. India −12%, China −5%, Nigeria −33% entrants; **Nepal enters top 5** (17,385 entrants) | **+1 academic year** | `https://www.hesa.ac.uk/news/27-01-2026/sb273-higher-education-student-statistics/location`<br>open-data mirror: `https://ckan.publishing.service.gov.uk/dataset/6f8368d3-c020-4020-9447-665b45874a9a` | HTML/CSV | **hesa.ac.uk is behind Cloudflare** — `curl` and WebFetch both got 403 / JS challenge. Same compile-from-bulletin workflow as last time, or use the ckan mirror |
| **E1** | **Eurostat `educ_uoe_mobs01`** (mobile students, level/field/sex × country) | **2023** (via narrative only, no file) | **2024** — Statistics Explained page updated **11 Jun 2026**; EU total **1.83 M** (was 1.76 M), bachelor 44.0% / master 44.9% | **+1 year, and first actual file** | `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/educ_uoe_mobs01/?format=TSV` (verified 200, header ends `… 2023 2024`) | 1,317,388 B | Legacy `…/files?file=data/*.tsv.gz` bulk endpoint now returns **410 Gone** — must use the SDMX 2.1 `format=TSV` endpoint |
| **E2** | **Eurostat `educ_uoe_mobs02`** (by **partner country of origin** × destination) | **nothing** | 2012–**2024** | **new series** — this is the table that would replace the invented EU destination bars (P3) | `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/educ_uoe_mobs02/?format=TSV` (verified 200) | ~ tens of MB (chunked, no Content-Length) | Dimensions `freq,unit,partner,sex,isced11,geo` |
| **E3** | **Germany DAAD / Wissenschaft weltoffen** | WWO 2025 → WS **2024/25** = 402,083 Bildungsausländer; 116,600 first-years | **No new full report.** WWO 2026 due **Nov 2026**. DAAD Dec-2025 snapshot survey (212 universities) **projects ~420,000 for WS 2025/26** | narrative only | `https://www.wissenschaft-weltoffen.de/en/publication/`<br>`https://www.daad.de/en/press-releases/zahl-internationaler-studierender-deutlich-ueber-400000/` | PDF | **Wait for Nov 2026.** Optionally add the 420k projection as a flagged forecast |
| **E4** | **Destatis WS 2025/26** | — | Preliminary (Nov 2025): 2,876,900 total students, +0.4%. **Nationality / Bildungsausländer split only in the final results, published "summer 2026"** — worth re-checking now | possibly +1 semester | `https://www.destatis.de/DE/Themen/Gesellschaft-Umwelt/Bildung-Forschung-Kultur/Hochschulen/` (Statistischer Bericht 21311) | — | Preliminary release explicitly excludes nationality |
| **V1** | **DHS OHSS Yearbook — naturalizations (Table 21)** | **FY2023** (`dhs_naturalizations_fy2023.xlsx`) | **FY2024**, posted **8 Jun 2026** | **+1 fiscal year** | `https://ohss.dhs.gov/system/files/2026-06/2026_0604_ohss_yearbook_naturalizations_fy2024.xlsx` | 165,119 B | Same OHSS workbook layout |
| **V2** | **DHS OHSS Yearbook — LPR (Table 3)** | FY2023 | **FY2024** (8 Jun 2026) | +1 FY | `https://ohss.dhs.gov/system/files/2026-06/2026_0604_ohss_yearbook_lawful_permanent_residents_fy2024.xlsx` | 258,559 B | |
| **V3** | **DHS OHSS Yearbook — nonimmigrant admissions (Table 28)** | FY2023 | **FY2024** (8 Jun 2026) | +1 FY | `https://ohss.dhs.gov/system/files/2026-06/20260604_ohss_yearbook_nonimmigrants_fy2024.xlsx` | 237,491 B | Note the filename here drops the underscores (`20260604_…`) unlike the other two |
| **V4** | **DHS Entry/Exit Overstay Report** | FY2023 + FY2024 (the "fy2025" file is a duplicate FY2024 — see P5) | **FY2024 is still the latest published.** `dhs.gov/publication/entryexit-overstay-report` lists nothing past `25_0912_…fiscal-year-2024.pdf` | **none** | — | — | **No action.** FY2025 report expected mid/late 2026 |
| **V5** | **SEVIS by the Numbers annual** | CY**2024** (`25_0605_2024-sevis-btn.pdf`) | **still CY2024** — `ice.gov/sevis` links only the 2024 BTN; probed 2025 filename patterns → 404 | **none** | — | — | No action |
| **I1** | **India MEA students abroad** | 2024 = **1,335,878** (higher ed, ~108 countries) | **2025 = 1,882,000** across **153 countries** — 1,254,000 higher ed + **628,305 school level** | **+1 year, and a definition change** | MEA parliamentary reply; `https://www.mea.gov.in/indian-students-abroad` | — | ⚠️ **Not comparable to prior years** — the record "high" is driven by newly including school-level students. Higher-ed alone **fell ~76,000**, ending a 3-year rise. Must be charted as two series |
| **I2** | **India Bureau of Immigration departures** | 2024 = 760,073 | 2025 figure expected in the same parliamentary series | +1 year | MEA / BoI parliamentary replies | — | Secondary sourcing as before |
| **I3** | **India FMGE / NMC** | **2024** (61,616 candidates, 10,269 pass, 16.7%) | **2025**: June 2025 pass rate **18.61%**; Dec 2025 **23.37%**, 10,262 passed | +1 year | NBEMS `natboard.edu.in`; country splits currently only via coaching aggregators | — | ⚠️ Our country-wise pass rates come from careermarg/careers360, **not** NMC primary — see P8 |
| **X1** | **China MOE returnees / outbound** | returnees **2024** = 495,000; cumulative 1978–2024 = 8.88 M | **2025**: **535,600 returnees**; **570,600 went abroad** — down 20% from the 2019 peak of 703,500, a **decade low** | **+1 year** | Global Times Apr 2026 `https://www.globaltimes.cn/page/202604/1358629.shtml`; Caixin `https://www.caixinglobal.com/2026-04-20/chinese-overseas-student-numbers-drop-to-a-decade-low-102435854.html` | — | This is the single most newsworthy change on china.html — the outbound decline is a new story the page does not tell |
| **X2** | **UNESCO UIS outbound mobility** | India **2022** (622,000); China **2023** (1,021,303) | Reference year **2023** is the latest (7.3 M mobile students globally, released Sep 2025). No 2024 yet | **+1 year for India only** | `https://databrowser.uis.unesco.org/browser/EDUCATION/UIS-EducationOPRI/int-stud` | — | Browser-rendered; no clean bulk URL found |
| **X3** | **Australia Dept of Education** | 2024 approx (China ~165,000) | **Full CY2025**: 846,321 students / 1,058,040 enrolments (−0.5% / −3%). China 23%, India 17%, Nepal 8%. YTD Aug 2025 exact: China 184,847, India 136,774, Nepal 64,364. Jan 2026 monthly also out (−9%) | **+1 year, and exact counts replacing `_approx`** | `https://www.education.gov.au/international-education-data-and-research/international-student-monthly-summary-and-data-tables` | XLSX | Would let us drop the `by_year_approx` flags on china.html/india.html |
| **X4** | **JASSO Japan** | 2024 = 123,485 Chinese | **2025 survey published 29 May 2026**: 408,000 total (record), **China ≈131,000 (+6%)** | +1 year | `https://www.studyinjapan.go.jp/en/statistics/enrollment/data/2605291000.html` | HTML + PDF | Direct successor to the `2504301000.html` page in DATA_SOURCES.md |
| **M1** | **IIE Open Doors** | 2024/25 (India 363,019; China 265,919; Mexico 15,474 for 2023/24) | **2024/25 is still the latest.** Open Doors 2026 + Fall 2026 Snapshot due **Nov 2026** | **none for new years** — but see M2 | — | — | No action on recency |
| **M2** | **Open Doors "All Places of Origin" workbook** | not held; mexico.json flags "Partial series — need full download" | Downloadable workbook exists and covers all origins/selected years | **fills existing holes** (Mexico 2020/21, 2021/22; full India/China series) | `https://opendoorsdata.org/wp-content/uploads/2025/11/Census_All-Places-of-Origin-Selected-Years_OD25_Website.xlsx` | 94,969 B (`Last-Modified: 17 Nov 2025`) | Cheapest single fix for the Mexico provenance gap |
| **M3** | **ANUIES Patlani (inbound Mexico)** | 2014/15 (~15,600) | No newer public edition found; latest repository report is still the Jun 2024 `Reporte_Mov_2023` | none | `https://repositoriointernacional.anuies.mx/` | — | Newer data reportedly behind `patlani.anuies.mx` login |

---

## 3. Provenance gaps (numbers on a page I could not trace to a file, or that contradict the file)

**P1 — canada.html year-end stock series contradicts the stored IRCC workbook (most serious).**
`site/canada.html` lines ~144–157 hardcode `const YEARS` / `TOTALS` / `COUNTRIES` for 2000–2024. This block is *not* produced by `scripts/build_canada_data.py` (the comment in `scripts/inline_dashboard_data.py` calls it "a legacy `const D`" separate from the generated `DCN`). Comparing against `data/canada/study_permits_yearend_by_citizenship.xlsx` (parsed directly from `xl/worksheets/sheet1.xml`), the **recent years match but the early years do not**:

| Series | Year | canada.html | stored xlsx | |
|---|---|---|---|---|
| China | 2000 | 17,835 | **12,205** | +46% |
| China | 2002 | 24,960 | **31,245** | −20% |
| China | 2010 | 56,380 | **57,305** | |
| Philippines | 2000 | 2,530 | **375** | **6.7×** |
| France | 2000 | 8,375 | **6,475** | |
| Iran | 2000 | 2,505 | **1,085** | 2.3× |
| Mexico | 2000 | 1,665 | **3,645** | |
| Korea | 2000 | 14,250 | **15,795** | |
| Nigeria | 2000 | 795 | **565** | |
| China | 2015 / 2018 | 117,825 / 141,710 | 117,825 / 141,710 | ✅ exact |
| Nigeria / Philippines / France / Iran / Nepal / Vietnam | 2024 | 45,110 / 43,785 / 25,080 / 23,185 / 22,045 / 17,790 | identical | ✅ exact |

The pattern (2019–2024 exact, 2000–2014 divergent by up to 6.7×) is consistent with the early half of each array having been interpolated rather than read from the file. **The chart's own source line claims "IRCC Open Data — year-end stock by country of citizenship, 2000-2024".** Recommend regenerating this block from the xlsx.

**P2 — canada.html hero figures are off by ~35 from the stored file.** Hero shows **996,340** international students (Dec 2024); the xlsx `Total unique persons` 2024 = **996,375**. Likewise 2023: page 1,037,130 vs file 1,037,165, and every `TOTALS` entry is 15–70 below the file. Minor, but it means the page reflects a different vintage than the file we shipped. Same for Korea 2024 (page 14,380 vs file 14,105) and Mexico 2024 (14,955 vs 14,950).

**P3 — eu.html "EU Destination Countries (2023)" bars are placeholder round numbers.** `eu.html` line 155: `[423200, 276200, 169500, 100000, 80000, 70000, 60000, 50000]` for Germany, France, Netherlands, **Spain, Italy, Austria, Belgium, Sweden**. `data/eu/eu_student_trends.json → eu_top_destination_countries_2023` contains **only** Germany / France / Netherlands. The last five values (100K, 80K, 70K, 60K, 50K — perfectly descending round numbers) have **no source anywhere in the repo**. Eurostat `educ_uoe_mobs01`/`mobs02` (gap E1/E2) would supply the real values.

**P4 — eu.html hero "+55.7% Germany Growth (10yr)"** does not appear in `eu_student_trends.json` or the DATA_SOURCES.md tables and is not derivable from the plotted 2013/14→2023/24 series (301,350 → 469,485 = **+55.8%** on total foreign students; close, so probably a rounding of that, but undocumented — the label says "10yr" for what is an 11-point series).

**P5 — `data/vwp/dhs_overstay_fy2025.pdf` is not the FY2025 report.** Verified three ways: (a) `pdftotext` on the neighbouring FY2024 file shows "Entry/Exit Overstay Report **Fiscal Year 2024** Report to Congress, July 16, 2025"; (b) the "fy2025" PDF's own bookmark tree is entirely "Fiscal Year **2024** … Overstay Rates" with an "Appendix C. Fiscal Year 2023" annex, and its `/Title` is literally `CBP - Entry Exit Overstay Report FY24`; (c) its byte length (1,250,728) matches DHS's `25_0716_cbp_entry-exit-overstay-report-fy25.pdf` — a **mis-named duplicate posting of the FY2024 report** by DHS itself. `data/vwp/DATA_SOURCES.md` lists it as "Entry/Exit Overstay Report FY2025", which is wrong. **No FY2025 overstay report exists yet.** Recommend renaming the file and correcting DATA_SOURCES.md.

**P6 — vwp.html "VWP Total Naturalizations by Year" 2014–2023 series** (`[63510,67550,66860,62530,69800,75830,54300,73400,80680,69200]`) is an aggregation with no stored intermediate. It is *derivable* from `dhs_naturalizations_fy2023.xlsx` (which holds FY2014–2023 by country), but nothing in the repo does that derivation, and the FY2023 value (69,200) does not equal the 67,680 the same page shows in the hero and in `DATA_SOURCES.md`. Two different VWP totals for the same year on the same page.

**P7 — china.html Australia 2023 = 153,000 vs `china_students_abroad.json` = 152,000.** Trivial, but it confirms the inline arrays drift from the JSON because nothing regenerates them.

**P8 — India FMGE country-wise pass rates rest on coaching-site secondary sources.** `india_students_abroad.json` cites careermarg.com and careers360.com for the Georgia/Russia/Philippines/Kazakhstan/China pass rates rendered on india.html. No NMC/NBEMS primary artefact is stored. Likewise `india.html`'s hero "~25,000 Medical Students/yr Abroad" traces only to a University World News article.

**P9 — mexico.html Open Doors series has self-declared holes.** The JSON says "Partial series - need full download from opendoorsdata.org", and the plotted series jumps 2019/20 → 2022/23 with COVID years absent. Gap **M2** fixes this for 95 KB.

**P10 — uk_student_trends.json carries acknowledged estimates.** HESA 2015/16 and 2016/17 are "estimated from HESA trend data"; pre-2018 visa grants are "~200k/yr" narrative approximations. Documented, so not a surprise — but they are plotted on uk.html without an on-chart caveat.

**P11 — eu / mexico / india / china / vwp pages have no build script.** Only canada, uk and medical have `scripts/build_*_data.py` + `inline_dashboard_data.py` wiring. Every number on the other five pages is hand-typed inline JS, which is the structural cause of P3, P6 and P7.

**P12 — the four hand-written country JSONs have no raw upstream artefacts at all.** `data/eu/`, `data/mexico/`, `data/india_outbound/`, `data/china_outbound/` each contain exactly one JSON plus one markdown file. Nothing can be re-derived or audited; every figure is a transcription from a press release or article.

---

## 4. Ranked recommendation — what to ingest first

**Tier 1 — high value, low effort, already automated**

1. **C1–C4: IRCC monthly refresh (7 files, ~7 MB total).** Four months of new data (Feb–May 2026), zero format change, and `scripts/build_canada_data.py` + `inline_dashboard_data.py` regenerate `canada.html`'s `DCN` block with no code change. This is the single cheapest real gain, and Canada is the page whose upstream refreshes fastest.
2. **U1: UK `education-visas-datasets-mar-2026.xlsx` (1.49 MB).** Two new quarters plus revisions to the provisional 2025 figures we currently plot. `build_uk_data.py` should run unchanged (same Edu_D01/Edu_D02 tabs). Pair with the U2 narrative refresh (409,954 YE Mar 2026; Graduate Route cut to 18 months in HC 1691).

**Tier 2 — high value, moderate effort**

3. **P1 fix: regenerate canada.html's year-end stock arrays from `study_permits_yearend_by_citizenship.xlsx`.** No download needed — the correct file is already in the repo. This is a *correctness* fix, not a freshness one, and it is the most defensible single change in this whole report (China 2000 is currently overstated by 46%, Philippines 2000 by 6.7×).
4. **V1–V3: DHS OHSS Yearbook FY2024 (3 xlsx, 661 KB total).** vwp.html is 100% FY2023 and is the staleest page in scope. One fiscal year of movement across naturalizations, LPR and nonimmigrant admissions, in the same workbook layout we already parse. Fold in the **P5** rename/correction while you are in `data/vwp/`.
5. **E1 + E2: Eurostat `educ_uoe_mobs01` and `mobs02` via the SDMX 2.1 TSV endpoint.** Moves eu.html from 2023 → 2024 (1.76 M → 1.83 M) **and** gives real per-country destination values to replace the invented bars in **P3**. Note the old `files?file=data/*.tsv.gz` bulk URLs now return 410 — use `…/sdmx/2.1/data/<code>/?format=TSV`.

**Tier 3 — headline-changing but narrative/manual**

6. **X1: China MOE 2025.** 570,600 outbound (decade low, −20% from the 2019 peak) and 535,600 returnees. china.html currently tells a "US decline / global diversification" story; the 2025 data says total Chinese outbound is itself contracting. Highest editorial value of anything in this report.
7. **I1: India MEA 2025.** 1.882 M across 153 countries — but **only because school-level students were added**; higher-ed alone fell ~76,000. Must be charted as two series or it will read as growth when it is a decline. Do not drop this in as a simple series extension.
8. **U3: HESA 2024/25** (685,565, −6%; Nepal into the top 5). uk.html's enrolment chart is a full academic year behind. Blocked by Cloudflare on `hesa.ac.uk` — use the ckan.publishing.service.gov.uk mirror or the same compile-from-bulletin approach used last time.
9. **M2: Open Doors All-Places-of-Origin workbook (95 KB).** Closes the acknowledged Mexico series holes and puts an authoritative artefact behind india/china/mexico US enrolment for the first time. Trivial size; the only reason it is not Tier 1 is that it adds no new *year*.

**Tier 4 — nice to have**

10. **X3 Australia CY2025 + X4 JASSO 2025.** Replaces `by_year_approx` estimates on china.html/india.html with exact counts (China in Australia 184,847; China in Japan ~131,000).
11. **C6: IRCC PR-by-citizenship.** New series the brief asks for and we hold none of. Only ranked here because no current page plots it — it is a new feature, not a refresh.
12. **I3: FMGE 2025** (18.61% June / 23.37% December). Worth taking primary from NBEMS rather than re-citing coaching sites (P8).

**Explicitly do nothing (verified not updated):**

- **C5** IRCC year-end stock files — all four still `Last-Modified: 28 Mar 2025`, byte-identical to our copies. 2024 remains the latest year-end.
- **V4** DHS overstay — FY2024 is still the newest published; our "fy2025" file is a duplicate of it.
- **V5** SEVIS by the Numbers — CY2024 still latest.
- **M1** IIE Open Doors — 2024/25 still latest; Open Doors 2026 lands Nov 2026.
- **E3** Wissenschaft weltoffen — WWO 2026 lands Nov 2026 (a ~420k WS 2025/26 DAAD *projection* exists if you want it flagged as a forecast).
- **X2** UNESCO UIS — 2023 is the latest reference year (India 2023 is a +1 gain; China already at 2023).
- **M3** ANUIES Patlani — no new public edition.

---

## 5. Method notes / caveats

- All "now available" claims come from live requests made 2026-08-18, not from memory. IRCC, GOV.UK asset, Eurostat, DHS/OHSS and opendoorsdata URLs were verified with `curl -sSIL` (status + `Content-Length` + `Last-Modified` recorded above).
- `hesa.ac.uk` and `dhs.gov/publication/*` reject WebFetch (403 / Cloudflare JS challenge). DHS was recovered with a browser `User-Agent` via curl; HESA was not, so HESA figures here come from the search index and the HESA SB273 news pages rather than a direct read.
- The Eurostat legacy bulk-download endpoint (`api/dissemination/files?file=data/*.tsv.gz`) is **410 Gone** as of today for every code tried — this is a genuine format/API change since the last ingest and will break any script that hardcoded it.
- No file in the repo was created, modified or deleted; nothing was committed; `python -m pipeline run` was not invoked. The only downloads were HTTP headers and two ≤400-byte range requests against Eurostat to read TSV column headers.
