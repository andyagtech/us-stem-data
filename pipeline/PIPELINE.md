# Functional Data Pipeline

## Overview

This pipeline transforms raw thesis/dissertation data from 101 US research
universities into enriched, analysis-ready datasets. It follows functional
programming principles: immutable state, pure transforms, composable steps,
and explicit error handling.

```
Raw Sources → Harvest → Process → Parse Federal → Enrich → Generate → Build Pages → Deploy
```

**Total data**: 298K+ STEM + 115K Non-STEM thesis/dissertation records,
enriched with H-1B, OPT, LCA, PERM, IPEDS enrollment, NSF HERD funding,
NSF GSS survey, SHEEO state appropriations, and USAspending federal
awards.

## CRITICAL: Step Ordering and Idempotency Rules

The pipeline has TWO critical invariants that must be preserved:

### Invariant 1: enrich must run before generate

```
✅ CORRECT:    process → parse_federal → enrich → generate → build_pages → deploy
❌ BROKEN:     process → parse_federal → generate → enrich → build_pages → deploy
```

**Why:** `enrich` writes federal data (h1b, opt, lca, perm, enrollment, funding,
state_funding, etc.) into `site/data/{stem,nonstem}/{key}.json`. `generate` then
refreshes the `records` field in those same files. If `generate` ran first, it
would write JSONs with only `{key, name, nra, records}` and then `enrich` would
add the federal fields on top.

### Invariant 2: generate must MERGE, not overwrite

`generate_name_lists_html.py` writes `site/data/{stem,nonstem}/{key}.json` files.
It MUST preserve any pre-existing enrichment fields (h1b, opt, lca, perm,
enrollment, funding, etc.) from a prior `enrich` run.

This is enforced by the merge logic in `generate_name_lists_html.py` (line ~2575):
```python
merged = {'key': uni_key, 'name': uni_name, 'nra': nra, 'records': compact}
if os.path.exists(json_path):
    existing = json.load(open(json_path))
    for k, v in existing.items():
        if k not in ('key', 'name', 'nra', 'records'):
            merged[k] = v  # preserve enrichment
```

This means you can safely run `generate` multiple times without losing data.

### Invariant 3: build_pages refuses to run on unenriched JSONs

`step5b_build_pages.py` checks that `site/data/stem/mit.json` has fields beyond
`{key, name, nra, records}`. If not, it errors out with a clear message telling
you to run `enrich` first. This prevents shipping broken static pages.

## Historical bug

**Symptom:** Running `generate` without `enrich` after destroyed all federal data
on the deployed site. The H-1B, OPT, enrollment, and funding panels would show
"No data available" for every university.

**Root cause:** `generate_name_lists_html.py` overwrote per-university JSONs with
only `{key, name, nra, records}`, silently destroying enrichment.

**Fix:** Three layers of defense:
1. Pipeline order: `enrich` runs before `generate` (defense in depth)
2. `generate` merges with existing enrichment (idempotent on subsequent runs)
3. `build_pages` refuses to build if JSONs look unenriched (canary)

## Architecture

### Principles

1. **Immutable state** — All pipeline state flows through frozen dataclasses
   (`@dataclass(frozen=True)`). No mutation; each step returns a new
   `PipelineState` with outcomes appended.

2. **Railway-oriented composition** — Steps are composed via `compose_pipeline()`.
   If any step fails (sets `halted=True`), subsequent steps are skipped
   automatically.

3. **Pure core, effectful shell** — Business logic is pure functions
   (no side effects). I/O happens only at step boundaries: reading files,
   writing JSON, HTTP requests, S3 uploads.

4. **Single source of truth** — University configs in `universities.json`,
   employer mappings in `entity_map.json`, tracking in `manifest.json`.

### State Types (`state.py`)

```python
@dataclass(frozen=True)
class PipelineState:
    config: PipelineConfig       # Universities, entity map, paths
    outcomes: tuple[StepOutcome, ...]  # Results from each step
    manifest: dict               # Per-university tracking data
    halted: bool = False         # Short-circuit on failure
    halt_reason: str = ""        # Why the pipeline halted
```

```python
@dataclass(frozen=True)
class StepOutcome:
    step_name: str
    university_key: str          # "" for global steps
    success: bool
    message: str
    data: dict                   # Metrics (record counts, etc.)
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    timestamp: str
```

