# Data Retrieval Implementation Plan

## Goal
Build a definitive list of **US universities with STEM PhD programs**, mapping:
**State → University → STEM Discipline → Department details (URLs, faculty directories, student lists)**

Two federal data sources provide the authoritative institution/program lists. The Gemini-exported spreadsheet (`data/gemini_exported_sheet.csv`) provides an initial list of ~120 top R1 research universities by state to cross-reference against.

---

## Phase 1: IPEDS Complete Data Files

### 1.1 — Download Raw Data (Automated: `scripts/download_ipeds.py`)
The script automates download from the [IPEDS Complete Data Files](https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx) page.
- Downloads **two** ZIP files for the most recent data year:
  - **`HD<year>.zip`** — Institutional Characteristics (Directory Information). Master list of institutions with `UNITID`, name, state, address, etc.
  - **`C<year>_A.zip`** — Completions. Every degree awarded by every institution, broken down by CIP code and award level.
- Also downloads the corresponding **Dictionary** files for both.
- Extracts all CSVs into `data/ipeds/`.

### 1.2 — Filter & Merge (Python Script: `scripts/ipeds_filter.py`)
1. **Load** `C<year>_A.csv` (Completions).
2. **Filter PhD only**: Keep rows where `AWLEVEL == 17` (Doctor's degree — research/scholarship).
3. **Filter STEM disciplines** by `CIPCODE` prefix:
   | CIP Prefix | Field | Category |
   |---|---|---|
   | `11.xxxx` | Computer and Information Sciences | Core STEM |
   | `14.xxxx` | Engineering | Core STEM |
   | `15.xxxx` | Engineering Technologies | Core STEM |
   | `26.xxxx` | Biological and Biomedical Sciences | Core STEM |
   | `27.xxxx` | Mathematics and Statistics | Core STEM |
   | `30.xxxx` | Multi/Interdisciplinary Studies (incl. Data Science) | Core STEM |
   | `40.xxxx` | Physical Sciences | Core STEM |
   | `42.xxxx` | Psychology | Core STEM |
   | `51.xxxx` | Health Professions / Clinical | Clinical/Medical |

   > **Note:** Clinical/Medical fields (`51.xxxx`) are downloaded and tagged but analyzed separately from Core STEM.
4. **Load** `HD<year>.csv` (Institutional Characteristics).
5. **Merge** filtered completions with HD on `UNITID` to get institution name, state, city, website, etc.
6. **Deduplicate** — group by `(State, University, CIP 2-digit family)` to get one row per institution-discipline pair.
7. **Export** to `data/ipeds/ipeds_stem_phd_programs.csv` with columns:
   - `UNITID`, `State`, `University`, `City`, `STEM_Discipline` (standardized name), `CIP_Code`, `Institution_URL`

### 1.3 — Validate
- Cross-reference against `data/gemini_exported_sheet.csv` to confirm coverage of known R1 institutions.
- Flag any top R1 universities that are missing from IPEDS output (likely means they didn't report completions that year).
- Flag any institutions in IPEDS output that are *not* in the Gemini list (potential additions).

---

## Phase 2: NSF GSS Data

### 2.1 — Download Raw Data (Automated: `scripts/download_nsf_gss.py`)
The script automates download from the [NCSES Data Portal](https://ncses.nsf.gov/data-explorer/).
- Downloads the public-use dataset ZIP (CSV files, typically named `gss_<year>_data.csv` or similar).
- Downloads the **Codebook / Methodology** PDF — essential for decoding GSS field codes and the `HDG` column.
- Extracts into `data/nsf_gss/`.

> If direct-URL download fails (NCSES sometimes requires interactive access), the script will print manual download instructions as a fallback.

### 2.2 — Filter (Python Script: `scripts/nsf_gss_filter.py`)
1. **Load** the GSS CSV.
2. **Filter doctoral institutions**: Keep rows where `HDG == 1` (institution grants doctorates). Verify exact flag value in codebook.
3. **Filter STEM fields**: Use the codebook to identify GSS field codes corresponding to:
   - Computer Sciences
   - Engineering (including Engineering Technologies)
   - Biological Sciences
   - Mathematics / Statistics
   - Physical Sciences
   - Multi/Interdisciplinary Studies
   - Psychology
   - Health/Clinical fields (tagged separately as `Clinical/Medical`)
4. **Group** by `(Institution Name, GSS Field Code)` to produce the target list.
5. **Export** to `data/nsf_gss/nsf_gss_stem_phd_programs.csv` with columns:
   - `Institution_Name`, `State` (if available), `GSS_Field`, `GSS_Field_Code`

### 2.3 — Validate
- Cross-reference GSS output against IPEDS output to find overlaps and gaps.
- GSS is pre-filtered to STEM, so it may surface specialized research institutes that IPEDS misses.

---

## Phase 3: Merge & Reconcile

### 3.1 — Script: `scripts/merge_sources.py`
1. Load IPEDS filtered output and NSF GSS filtered output.
2. Fuzzy-match institution names between datasets (university naming varies — e.g., "University of California-Berkeley" vs "UC Berkeley"). Use `fuzzywuzzy` or `rapidfuzz`.
3. Produce a **unified master list**: `data/master_stem_phd_institutions.csv`
   - Columns: `State`, `University` (standardized), `STEM_Discipline` (standardized), `Category` (Core STEM / Clinical-Medical), `Source` (IPEDS / GSS / Both), `UNITID`, `CIP_Code`, `GSS_Field_Code`, `Institution_URL`
4. Cross-reference with `data/gemini_exported_sheet.csv` to flag coverage gaps.

### 3.2 — Output
- The master CSV becomes the input for the next phase: scraping department-level URLs (faculty directories, PhD student lists, etc.) as described in the Gemini conversation's spreadsheet schema.

---

## Phase 4: Scaffold for Department-Level Scraping (Future)

Once the master institution-discipline list exists, the next step (outside this plan) is:
- For each (University, STEM Discipline) pair, discover the department homepage URL.
- From that homepage, find Faculty Directory URL, PhD Student List URL, MSc Student List URL, Alumni List URL.
- Populate the full spreadsheet schema:
  `State | University | STEM Discipline | Department Name | Dept Home URL | Faculty Directory URL | PhD Student List URL | MSc Student List URL | Alumni List URL | Notes`

---

## File Structure

```
usds_china/
├── data/
│   ├── gemini_exported_sheet.csv        # Existing — R1 universities by state
│   ├── ipeds/
│   │   ├── HD<year>.csv                 # Download — Institutional Characteristics
│   │   ├── C<year>_A.csv               # Download — Completions
│   │   ├── dictionaries/               # Download — Column dictionaries
│   │   └── ipeds_stem_phd_programs.csv  # Generated — Filtered output
│   ├── nsf_gss/
│   │   ├── gss_<year>_data.csv         # Download — GSS public use data
│   │   ├── codebook.pdf                # Download — Field code reference
│   │   └── nsf_gss_stem_phd_programs.csv # Generated — Filtered output
│   └── master_stem_phd_institutions.csv # Generated — Merged final list
├── scripts/
│   ├── download_ipeds.py               # Phase 1 automated download
│   ├── ipeds_filter.py                  # Phase 1 filtering
│   ├── download_nsf_gss.py             # Phase 2 automated download
│   ├── nsf_gss_filter.py               # Phase 2 filtering
│   └── merge_sources.py                # Phase 3 merging
├── plans/
│   ├── datasource_1.md                  # Existing — IPEDS plan
│   ├── datasource_2.md                  # Existing — NSF GSS plan
│   └── implementation_plan.md           # This file
└── specs/
    └── (future scraper specs)
```

---

## Dependencies

```
pandas
rapidfuzz       # for fuzzy institution name matching
requests        # for direct-URL download fast path
openpyxl        # for reading .xlsx files
playwright      # for browser-automated downloads (IPEDS + NCSES)
```

> **Setup:** After `pip install -r requirements.txt`, run `playwright install chromium` to install the browser.

---

## Execution Order

| Step | Action | Script | Output |
|---|---|---|---|
| 1 | Download IPEDS HD + Completions ZIPs | `scripts/download_ipeds.py` | `data/ipeds/*.csv` |
| 2 | Download NSF GSS data + codebook | `scripts/download_nsf_gss.py` | `data/nsf_gss/*` |
| 3 | Filter IPEDS for STEM + Clinical PhDs | `scripts/ipeds_filter.py` | `data/ipeds/ipeds_stem_phd_programs.csv` |
| 4 | Filter NSF GSS for STEM + Clinical docs | `scripts/nsf_gss_filter.py` | `data/nsf_gss/nsf_gss_stem_phd_programs.csv` |
| 5 | Merge & reconcile both sources | `scripts/merge_sources.py` | `data/master_stem_phd_institutions.csv` |
| 6 | Review & validate master list | Manual review | Corrections applied |

---

## Resolved Decisions

1. **Expanded STEM fields** — CIP codes 15, 30, and 42 added to Core STEM. CIP 51 (Clinical/Medical) included but tagged separately for independent analysis.
2. **Download automation** — Scripts try direct-URL downloads first (fast path), then fall back to Playwright browser automation for interactive pages (IPEDS ASP.NET form, NCSES terms-of-use). Use `--headed` flag to watch the browser for debugging.
3. **Scope** — Core STEM and Clinical/Medical are both captured in the dataset. The `Category` column distinguishes them so they can be analyzed together or separately.
