# Documentation Accuracy Audit — PhD Demographics

Date: 2026-08-18
Auditor: doc-audit subagent
Repos: `/Users/andy/usds_china` (public, branch `assistant`), `/Users/andy/usds_china_private`
Baseline commits reviewed: `fa0e9ad`, `3ee3197`, `5213be1`, `b0061f8`, `1a977c6`, `a23a60a`

Line numbers refer to the files **as they were before my edits**.

---

## 0. Ground truth measured from the repo

| Fact | Verified value | How verified |
|---|---|---|
| Universities in `pipeline/universities.json` | **101** | `json.load` key count |
| Configs in `scripts/generate_name_lists.py` CONFIGS | **105** | `grep -c "'key': '...'"` |
| `pipeline/entity_map.json` mappings | **292** | key count |
| `pipeline/system_h1b_map.json` entries | **1** (`missouri_st` → `umissouri`) | key count |
| `data/taxonomy.json` canonical categories | **44** (29 STEM + 15 Non-STEM) | key count |
| `data/taxonomy_lookup.json` variants | **277** | key count |
| Year filter caps (post `3ee3197`) | **2016–2026** for 98/101; `utk` 2016–2022, `pdx` 2019–2026, `caltech` 1966–2026 | universities.json `processing.years` |
| `infer_degree_type()` chain length | **9 steps** (ETDMS lookup inserted at position 2 by `fa0e9ad`) | read source, lines 1379–1464 |
| University-specific dept extractors | **8** `extract_dept_from_*` fns + `normalize_stanford_dept` + `get_dept_from_oai` + `column_department`; 11 `dept_source` values total | grep |
| Platform types in `scripts/scrape_oai_etds.py` | **8** real (`bepress`, `blacklight`, `dspace`, `dspace5`, `eprints`, `figshare`, `hyrax`, `invenio`) + `unknown` | regex over REPOS |
| Repos in `scrape_oai_etds.py` REPOS | 104 | regex |
| `enrich_concurrent.py` universities / threads | **10 / 15** | REPOS keys, `CONCURRENCY = 15` |
| Parquet schema | **9 cols**: university, department, year, name, classification, confidence, title, url, degree | `step2_process._export_parquet`, `build_parquet_from_site.py` |
| Static pages built | 101 STEM + 98 non-STEM = **199**; `sitemap.xml` = **214** `<loc>` | `ls`, `grep -c` |
| `site/data/{stem,nonstem}/` file count | **102** each (101 unis + `_search.json`) | `ls | wc -l` |
| `data/h1b/h1b_by_university.json` | **101** universities, all non-empty | json |
| `data/h1b/lca_by_university.json` | **101** universities, all non-empty | json |
| `data/h1b/opt_by_university.json` | **59** universities, CY2017–2024 | json |
| `data/h1b/perm_by_university.json` | **71** universities | json |
| LCA source files | **32** xlsx, **3.3 GB**, FY2013 → FY2026Q1; parsed years 2014–2025 | `ls`, `du -sh` |
| H-1B Data Hub CSVs | FY2010–FY2026 | `ls` |
| HERD funding | 101 universities, 2010–2024 | json |
| `data/western_us_dissertations/` | **110** CSVs, **981 MB** | `ls`, `du -sh` |
| `data/sevp/sevis_data_mapping_*.csv` | **7** country-level + **6** `_stem` | `ls` |
| `data/nsf_sed/parsed/` | **7** CSVs; `sed_top10_countries_by_year.csv` and `sed_citizenship_by_field.csv` live in `data/nsf_sed/` (not `parsed/`) | `ls`, `find` |
| `data/nsf_sed` raw XLSX | 96 | `find -name '*.xlsx' | wc -l` |
| Enriched per-university JSON fields | completions_trend, dept_links, enrollment, enrollment_ipeds, faculty, financial_aid, funding, h1b, h1b_system_note, key, lca, name, nra, opt, perm, records, state_funding, state_funding_institution, tuition, usaspending | union over `site/data/stem/*.json` |
| Pipeline steps registered | **7**: harvest, process, parse_federal, enrich, generate, build_pages, deploy | `pipeline/__main__.py` |
| `generate_name_lists_html.py` merge block | line **~2575** (file is 2648 lines) | grep |
| `data/etdms_degrees/` | 11 university JSONs + `_run.log` (bgsu, binghamton, boise_state, niu, udenver, ulouisville, umemphis, unm, usc_columbia, usd, utah_state) — **growing** | `ls` |
| `scripts/archive/` | 13 scripts, exactly matching `scripts/archive/README.md` | `ls` |