### Runner (`runner.py`)

```python
pipeline = compose_pipeline(
    step1_harvest,
    step2_process,
    step3_parse_federal,
    step4_enrich,         # MUST be before step5_generate (writes federal data)
    step5_generate,       # Refreshes records, merges with existing enrichment
    step5b_build_pages,   # Builds Parquet + 199 static SEO pages
    step6_deploy,         # S3 + CloudFront
)
state = pipeline(initial_state)
```

The default `python -m pipeline run` order (in `pipeline/__main__.py`):
```python
order = ["harvest", "process", "parse_federal",
         "enrich",        # before generate (writes federal data)
         "generate",      # merges with existing enrichment
         "build_pages",   # static pages + Parquet
         "deploy"]
```

## Data Flow

```
                    ┌─────────────────────┐
                    │  universities.json   │  101 university configs
                    │  entity_map.json     │  292 employer name mappings
                    │  system_h1b_map.json │  Multi-campus system mappings
                    └──────────┬──────────┘
                               │
  ┌────────────────────────────▼────────────────────────────┐
  │  Step 1: HARVEST                                        │
  │  OAI-PMH scraping → data/western_us_dissertations/*.csv │
  │  Supports oai_dc and oai_etdms metadata prefixes        │
  └────────────────────────────┬────────────────────────────┘
                               │
  ┌────────────────────────────▼────────────────────────────┐
  │  Step 2: PROCESS                                        │
  │  Raw CSV → degree inference, dept taxonomy, name origin │
  │  Output: data/processed/{stem,nonstem}/{key}.json       │
  │  Optional: Step 2b AI classification (Claude Haiku)     │
  └────────────────────────────┬────────────────────────────┘
                               │
  ┌────────────────────────────▼────────────────────────────┐
  │  Step 3: PARSE_FEDERAL                                  │
  │  H-1B CSV, LCA XLSX, OPT JSON, PERM JSON               │
  │  Output: data/h1b/{h1b,lca,opt,perm}_by_university.json │
  │  DuckDB fast path for LCA (XLSX → CSV cache → SQL)      │
  └────────────────────────────┬────────────────────────────┘
                               │
  ┌────────────────────────────▼────────────────────────────┐
  │  Step 4: ENRICH                                         │
  │  Merges all federal data sources into per-uni JSONs     │
  │  Reads: data/processed/ (or site/data/ if exists)       │
  │  Writes: site/data/{stem,nonstem}/{key}.json            │
  │  Adds: h1b, opt, lca, perm, enrollment, funding,        │
  │        state_funding, usaspending, dept_links,          │
  │        completions_trend, tuition, financial_aid,       │
  │        faculty                                          │
  └────────────────────────────┬────────────────────────────┘
                               │
  ┌────────────────────────────▼────────────────────────────┐
  │  Step 5: GENERATE                                       │
  │  site/data/*.json → site/stem.html, site/non_stem.html  │
  │  Also writes site/data/{stem,nonstem}/{key}.json:       │
  │    - Refreshes the `records` field                      │
  │    - MERGE-NOT-OVERWRITE: preserves all enrichment      │
  │  Also writes site/data/universities_index.json          │
  │    (sidebar index, shared by SPA + sidebar.js)          │
  └────────────────────────────┬────────────────────────────┘
                               │
  ┌────────────────────────────▼────────────────────────────┐
  │  Step 5b: BUILD_PAGES                                   │
  │  1. Validates site/data is enriched (refuses if not)    │
  │  2. Rebuilds Parquet exports (stem_records.parquet)     │
  │  3. Pre-renders 199 static SEO pages:                   │
  │     site/universities/{key}.html                        │
  │  4. Generates site/sitemap.xml                          │
  └────────────────────────────┬────────────────────────────┘
                               │
  ┌────────────────────────────▼────────────────────────────┐
  │  Step 6: DEPLOY                                         │
  │  Pre-gzip HTML/JSON, upload to S3, invalidate CDN       │
  │  Uploads: site/*.html, site/data/*.json (top + nested), │
  │           site/data/exports/*.parquet,                  │
  │           site/universities/*.html (gzipped),           │
  │           site/sitemap.xml, static assets               │
  │  Cache: HTML 5min, JSON 1h, Parquet 1h, Assets 1wk      │
  └─────────────────────────────────────────────────────────┘
```

## Step Details

