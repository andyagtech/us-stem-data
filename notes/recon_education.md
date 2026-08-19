# Data Freshness Recon — US Education & Research Funding

**Repo:** `/Users/andy/usds_china`
**Recon date:** 2026-08-18
**Last project ingest:** ~2026-04-06 (some IPEDS files ~2026-03-07/08)
**Method:** local filesystem inspection + live HTTP probes (`curl` range requests, ZIP central-directory reads, WebFetch/WebSearch). No bulk downloads, no repo modifications.

> **Terminology used throughout:** *survey year* = the reference year of the data (e.g. IPEDS `C2025_A` = degrees conferred July 1 2024 – June 30 2025). *Release year* = when NCES/NCSES published it. IPEDS "provisional" = first public release; "revised/final" (`_rv`) ships bundled inside the same ZIP roughly one year later.

---

## 0. HEADLINE FINDINGS

1. **NCES moved the IPEDS Complete Data Files to a new URL path.** Files are now served from
   `https://nces.ed.gov/ipeds/complete-data-files/{STEM}.zip`.
   The old path in `scripts/ipeds_config.py` (`DIRECT_BASE_URL = "https://nces.ed.gov/ipeds/datacenter/data"`) still serves *older* files but **404s on everything from the 2025-26 collection onward**. This is a hard blocker: `scripts/download_ipeds.py` cannot fetch a single new file until the constant changes.

2. **IPEDS survey year 2025 completions (`C2025_A`) is available and we do not have it.** Released as part of the 2025-26 Fall provisional release (collection closed 2025-10-15). Schema is byte-for-byte compatible with 2011+ (64 columns, `CTOTALT`/`CNRALT`/… ). We are one full survey year behind.

3. **Three entire IPEDS collections released since our ingest were missed**, not just completions: Spring 2024-25 (Fall Enrollment `EF2024*`, HR `S2024_IS`/`SAL2024_IS`, Finance `F2324_*`, Academic Libraries), Winter 2024-25 (`ADM2024`, `GR2024`, `OM2024`, `SFA2324`), and Fall 2025-26 (`C2025_A`, `HD2025`, `IC2025`, `EFFY2025`).

4. **`data/ipeds/enrollment/EF2024A.zip` is not a ZIP.** It is a 1,245-byte HTML 404 error page saved with a `.zip` extension. `data/DATA_DICTIONARY.md` claims Fall 2024 enrollment is present — it is not. Silent-failure bug.

5. **The 2008-2009 "gap" in `ipeds_dashboard.html` is an ingestion artifact, NOT an upstream gap — and the currently deployed dashboard no longer has it.** The raw upstream files are complete. The stale derived CSV `data/ipeds/ipeds_stem_phd_demographics_by_year.csv` (mtime 2026-03-08) has `Total=0` for 2008/2009; the regenerated `site/ipeds_dashboard.html` (mtime 2026-04-07) has correct 2008/2009 values. **However I found a real, still-live sibling bug: survey year 2010 race counts are undercounted by ~46%** (details in §5).

6. **SHEEO SHEF FY2025 was published 2026-04-09 — three days after our ingest.** Clean one-year extension of a series we already parse.

7. **NSF NCSES is fully current**: HERD FY2024 (NSF 26-304), GSS Fall 2024 (NSF 26-307), SED 2024 (NSF 25-349) are all the newest editions and we already hold them. No NCSES survey gap. Two *new NSB reports* appeared in May 2026 that we lack.

8. **NIH RePORTER FY2025 and NSF Awards CY2025 are complete and missing.** Both are API-driven and trivially backfillable.

9. **NRMP published four 2026 reports since our ingest**, including the Non-U.S. Citizen IMG Charting Outcomes edition — a direct upgrade over our 2024 IMG file. ECFMG/Intealth and AAMC have published nothing new.

---

## 1. WHAT WE ALREADY HAVE (observed, not assumed)

Every "max year" below was read off the filesystem, not inferred from docs.

### 1.1 IPEDS Completions — `data/ipeds/`

| Observation | Evidence |
|---|---|
| Max survey year on disk: **2024 (provisional)** | `data/ipeds/C2024_a.csv`, 62,757,116 bytes, mtime 2026-03-08. **No `C2024_a_RV.csv` exists.** |
| Latest revised/final on disk: **2023** | `data/ipeds/C2023_a_RV.csv`, 61,888,672 bytes |
| Config cap: **2024** | `scripts/ipeds_config.py:53` — `list(range(2000, 2025))  # 2000-2024`; also lines 99 and 112 |
| Derived aggregate max year: **2024** | `data/ipeds/ipeds_stem_phd_all_years.csv` — year counts run 1984…2024 (2024 = 2,087 rows). Known gaps 1990, 1999 (upstream, documented in `ipeds_config.MISSING_YEARS`) |
| Per-year filtered files: 39 files, **1984–2024** | `data/ipeds/filtered/ipeds_stem_phd_1984.csv` … `ipeds_stem_phd_2024.csv` |

I verified the local `C2024_a.csv` is byte-identical to what NCES serves: CRC32 of the local file = **1245379766**, which exactly matches the CRC stored in the central directory of the old-path `C2024_A.zip`. So our 2024 file is genuine and complete — just provisional.

### 1.2 IPEDS other surveys

| Survey | Directory | Max survey year on disk | Evidence |
|---|---|---|---|
| Institutional directory (HD) | `data/ipeds/` | **2024** | `HD2024.csv` |
| Institutional characteristics (IC) | `data/ipeds/ic_tuition/` | **2023** | `IC2023.csv`, `IC2023_RV.csv`, `ic2023_ay.csv` |
| Fall enrollment (EF-A) | `data/ipeds/enrollment/` | **2023** | `ef2023a.csv`. `EF2024A.zip` is present but is a **1,245-byte HTML 404 page**, not a ZIP (`unzip -l` → "End-of-central-directory signature not found") |
| Enrollment by major (EF-D) | `data/ipeds/enrollment_major/` | **2023** | `ef2023d.csv` |
| Student financial aid (SFA) | `data/ipeds/sfa/` | **AY2022-23** | `sfa2223.csv` |
| Human resources (S / SAL) | `data/ipeds/hr/` | **2022** | `s2022_is.csv`, `sal2022_is.csv`, `s2022_sis.csv` — two years stale |
| Finance (F1A only) | `data/ipeds_finance/` | **FY2022-23** | `f2223_f1a.csv` |
| Dictionaries | `data/ipeds/dictionaries/` | 2023 | only `C2023_a_dict.xlsx`, `HD2023_dict.xlsx` |