---

## 1. Inaccuracies found and FIXED (structural / path / naming)

### `/Users/andy/usds_china/README.md`
| Line | Claimed | Actual | Action |
|---|---|---|---|
| 22–24 | Install = `pip install openpyxl duckdb` + `pip install anthropic` | `requirements.txt` exists and additionally requires pandas, requests, beautifulsoup4, rapidfuzz, playwright, pytest | Rewrote Quick Start step 2 to use `pip install -r requirements.txt` plus the two documented optionals |
| 51 | `pipeline/ # Functional data pipeline (6 steps)` | 7 registered steps | → "(7 steps)" |
| 56 | `step1_harvest.py # OAI-PMH scraping (101 repositories)` | `universities.json` contains **zero** harvest configs (see Bug 1); the scraper registry has 104 repos | → "OAI-PMH + REST API harvesting" |
| 58–68 | pipeline/ tree stops at `step4_enrich.py`; no `step5b_build_pages.py` | `pipeline/step5b_build_pages.py` exists in the public repo and is in the default step order | Added the line |
| 74 | `scrape_oai_etds.py … (10 platforms: …)` | 8 platform types | → 8 |
| 71–86 | scripts/ tree omits `build_static_pages.py`, `build_parquet_from_site.py`, `enrich_etdms_degrees.py` | All three exist and are invoked by the pipeline / labeling chain | Added the three lines |
| 88–101 | data/ tree omits `etdms_degrees/` | Exists and feeds `infer_degree_type()` step 2 | Added the line |
| 103–107 | tests/ tree omits `test_universities.py` (which the same README invokes at line 174/180) | Exists | Added the line |
| 118 | `[1. HARVEST] ── OAI-PMH (10 platforms) …` | 8 | → 8 |
| 121 | `[2. PROCESS] … ──▶ data/processed/*.parquet` | Step 2 writes `data/processed/{stem,nonstem}/{key}.json` **and** `data/processed/{stem,nonstem}_records.parquet` | Corrected |
| 138 | `2016-2024 thesis record coverage` | Caps bumped to 2026 by `3ee3197` | → 2016-2026 |
| 146 | Data-sources table: Thesis/Dissertation coverage `2016-2024` | 2016-2026 | → 2016-2026 |
| 206–207 | Parquet schema: `university, department, year, name, title, url, degree` (7 cols) | 9 cols — `classification` and `confidence` added by `b0061f8` | Corrected |

