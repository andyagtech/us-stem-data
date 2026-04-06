# Functional Data Pipeline

## Overview

This pipeline transforms raw thesis/dissertation data from 101 US research
universities into enriched, analysis-ready datasets. It follows functional
programming principles: immutable state, pure transforms, composable steps,
and explicit error handling.

```
Raw Sources → Process → Parse Federal → Enrich → Parquet / JSON
```

**Total data**: 294K+ thesis/dissertation records, enriched with H-1B, OPT,
LCA, PERM, IPEDS enrollment, NSF HERD funding, and NSF GSS survey data.

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
```

```python
@dataclass(frozen=True)
class StepOutcome:
    step_name: str
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
    step4_enrich,
    step5_generate,
    step6_deploy,
)
state = pipeline(initial_state)
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
  │  Merge federal data + IPEDS + HERD + GSS + dept_links   │
  │  Output: site/data/{stem,nonstem}/{key}.json             │
  │  *** ONLY step that writes to site/data/ ***             │
  └────────────────────────────┬────────────────────────────┘
                               │
  ┌────────────────────────────▼────────────────────────────┐
  │  Step 5: GENERATE                                       │
  │  site/data/*.json → site/stem.html, site/non_stem.html  │
  │  Read-only access to site/data/ (never writes to it)    │
  └────────────────────────────┬────────────────────────────┘
                               │
  ┌────────────────────────────▼────────────────────────────┐
  │  Step 6: DEPLOY                                         │
  │  Pre-gzip JSON, upload to S3, invalidate CloudFront     │
  │  HTML: 5-min cache, JSON: 1-hour, Assets: 1-week        │
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
  - `infer_degree_type()` — 8-step inference chain (config → degree fields →
    degree_level → OAI sets → type → relation → description → late OAI fallback)
  - Department extraction (13 university-specific extractors + generic fallback)
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

Additionally, a trained sklearn classifier (`degree_classifier.pkl`) provides
offline classification using TF-IDF + LogisticRegression on 228K labeled titles.

### Step 3: PARSE_FEDERAL (`step3_parse_federal.py`)

Parses all federal government data sources into per-university aggregates.

**H-1B Data Hub** (`data/h1b/h1b_datahub_*.csv`):
- USCIS Employer Data Hub, FY2010-2026
- Handles UTF-16 crosstab and standard CSV formats
- Entity resolution via `entity_map.json` (292 mappings including truncated names)
- Output: `data/h1b/h1b_by_university.json`

**LCA** (`data/h1b/lca/*.xlsx`):
- DOL Labor Condition Applications, FY2015-2024
- 32 Excel files, 3.6 GB total
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
- 72 universities with approval data

### Step 4: ENRICH (`step4_enrich.py`)

Merges all data sources into final per-university JSON files.

- **Input**: Step 2 processed records + Step 3 federal data + IPEDS/HERD/GSS
- **Output**: `site/data/{stem,nonstem}/{key}.json`
- **Critical design rule**: This is the ONLY step that writes to `site/data/`
- **Merges**: H-1B, OPT, LCA, PERM, IPEDS enrollment/completions/tuition,
  NSF HERD R&D funding, NSF GSS enrollment, department links, system H-1B fallback

**System H-1B mapping** (`system_h1b_map.json`):
Multi-campus universities (e.g., Missouri S&T) inherit parent system's H-1B data
with a disclaimer. The parent system's aggregate data is shown because USCIS
reports at the employer (system) level, not campus level.

### Step 5: GENERATE (`step5_generate.py`)

Generates HTML pages from enriched JSON files.

- **Input**: `site/data/{stem,nonstem}/*.json`
- **Output**: `site/stem.html`, `site/non_stem.html`
- **Key rule**: NEVER writes to `site/data/` — HTML generation only
- **Features**: Client-side rendering, lazy-loaded per-university JSON,
  Chart.js visualizations, nationwide stats landing page, coach marks

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
    "harvest": {
      "oai_base": "https://dspace.mit.edu/oai/request",
      "platform": "dspace",
      "sets": ["com_1721.1_7582"],
      "metadata_prefix": "oai_dc"
    },
    "processing": {
      "file": "data/western_us_dissertations/mit_etds.csv",
      "years": [2016, 2024],
      "dept_source": "subject_generic"
    },
    "employer_names": ["MASSACHUSETTS INSTITUTE OF TECHNOLOGY"]
  }
}
```

### `entity_map.json` — 292 employer name mappings

Maps USCIS employer names (often truncated/abbreviated) to university keys:

```json
{
  "MASSACHUSETTS INSTITUTE OF TECHNOLOGY": "mit",
  "THE LELAND STANFORD JR UNIVERSITY": "stanford",
  "THE CURATORS OF THE UNIV OF MISSOU": "umissouri",
  "UNIVERSITY OF CALIFORNIA DAVIS": "uc_davis"
}
```

### `manifest.json` — Per-university tracking

Records processing state, record counts, and data source availability:

```json
{
  "mit": {
    "process": {
      "records": 12906,
      "phd": 6615,
      "ms": 0,
      "unlabeled": 6291,
      "labeling_pct": 51.3
    },
    "h1b": true,
    "opt": true,
    "lca": true
  }
}
```

## Degree Labeling

The 8-step `infer_degree_type()` inference chain (in priority order):

1. **Config override** — `degree_label: 'phd'` or `'ms'` in university config
2. **Explicit degree fields** — `degree_type`, `degree`, `degree_name` columns
3. **ETD degree_level** — `degree_level: "Dissertation"` → PhD, `"Thesis"` → MS
4. **OAI set membership** — `publication:dissertations` → PhD, `degree_level:doctoral` → PhD
5. **Type field** — `type: "doctoral"` → PhD, `type: "masters"` → MS
6. **Relation field** — Penn State stores `PHD`/`MASTERS` here
7. **Description regex** — `ph.d`, `s.m.`, `m.s.`, `m.eng`, etc.
8. **Late OAI set fallback** — `publication:theses` → MS (only if no dissertations set)

**Current labeling rate**: ~82% across all universities. The oai_etdms metadata
prefix (steps 2-3 in the chain) significantly improved labeling for bepress
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
├── step5_generate.py        # HTML generation (read-only access to site/data/)
├── step6_deploy.py          # S3 sync + CloudFront invalidation
├── PIPELINE.md              # This document
├── LABELING_METHODOLOGY.md  # Detailed degree inference documentation
└── AI_CLASSIFIER_DESIGN.md  # AI classification approaches
```

## Key Design Decisions

1. **`site/data/` is written ONLY by step4_enrich** — eliminates the
   original bug where HTML generation overwrote enriched JSONs.

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
