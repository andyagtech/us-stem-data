# PhD Demographics — US Graduate Program Research

Thesis & dissertation records from 101 US research universities, enriched with
government data from IPEDS, NSF, USCIS, DOL, and DHS/ICE.

**Live site**: *deployed privately*

## Start here if you are working on this

`CLAUDE.md` holds the working rules: the gate to run before deploying, the
fact that the site and the chat assistant deploy separately, the data rules
that have already been got wrong once, and how the writing is meant to read.
`REPO_MAP.md` (generated) maps the directories. `SOURCES.md` lists every
federal source. `HANDOFF.md` and `TASKS.md` are dated archives, not current
status.

## What This Is

A data pipeline and static website that tracks the immigration-via-education
pipeline: international students earning PhDs at American universities, then
transitioning to OPT work authorization, H-1B visas, and green cards. All data
comes from official US government sources and university institutional repositories.

## Quick Start

```bash
# 1. Clone
git clone <repo-url>
cd us-stem-data

# 2. Install Python dependencies
pip install -r requirements.txt
pip install -r requirements.txt # duckdb and anthropic are REQUIRED, not optional:
                                # a missing one ships stale data silently
pip install anthropic           # Optional: AI degree classification

# 3. Download raw data from S3 (5.5 GB)
aws s3 sync s3://phd-demographics-raw-data/data/ data/ --no-sign-request

# 4. Run the pipeline
python -m pipeline run

# Or run individual steps:
python -m pipeline run --step process          # Classify records
python -m pipeline run --step enrich           # Enrich with federal data
python -m pipeline run --step process --mode top20  # Just top 20 NRA universities
python -m pipeline status                      # Show pipeline state
```

## Entrypoints

Everything routes through two commands. `make help` lists the targets.

| command | what it does |
|---|---|
| `make check` | every offline check: consistency, site copy, query page, unit tests, chat |
| `make check-live` | the above, plus checks that hit the deployed site |
| `make verify-deploy` | compares what S3 serves against what is on disk |
| `python3 -m pipeline run` | the full pipeline; `--step harvest,process,...` for one stage |
| `python3 -m pipeline datasets` | what builds each artefact, and what is out of date |
| `python3 -m pipeline status` | where the last run got to |

Individual `make` targets run one slice of `check`: `consistency`, `site`,
`query`, `units`, `chat`, `docs`, `lint-deps`.

### Data acquisition and heavy rebuilds

These are deliberately not part of `make check` -- they cost money, time, or
both, and none of them ever deletes or overwrites existing data.

| script | what it does |
|---|---|
| `scripts/download_ipeds.py` | IPEDS completions from NCES |
| `scripts/download_lca_archive.py` | DOL LCA years not already held (`--list` first) |
| `scripts/download_sed_archive.py` | NSF SED data-table releases, one dir each |
| `scripts/build_sed_annual_series.py` | chains those releases into an annual series |
| `scripts/aws_lca_rebuild.sh` | rebuilds the LCA aggregate on EC2 -- the ~6 GB intermediate does not fit on a full laptop disk |
| `scripts/reharvest_dspace.py` | re-harvests DSpace repositories, resumable |
| `scripts/analyze_lca_legal.py` | law firms and attorneys behind university filings |
| `scripts/diff_year_series.py` | what a re-harvest does to a university's year histogram |

## Environment Variables

All credentials are factored out into environment variables:

| Variable | Required | Used By | Default |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | For AI classify | `step2b_ai_classify.py` | *(none — required if using AI classification)* |

## Repository Structure