### Step 1: HARVEST (`step1_harvest.py`)

Fetches thesis/dissertation metadata from university OAI-PMH repositories.

- **Input**: University harvest configs (OAI base URL, sets, metadata prefix)
- **Output**: `data/western_us_dissertations/{key}_etds.csv`
- **Metadata prefixes**:
  - `oai_dc` — Dublin Core (standard, used by most repos)
  - `oai_etdms` — ETD Metadata Standard (degree.name, degree.level, degree.discipline)
- **Smart re-harvest**: Checks manifest; skips if data exists and is recent

### Step 2: PROCESS (`step2_process.py`)

Transforms raw CSVs into classified, structured records.

- **Input**: Raw CSVs from Step 1
- **Output**: `data/processed/{stem,nonstem}/{key}.json`
- **Pure functions imported from `generate_name_lists.py`**:
  - `infer_degree_type()` — 9-step inference chain (config → ETDMS lookup →
    degree fields → degree_level → OAI sets → type → relation → description →
    late OAI fallback)
  - Department extraction (8 university-specific extractors + generic fallback)
  - STEM/non-STEM taxonomy classification
  - Name origin classification (Chinese, Indian, Iranian, Korean, Vietnamese, Turkish, Arabic)
  - Deduplication by (name, year, dept, title)

### Step 2b: AI CLASSIFY (`step2b_ai_classify.py`) — Optional

Uses Claude Haiku to classify remaining unlabeled records by thesis title.

- **Input**: Unlabeled records from Step 2
- **Output**: `pipeline/ai_classifications.json` (cached results)
- **Batch size**: 50 titles per API call
- **Cost**: ~$4 for 50K records at Haiku pricing
- **Usage**: `python -m pipeline.step2b_ai_classify [--dry-run] [--max N]`
- **Requires**: `ANTHROPIC_API_KEY` environment variable

A trained sklearn classifier (`degree_classifier.pkl`, TF-IDF + LogisticRegression)
also lives in `pipeline/`, but no pipeline step currently loads it.

### Step 3: PARSE_FEDERAL (`step3_parse_federal.py`)

Parses all federal government data sources into per-university aggregates.

**H-1B Data Hub** (`data/h1b/h1b_datahub_*.csv`):
- USCIS Employer Data Hub, FY2010-2026
- Handles UTF-16 crosstab and standard CSV formats
- Entity resolution via `entity_map.json` (292 mappings including truncated names)
- Output: `data/h1b/h1b_by_university.json`

**LCA** (`data/h1b/lca/*.xlsx`):
- DOL Labor Condition Applications, FY2014-2025
- 32 Excel files, 3.3 GB total
- **DuckDB fast path**: Converts XLSX → CSV (one-time), then SQL queries
- **openpyxl fallback**: Row-by-row parsing (~25 min)
- Extracts: job titles, SOC codes, wage statistics, yearly certifications
- Output: `data/h1b/lca_by_university.json`

**OPT** (`data/h1b/opt_by_university.json`):
- ICE/SEVP SEVIS data, CY2017-2024
- Pre-parsed from PDF tables
- 59 universities with OPT/STEM OPT/CPT counts

**PERM** (`data/h1b/perm_by_university.json`):
- DOL PERM (permanent labor certification / green card)
- 71 universities with approval data

### Step 4: ENRICH (`step4_enrich.py`)

Merges all data sources into final per-university JSON files.

- **Input**: Step 2 processed records + Step 3 federal data + IPEDS/HERD/GSS
- **Output**: `site/data/{stem,nonstem}/{key}.json`
- **Critical design rule**: This is the only step that writes the federal
  enrichment fields into `site/data/`. Step 5 rewrites the `records` field of the
  same files and must preserve everything enrich added (see Invariant 2).
- **Merges**: H-1B, OPT, LCA, PERM, IPEDS enrollment/completions/tuition/aid/faculty,
  NSF HERD R&D funding, NSF GSS enrollment, SHEEO state appropriations,
  state-specific institutional funding, USAspending federal awards, department links,
  system H-1B fallback

**System H-1B mapping** (`system_h1b_map.json`):
Multi-campus universities (e.g., Missouri S&T) inherit parent system's H-1B data
with a disclaimer. The parent system's aggregate data is shown because USCIS
reports at the employer (system) level, not campus level.