Note on Finance: we hold **only F1A (FASB — private institutions and FASB-reporting publics)**. `F*_F2` (GASB — the great majority of public universities) has never been ingested. That is a coverage hole independent of freshness.

### 1.3 NSF NCSES

| Source | Directory | Max year on disk | Evidence |
|---|---|---|---|
| HERD | `data/herd/` | **FY2024** | `herd_fy2024_table13.xlsx` (176,409 bytes), `herd_fy2024_table14.xlsx`; derived `funding_by_university.json` (mtime 2026-04-06). `scripts/build_herd_funding.py:33` hardcodes `data/herd/herd_fy2024_table13.xlsx` |
| GSS | `data/nsf_gss/` | **2024** | `graduate_students_postdocs_2024.zip` (17.2 MB), `gss2024_code.sas7bdat`, `gss2024_Code.xlsx`. Adjusted-institutions file is only 2023 (`gss2023adjusted_institutions.xlsx`) |
| SED | `data/nsf_sed/` | **2024** | `parsed/table_1_6_broad_field_citizenship_1979_2024.csv`, `parsed/table_7_5_top_institutions_temp_visa.csv` (2024), `parsed/table_7_8_top_countries_2024.csv` |
| SDR (microdata) | `data/nsf_workforce/sdr_2023/` | **2023** | `psd23Public/epsd23.csv`, 80,143 records |
| NSCG (microdata) | `data/nsf_workforce/nscg_2023/` | **2023** | `pcg23Public/epcg23.csv`, 94,606 records |
| NSB S&E Indicators | `data/nsf_workforce/` | **NSB-2026-1**, NSB-2024-5 | `nsb20261_report_tables/`, `nsb20261_stem_labor/` (24+ `nsb20261-tabstal-*.xlsx`), `nsb_foreign_born_stem/` (`nsb20245-tabslbr-*.xlsx`) |

`data/DATA_DICTIONARY.md` (line 3: "Last updated: 2026-03-31") cites the SED source as `nsf25300`; the actual current SED 2024 data-tables publication is **NSF 25-349**. The parsed tables we hold do carry 2024 data, so this is a citation error in the dictionary rather than a data problem.

### 1.4 Funding / state finance

| Source | Directory | Max year on disk | Evidence |
|---|---|---|---|
| SHEEO SHEF | `data/shef/`, `data/state_funding/sheeo/` | **FY2024** | `SHEEO_SHEF_FY24_Report_Data.xlsx` (711,617 bytes) + FY24 Sector/Adjustments/Capital/Stimulus/PBF/Residency. State Effort & Capacity is FY23. `scripts/build_sheeo_json.py` hardcodes `SHEEO_SHEF_FY24_Report_Data.xlsx` and reads sheet `'Report Data'` |
| SHEEO Grapevine | `data/state_funding/sheeo/` | **FY2026** | `SHEEO_Grapevine_FY26_Data_Download.xlsx`, `SHEEO_Grapevine_FY26_All-Tables.xlsx` |
| NIH RePORTER | `data/state_funding/nih_reporter/` | **FY2024** | `README.md`: "Fiscal years fetched: 2020, 2021, 2022, 2023, 2024"; `nih_by_university.json` `by_year` keys 2020–2024 (e.g. MIT FY2024 = 222 grants, $102,857,783) |
| NSF Awards API | `data/state_funding/nsf_awards/` | **CY2024** | `scripts/fetch_nsf_awards.py:28-30` — `DATE_START="01/01/2020"`, `DATE_END="12/31/2024"`, `YEARS=["2020".."2024"]`; `nsf_by_university.json` `by_year` keys 2020–2024 |

### 1.5 Medical (`data/medical/`, `DATA_SOURCES.md` "Downloaded: 2026-04-05")

| Item | On disk |
|---|---|
| NRMP Advance Data Tables | **2025** (`nrmp_2025_advance.pdf`) |
| NRMP Charting Outcomes IMG | **2024** (`charting_outcomes_img_2024.pdf`) |
| NRMP Results and Data (Main Match) | **absent entirely** |
| ECFMG certificates by year | **2000–2024** (`CertsbyYear2000-2024.pdf`) |
| ECFMG top-5 citizenship countries | **2000–2024** |
| ECFMG EVSP J-1 physician set | **2025** (Country / States / Specialties ×2 / Sponsorship 2015-2025) |
| Intealth IMG match infographic | **2026** (`Match2026Infographic.pdf`) |
| AAMC FACTS | **2025 edition** (8 files, incl. Table 1 2016-2026, B-1.2 2021-2026, A-25 DACA 2018-2026) |

---

## 2. WHAT IS NOW AVAILABLE UPSTREAM (live-probed 2026-08-18)

### 2.1 The IPEDS URL migration — read this first

`scripts/ipeds_config.py:26` currently has:

```python
DIRECT_BASE_URL = "https://nces.ed.gov/ipeds/datacenter/data"
```

I scraped the live IPEDS Complete Data Files page (`https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx`, reached with a session cookie via `Default.aspx?gotoReportId=7`). Every download link on it now points at a **different path**:

```html
<a href="/ipeds/complete-data-files/C2025_A.zip">C2025_A</a>
<a href="/ipeds/complete-data-files/C2025_A_Dict.zip">Dictionary</a>
```

Side-by-side probe results (HTTP status from ranged GET):

| Stem | `…/datacenter/data/` (old, in config) | `…/ipeds/complete-data-files/` (new) |
|---|---|---|
| `C2023_A` | 206 | 206 |
| `C2024_A` | 206 | 206 |
| `C2025_A` | **404** | **206** |
| `HD2025` | **404** | **206** |
| `IC2025` | **404** | **206** |
| `EF2024A` | **404** | **206** |
| `S2024_IS` | **404** | **206** |
| `F2324_F1A` | **404** | **206** |
| `SFA2324` | **404** | **206** |
| `ADM2024` / `GR2024` / `OM2024` / `AL2024` | **404** | **206** |

The old path is a frozen mirror of pre-2024-25-collection files. **Nothing published in the last ~18 months is reachable from it.** This is why the repo appears to have "no 2025 data available" — the downloader has been asking the wrong host path.

