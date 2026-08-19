# US Federal Immigration Data — Freshness Recon
**Repo:** `/Users/andy/usds_china` · **Date of audit:** 2026-08-18 · **Last ingest:** ~2026-04-06
**Method:** read-only. Repo files inspected directly (row counts / decision-date ranges computed from the
actual XLSX/CSV bytes, not from filenames). Upstream verified by fetching the live pages.

> **Access note:** `dol.gov`, `ice.gov`, `studyinthestates.dhs.gov` and `ohss.dhs.gov` all 403 `curl` and
> `WebFetch` (Akamai/CF bot rules) but serve `wget` fine. `travel.state.gov` 403s everything; its content is
> mirrored verbatim at `adoption.state.gov/content/travel/...`, which does serve. Any downloader added to the
> pipeline needs this — a naive `requests.get()` will get 403s from DOL and State.

---

## 1. What we already have (observed, not inferred)

### 1.1 USCIS H-1B Employer Data Hub
| File | Format | FY observed | Rows |
|---|---|---|---|
| `data/h1b/h1b_datahub_fy2010.csv` … `_fy2023.csv` | plain CSV (`"Fiscal Year",Employer,"Initial Approval",…`) | 2010–2023, one FY per file | — |
| `data/h1b/h1b_datahub_fy2024.csv` | **UTF-16 TSV crosstab** export | 2024 (only value in col 2) | 61,824 |
| `data/h1b/h1b_datahub_fy2025.csv` | UTF-16 TSV crosstab | 2025 | 62,324 |
| `data/h1b/h1b_datahub_fy2026.csv` | UTF-16 TSV crosstab | **2026** | 24,362 |

Junk in the same directory: `h1b_datahub_fy2026-2.csv` (30 bytes, UTF-16 text "Reset Filters"),
`h1b_datahub_fy2024-checkthis.csv` / `fy2025-checkthis.csv` (byte-identical dupes; excluded by the parser's
`"checkthis" in fn` guard).

**Processed:** `data/h1b/h1b_by_university.json` — 101 universities, FY keys **2010–2026**.
The FY2026 slice was pulled ~2026-04-02, i.e. it is **FY2026 Q1 only** (~24K employer-rows).

### 1.2 DOL OFLC — LCA (H-1B/H-1B1/E-3)
`data/h1b/lca/` holds 33 XLSX (~7.0 GB): `lca_LCA_FY2013`, `lca_H-1B_FY2018`,
`H-1B_Disclosure_Data_FY15_Q4`/`FY16`/`FY17`/`FY2018_EOY`/`FY2019`, then `lca_fy2020_Q1..Q4` through
`lca_FY2025_Q1..Q4`, and **`lca_FY2026_Q1.xlsx` (75,609,372 B) as the newest**.

I decoded `DECISION_DATE` (column D) straight out of the sheet XML for the recent files:

| File | DECISION_DATE min | max | verdict |
|---|---|---|---|
| `lca_FY2025_Q1.xlsx` | 2024-10-01 | 2024-12-31 | Q1 only |
| `lca_FY2025_Q2.xlsx` | 2025-01-01 | 2025-03-31 | Q2 only |
| `lca_FY2025_Q3.xlsx` | 2025-04-01 | 2025-06-30 | Q3 only |
| `lca_FY2025_Q4.xlsx` | 2025-07-01 | 2025-09-30 | Q4 only |
| `lca_FY2026_Q1.xlsx` | 2025-10-01 | 2025-12-31 | Q1 only |