### `/Users/andy/usds_china/pipeline/PIPELINE.md`
| Line | Claimed | Actual | Action |
|---|---|---|---|
| 14–17 | Enrichment includes "NIH RePORTER grants, and NSF Awards" | Nothing reads `data/state_funding/nih_reporter/nih_by_university.json` or `nsf_awards/nsf_by_university.json`; `step4_enrich` merges SHEEO, state-specific funding and **USAspending** | Replaced with "and USAspending federal awards" |
| 42 | merge logic "(line ~2268)" of `generate_name_lists_html.py` | line ~2575 | → ~2575 |
| 96–102 | `PipelineState` dataclass omits `halt_reason` | Field exists | Added |
| 104–114 | `StepOutcome` dataclass omits `university_key` | Field exists (first positional after `step_name`) | Added |
| 229–231 | "8-step inference chain (config → degree fields → degree_level → OAI sets → type → relation → description → late OAI fallback)" | 9 steps; ETDMS lookup is step 2 | Rewrote as 9-step chain including ETDMS |
| 230 | "Department extraction (13 university-specific extractors + generic fallback)" | 8 university-specific extractors | → 8 |
| 260–263 | LCA "FY2015-2024", "32 Excel files, 3.6 GB total" | Files span FY2013–FY2026Q1, parsed years 2014–2025; 32 files, 3.3 GB | → FY2014-2025, 3.3 GB |
| 275 | PERM "72 universities with approval data" | 71 | → 71 |
| 283 | "**Critical design rule**: This is the ONLY step that writes to `site/data/`" | Contradicts Invariant 2 in the same doc and the actual code — `generate` also writes those files (merge-not-overwrite) | Reworded: enrich is the only step that writes the *federal enrichment fields* |
| 284–285 | "Merges:" list omits USAspending and state-specific funding | Both merged (`usaspending`, `state_funding_institution` keys present) | Added |
| 356 | `universities.json` example: `"years": [2016, 2024]` | `[2016, 2026]` | → 2026 |
| 346–359 | Example shows a populated `harvest` block and `employer_names` for `mit` | Real file has `"harvest": {}` and `"employer_names": []` for **all 101** universities | Replaced with the actual `mit` entry |
| 372 | entity_map example `"UNIVERSITY OF CALIFORNIA DAVIS": "uc_davis"` | Actual value is `ucdavis` (there is no `uc_davis` key) | → `ucdavis` |
| 381–395 | `manifest.json` example shape `{"mit": {"process": {...}, "h1b": true, ...}}` | Real shape is `{key: {"records": {...}, "data_sources": {"h1b": true, ...}, "h1b_system_note": "", "process": {...}}}` | Replaced with real shape |
| 400 | "The 8-step `infer_degree_type()` inference chain" + 8 numbered items | 9 steps | Renumbered to 9, inserted ETDMS |
| 441–463 | File Structure tree omits `step5b_build_pages.py` | Exists | Added |
| 467–468 | "`site/data/` is written ONLY by step4_enrich" | Same contradiction as line 283 | Reworded |

### `/Users/andy/usds_china/pipeline/LABELING_METHODOLOGY.md`
| Line | Claimed | Actual | Action |
|---|---|---|---|
| 8–46 | 7 numbered steps | 9 steps: ETDMS lookup (step 2) and the dedicated `degree_level` check (step 4) were undocumented | Inserted both, renumbered to 9 |
| 74–81 | "The `oai_etdms` Fix … *would fix* SMU, Binghamton, BYU, U Arkansas, Mississippi State" | Done. `scrape_oai_etds.py` sets `metadata_prefix: "oai_etdms"` for all five; `fa0e9ad` added `scripts/enrich_etdms_degrees.py` + `data/etdms_degrees/` for 9 more bepress schools | Rewrote as completed work, naming the actual mechanism |
| 85 | "In the future pipeline, degree labeling happens in Step 2: PROCESS" | The pipeline exists; step 2 is `pipeline/step2_process.py` | Present tense |
| 88 | "Load raw CSV from `data/raw/{key}.csv`" | `data/western_us_dissertations/{key}_etds.csv`; `data/raw/` does not exist | Corrected |
| 91 | "Output to `data/processed/{key}.json`" | `data/processed/{stem,nonstem}/{key}.json` | Corrected |