Secondary detail worth knowing: the new path serves **unquoted** CSVs while the old path served quoted ones. Same data, ~30% smaller files. Verified on C2024: old path entry `C2024_a.csv` uncompressed = 62,757,116 bytes; new path entry `c2024_a.csv` uncompressed = 43,679,279 bytes; first data row identical in both (`100654,01.0999,1,5,R,12,R,2,R,10,…`). `pandas.read_csv` handles both transparently, so this is cosmetic — but it means byte-size comparisons against existing files will look alarming and are not.

### 2.2 IPEDS release state as of 2026-08-18

Provisional vs final determined by reading each ZIP's **central directory** via a tail range request (a `_rv` member inside the ZIP = the revised/final file has shipped). No bulk downloads were needed.

| ZIP | Members found in central directory | Status |
|---|---|---|
| `C2025_A.zip` | `c2025_a.csv` | **provisional only** |
| `C2024_A.zip` | `c2024_a.csv` | **provisional only — 2024 has NOT been revised to final** |
| `C2023_A.zip` | `c2023_a_RV.csv`, `c2023_a.csv` | final available (we have it) |
| `EF2024A.zip` | `ef2024a.csv` | provisional only |
| `EF2023A.zip` | `ef2023a_rv.csv`, `ef2023a.csv` | final available (**we hold only the provisional `ef2023a.csv`**) |
| `HD2025.zip` | `hd2025.csv` | provisional |
| `IC2025.zip` | `ic2025.csv` | provisional |
| `S2024_IS.zip` | `s2024_is.csv` | provisional |
| `SAL2024_IS.zip` | `sal2024_is.csv` | provisional |
| `F2324_F1A.zip` | `f2324_f1a.csv` | provisional |
| `F2324_F2.zip` | `f2324_f2.csv` | provisional (GASB — never ingested) |
| `SFA2324.zip` | `sfa2324.csv` | provisional |
| `EFFY2025.zip` | `effy2025.csv` | provisional |

So: **the newest IPEDS revised/final year is still 2023.** Survey year 2024 remains provisional even though 2025 provisional has shipped, which departs from the usual "provisional N ships alongside final N-1" cadence. Do not wait for a 2024 final that may not arrive on schedule.

Confirmed release provenance (IPEDS release memos, `nces.ed.gov/ipeds/survey-components/release-memo`):
- **2025-26 Fall provisional** — collection closed **2025-10-15**; covers Institutional Characteristics (5,777 institutions), Completions (5,701), 12-Month Enrollment (5,692). This is `IC2025` / `C2025_A` / `EFFY2025` / `HD2025`.
- **2024-25 Spring provisional** — released **2026-01-06**; covers Fall Enrollment (fall 2024), Human Resources (fall 2024), Finance (FY2024), Academic Libraries. This is `EF2024*` / `S2024_*` / `SAL2024_*` / `F2324_*` / `AL2024`.
- The 2025-26 memo flags a **terminology change**: "gender"→"sex", "men"→"male", "women"→"female". **I verified this did NOT change column names.** `C2025_A` header is the identical 64-column layout: `UNITID,CIPCODE,MAJORNUM,AWLEVEL,XCTOTALT,CTOTALT,XCTOTALM,CTOTALM,XCTOTALW,CTOTALW,XCAIANT,…,XCNRALW,CNRALW`. `CTOTALM`/`CTOTALW` retained.

Also verified from `C2025_A_Dict.zip` (80 KB, the only file I actually downloaded): AWLEVEL still enumerates *"Doctor's degree - research/scholarship"*, *"- professional practice"*, *"- other"*. So `ipeds_config.phd_awlevels(2025) → [17]` is correct and needs no change.

`HD2025.zip` header: 70 columns, contains `INSTNM`, `CITY`, `STABBR`, `WEBADDR` (plus `UNITID` behind a UTF-8 BOM) — `resolve_inst_columns()` will resolve all five cleanly.
`EF2024A.zip` header: 73 columns, contains `UNITID`, `EFALEVEL`, `LINE`, `LSTUDY`, `EFTOTLT/M/W`, `EFNRALT/M/W` — same layout as `ef2023a.csv`.

Not yet released (all 404 on both paths): `C2026_A`, `HD2026`, `EF2025A`, `S2025_IS`, `SFA2425`, `F2425_F1A`, `ADM2025`. Also **`IC2024_AY` and `IC2025_AY` do not exist** — `IC2023_AY` (345,600 bytes) is the last academic-year tuition file NCES published under that name.

### 2.3 NSF NCSES — current editions

| Survey | Latest published | Pub no. | Release date | We have it? |
|---|---|---|---|---|
| HERD | **FY2024** | NSF 26-304 | 2025-12-23 | **Yes** — verified: `nsf26304-tab013.xlsx` on the NCSES server is **176,409 bytes**, byte-size-identical to our `data/herd/herd_fy2024_table13.xlsx`. Same file. |
| HERD analytic report | FY2024 ("8.1% growth … $117 billion") | NSF 26-305 | 2026-02-10 | Not held (narrative only, no new data) |
| GSS | **Fall 2024** | NSF 26-307 | 2026-02-18 | **Yes** (PUF `graduate_students_postdocs_2024.zip`) |
| SED data tables | **2024** | NSF 25-349 | 2025-08-28 | **Yes** |
| SED analytic report | 2024 | NSF 26-315 | 2026-03-13 | Not held (narrative) |
| SED 2025 | — | — | **not released** (`ncses.nsf.gov/surveys/earned-doctorates/2025` → HTTP 404) | n/a |
| HERD FY2025 | — | — | **not released** (FY2026 questionnaire opens Nov 2026; FY2025 tables expected ~Dec 2026) | n/a |
| SDR / NSCG | 2023 | — | biennial; 2025 cycle not yet published | Yes (2023 + 2021) |

**Conclusion: NCSES surveys have no freshness gap.** Every survey in scope is at its newest published year in our repo. Anyone assuming "four months means new NSF data" would be wrong here — the NCSES annual cadence puts the next HERD/SED/GSS releases in Dec 2026 – Feb 2027.

New NCSES/NSB *publications* since 2026-04-06 that we do not have:

| Publication | Pub no. | Released | Notes |
|---|---|---|---|
| **The State of U.S. Science and Engineering 2026** | NSB-SEP-2026-1 | **2026-05-04** | Biennial flagship. Downloads: all tables 472 KB zip, Excel tables 40 KB, supplemental tables 161 KB, full report PDF 8.7 MB, everything 21.3 MB. Covers STEM education at all degree levels, STEM workforce, R&D. |
| **Translation to Impact: U.S. and Global STI Output** | NSB-2026-2 | **2026-05-01** | Companion Indicators volume. |
| Federal R&D obligations / funding tables & briefs | NSF 26-316, 26-317, 26-319, 26-320 | 2026-05-04 and 2026-06-24 | Agency-level federal R&D obligations. |

Adjacent source we have **never** ingested, flagged because it is directly on-topic for the research-funding pages:

- **Survey of Federal Science & Engineering Support to Universities, Colleges and Nonprofit Institutions (FSS)** — FY2023 data tables, **NSF 25-339**, with the analytic report **NSF 26-318** (released 2026-03-17). Its **Table 17 is institution-level federal S&E support** (e.g. Johns Hopkins largest at $2.1B in FY2023). This is per-institution federal obligations across all agencies — strictly more complete than our NIH-plus-NSF-only picture. Landing page: `https://ncses.nsf.gov/surveys/federal-support-survey/2023#data`; table builder `https://ncsesdata.nsf.gov/builder/fss`.

### 2.4 SHEEO

**SHEF FY2025 was published 2026-04-09** — three days after our 2026-04-06 ingest. Confirmed live on `https://shef.sheeo.org/data-downloads/`:

| File | Coverage | URL | Size / Last-Modified |
|---|---|---|---|
| Report Data | FY1980–2025 | `https://shef.sheeo.org/wp-content/uploads/2026/04/SHEEO_SHEF_FY25_Report_Data.xlsx` | **737,137 B**, Last-Modified 2026-04-03 |
| Sector Data | FY2019–2025 | `…/2026/04/SHEEO_SHEF_FY25_Sector_Data.xlsx` | **159,031 B**, 2026-04-03 |
| Data Adjustments | FY1980–2025 | `…/2026/04/SHEEO_SHEF_FY25_Data_Adjustments.xlsx` | 200 OK |
| Capital Appropriations | FY2020–2025 | `…/2026/07/SHEEO_SHEF_FY25_Capital_Appropriations_Data.xlsx` | 200 OK |
| Federal Stimulus | FY2009–2025 | `…/2026/07/SHEEO_SHEF_FY25_Federal_Stimulus_Funding_Data.xlsx` | 200 OK |
| PBF Data | FY2020–2025 | `…/2026/07/SHEEO_SHEF_FY25_PBF_Data.xlsx` | 200 OK |
| Residency Data | FY2020–2025 | `…/2026/07/SHEEO_SHEF_FY25_Residency_Data.xlsx` | 200 OK |
| Main report PDF | — | `…/2026/04/SHEF_FY25_Report.pdf` | — |
| State Effort & Capacity | FY1980–**2023** | `…/2025/06/SHEEO_SHEF_FY23_State_Effort_Capacity.xlsx` | unchanged — already have it |

SHEEO's own FY25 release note: $130.7B in state+local appropriations (record high, +2.6% real over FY2024) but FTE enrollment rose 3.6% (10.4M → 10.8M), producing a **1.0% decline in per-student funding — the first per-student decrease since 2012.** That is a genuinely new, publishable finding for the state-funding page.

Grapevine: FY2026 is still the latest edition (we have it). FY2027 Grapevine is due ~Jan 2027.

### 2.5 NIH RePORTER and NSF Awards

Both APIs live and current. Probed directly:

- **NIH RePORTER v2** (`POST https://api.reporter.nih.gov/v2/projects/search`) — MIT, `fiscal_years:[2025]` → `"total": 235`. FY2025 closed 2025-09-30, so this is a **complete** fiscal year. `fiscal_years:[2026]` → `"total": 161`, i.e. partial (FY2026 runs to 2026-09-30) — ingest FY2026 only if partial-year data is explicitly labelled as such.
  For scale: our stored MIT FY2024 = 222 grants; FY2025 = 235. Consistent magnitude, no schema surprise.
- **NSF Award Search API** (`https://api.nsf.gov/services/v1/awards.json`) — returns 2025 awards for MIT normally. `scripts/fetch_nsf_awards.py` needs only its three date/year constants widened.

### 2.6 Medical — NRMP / ECFMG / AAMC

**NRMP — four new 2026 reports since our ingest** (all URLs verified with ranged GET):

| Report | Released | URL | Size |
|---|---|---|---|
| **Results and Data: 2026 Main Residency Match** | 2026-05-26 | `https://www.nrmp.org/wp-content/uploads/2026/05/Main_Match_Results_and_Data-2026.pdf` | **2,758,582 B** |
| **Charting Outcomes: Non-U.S. Citizen IMGs, 2026 Main Residency Match** | 2026-07-28 | `https://www.nrmp.org/wp-content/uploads/2026/07/Non-US-IMG_Charting-Outcomes_FINAL.pdf` | **38,299,799 B** |
| **Charting Outcomes: U.S. Citizen IMGs, 2026 Main Residency Match** | 2026-07-28 | `https://www.nrmp.org/wp-content/uploads/2026/07/US-IMG_Charting-Outcomes_FINAL.pdf` | **33,028,173 B** |
| Charting Outcomes: Demographic Characteristics, MRM & SOAP 2026 | 2026-05 | `https://www.nrmp.org/wp-content/uploads/2026/05/Charting_Outcomes_Demographics_Report-MRM_2026-new-dashboard_final.pdf` | **383,431 B** |

Also on the 2026 index but not chased down: U.S. MD Seniors and U.S. DO Seniors Charting Outcomes (2026-07-28), USMLE Step 2 CK / COMLEX Level 2-CE baselines, 2026 SMS results (2026-02).
I could **not** find a 2026 Advance Data Tables PDF at the conventional URL pattern (`Advance_Data_Tables_2026.pdf` → 404). The 2026 Results-and-Data report supersedes it anyway, so this is moot.

**ECFMG / Intealth (`https://www.intealth.org/data/`) — NO CHANGE.** Still `CertsbyYear2000-2024.pdf`, `Top5CitizenshipCountries2000-2024.pdf`, EVSP 2025 set, `EVSP-Sponsorship-2015-2025.pdf`, `Match2026Infographic.pdf`. We already hold every file on that page. The 2025-certificate-year update has not posted.