```
us-stem-data/
├── pipeline/                    # Functional data pipeline (7 steps)
│   ├── __init__.py              # Step registry (decorator pattern)
│   ├── __main__.py              # CLI: python -m pipeline run [options]
│   ├── runner.py                # compose_pipeline(), railway-oriented execution
│   ├── state.py                 # Frozen dataclasses: PipelineState, StepOutcome
│   ├── step1_harvest.py         # OAI-PMH + REST API harvesting
│   ├── step2_process.py         # Record processing (degree labeling, dept extraction)
│   ├── step2b_ai_classify.py    # Optional: Claude Haiku degree classification
│   ├── step3_parse_federal.py   # H-1B, LCA, OPT, PERM parsing
│   ├── step4_enrich.py          # Merge all sources → per-university JSONs
│   ├── step5b_build_pages.py    # Parquet exports + 199 pre-rendered university pages
│   ├── universities.json        # 106 university configs (harvest, processing, employer names)
│   ├── entity_map.json          # 301 employer name → university key mappings
│   ├── system_h1b_map.json      # Multi-campus system H-1B fallback mappings
│   ├── manifest.json            # Per-university tracking (auto-updated by pipeline)
│   ├── ai_classifications.json  # AI degree classification cache
│   ├── PIPELINE.md              # Detailed pipeline architecture documentation
│   ├── LABELING_METHODOLOGY.md  # 9-step degree inference chain documentation
│   └── AI_CLASSIFIER_DESIGN.md  # AI classification design options
│
├── scripts/                     # Data collection and processing
│   ├── generate_name_lists.py       # Core: 105 university CONFIGS, infer_degree_type(),
│   │                                #   load_records(), 8 dept extractors, STEM taxonomy
│   ├── scrape_oai_etds.py           # OAI-PMH harvester (8 platforms: bepress, DSpace,
│   │                                #   Hyrax, Figshare, EPrints, Invenio, Blacklight)
│   ├── enrich_etdms_degrees.py      # oai_etdms degree.name/level scrape for bepress repos
│   ├── scrape_checkpoint.py         # Reusable checkpoint/dedup module (SQLite-backed)
│   ├── enrich_concurrent.py         # Concurrent REST API enrichment (10 universities,
│   │                                #   15 threads, DSpace UUID resolution)
│   ├── enrich_university_json.py    # IPEDS/GSS/HERD/faculty data merging
│   ├── download_ipeds.py            # IPEDS Complete Data Files downloader
│   ├── download_nsf_gss.py          # NSF GSS survey data downloader
│   ├── ipeds_config.py              # Shared IPEDS pipeline config
│   ├── ipeds_filter.py              # Extract STEM PhD programs from IPEDS
│   ├── build_dept_links.py          # Department URL mapping
│   ├── build_static_pages.py        # Server-renders per-university SEO pages + sitemap
│   ├── build_parquet_from_site.py   # Rebuilds Parquet exports from enriched site JSONs
│   ├── data_anomaly_check.py        # Data quality: dropoff detection, gap analysis
│   ├── qa_report.py                 # Per-university quality metrics
│   └── archive/                     # Historical scripts (kept for reproducibility)
│
├── data/                        # Curated data summaries (bulk data on S3)
│   ├── h1b/                         # H-1B, LCA, OPT, PERM parsed data
│   │   ├── h1b_by_university.json   # USCIS Data Hub aggregated by university
│   │   ├── lca_by_university.json   # DOL LCA with wage stats
│   │   ├── opt_by_university.json   # ICE/SEVP OPT by university
│   │   ├── perm_by_university.json  # DOL PERM green card data
│   │   └── national_opt_trends.json # National OPT/STEM OPT/CPT 2007-2024
│   ├── herd/                        # NSF HERD R&D funding
│   │   └── funding_by_university.json
│   ├── etdms_degrees/               # oai_etdms degree.name/level maps (bepress repos)
│   ├── dept_links.json              # Department URL mappings
│   ├── taxonomy.json                # 44 canonical department categories
│   ├── taxonomy_lookup.json         # 277 variant → canonical mappings
│   ├── DATA_DICTIONARY.md           # Complete data field documentation
│   └── university_repositories.md   # Repository access guide
│
├── tests/                       # Test suite (pytest)
│   ├── test_degree_inference.py     # 9-step degree classification chain
│   ├── test_department_extraction.py # Department extraction + STEM taxonomy
│   ├── test_entity_resolution.py    # H-1B employer name matching
│   ├── test_pipeline_state.py       # Immutable state types + composition
│   └── test_universities.py         # Per-university integration tests (needs raw data)
│
└── .gitignore
```

## Data Flow

```
universities.json (105 configs)
    │
    ▼
[1. HARVEST] ── OAI-PMH (8 platforms) + REST API (10 unis) ──▶ data/*.csv
    │
    ▼
[2. PROCESS] ── degree inference + dept extraction ──▶ data/processed/{stem,nonstem}/*.json
                                                       + data/processed/*_records.parquet
    │
    ▼
[3. PARSE FEDERAL] ── H-1B + LCA + OPT + PERM ──▶ data/h1b/*_by_university.json
    │
    ▼
[4. ENRICH] ── merge all sources + IPEDS + HERD + GSS ──▶ per-university JSONs
```