### `/Users/andy/usds_china/data/DATA_DICTIONARY.md`
| Line | Claimed | Actual | Action |
|---|---|---|---|
| 622 | `sdr_citizenship_findings.json` documented under **Directory:** `data/nsf_workforce/sdr_2023/psd23Public/` | File is at `data/nsf_workforce/sdr_citizenship_findings.json` | Qualified the path |
| 823–828 | "harvested … from 107 university digital repositories", "107 CSV files", "~872 MB" | 110 CSVs, 981 MB, 101 tracked universities | Corrected file count + size; reworded the repository count |
| 995–997 | site/data example file `auburn.json` | No `auburn` key exists in `universities.json` | → `binghamton.json` |
| 997 | "**Files:** 108 JSON files in each directory" | 102 each (101 universities + `_search.json`) | → 102 |

### `/Users/andy/usds_china/data/university_repositories.md`
| Line | Claimed | Actual | Action |
|---|---|---|---|
| 9 | Summary table "On Site \| **103**" | 101 | → 101 |
| 16 | Heading "## On Site (**98** universities)" | 101 (and it contradicted line 9 in the same file) | → 101 |

### `/Users/andy/usds_china/data/visa_correlation_analysis.md`
| Line | Claimed | Actual | Action |
|---|---|---|---|
| 7 | `data/sevp/sevis_data_mapping_{month}{year}.csv` (**8** snapshots) | 7 | → 7 |
| 22 | "`data/nsf_sed/parsed/*.csv` (7 parsed tables) + 90+ raw XLSX tables" but the table below lists **9** files | 7 in `parsed/`; `sed_top10_countries_by_year.csv` and `sed_citizenship_by_field.csv` are in `data/nsf_sed/`; 96 raw XLSX | Corrected the header line |
| 44 | `h1b_by_university.json` (**97** universities matched) | 101 | → 101 |
| 51 | `lca_by_university.json` (**78** universities) | 101 | → 101 |

### `/Users/andy/usds_china_private/README.md`
| Line | Claimed | Actual | Action |
|---|---|---|---|
| 18–19 | "the full development environment with all **6** pipeline steps" | 7 | → 7 |
| 35–36 | `infra/` listed with only `analytics_lambda.py` | `infra/` also contains `chat/` and `contact/` | Added |
| 25–29 | `scripts/` listing omits `build_dashboard.py` and `generate_dashboard_data.py` | `link.sh` symlinks both | Added |
| 44 | Deploy: `python -m pipeline run --step generate,deploy` | Skips `build_pages`, which pre-renders the 199 static pages + Parquet that `deploy` uploads — deploying without it ships stale university pages | → `generate,build_pages,deploy` |

### `/Users/andy/usds_china_private/plans/`
| File:Line | Claimed | Actual | Action |
|---|---|---|---|
| `datasource_2.md:56,64` | `scripts/scrape_uw_dissertations.py` | Moved to `scripts/archive/` | Path corrected |
| `datasource_2.md:73` | `scripts/scrape_escholarship.py` | `scripts/archive/` | Path corrected |
| `datasource_2.md:86` | `scripts/scrape_stanford_dissertations.py` | `scripts/archive/` | Path corrected |
| `datasource_2.md:104,114` | `scripts/scrape_or_wa_dissertations.py` | `scripts/archive/` | Path corrected |
| `implementation_plan.md:85,161` | `scripts/merge_sources.py` | `scripts/archive/` | Path corrected |

### `/Users/andy/usds_china/scripts/archive/README.md`
No inaccuracies. All 13 listed scripts exist in `scripts/archive/`; the S3 sync command matches the one in the root README.

---

## 2. Number-dependent placeholders — AWAITING AUTHORITATIVE STATS

These were **left untouched**. Every entry is a record count, labeling percentage, or
per-university statistic that the in-flight `process` re-run supersedes.

### `/Users/andy/usds_china/README.md`
| Line | Current text | Statistic it represents |
|---|---|---|
| 132 | `**101** universities (55 R1, 25 R2)` | R1/R2 split. Note: 55+25=80 ≠ 101, and no Carnegie field exists anywhere in `universities.json` — this number cannot be reproduced from the repo at all. |
| 133 | `**294,280** total thesis/dissertation records` | Total records. Commit `3ee3197` already states 455,524 total / 328,581 STEM after the year-cap bump. |
| 134 | `**160,193** PhD + **70,554** Master's classified (82% labeling rate)` | PhD count, MS count, site-wide labeling rate. `fa0e9ad` states site-wide moved 79.6% → 82.7%. |