So **the archived FY2025-and-earlier LCA quarterly files are quarter-disjoint** — appending them is additive.
(This matters below, because the FY2026 file on DOL's site is *not*.)

Duplicated copies sit at `data/h1b/LCA_Disclosure_Data_FY2024_Q4.xlsx` and `…_FY2025_Q1.xlsx` (byte-identical
to the `lca/` ones — 83,056,843 B and 87,690,398 B). They are outside `lca/` so the parser ignores them.

**Processed:** `data/h1b/lca_by_university.json` — 101 keys, `yearly` buckets **2014–2025**.
⚠️ Those keys are **calendar years of DECISION_DATE**, not fiscal years (see §4).

### 1.3 DOL OFLC — PERM
Only one file: **`data/h1b/perm_fy2024_q4.xlsx`** (76,167,854 B, 155 columns, 92,258 data rows).
`DECISION_DATE` spans **2023-10-01 → 2024-09-30**, i.e. the file is the *cumulative full FY2024*.
**Processed:** `data/h1b/perm_by_university.json` — 71 universities, and **no year dimension at all**
(`{certified, denied, total, top_titles}` only).

Note the PERM schema carries fields this project is not yet using and would want:
`COUNTRY_OF_CITIZENSHIP`, `FOREIGN_WORKER_BIRTH_COUNTRY`, `CLASS_OF_ADMISSION`, `FOREIGN_WORKER_EDUCATION`
(Doctorate/Master's/…), `FOREIGN_WORKER_INFO_MAJOR`, `FOREIGN_WORKER_INST_OF_ED`, `PW_SOC_CODE`.
That is a PhD→green-card link at *individual* granularity, including the degree-granting institution.

### 1.4 ICE / SEVP — OPT
* PDFs `data/h1b/*.pdf`: top-100 school pre/post-completion OPT and STEM-OPT lists for **CY2017–CY2024**;
  `sevis_btn_2024.pdf` (1,391,792 B) = CY2024 SEVIS by the Numbers.
* `data/h1b/opt_by_university.json` — 59 universities, years **2017–2024** (calendar years).
* `data/h1b/opt_by_school.json` — only 4 keys (`2022_opt`, `2022_stem_opt`, …).
* `data/h1b/national_opt_trends.json` — CY**2007–2024** (opt / stem_opt / cpt).
* **Broken:** `data/h1b/2024_Top200_Schools_OPT_STEM_OPT_Students.pdf` and
  `2024_Top200_Schools_Pre_Post_OPT_Students.pdf` are **10 bytes each** — failed downloads never noticed.

### 1.5 ICE / SEVP — SEVIS Data Mapping Tool
`data/sevp/`: `sevis_data_mapping_{jan2024, dec2024, aug2025, dec2025, jan2026, feb2026, mar2026}.csv`
plus `_stem` variants for all of those **except dec2025**. Latest = **March 2026**. Not a continuous monthly
series — it's 7 spot snapshots.

### 1.6 State Department
`data/h1b/state_dept/`: `FYs97-24_NIVDetailTable.xlsx` (2,533,585 B, FY1997–**FY2024**),
`FY2024AnnualReport_TableXVB_NIVbyClass.pdf`, `FY2024AnnualReport_TableXIII_IVbyChargeability.pdf`,
`FY2024_TableV_IV_by_preference.pdf`, `refusal_rates_FY19…FY25.pdf`, `b_visa_refusal_rates_fy23/24/25.csv`,
`niv_by_country_fy2024.csv`, `niv_timeseries_key_countries.csv`, `eb_visas_by_country_fy2024.csv`,
`immigrant_visas_by_country_fy2015_2024.csv`.

**Processed:** `data/h1b/national_visa_trends.json` (created 2026-04-05) —
`f1_issuances` FY2005–**FY2024**; `j1_issuances`, `h1b_issuances`, `o1_issuances`, `l1_issuances` likewise to
FY2024; `h1b_petitions_approved` to **FY2024**; `o1a_petitions_approved` to **FY2023**;
J-1 participants CY2015–CY2025 (CY2025 partial).

### 1.7 J-1 / BridgeUSA
`data/h1b/j1_participation_cy2015_2025.xlsx` (40,585 B) — CY2015–CY2025.

### 1.8 DHS Yearbook of Immigration Statistics
**Not used anywhere.** `grep -ril yearbook` over `*.py|*.md|*.json|*.html` returns no immigration-yearbook hit.
There is no `data/dhs_yearbook/`. (Given: the entry/exit **overstay** report has no FY2025 edition —
FY2024 is latest — and `data/vwp/dhs_overstay_fy2025.pdf` is misnamed, it holds the FY2024 report.)

### 1.9 What the site claims
`site/data_sources.html` (symlink into `usds_china_private`, last written 2026-04-06) advertises:
OPT **CY2017–2024** (59 schools) · H-1B Data Hub **FY2010–2026** (98 unis) · LCA **FY2020–2025** (78 unis) ·
PERM **FY2024** (71 unis) · SEVIS **Jan 2024–Mar 2026**.
`data/DATA_DICTIONARY.md` §"DOL H-1B Disclosure Data" is already stale — it lists only
`LCA_Disclosure_Data_FY2024_Q4.xlsx` + `FY2025_Q1.xlsx` and "~176 MB", whereas `lca/` actually holds 33 files.
`data/analyses/build_analyses.py` pins FY2024 State-Dept visas, SED 2024, FY2025 B-visa refusals, and
"SEVP SEVIS STEM Data Mapping, March 2026".

---

## 2. What is now available upstream

### 2.1 USCIS H-1B Employer Data Hub — **FY2026 Q3 available**
`https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub` (fetched 2026-08-18) states verbatim:

> "The H-1B Employer Data Hub includes data from **fiscal year 2009 through fiscal year 2026 (quarter 3)**…"

The **archive page has not moved and has not been extended**:
`https://www.uscis.gov/archive/h-1b-employer-data-hub-files` still lists only
`h1b_datahubexport-2009.csv` … `-2023.csv`. I HEAD-checked the obvious continuations:

| URL | status |
|---|---|
| `…/document/data/h1b_datahubexport-2023.csv` | 200 |
| `…/document/data/h1b_datahubexport-2024.csv` | **404** |
| `…/document/data/h1b_datahubexport-2025.csv` | **404** |
| `…/document/data/h1b_datahubexport-2026.csv` | **404** |

So FY2024+ is still **only** obtainable through the Tableau widget (the page's own instructions:
*Crosstab View → filters → Download to Excel → CSV*), which is what produced the existing UTF-16 TSV files.
That is a **manual/browser-automation step, not a URL fetch** — same as last time.

### 2.2 DOL OFLC — canonical URL **has moved** for the current FY
The index page `https://www.dol.gov/agencies/eta/foreign-labor/performance` is still canonical, but the
current-fiscal-year files are no longer under `/sites/dolgov/files/ETA/oflc/pdfs/`. They are now at
**`https://www.dol.gov/media/…`** (prior-FY archives stay at the old `/pdfs/` path). The page also carries a
typo — the visible link text reads `LCA_Dislclosure_Data_FY2026_Q3.xlsx` while the `href` is correct — and the
LCA href is emitted with a double slash (`https://www.dol.gov//media/...`), which still resolves.

Page text, "Latest Quarterly Updates":
> "The following case disclosure files cover determinations issued between **October 1, 2025 and June 30, 2026**."
and, in the standing description:
> "**Each data set is cumulative for the fiscal year**, containing unique records identified by the applicable
> OFLC case number based on the most recent date a case determination decision was issued."

| File | URL | Size | Last-Modified |
|---|---|---|---|
| LCA FY2026 Q3 | `https://www.dol.gov/media/LCA_Disclosure_Data_FY2026_Q3.xlsx` | **251,850,891 B (240 MB)** | 2026-08-07 |
| LCA Worksites FY2026 Q3 | `https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/FY26Q3/LCA_Worksites_FY_2026_Q3.xlsx` | 45,032,522 B | 2026-08-07 |
| LCA Appendix A FY2026 Q3 | `…/FY26Q3/LCA_Appendix_A_FY2026_Q3.xlsx` | 32,995 B | 2026-08-07 |
| LCA Record Layout FY2026 Q3 | `…/FY26Q3/LCA_Record_Layout_FY2026_Q3.pdf` | — | 2026-08-07 |
| PERM FY2026 Q3 | `https://www.dol.gov/media/PERM_Disclosure_Data_FY2026_Q3.xlsx` | **156,267,808 B (149 MB)** | 2026-08-07 |
| PERM FY2025 (full FY) | `https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/PERM_Disclosure_Data_FY2025_Q4.xlsx` | 87,007,731 B | 2025-12-18 |
| PERM FY2024 **New Form** | `…/pdfs/PERM_Disclosure_Data_New_Form_FY2024_Q4.xlsx` | 13,734,583 B | 2024-11-12 |
| PERM Record Layout FY2026 Q3 | `…/FY26Q3/PERM_Record_Layout_FY2026_Q3.pdf` | 250,129 B | 2026-08-07 |

Sanity check on the archived quarter files: `…/pdfs/LCA_Disclosure_Data_FY2025_Q4.xlsx` is 79,134,156 B,
byte-for-byte the size of our local `lca_FY2025_Q4.xlsx` — our copies are the canonical ones.

#### ⚠️ The FY2026 LCA file is CUMULATIVE — this is the single biggest trap in this audit
I verified it rather than trusting the blurb. I streamed the first ~63% of
`LCA_Disclosure_Data_FY2026_Q3.xlsx`, inflated `xl/worksheets/sheet1.xml` in place and decoded 317,470
`DECISION_DATE` values. Month histogram:

```
2025-10  1,459   2025-11 47,046   2025-12 34,444
2026-01 40,103   2026-02 37,506   2026-03 45,130
2026-04 76,744   2026-05 35,038   (…rest of file not read)
```

It contains **Oct 2025 through Jun 2026 in one file** — Q1+Q2+Q3. Our `lca_FY2026_Q1.xlsx` is a strict subset
of it (its ~83K Oct–Dec 2025 records line up with the 82,949 Oct+Nov+Dec seen here).
**Dropping the new file into `data/h1b/lca/` alongside `lca_FY2026_Q1.xlsx` would double-count Q1.**

Note the behaviour changed between fiscal years: FY2025's four archived files are quarter-disjoint (§1.2),
FY2026's single current file is cumulative. Do not assume either; re-check decision dates after download.
Structurally the FY2026 file is unchanged — 98 columns, same header names (`CASE_NUMBER, CASE_STATUS,
RECEIVED_DATE, DECISION_DATE, …, EMPLOYER_NAME, …, WAGE_RATE_OF_PAY_FROM, WAGE_UNIT_OF_PAY, …`), one worksheet,
1.60 GB uncompressed.

### 2.3 ICE / SEVP — SEVIS Data Mapping Tool: **through August 2026**
`https://studyinthestates.dhs.gov/sevis-by-the-numbers/sevis-by-the-numbers-data` lists monthly pages up to
`/sevis-data-mapping-tool/august-2026-sevis-data-mapping-tool-data` and
`…/august-2026-stem-sevis-data-mapping-tool-data`. Continuous coverage exists for **Apr, May, Jun, Jul, Aug 2026**
(both country-level and STEM), all missing locally.

There is **no CSV endpoint** — the monthly page renders the data as an HTML `<table>` (16,559 `<td>` cells on the
Aug-2026 country page, headers `Country of Citizenship, Continent, Region, Active Students, Male, Female,
Associate…Secondary, AK…WY`, exactly matching our local CSV schema). Ingest = scrape the table, which is easy
and stable. Page ≈ 250 KB (country) and considerably larger for STEM (~28K rows).

### 2.4 ICE / SEVP — SEVIS by the Numbers: **still CY2024** (given; re-confirmed)
`https://www.ice.gov/sevis` links only `https://www.ice.gov/doclib/sevis/btn/25_0605_2024-sevis-btn.pdf`, which
we already hold as `data/h1b/sevis_btn_2024.pdf`. Probed `26_0605_2025-sevis-btn.pdf` and `2025-sevis-btn.pdf`
→ both 404. The 2024 edition was published 2025-06-05; a 2025 edition is now ~2.5 months past that cadence.
Context: `ice.gov` currently shows a banner — *"Due to the lapse in federal funding, this website will not be
actively managed."* Also new on that page: **on 2026-07-17 DHS published a final rule establishing a fixed
period of admission and an extension-of-stay procedure for F and J nonimmigrants** — a policy break that will
show up in future SEVIS/OPT series and is worth a footnote on the site.

Consequence: the **CY2025 top-100 OPT / STEM-OPT school tables do not exist yet**, so `opt_by_university.json`
cannot advance past CY2024 by any means.

### 2.5 State Department — **frozen since December 2025**
Verified via the `adoption.state.gov` mirror of `travel.state.gov`:

* **Annual reports index** lists `report-of-the-visa-office-2000` … **`-2024`**. No FY2025 report.
  `FY2025AnnualReport/…TableXVB.pdf` → 404.
* **NIV Detail Tables**: latest are `FY24NIVDetailTable.xlsx` and `FYs97-24_NIVDetailTable.xlsx`.
  `FYs97-25_NIVDetailTable.xlsx` → **404**. The FY97-24 file was *re-uploaded* 2026-08-08 but is still
  **2,533,585 B — identical in size to our copy**, so no revision to re-ingest.
* **Monthly NIV Issuance Statistics**: the "Fiscal Year 2026" block contains only
  **October 2025, November 2025, December 2025** (Nationality and Post, XLSX+PDF). Nothing since.
  Direct pattern: `https://travel.state.gov/content/dam/visas/Statistics/Non-Immigrant-Statistics/
  MonthlyNIVIssuances/DECEMBER%202025%20-%20NIV%20Issuances%20by%20Nationality%20and%20Visa%20Class.xlsx`

**State has effectively stopped publishing.** Nothing for F-1/J-1/H-1B/O-1/L-1 FY2025 annual issuances is
obtainable today; the only forward motion available is Oct–Dec 2025 monthly files (FY2026 Q1 partial).

### 2.6 USCIS congressional reports — **two new H-1B reports we don't have**
| Report | URL | Size | Published |
|---|---|---|---|
| H-1B Characteristics FY2025 | `https://www.uscis.gov/sites/default/files/document/data/fy25_h1b_characteristics_congress_signed_04242026.pdf` | 1,178,009 B | 2026-05-05 |
| H-1B Petitions annual report FY2025 | `https://www.uscis.gov/sites/default/files/document/legal-docs/fy25_h1b_petitions_021126_v1.0.pdf` | 477,616 B | 2026-02-12 |
| (we cite) H-1B Characteristics FY2024 | `…/reports/ola_signed_h1b_characteristics_congressional_report_FY24.pdf` | 200 | — |

These are the source for `national_visa_trends.json → h1b_petitions_approved`, which currently stops at FY2024.
Also: USCIS quarterly form data now runs through **FY2026 Q2 (Jan–Mar 2026)** — including
*"Nonimmigrant Worker Petitions by Case Status and RFE (FY2026 Q2)"* — on
`https://www.uscis.gov/tools/reports-and-studies/immigration-and-citizenship-data`.

**Broken source:** `…/data/stem_related_petition_trends_eb2_and_o1a_categories_factsheet_fy23.pdf` — the
factsheet behind `o1a_petitions_approved` (FY2018–FY2023) — is **still linked but now returns 404**. The O-1A
series is dead unless a newer factsheet appears; our existing values are the archive.

### 2.7 J-1 / BridgeUSA — **unchanged**
`https://j1visa.state.gov/basics/facts-and-figures/` serves
`https://j1visa.state.gov/wp-content/uploads/2026/02/EV-Participation-_-CY2015_2025_For-Website-Inquiries.xlsx`
= **40,585 B**, Last-Modified 2026-02-18 — byte-size identical to our `j1_participation_cy2015_2025.xlsx`.
Same file, no delta. (CY2026 flyers exist per-category but are PDFs of CY2025 data.)

### 2.8 DHS Yearbook of Immigration Statistics — **not usable yet, and not currently used**
`https://ohss.dhs.gov/topics/immigration/yearbook`: both **2023 and 2024 show "Download coming soon"** for the
compiled PDF. OHSS states *"We release data tables as they become available. We release the final yearbook PDF
in September of the following fiscal year."* For the 2024 yearbook, refugee tables 13–15 are posted and LPR
tables 1–12 are "coming soon". Individual tables live at `https://ohss.dhs.gov/topics/immigration/yearbook/2024/tableN`.
The Nonimmigrant-Admissions (I-94, F/J/H) tables are published separately under
`https://ohss.dhs.gov/topics/immigration/nonimmigrant-admissions`.
This is a **greenfield source for this project, not a refresh** — nothing to re-ingest.
(Given: DHS entry/exit overstay report has no FY2025 edition; `data/vwp/dhs_overstay_fy2025.pdf` is a misnamed
copy of the FY2024 report and should be renamed.)

---

## 3. Gap table

| # | Source | What we have (file · max observed) | Now available | Delta | Direct URL | Size | Parser (`step3_parse_federal.py`) |
|---|---|---|---|---|---|---|---|
| 1 | **DOL LCA (H-1B)** | `data/h1b/lca/lca_FY2026_Q1.xlsx` — decisions 2025-10-01→2025-12-31 | FY2026 **Q3 cumulative**, decisions 2025-10-01→2026-06-30 | **+2 quarters (Jan–Jun 2026)** | `https://www.dol.gov/media/LCA_Disclosure_Data_FY2026_Q3.xlsx` | **240 MB** (1.6 GB unzipped) | ✅ schema-compatible (98 cols, unchanged names) — ❌ **must first delete `lca_FY2026_Q1.xlsx` *and* its `lca/csv_cache/` CSV**, else Q1 double-counts |
| 2 | **DOL PERM** | `data/h1b/perm_fy2024_q4.xlsx` — full FY2024 (2023-10-01→2024-09-30); `perm_by_university.json` has **no year dimension** | Full **FY2025**, plus **FY2026 Q1–Q3 cumulative** | **+1 full FY, +3 quarters** | `…/pdfs/PERM_Disclosure_Data_FY2025_Q4.xlsx` · `https://www.dol.gov/media/PERM_Disclosure_Data_FY2026_Q3.xlsx` | 83 MB · **149 MB** | ❌ **No PERM parser exists.** step3 only *re-reads* a pre-built `perm_by_university.json`. New code required. |
| 2b | DOL PERM (new ETA-9089 form) | *(missing entirely)* | `PERM_Disclosure_Data_New_Form_FY2024_Q4.xlsx` | FY2024 new-form cases we never ingested | `…/pdfs/PERM_Disclosure_Data_New_Form_FY2024_Q4.xlsx` | 13 MB | ❌ different record layout, separate parser branch |
| 3 | **USCIS H-1B Data Hub** | `h1b_datahub_fy2026.csv` — FY2026 **Q1**, 24,362 rows; `h1b_by_university.json` FY2010–2026 | Hub advertises **FY2009 – FY2026 Q3** | **+2 quarters of FY2026** | ⚠️ no file URL — Tableau *Crosstab View → Download to Excel → CSV*. Archive CSVs stop at 2023 (`-2024/-2025/-2026.csv` all **404**) | ~15 MB/FY | ✅ **no change needed** — `_parse_h1b_files` already sniffs the UTF-16 BOM and reads the crosstab TSV (`row[1]`=FY, `row[2]`=employer, `row[8..11]`=approvals/denials). Just overwrite `h1b_datahub_fy2026.csv`. |
| 4 | **SEVIS Data Mapping Tool** | `data/sevp/sevis_data_mapping_mar2026.csv` (+`_stem`) | Monthly pages through **August 2026** | **+5 months** (Apr–Aug 2026), country **and** STEM | `https://studyinthestates.dhs.gov/sevis-data-mapping-tool/august-2026-sevis-data-mapping-tool-data` (and `…-stem-…`) | ~250 KB/page country; ~2 MB STEM | ❌ not parsed by step3 at all — HTML `<table>` scrape; schema identical to existing CSVs so downstream consumers are unaffected |
| 5 | **ICE SEVIS by the Numbers / OPT top-100** | `sevis_btn_2024.pdf` + CY2017–CY2024 school PDFs; `opt_by_university.json` CY2017–2024 | **Still CY2024.** No 2025 edition. `26_0605_2025-sevis-btn.pdf` → 404 | **none** | n/a | n/a | n/a — nothing to ingest. Fix the two **10-byte** `2024_Top200_Schools_*.pdf` stubs instead. |
| 6 | **State Dept NIV annual (F-1/J-1/H-1B/O-1/L-1)** | `FYs97-24_NIVDetailTable.xlsx` FY1997–**FY2024**; `national_visa_trends.json` to FY2024 | **Still FY2024.** No FY2025 Report of the Visa Office; `FYs97-25_…xlsx` → 404 | **none** (FY97-24 re-uploaded 2026-08-08, same 2,533,585 B ⇒ unchanged) | n/a | n/a | n/a |
| 7 | **State Dept monthly NIV issuances** | not held (project uses annual only) | FY2026 block: **Oct, Nov, Dec 2025 only** | +3 months of FY2026 Q1, then a hard stop | `…/MonthlyNIVIssuances/DECEMBER%202025%20-%20NIV%20Issuances%20by%20Nationality%20and%20Visa%20Class.xlsx` | ~200 KB each | ❌ new parser; different (post-level/nationality) shape than the annual detail table |
| 8 | **USCIS H-1B congressional reports** | FY2024 only (cited in `DOWNLOAD_LINKS.md`); `h1b_petitions_approved` → FY2024 | **FY2025** characteristics (2026-05-05) and **FY2025** petitions report (2026-02-12) | **+FY2025** national petition totals | `…/data/fy25_h1b_characteristics_congress_signed_04242026.pdf` · `…/legal-docs/fy25_h1b_petitions_021126_v1.0.pdf` | 1.2 MB · 0.5 MB | ❌ manual PDF read → hand-edit `national_visa_trends.json` (that file is hand-curated, not generated) |
| 9 | **O-1A STEM petition trends** | `o1a_petitions_approved` FY2018–**FY2023** | **Source URL now 404** — factsheet withdrawn | none; series is frozen | (dead) `…/data/stem_related_petition_trends_eb2_and_o1a_categories_factsheet_fy23.pdf` | — | n/a — mark as discontinued in `data_sources.html` |
| 10 | **J-1 / BridgeUSA** | `j1_participation_cy2015_2025.xlsx` 40,585 B | Same file, 40,585 B, LM 2026-02-18 | **none** | `https://j1visa.state.gov/wp-content/uploads/2026/02/EV-Participation-_-CY2015_2025_For-Website-Inquiries.xlsx` | 40 KB | n/a |
| 11 | **DHS Yearbook** | **not used at all** | 2023 & 2024 yearbooks still "Download coming soon"; individual tables trickling out | new source, not a refresh | `https://ohss.dhs.gov/topics/immigration/yearbook/2024/tableN` | small | ❌ would need new code; low value right now |

---

## 4. Fiscal vs calendar year — the traps in this dataset

1. **`lca_by_university.json → yearly` keys are CALENDAR years, not fiscal years.** `step3` resolves its year
   column with `find_col("FISCAL_YEAR", "DECISION_DATE")`; the LCA layout has **no `FISCAL_YEAR` column**, so it
   always falls through to `DECISION_DATE` and then does `int(fy_str[:4])`. `site/data_sources.html` labels this
   "DOL LCA Disclosure Data — FY 2020–2025", which is wrong: it is CY2014–CY2025 of decision dates.
   Adding LCA FY2026 Q3 will populate CY2026 through June only — a **half year that will look like a 50% crash**
   on any per-university trend chart unless it is labelled partial.
2. **PERM and LCA use opposite file conventions.** PERM's `FY2024_Q4` file is the *cumulative full fiscal year*
   (verified: 2023-10-01→2024-09-30). LCA's archived `FY2025_Q1..Q4` files are *quarter-disjoint* (verified).
   And LCA's current `FY2026_Q3` is *cumulative*. Three different behaviours in one agency's output.
3. **H-1B Data Hub is fiscal year** (petition first-decision FY). `h1b_by_university.json` FY2026 is Q1-only
   today and would become Q1–Q3 after refresh — still a partial FY, again ~75% of a year.
4. **OPT / SEVIS by the Numbers are calendar year** (CY2024). `national_opt_trends.json` and
   `opt_by_university.json` are CY. Do not chart them on the same axis as the FY series without a note.
5. **SEVIS Data Mapping Tool is a point-in-time snapshot**, neither FY nor CY — "active records as of month X".
6. **State Dept issuances are FY**, and are *visa stamps issued abroad*; USCIS petition counts are domestic
   approvals. `national_visa_trends.json`'s own `_metadata.notes` already says these are not additive — keep it.

---

## 5. Parser verdict, per source

**`_parse_h1b_files` (H-1B Data Hub) — works unchanged.** It sniffs the UTF-16 BOM and switches to a
tab-delimited reader, mapping `row[8..11]` → initial approvals/denials, continuing approvals/denials, which is
exactly the crosstab column order (`…, New Employment Approval, New Employment Denial, Continuation Approval,
Continuation Denial, …`). Overwriting `h1b_datahub_fy2026.csv` with a fresh FY2026 export is a drop-in.
Housekeeping: `h1b_datahub_fy2026-2.csv` (30 B, "Reset Filters") is harmlessly skipped (`len(row) < 10`), and
the two `*-checkthis.csv` dupes are filtered by name; both are still clutter worth deleting.

**`_parse_lca_files` (LCA) — works structurally, but the cache is a landmine.** The DuckDB path converts every
`*.xlsx` in `data/h1b/lca/` into `lca/csv_cache/<same-name>.csv` once, then queries `csv_cache/*.csv` with
`union_by_name=true`. Two consequences:
* Removing `lca_FY2026_Q1.xlsx` is **not enough** — its `csv_cache/lca_FY2026_Q1.csv` would survive and keep
  being unioned. Both must go. (`csv_cache/` is currently empty, so the next run rebuilds all 33+1 files —
  budget a long first pass; the FY2026 Q3 sheet alone is 1.6 GB uncompressed.)
* The employer join is `UPPER(TRIM(EMPLOYER_NAME)) = e.employer_name` — **exact match only** against the 292
  patterns in `pipeline/entity_map.json`. The openpyxl fallback uses substring matching, so the two paths
  disagree. New universities appearing in FY2026 filings under a changed legal name will silently drop.

**PERM — no parser exists.** `step3` merely does `if perm_path.exists(): json.load(...)`. `grep -rl
"perm_by_university"` finds only `step3_parse_federal.py`, `step4_enrich.py` and
`scripts/enrich_university_json.py` — all *consumers*. Ingesting FY2025/FY2026 PERM means writing a builder
(and, ideally, adding the year dimension the current JSON lacks).

**OPT — no parser exists** either; `opt_by_university.json` was hand-extracted from the top-100 PDFs. Moot
until a CY2025 SEVIS BTN appears.

**SEVIS Data Mapping — no parser**; the CSVs were saved by hand. A small HTML-table scraper would automate it.

**Downloader — needs a real user agent and, for State, a mirror.** DOL/ICE/DHS 403 `curl`+`requests` but
accept `wget`; `travel.state.gov` 403s everything and must be read via `adoption.state.gov/content/travel/…`.

---

## 6. Ranked recommendation

**1 — DOL LCA FY2026 Q3 (240 MB).** *Highest value per unit of work.* Biggest real delta on the board
(+6 months of decisions, Jan–Jun 2026, on the project's richest university-level employment dataset), the
parser already handles the format, and it directly refreshes `lca_by_university.json` for 101 universities.
**Do this first, but do it carefully:** move `lca_FY2026_Q1.xlsx` out of `lca/`, purge any
`lca/csv_cache/lca_FY2026_Q1.csv`, download, then **verify the new file's `DECISION_DATE` min/max before
running step 3** — the cumulative-vs-quarterly behaviour changed between FY2025 and FY2026 and could change
again. Label FY2026 as partial (through 2026-06-30) wherever it renders.

**2 — USCIS H-1B Data Hub FY2026 refresh (Q1 → Q3).** Zero code risk (parser is already compatible) and it
un-staleness the headline "FY2010–2026, 98 universities" claim on `data_sources.html`. The cost is that it is
a **manual Tableau crosstab export**, not a fetch — so it needs a human or a browser-automation step. Worth
doing in the same session as #1 so the H-1B and LCA vintages stay aligned (both then run through Jun 2026).

**3 — DOL PERM FY2025 + FY2026 Q3 (83 MB + 149 MB).** The largest *coverage* gap in the repo: we hold exactly
one PERM year (FY2024) and two more are sitting there. This is the green-card stage of the site's headline
"PhD → OPT → H-1B → Green Card" pipeline and it is currently a single frozen data point with no year axis at
all. Ranked third only because it needs **new parser code**. When writing it, pick up
`FOREIGN_WORKER_EDUCATION`, `FOREIGN_WORKER_INST_OF_ED`, `FOREIGN_WORKER_INFO_MAJOR`,
`COUNTRY_OF_CITIZENSHIP` and `CLASS_OF_ADMISSION` — PERM is the only federal file that links a named
degree-granting institution to a green-card sponsorship, which is squarely this project's thesis. Grab the
13 MB `PERM_Disclosure_Data_New_Form_FY2024_Q4.xlsx` at the same time to close FY2024.

**4 — SEVIS Data Mapping Apr–Aug 2026 (5 months, country + STEM).** Cheap (HTML table scrape, schema already
matches), and it is the *only* immigration series in this whole audit with data more recent than June 2026.
`data_sources.html` currently advertises "Jan 2024 – Mar 2026"; this moves the site's freshest number forward
by five months and refreshes the "229,463 active Chinese students" headline. Low value per row but very low cost.

**5 — USCIS FY2025 H-1B congressional reports (2 PDFs, 1.7 MB).** Extends
`national_visa_trends.json → h1b_petitions_approved` from FY2024 to FY2025. Manual PDF read + hand-edit of a
curated JSON, ~15 minutes, but it is the only way to advance any *national* series past FY2024 right now.

**Do NOT bother this cycle:** State Dept (frozen at FY2024; monthly stops at Dec 2025), SEVIS by the Numbers /
OPT school tables (still CY2024), J-1 (byte-identical), O-1A factsheet (404, discontinued), DHS Yearbook
(2023 *and* 2024 still unpublished).

**Housekeeping worth folding in (no downloads):**
* `data/vwp/dhs_overstay_fy2025.pdf` is the FY2024 report — rename it.
* `data/h1b/2024_Top200_Schools_OPT_STEM_OPT_Students.pdf` and `…_Pre_Post_OPT_Students.pdf` are 10-byte stubs.
* Delete `h1b_datahub_*-checkthis.csv`, `h1b_datahub_fy2026-2.csv`, and the duplicate
  `data/h1b/LCA_Disclosure_Data_FY2024_Q4.xlsx` / `…_FY2025_Q1.xlsx` (≈170 MB of exact dupes).
* `data/DATA_DICTIONARY.md` §"DOL H-1B Disclosure Data" lists 2 LCA files / "~176 MB"; there are 33 / ~7 GB.
* `data_sources.html` mislabels the LCA coverage as fiscal years when it is decision **calendar** years, and
  should note the 2026-07-17 DHS final rule on fixed periods of admission for F/J nonimmigrants.