**AAMC FACTS — NO CHANGE.** `https://www.aamc.org/data-reports/students-residents/report/facts` still serves the **2025** edition (Applicants & Matriculants, Enrollment/Graduates/MD-PhD, ERAS, Glossary). No 2026 tables posted. The 2026 edition normally lands Oct–Dec. Our April download is current.

---

## 3. GAP TABLE

Sizes are the compressed `.zip` / file sizes read from `Content-Range` headers. "Consumable as-is?" refers to the existing downloader/parser in `scripts/`.

### 3.1 IPEDS

| Source | What we have | Now available | Delta | Direct download URL | Approx size | Consumable as-is? |
|---|---|---|---|---|---|---|
| **Completions (C)** | SY2024 provisional (`C2024_a.csv`); final only to SY2023 | **SY2025 provisional** | **+1 survey year** | `https://nces.ed.gov/ipeds/complete-data-files/C2025_A.zip` | **4.5 MB** zip → 44 MB csv | **No — 2 changes.** (a) `DIRECT_BASE_URL` must move to `/ipeds/complete-data-files`; (b) `ALL_YEARS` and the two `range(…, 2025)` loops in `ipeds_config.py` must extend to 2026. After that: schema identical, `phd_awlevels(2025)=[17]` correct, no parser change. |
| **Completions revised** | `C2023_a_RV` | still `C2023_a_RV` | **none** | — | — | n/a — SY2024 final not yet published |
| **Institutional directory (HD)** | HD2024 | **HD2025** | +1 year | `…/complete-data-files/HD2025.zip` | **1.0 MB** | Same two config changes; 70 cols, all 5 canonical fields resolve |
| **Institutional characteristics (IC)** | IC2023 | **IC2024, IC2025** | +2 years | `…/complete-data-files/IC2024.zip`, `IC2025.zip` | 135 KB, **133 KB** | Yes, once base URL fixed (no year map for IC in `ipeds_config`; downloaded ad hoc today) |
| **IC academic-year tuition** | `ic2023_ay.csv` | `IC2023_AY` is still the newest | **none** | — | 346 KB | NCES appears to have discontinued the `_AY` file — `IC2024_AY`/`IC2025_AY` both 404 |
| **Fall enrollment (EF-A)** | `ef2023a.csv` (provisional). **`EF2024A.zip` on disk is a corrupt 1,245-byte 404 page** | **EF2024A provisional; EF2023A revised (`ef2023a_rv.csv`)** | +1 year, +1 revision | `…/complete-data-files/EF2024A.zip`, `EF2023A.zip` | **3.2 MB**, 6.5 MB | Ad hoc — no downloader covers EF. Header verified compatible with `ef2023a.csv` |
| **Fall enrollment B/C** | none | EF2024B, EF2024C | new components | `…/EF2024B.zip`, `…/EF2024C.zip` | 1.1 MB, 344 KB | Not currently parsed |
| **Enrollment by major (EF-D)** | `ef2023d.csv` | **EF2024D** | +1 year | `…/complete-data-files/EF2024D.zip` | **105 KB** | Ad hoc |
| **Student financial aid (SFA)** | `sfa2223.csv` | **SFA2324** | +1 year | `…/complete-data-files/SFA2324.zip` | **792 KB** | Ad hoc |
| **Human resources (S)** | `s2022_is.csv` | **S2023_IS, S2024_IS** (+ `S2023_SIS`/`S2024_SIS`) | **+2 years** | `…/S2023_IS.zip`, `…/S2024_IS.zip` | 1.9 MB, **937 KB** | Ad hoc; `scripts/enrich_university_json.py:447` hardcodes `hr/faculty_demographics_2022.csv` |
| **Human resources (SAL)** | `sal2022_is.csv` | **SAL2023_IS, SAL2024_IS** | **+2 years** | `…/SAL2023_IS.zip`, `…/SAL2024_IS.zip` | 2.3 MB, 1.1 MB | Ad hoc |
| **Finance F1A (FASB)** | `f2223_f1a.csv` | **F2324_F1A** | +1 year | `…/complete-data-files/F2324_F1A.zip` | **811 KB** | Ad hoc |
| **Finance F2 (GASB — publics)** | **nothing** | F2223_F2, **F2324_F2** | new component | `…/complete-data-files/F2324_F2.zip` | 633 KB | **New parser needed.** Without it, state-appropriations analysis omits most public universities |
| **12-month enrollment (EFFY)** | nothing | EFFY2024, **EFFY2025** | new component | `…/complete-data-files/EFFY2025.zip` | 3.4 MB | Not currently parsed |
| **Winter collection (ADM/GR/OM)** | nothing | ADM2024, GR2024, OM2024, GR200_24 | out of current scope | `…/complete-data-files/{ADM2024,GR2024,OM2024}.zip` | — | Not parsed; noted for completeness |

### 3.2 NSF NCSES

| Source | What we have | Now available | Delta | URL | Size | Consumable as-is? |
|---|---|---|---|---|---|---|
| **HERD** | FY2024 tab13/tab14 (NSF 26-304) | FY2024 (NSF 26-304) | **NONE — current** | — | — | n/a. Byte-size match confirmed (176,409 B) |
| **GSS** | Fall 2024 PUF | Fall 2024 (NSF 26-307) | **NONE — current** | — | — | Optional: 2024 adjusted-institutions file (we hold only 2023) + `nsf26307` data tables zip |
| **SED** | 2024 tables | 2024 (NSF 25-349) | **NONE — current** | — | — | 2025 not released (`/earned-doctorates/2025` → 404) |
| **SDR / NSCG** | 2023 microdata | 2023 | **NONE** | — | — | Biennial; next cycle not out |
| **NSB Indicators** | NSB-2026-1, NSB-2024-5 | + **NSB-SEP-2026-1** (2026-05-04), **NSB-2026-2** (2026-05-01) | **+2 reports** | `https://ncses.nsf.gov/pubs/nsbsep20261`, `https://ncses.nsf.gov/pubs/nsb20262` | tables 472 KB zip; supplemental 161 KB; full 21.3 MB | Same xlsx table pattern as `nsb20261_*` dirs — existing extraction approach applies |
| **Federal S&E Support (FSS)** | **nothing** | FY2023 tables (NSF 25-339); report NSF 26-318 | **new source** | `https://ncses.nsf.gov/surveys/federal-support-survey/2023#data` | small (xlsx tables) | **New parser.** Table 17 = institution-level federal S&E support |