### `/Users/andy/usds_china/pipeline/PIPELINE.md`
| Line | Current text | Statistic it represents |
|---|---|---|
| 14 | `**Total data**: 298K+ STEM + 115K Non-STEM thesis/dissertation records` | STEM / non-STEM record totals |
| 271 | OPT: `59 universities with OPT/STEM OPT/CPT counts` | Verified 59 today — recheck if OPT data is re-parsed |
| 383–393 | manifest example values `records: 12906, phd: 6615, ms: 0, unlabeled: 6291, labeling_pct: 51.3` (MIT) | Per-university process stats used as an illustrative example |
| 411 | `**Current labeling rate**: ~82% across all universities` | Site-wide labeling rate |
| 412–413 | `BYU (6% → 97%), Mississippi State (7% → 100%), U Arkansas (9% → 100%)` | Per-university before/after labeling. Also note: the 9 schools actually enriched in `fa0e9ad` were boise_state, niu, udenver, usc_columbia, ulouisville, umemphis, usd, utah_state, unm — **not** these three. Worth deciding whether to re-point this sentence at the real set. |

### `/Users/andy/usds_china/pipeline/LABELING_METHODOLOGY.md`
| Line | Current text | Statistic it represents |
|---|---|---|
| 49–59 | "Fully Labeled (>95%)" / "Well Labeled (50-95%)" university groupings, incl. `MIT (51%)`, `NC State (64%)`, `Rice, Boston U, Cornell (40-60%)` | Per-university labeling rates |
| 61–72 | "Poorly Labeled (<20%)" table: CMU 2,985/10%; SMU 487/16%; Binghamton 94/3%; U Houston 3,466/19%; BYU 2,393/6%; UIUC 4,508/5%; U Arkansas 2,332/9%; Mississippi State 2,389/7% | Per-university record counts + labeling rates. **All of these predate `3ee3197` and `fa0e9ad`** — the year-cap bump and ETDMS enrichment invalidate every row. The "Fix" column is also now historical for the bepress rows. |

### `/Users/andy/usds_china/pipeline/AI_CLASSIFIER_DESIGN.md`
| Line | Current text | Statistic it represents |
|---|---|---|
| 3 | `22 universities have <20% degree labeling` | Count of low-labeling universities |
| 57 | `294K records × ~50 tokens/record = ~15M tokens` | Total record count |
| 88 | `Use the 230K already-labeled records as training data` | Labeled record count |
| 129–130 | `We have 230K labeled records as training data` | Labeled record count |

### `/Users/andy/usds_china/data/DATA_DICTIONARY.md`
| Line | Current text | Statistic it represents |
|---|---|---|
| 3 | `Last updated: 2026-03-31` | Doc freshness stamp — bump once stats land |
| 828 | `~1.4 million total rows` (western_us_dissertations) | Raw harvested row count |
| 976 | `16 datasets, 285,544 total rows` (finished_data) | Archive row count |

### `/Users/andy/usds_china/data/university_repositories.md`
| Line | Current text | Statistic it represents |
|---|---|---|
| 3 | `Last updated: 2026-03-30` | Doc freshness stamp |
| 10–12 | `In Progress: 1`, `Blocked: ~6`, `Not viable: ~3` | Repository-status counts |
| 45–165 | Per-university `NRA: X%, N PhDs/yr` figures throughout Tiers B/C/D | Per-university NRA + PhD-per-year |