## Key Numbers

Every figure here is wrapped in a `<!--auto:...-->` marker and refilled from
the real artefacts by `scripts/sync_docs.py --write`. `make check` fails if any
of them has gone stale.

- **<!--auto:universities_count-->106<!--/auto-->** universities
- **<!--auto:total_records-->708,393<!--/auto-->** thesis/dissertation records
  (<!--auto:stem_records-->509,072<!--/auto--> STEM,
  <!--auto:nonstem_records-->199,321<!--/auto--> non-STEM)
- **<!--auto:entity_map_count-->301<!--/auto-->** employer name mappings for
  H-1B/LCA/PERM entity resolution
- **<!--auto:config_count-->110<!--/auto-->** per-university processing configurations
- **<!--auto:record_years-->2010-2026<!--/auto-->** thesis record coverage
  (the modal window; a few universities differ, see `scripts/generate_name_lists.py`)
- **<!--auto:lca_files-->39<!--/auto-->** DOL LCA disclosure files,
  <!--auto:lca_years-->FY2008-FY2026<!--/auto-->

## Data Sources

All data comes from official US government agencies and university repositories:

| Source | Agency | What | Coverage |
|---|---|---|---|
| **Thesis/Dissertation** | University repositories | OAI-PMH metadata | 2010-2026 |
| **IPEDS** | NCES (Dept of Education) | Completions, enrollment, finance | 1984-2025 |
| **NSF SED** | NSF NCSES | Survey of Earned Doctorates | 1979-2024 |
| **NSF GSS** | NSF NCSES | Graduate enrollment by field | 2024 |
| **NSF HERD** | NSF NCSES | R&D expenditures by university | 2010-2024 |
| **H-1B** | USCIS | Employer visa petitions | FY2010-2026 |
| **LCA** | DOL ETA | Labor Condition Applications | FY2008-FY2026 |
| **OPT/CPT** | DHS ICE/SEVP | Work authorization (SEVIS) | CY2017-2024 |
| **PERM** | DOL ETA | Green card labor certification | FY2024 |

Two coverage notes that the spans above do not convey:

* **IPEDS carries no citizenship before 1995.** The 1984-1994 completions files
  exist and are held here, but they publish only total men and total women --
  no non-resident breakdown, and NCES publishes no race-bearing completions
  file for those years. 1990 and 1999 are missing from NCES itself.
* **SED is five-yearly before 2009 and annual after.** No single SED release
  carries a long annual citizenship series; `scripts/download_sed_archive.py`
  and `scripts/build_sed_annual_series.py` chain seven releases to get one.

## Replicating This Project

### Prerequisites
- Python 3.10+
- AWS CLI (for data download and deployment)
- ~6 GB disk space for raw data

### Run Tests

```bash
python -m pytest tests/ -v
```

Tests covering degree inference, department extraction, entity resolution,
pipeline state immutability, and per-university integration.

```bash
# Core tests only (no data needed):
python -m pytest tests/ -v --ignore=tests/test_universities.py

# Full suite including per-university integration tests (needs data):
python -m pytest tests/ -v

# Top-20 NRA universities only:
python -m pytest tests/test_universities.py -v -k "top20"
```

### Validate the Methodology

The core processing logic is deterministic and doesn't require AWS credentials:

```bash
# Download raw data
aws s3 sync s3://phd-demographics-raw-data/data/ data/ --no-sign-request

# Run processing only (no deploy)
python -m pipeline run --step process

# Or just the top 20 highest-NRA universities:
python -m pipeline run --step process --mode top20

# Check labeling statistics
python -m pipeline status

# Query the output with DuckDB:
duckdb -c "SELECT university, COUNT(*), ROUND(100.0 * COUNT(NULLIF(degree,'')) / COUNT(*), 1) as labeled_pct FROM 'data/processed/stem_records.parquet' GROUP BY university ORDER BY COUNT(*) DESC"
```

Step 2 outputs Parquet files (`data/processed/stem_records.parquet` and
`nonstem_records.parquet`) that can be loaded in DuckDB, pandas, R, or any
tool that reads Parquet. Schema: `university`, `department`, `year`, `name`,
`classification`, `confidence`, `title`, `url`, `degree`.

Every thesis record links directly to its source in the university's institutional
repository for manual verification.

## Architecture

See [pipeline/PIPELINE.md](pipeline/PIPELINE.md) for the full technical architecture.