### Step 5: GENERATE (`step5_generate.py` → `scripts/generate_name_lists_html.py`)

Generates the SPA HTML and refreshes per-university record data.

- **Input**: `site/data/{stem,nonstem}/{key}.json` (already enriched by Step 4)
- **Output**:
  - `site/stem.html` and `site/non_stem.html` (the SPA)
  - `site/data/{stem,nonstem}/{key}.json` (refreshed records, merged with enrichment)
  - `site/data/{stem,nonstem}/_search.json` (cross-university search index)
  - `site/data/universities_index.json` (top-level shared sidebar source)
- **Critical: MERGE-NOT-OVERWRITE**: When writing per-university JSONs,
  generate reads the existing file and preserves all fields beyond
  `{key, name, nra, records}`. This prevents destruction of enrichment data.
- **Features**: Client-side rendering, lazy-loaded per-university JSON,
  Chart.js visualizations, nationwide stats landing page, coach marks

### Step 5b: BUILD_PAGES (`step5b_build_pages.py`)

Builds the static SEO surface and the Parquet exports for the SQL query page.

- **Input**: `site/data/{stem,nonstem}/{key}.json` (enriched + refreshed)
- **Outputs**:
  - `site/data/exports/stem_records.parquet` (9-column ZSTD-compressed Parquet)
  - `site/data/exports/nonstem_records.parquet`
  - `site/universities/{key}.html` (101 STEM pre-rendered pages)
  - `site/universities/nonstem/{key}.html` (98 non-STEM pages)
  - `site/sitemap.xml` (214 URLs)
- **Pre-flight check**: Refuses to run if `site/data/stem/mit.json` has only
  the bare `{key, name, nra, records}` keys (would mean enrichment was wiped).
- **How static pages work**: Each is a clone of `stem.html` with one
  university's data preloaded into `UNI_CACHE`, plus an auto-load script
  that calls `showUni(key)` on page load. This gives full SPA functionality
  (toggles, panels, charts) on a per-university URL for SEO + CDN caching.

### Step 6: DEPLOY (`step6_deploy.py`)

Uploads the site to S3 with optimized caching.

- **Pre-gzip**: All JSON files compressed at level 9 before upload
- **Cache-Control headers**:
  - HTML: `max-age=300` (5 minutes)
  - JSON: `max-age=3600, Content-Encoding: gzip`
  - Assets: `max-age=604800` (1 week)
- **CloudFront**: Full invalidation (`/*`) after upload
- **AWS**: Configured via `S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION`, `AWS_PROFILE` env vars

## Configuration Files

### `universities.json` — 101 university configs

```json
{
  "mit": {
    "name": "MIT",
    "nra": 43.8,
    "unitid": 166683,
    "harvest": {},
    "processing": {
      "file": "data/western_us_dissertations/mit_etds.csv",
      "years": [2016, 2026],
      "dept_source": "subject_generic",
      "type_filter": null,
      "exclude_type": null,
      "degree_label": null,
      "degree_filter": null,
      "campus_filter": null
    },
    "employer_names": []
  }
}
```

The `harvest` and `employer_names` blocks are currently empty for every
university: harvesting is driven by the `REPOS` registry in
`scripts/scrape_oai_etds.py`, and employer resolution by `entity_map.json`.

### `entity_map.json` — 292 employer name mappings

Maps USCIS employer names (often truncated/abbreviated) to university keys:

```json
{
  "MASSACHUSETTS INSTITUTE OF TECHNOLOGY": "mit",
  "THE LELAND STANFORD JR UNIVERSITY": "stanford",
  "THE CURATORS OF THE UNIV OF MISSOU": "umissouri",
  "UNIVERSITY OF CALIFORNIA DAVIS": "ucdavis"
}
```

### `manifest.json` — Per-university tracking

Records processing state, record counts, and data source availability:

```json
{
  "mit": {
    "records": {"total": 12906, "phd": 6615, "ms": 0, "unlabeled": 6291, "label_pct": 51.3},
    "data_sources": {
      "h1b": true, "h1b_years": 17, "opt": true, "opt_years": 8,
      "lca": true, "lca_total": 3521, "perm": true,
      "enrollment": true, "funding": true, "dept_links": true
    },
    "h1b_system_note": "",
    "process": {
      "last_run": "2026-08-18T11:11:32",
      "records": 12906,
      "phd": 6615,
      "ms": 0,
      "unlabeled": 6291,
      "labeling_pct": 51.3,
      "filter": "stem"
    }
  }
}
```