### `/Users/andy/usds_china/data/student_directory_audit.md`
| Line | Current text | Statistic it represents |
|---|---|---|
| 3 | `Last updated: 2026-04-01` | Doc freshness stamp |
| 7 | `Searched 60+ universities` | Search breadth |
| 11 | `Universities with student directory links: 42/107` | Denominator is 107; the project tracks **101** universities and 105 configs — needs reconciliation |
| 12 | `Total student directory URLs found: 137` | URL count (the tables list ~53 rows + "16 more UW departments") |
| 13 | `Universities where NO public directory exists: ~65` | Count |

### `/Users/andy/usds_china/data/visa_correlation_analysis.md`
Entirely built out of external-source numbers (SEVIS, SED, State Dept). None are
derived from the pipeline, so none block on the `process` re-run. Left as-is:
lines 12, 16, 36, 52, 65–70, 76–80, 87, 101–106, 112, 119–124, 218, 223–226,
236, 242–243, 287.

---

## 3. Real bugs (not documentation errors)

### Bug 1 — `pipeline/universities.json` has NO harvest configs: Step 1 is inert
All 101 entries have `"harvest": {}` and `"employer_names": []`.
`step1_harvest._build_harvest_plan()` does:
```python
harvest = uni.harvest
if not harvest.get("oai_base"):
    continue
```
so the plan is always empty and `python -m pipeline run` never harvests anything.
Verified this has been true since the file was introduced in `57589a1` — it was
never populated. The real harvest registry lives in `scripts/scrape_oai_etds.py`
(`REPOS`, 104 entries with `oai_base`/`platform`/`sets`/`metadata_prefix`).
Consequence: README and PIPELINE.md both describe a config-driven harvest step
that cannot run. Either populate `universities.json.harvest` from
`scrape_oai_etds.REPOS`, or make `step1_harvest` read `REPOS` directly.
`employer_names` being empty is harmless — entity resolution goes through
`entity_map.json`, which is complete.

### Bug 2 — `--mode top50` contains 6 university keys that do not exist
`pipeline/__main__.py:22-29` `MODE_TOP50` lists:
`osu`, `uc_davis`, `uc_san_diego`, `uc_berkeley`, `uc_los_angeles`, `stonybrook`.
The real keys are `ucdavis`, `ucsd`, `ucberkeley`, `ucla`, `stony_brook`;
`osu` (Ohio State) is not in `universities.json` at all (though `entity_map.json`
still maps 3 Ohio State employer names to the orphaned `osu` key).
`run_pipeline()` prints `WARNING: Unknown university keys` and silently drops them,
so `--mode top50` actually runs 44 universities, not 50.
`MODE_TOP20` / `tests/test_universities.py:TOP_20_KEYS` are all valid.

### Bug 3 — `pipeline/degree_classifier.pkl` is dead weight
Documented in `PIPELINE.md:247` as providing "offline classification using
TF-IDF + LogisticRegression on 228K labeled titles" and listed in the file tree,
but `grep -rn "degree_classifier\|joblib\|sklearn"` across both repos' `scripts/`
and `pipeline/` finds **zero** load sites. The 237 KB artifact from `ae57f50`
is never invoked. (I softened the PIPELINE.md wording; the artifact itself needs
a decision — wire it in or delete it.)

### Bug 4 — `step5b_build_pages.py` docstring says 101 non-STEM pages
`pipeline/step5b_build_pages.py:11` claims
`site/universities/nonstem/{key}.html (101 non-STEM pages)`; the build produces
**98** (PIPELINE.md is right, the docstring is wrong). Not edited — code file.

### Bug 5 — `step5_generate.py` docstring describes the OLD, reverted step order
`/Users/andy/usds_china_private/pipeline/step5_generate.py:4-5,22-29` says
"This step ONLY reads from site/data/ … It NEVER modifies per-university JSON
files" and then a TODO reading "since we run step4_enrich AFTER this … we run the
generator first and enrichment second to work around the overwrite issue."
Both statements are now false: `enrich` runs **before** `generate` (`__main__.py:78`),
and the generator does write the per-university JSONs (merge-not-overwrite,
`generate_name_lists_html.py:2575`). Not edited — code file in the private repo.