### 3.3 Funding / state finance / medical

| Source | What we have | Now available | Delta | URL | Size | Consumable as-is? |
|---|---|---|---|---|---|---|
| **SHEEO SHEF** | FY2024 (7 files) | **FY2025 (7 files), pub. 2026-04-09** | **+1 fiscal year across whole series** | `https://shef.sheeo.org/wp-content/uploads/2026/04/SHEEO_SHEF_FY25_Report_Data.xlsx` (+ Sector, Adjustments in `/2026/04/`; Capital, Stimulus, PBF, Residency in `/2026/07/`) | **737 KB** main; ~1.5 MB total | **Near — one-line change.** `scripts/build_sheeo_json.py` hardcodes the `FY24` filename; sheet name `'Report Data'` and the `keep_cols` labels must be re-verified against FY25 (SHEEO is usually stable year to year). Note `sheeo_by_state.json` is currently capped at 2010–2024. |
| **SHEEO Grapevine** | FY2026 | FY2026 | **NONE** | — | — | FY2027 due ~Jan 2027 |
| **NIH RePORTER** | FY2020–2024 | **FY2025 complete** (+FY2026 partial) | **+1 full FY** | `POST https://api.reporter.nih.gov/v2/projects/search` | API (no bulk) | **Yes.** `data/state_funding/nih_reporter/fetch_nih.py` is resumable and year-parameterised; add 2025 to the fiscal-year list |
| **NSF Awards** | CY2020–2024 | **CY2025 complete** | **+1 calendar year** | `https://api.nsf.gov/services/v1/awards.json` | API | **Yes.** Edit 3 constants in `scripts/fetch_nsf_awards.py:28-30` (`DATE_END`, `YEARS`) |
| **NRMP** | 2025 Advance Tables; Charting Outcomes IMG **2024** | 2026 Results & Data; **2026 Charting Outcomes Non-US IMG / US IMG**; 2026 demographics | **+4 reports, IMG data 2 years fresher** | see §2.6 | 2.8 MB + 38.3 MB + 33.0 MB + 383 KB | PDF — manual/LLM extraction, same as existing workflow |
| **ECFMG / Intealth** | all current files | identical file list | **NONE** | — | — | Certificates still end at 2024 |
| **AAMC FACTS** | 2025 edition | 2025 edition | **NONE** | — | — | 2026 edition due Oct–Dec 2026 |

---

## 4. THE 2008–2009 QUESTION — VERDICT

**Verdict: ingestion bug, not an upstream gap. And the version currently deployed in `site/ipeds_dashboard.html` no longer exhibits it — the complaint tracks a stale derived CSV, not the live page.**

### 4.1 Upstream is complete

`C2008_A` and `C2009_A` are fully present and always have been. Locally:

```
data/ipeds/c2008_a.csv      90,482,510 bytes
data/ipeds/c2008_a_rv.csv   90,502,010 bytes
data/ipeds/c2009_a.csv      93,931,418 bytes
data/ipeds/c2009_a_rv.csv   93,949,568 bytes
```

The filtered outputs exist too: `data/ipeds/filtered/ipeds_stem_phd_2008.csv` (1,767 lines) and `…_2009.csv` (1,764 lines) — right in line with 2007 (1,787) and 2010 (1,681). And `ipeds_stem_phd_all_years.csv` carries 1,766 rows for 2008 and 1,763 for 2009. Nothing is missing from the source.

`ipeds_config.MISSING_YEARS` is `{1990, 1999}` — those are the only genuine upstream completions gaps, and they are unrelated.

### 4.2 Where the zeros actually live

`data/ipeds/ipeds_stem_phd_demographics_by_year.csv` (mtime **2026-03-08**):

```
2006,17935.0,15797.0,33732,53.2,46.8,466,16446.0,2098.0,11197.0,...
2007,19404.0,17776.0,37180,52.2,47.8,483,18362.0,2259.0,12044.0,...
2008,,,0,,,457,18000.0,2207.0,0.0,1208.0,1211.0,116.0,,,0.0,,,,,,,,,
2009,,,0,,,432,16155.0,2007.0,0.0,1024.0,1162.0,115.0,,,0.0,,,,,,,,,
2010,18006.0,14737.0,32743,55.0,45.0,403,7000.0,811.0,11120.0,...
```

2008 and 2009 have `Total_Men`/`Total_Women` blank, `Total` = 0, `NonresAlien` = 0, and every percentage column empty. **That** is the "missing 2008-2009". The cause is the 2008 IPEDS column-format transition: pre-2008 files use `CRACE15`/`CRACE16` for men/women totals and `CRACE01/02` for non-resident alien; from 2008 those became `CTOTALM`/`CTOTALW` and `CNRALM/CNRALW/CNRALT`. Whatever produced that CSV only knew the `CRACE*` names, so the columns it looked for did not exist in `c2008_a.csv`/`c2009_a.csv` and it wrote zeros.

Header evidence (`head -1` of each raw file):
- `c2007_a.csv`: `XCRACE01 CRACE01 … XCRACE24 CRACE24` — old scheme only.
- `c2008_a.csv` / `c2009_a.csv` / `c2010_a.csv`: **hybrid** — `XCNRALM CNRALM XCNRALW CNRALW XCRACE03 CRACE03 … XCTOTALM CTOTALM XCTOTALW CTOTALW … XCHISPT CHISPT XCAIANT CAIANT XCASIAT CASIAT … XCWHITT CWHITT XC2MORT C2MORT`. Both schemes coexist.
- `c2011_a.csv`: `XCTOTALT CTOTALT … XCNRALW CNRALW` — new scheme only.

This CSV is **orphaned**: `grep -rn "ipeds_stem_phd_demographics\|demographics_by_year"` across `scripts/*.py` and `pipeline/*.py` returns no writer and no reader. It is a leftover from an archived pipeline (`scripts/archive/run_ipeds_pipeline.py` era). Deleting or regenerating it is safe.

### 4.3 The live dashboard is already fixed

`site/ipeds_dashboard.html` (mtime **2026-04-07**) is generated by `scripts/build_dashboard.py`, which *does* handle the transition — see its `CRACE_MAP` (lines 44–61), its `MODERN` map (lines 64–71), and `_extract_demographics()` (line 117) with the explicit `elif year >= 2008:` branch. Parsing the embedded `const D = {…}` payload out of the deployed HTML:

- `national_trend`: 2007=37,180 · **2008=37,578** · **2009=37,082** · 2010=32,743 · 2011=34,257
- `gender_trends` men: 2007=19,404 · **2008=19,672** · **2009=19,396** · 2010=18,006
- `race_trends` (`years` 1995…2024, all nine series populated for 2008 and 2009)
- `trends_by_discipline`: every discipline's `years` array includes 2008 and 2009 with non-null totals

So 2008-2009 renders. If someone is still seeing a gap on the live site, it is a cached/stale deploy, not a data defect.

### 4.4 A real bug I found next door: survey year 2010 race counts are ~46% short

`_extract_demographics()`'s comment says the "modern" columns "only exist from 2011+" and that 2008-2010 "still use the legacy `CRACE01-CRACE14` columns", so for `year >= 2008` it applies the modern map first and then lets `CRACE_MAP` **overwrite** the race fields. That premise is wrong for 2010. I measured it directly on the raw files (AWLEVEL ∈ {9,17}, CIP families 11/14/15/26/27/30/40/42/51):

| Survey year | `CRACE11+CRACE12` (old White) | `CWHITT` (new White) | Institutions reporting old scheme | reporting new scheme | Dashboard's White value |
|---|---|---|---|---|---|
| 2008 | 17,998 | 228 | 384 | 9 | 18,000 → **misses ~1.3%** |
| 2009 | 16,149 | 2,207 | 322 | 55 | 16,155 → **misses ~12%** |
| 2010 | 8,094 | 6,960 | 165 | 192 | 8,045 → **misses ~46%** |

Institutions report under **one** scheme or the other, never both — so the two columns are complementary and should be **summed**, not have one overwrite the other. By 2010 more institutions had migrated to the new categories (192) than remained on the old (165), so "legacy wins" discards the majority.

This is visible in the deployed payload as an obvious 2010 notch: White 2007=18,362 → 2008=18,000 → 2009=16,155 → **2010=8,045** → 2011=15,595. Same notch in Asian (2,007 → 1,275 → 2,158), Hispanic (1,024 → 601 → 1,243), Black (1,162 → 548 → 1,245), AmerIndian (115 → 48 → 102). Note `NonresAlien` is *correct* across the transition (2009=11,599, 2010=11,120, 2011=11,580) because it comes from `CNRALT`, a modern-scheme column — which is exactly why the flagship NRA metric looks fine while every domestic race series dips.

**Fix:** in `_extract_demographics()`, for 2008 ≤ year ≤ 2010, add the legacy and modern race columns together rather than letting the legacy map overwrite. 2008 and 2009 are also affected (1.3% and 12%), just less visibly.

---

## 5. CODE CHANGES REQUIRED

Read-only recon — nothing below was applied.

### 5.1 Blocking (nothing new downloads without these)

`scripts/ipeds_config.py`:

- **Line 26** — `DIRECT_BASE_URL = "https://nces.ed.gov/ipeds/datacenter/data"` → `"https://nces.ed.gov/ipeds/complete-data-files"`.
- **Line 53** — `+ list(range(2000, 2025))  # 2000-2024` → `range(2000, 2026)`.
- **Line 99** — `for y in range(2000, 2025):` (completions `C{y}_A` map) → `range(2000, 2026)`.
- **Line 112** — `for y in range(2002, 2025):` (institutions `HD{y}` map) → `range(2002, 2026)`.

No change needed to `phd_awlevels()` (verified: AWLEVEL 17 = "Doctor's degree - research/scholarship" still present in the C2025 dictionary), to `CIP_FAMILIES`, or to `resolve_inst_columns()` (HD2025 carries INSTNM/CITY/STABBR/WEBADDR).

`scripts/download_ipeds.py` — logic is fine as-is once the base URL changes. One robustness note: the guard at `download_zip()` is `if len(resp.content) < 500` and the NCES 404 page is **1,245 bytes**, so it slips past the size check. It is then caught by `zipfile.BadZipFile`, so `download_ipeds.py` itself would not have written the bogus `EF2024A.zip` — that file came from some ad hoc `curl`. Still worth raising the threshold and/or asserting `content[:4] == b"PK\x03\x04"`.

### 5.2 Cosmetic / follow-on

- `site/ipeds_dashboard.html` line 470: subtitle hardcodes `1984&ndash;2024` — bump when 2025 lands.
- `scripts/qa_report.py`: `has_2024` flag (line 77, 147), `expected_years = set(range(2016, 2025))` (line 146), and the "No 2024 data" rule (line 289) all need a year bump.
- `scripts/build_sheeo_json.py`: hardcoded `SHEEO_SHEF_FY24_Report_Data.xlsx`; docstring says the output covers 2010–2024.
- `scripts/build_herd_funding.py:33`: hardcoded `herd_fy2024_table13.xlsx` — fine for now (FY2024 *is* current), will need touching in Dec 2026.
- `scripts/enrich_university_json.py`: hardcodes `data/ipeds/enrollment/grad_enrollment_demographics_2022.csv` (line 231) and `data/ipeds/hr/faculty_demographics_2022.csv` (line 449) — both derived from 2022 inputs that are now three years stale.
- `scripts/build_dashboard.py` `_extract_demographics()`: the 2008–2010 race-column merge bug in §4.4.
- `data/DATA_DICTIONARY.md`: claims Fall 2024 enrollment is present (it is not — corrupt zip); cites SED as `nsf25300` (should be NSF 25-349); IPEDS date range says 1984-2024.
- `data/ipeds/ipeds_stem_phd_demographics_by_year.csv`: orphaned and wrong for 2008/2009 — delete or regenerate.

### 5.3 Verified NOT to be a problem

- C2025 column layout is identical to 2011+ (64 cols, `CTOTALM`/`CTOTALW` retained despite the "men→male" terminology memo).
- C2025 CSV carries a UTF-8 BOM; `ipeds_filter._read_csv_robust()` already tries `utf-8-sig` first.
- New-path CSVs are unquoted where old-path ones were quoted — `pandas.read_csv` is indifferent.
- EF2024A and HD2025 headers match the layouts already parsed.

---

## 6. RANKED RECOMMENDATION

Ranked by (analytic value delivered) ÷ (effort + risk).