## Degree Labeling

The 9-step `infer_degree_type()` inference chain (in priority order):

1. **Config override** — `degree_label: 'phd'` or `'ms'` in university config
2. **ETDMS lookup** — `data/etdms_degrees/{key}.json`, keyed by OAI identifier;
   checks `thesis.degree.name` before `thesis.degree.level`
3. **Explicit degree fields** — `degree_type`, `degree`, `degree_name`, `degree_level` columns
4. **ETD degree_level** — `degree_level: "Dissertation"` → PhD, `"Thesis"` → MS
5. **OAI set membership** — `publication:dissertations` → PhD, `degree_level:doctoral` → PhD
6. **Type field** — `type: "doctoral"` → PhD, `type: "masters"` → MS
7. **Relation field** — Penn State stores `PHD`/`MASTERS` here
8. **Description regex** — `ph.d`, `s.m.`, `m.s.`, `m.eng`, etc.
9. **Late OAI set fallback** — `publication:theses` → MS (only if no dissertations set)

**Current labeling rate**: ~82% across all universities. The oai_etdms metadata
(steps 2-4 in the chain) significantly improved labeling for bepress
repositories: BYU (6% → 97%), Mississippi State (7% → 100%), U Arkansas (9% → 100%).

## CLI Usage

```bash
# Run full pipeline
python -m pipeline run

# Run specific step(s)
python -m pipeline run --step process
python -m pipeline run --step enrich,generate,deploy

# Single university
python -m pipeline run --university mit

# Dry run (show what would be done)
python -m pipeline run --dry-run

# Show status
python -m pipeline status

# AI classification (supplementary)
python -m pipeline.step2b_ai_classify --dry-run
python -m pipeline.step2b_ai_classify --max 1000
```

## File Structure

```
pipeline/
├── __init__.py              # Step registry (decorator pattern)
├── __main__.py              # CLI: python -m pipeline run [options]
├── runner.py                # compose_pipeline(), run_pipeline()
├── state.py                 # PipelineConfig, PipelineState, StepOutcome
├── universities.json        # 101 university configs
├── entity_map.json          # 292 employer name → university key
├── system_h1b_map.json      # Multi-campus system H-1B mappings
├── manifest.json            # Per-university tracking (auto-updated)
├── degree_classifier.pkl    # Trained sklearn model (TF-IDF + LogReg)
├── ai_classifications.json  # Claude Haiku classification cache
├── step1_harvest.py         # OAI-PMH + REST API harvesting
├── step2_process.py         # Record processing: degrees, taxonomy, classification
├── step2b_ai_classify.py    # Claude Haiku AI classification (optional)
├── step3_parse_federal.py   # H-1B, LCA, OPT, PERM parsing
├── step4_enrich.py          # Merge all sources → final per-university JSONs
├── step5_generate.py        # HTML generation (refreshes records, merges enrichment)
├── step5b_build_pages.py    # Parquet exports + 199 pre-rendered university pages
├── step6_deploy.py          # S3 sync + CloudFront invalidation
├── PIPELINE.md              # This document
├── LABELING_METHODOLOGY.md  # Detailed degree inference documentation
└── AI_CLASSIFIER_DESIGN.md  # AI classification approaches
```

## Key Design Decisions

1. **Federal enrichment fields in `site/data/` are written only by step4_enrich**
   — `generate` may refresh `records` but must merge everything else through,
   which eliminates the original bug where HTML generation overwrote enriched JSONs.

2. **Entity resolution in one place** — `entity_map.json` with 292 mappings
   handles USCIS name truncation (35-char limit), abbreviations
   ("UNIVERSITY" → "UNIV"), and multi-campus systems.

3. **oai_etdms support** — ETD Metadata Standard provides degree.name,
   degree.level, and degree.discipline fields that dramatically improve
   labeling for bepress repositories.

4. **DuckDB acceleration** — LCA XLSX files are converted to CSV once,
   then queried via DuckDB SQL for fast aggregation.

5. **Steps are idempotent** — Re-running any step produces the same result.
   Manifest tracking prevents unnecessary re-harvesting.

6. **Functional core** — Pure transforms with effectful boundaries
   (harvest, deploy). State flows through frozen dataclasses.