### Bug 6 — orphaned `osu` entries in `entity_map.json`
`THE OHIO STATE UNIVERSITY`, `OHIO STATE UNIVERSITY`, and
`THE OHIO STATE UNIVERSITY WEXNER MEDICAL CENTER` all map to `osu`, which is not
a key in `universities.json`. `step3_parse_federal._match_employer` will happily
aggregate Ohio State H-1B/LCA/PERM rows under a key nothing ever reads.
It is the only orphaned value in the whole map.

### Bug 7 — NIH RePORTER / NSF Awards data is fetched but never consumed
`data/state_funding/nih_reporter/nih_by_university.json` and
`data/state_funding/nsf_awards/nsf_by_university.json` (from `a23a60a`, covering
101 universities each) are written by `fetch_nih.py` / `scripts/fetch_nsf_awards.py`
and read by nothing. `step4_enrich` does not merge them and no per-university JSON
contains an NIH or NSF-awards field. PIPELINE.md claimed otherwise (fixed).

---

## 4. Observations that are neither bugs nor fixed drift

- `pipeline/AI_CLASSIFIER_DESIGN.md` is a *design-options* document. Its
  `pipeline/ai_classify_config.json` (line 116) and `degree_source` /
  `degree_confidence` record fields (lines 121–124) were never implemented —
  `step2b_ai_classify.py` writes a flat cache to `pipeline/ai_classifications.json`
  and takes `--dry-run/--max/--min-unlabeled`. I left the doc alone because it
  describes proposals, not shipped behaviour; if it is meant to read as current
  documentation it needs a rewrite, which is out of audit scope.
- `AI_CLASSIFIER_DESIGN.md:113-115` says step 2b's input/output is
  `data/processed/{key}.json`; the implementation reads the raw CSVs via `CONFIGS`
  and never writes back to `data/processed/`.
- `README.md:43-45` env-var table lists only `ANTHROPIC_API_KEY`. The codebase also
  honours `S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION`, `AWS_PROFILE` (step6_deploy) and
  `SITE_DOMAIN`, `ANALYTICS_ENDPOINT` (generate_name_lists_html). PIPELINE.md:336
  documents the AWS three. Not expanded — deploy lives in the private repo.
- `tests/test_degree_inference.py:1,4` docstring still says "8-step" and
  "294K records". Code file; not edited.
- `README.md:174` suggests `--ignore=tests/test_universities.py` for the core suite,
  but `tests/test_chat_assistant.py` also needs the private/infra tree. Not changed.
- `link.sh:33` removes a `LOCAL_DEVELOPMENT.md` symlink that the link path
  (lines 48–68) never creates, and neither repo contains that file.
- `pytest` is not installed in the environment, so I could not execute the suites
  the READMEs reference.
- `data/etdms_degrees/` is being written by a background job; the 11-file count
  above is a snapshot.

---

## 5. Note on in-flight work

While this audit was running, the background job added two artifacts that are not yet
reflected in any doc (and were still growing at the time of writing):

- `scripts/enrich_degree_metadata.py` (untracked)
- `data/degree_enrichment/` (untracked)
- more files under `data/etdms_degrees/` (byu.json etc.)

The README tree I updated documents `scripts/enrich_etdms_degrees.py` and
`data/etdms_degrees/`, which are the committed (`fa0e9ad`) versions. If
`enrich_degree_metadata.py` / `data/degree_enrichment/` supersede or extend them,
the README `scripts/` and `data/` trees and LABELING_METHODOLOGY step 2 will need a
follow-up pass once that work settles.

`pipeline/manifest.json` was being rewritten by the main session throughout
(`process.last_run` timestamps of 2026-08-18T11:11). It was not read for any
statistic in this audit and was not modified.