**1 — Fix `DIRECT_BASE_URL`, then ingest IPEDS C2025 + HD2025 + IC2025.** *(4.5 MB + 1.0 MB + 133 KB)*
This is the whole ballgame. It is a one-constant edit plus three `range()` bumps, and until it happens **every** IPEDS refresh is silently impossible — the downloader is pointed at a path NCES has frozen. The payoff is a full extra survey year of the project's primary series (STEM PhD completions by institution, field, and NRA status through June 2025), extending the flagship chart from 1984-2024 to 1984-2025. The schema is confirmed unchanged, `phd_awlevels(2025)` is confirmed correct, and the filter/aggregate stages need no edits. Highest value, lowest risk, and it unblocks everything else in IPEDS.
*Caveat to state on the page:* SY2025 is **provisional**. SY2024 has still not been revised to final, so two consecutive provisional years now sit at the end of the series — flag both.

**2 — SHEEO SHEF FY2025.** *(737 KB main file, ~1.5 MB for all seven)*
Published 2026-04-09, three days after the last ingest — pure bad luck, and the cheapest real win available. It extends a series we already parse (`sheeo_by_state.json`, `sheeo_by_university.json`, currently 2010–2024) by a full fiscal year, and it carries a headline finding worth writing up: record $130.7B in appropriations but the **first per-student funding decline since 2012**, because enrollment (10.4M → 10.8M FTE) outran funding. Effort is one filename constant plus a re-verification that the `'Report Data'` sheet name and `keep_cols` labels survived the FY24→FY25 edition change.

**3 — NIH RePORTER FY2025 and NSF Awards CY2025.** *(API only, no bulk download)*
Both fiscal/calendar years are closed and complete (MIT: 235 NIH projects in FY2025 vs 222 in FY2024). `fetch_nih.py` is already resumable and year-parameterised; `fetch_nsf_awards.py` needs three constants widened. This takes the funding series from a 5-year to a 6-year window and keeps the research-funding pages from looking a year behind. Only real cost is API wall-clock across ~101 institutions. Skip NIH FY2026 (partial — 161 vs 235) unless it is explicitly labelled year-to-date.

**4 — Fix the 2008–2010 race-column merge bug in `build_dashboard.py`.** *(no download at all)*
Pure code fix, zero ingest. Right now the dashboard understates 2010 White PhD completions by ~46% (8,045 vs a true ~15,054) and 2009 by ~12%, producing a fake collapse-and-rebound notch across every domestic race series. Because `NonresAlien` is sourced from a modern-scheme column and is *correct*, the bug silently inflates the apparent NRA share in exactly those years — which is the project's central metric. I rank it above further data ingestion because it corrupts a published number rather than merely omitting a new one.

**5 — Backfill the IPEDS surveys that have quietly fallen two years behind: HR (`S2023_IS`, `S2024_IS`, `SAL2023_IS`, `SAL2024_IS`), Fall Enrollment (`EF2024A`, `EF2024D`), SFA (`SFA2324`), Finance (`F2324_F1A`).** *(~10 MB total)*
All are now reachable once step 1 lands. Priority within this group: **EF2024A first** — partly because `data/ipeds/enrollment/EF2024A.zip` is currently a corrupt 1,245-byte 404 page that `DATA_DICTIONARY.md` advertises as real data, which is worse than an honest absence; and partly because faculty/HR data at 2022 is the stalest thing in the repo (`enrich_university_json.py` still reads `faculty_demographics_2022.csv`). Also grab `EF2023A.zip` again to pick up the now-published `ef2023a_rv.csv` revision.

**6 — NRMP 2026 reports for `medical.html`.** *(~74 MB, mostly the two IMG PDFs)*
The 2026 Charting Outcomes **Non-U.S. Citizen IMG** edition (38.3 MB) directly replaces our 2024 IMG file — two years fresher on the single most relevant medical dataset for a foreign-national-pipeline project — plus Results and Data: 2026 Main Residency Match (2.8 MB), which we have never held in any year. Ranked here only because PDF extraction is manual and the payload is large. Note ECFMG/Intealth and AAMC published **nothing** new, so this is the entire medical delta.

**7 — NSB-SEP-2026-1 and NSB-2026-2.** *(472 KB tables; 161 KB supplemental)*
"The State of U.S. Science and Engineering 2026" (2026-05-04) and "Translation to Impact" (2026-05-01). Same `nsb*-tab*.xlsx` shape as the `nsb20261_*` directories we already extract, so the existing approach applies. Narrative/indicator value rather than new institution-level microdata — worth having, not urgent.

**8 — New source: NCSES Federal S&E Support (FSS), FY2023, NSF 25-339.** *(small xlsx tables)*
Not a freshness gap — a coverage gap. Its Table 17 gives **institution-level federal S&E obligations across all 30 reporting agencies**, which is strictly broader than our NIH + NSF picture. Ranked last because it needs a new parser and a new page/section rather than slotting into an existing series, but it is the highest-ceiling *new* dataset found in this sweep.

### Explicitly do NOT bother right now

- **HERD** — FY2024 (NSF 26-304) is current; our `herd_fy2024_table13.xlsx` is a byte-size match for the server copy. Next release ~Dec 2026.
- **GSS** — Fall 2024 (NSF 26-307) is current. Next ~Feb 2027.
- **SED** — 2024 (NSF 25-349) is current; `/earned-doctorates/2025` returns 404. Next ~Aug–Dec 2026, worth a re-check in a month.
- **SDR / NSCG** — biennial, 2023 is current.
- **ECFMG / Intealth** — file list byte-for-byte identical to what we downloaded on 2026-04-05.
- **AAMC FACTS** — still the 2025 edition; 2026 due Oct–Dec.
- **SHEEO Grapevine** — FY2026 is current; FY2027 ~Jan 2027.
- **IPEDS SY2024 revised/final** — has not shipped and shows no sign of shipping on the normal cadence. Do not block on it.

### Re-check calendar

| When | What |
|---|---|
| ~Sep 2026 | SED 2025 data tables |
| Oct–Dec 2026 | AAMC FACTS 2026 |
| ~Dec 2026 | HERD FY2025 (NSF 27-3xx) |
| ~Jan 2027 | SHEEO Grapevine FY2027; IPEDS 2025-26 Winter provisional |
| ~Feb 2027 | GSS Fall 2025 |
| ~Apr 2027 | SHEEO SHEF FY2026 |
| Anytime | IPEDS SY2024 completions revised/final (overdue) |
