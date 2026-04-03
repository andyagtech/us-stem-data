# Degree Labeling Methodology

## How PhD vs Master's is Determined

Each thesis/dissertation record is classified as PhD, MS, or unlabeled using
the `infer_degree_type()` function in `scripts/generate_name_lists.py`.

The function checks fields in this priority order:

### 1. Config Override (`degree_label`)
If the university config specifies `degree_label: 'phd'` or `'ms'`, all records
get that label. Used for universities with separate PhD and MS collections
(e.g., Missouri S&T has two configs — one for each).

### 2. Explicit Degree Fields
Checks `degree_type`, `degree`, `degree_name`, `degree_level` columns (from
OAI metadata or REST API enrichment). Matches patterns like:
- **PhD**: "phd", "doctoral", "doctorate", "dissertation", "ph.d", "edd", "sjd", "dnp", "dma"
- **MS**: "masters", "master", "ms", "msc", "ma", "mfa", "master's thesis", starts with "m.s", "m.a"
- **BS**: "bs", "ba", "bsc" (filtered out — not graduate work)

### 3. OAI Set Membership
Checks the OAI-PMH set names for degree indicators:
- **PhD**: Individual set parts containing "dissertation" without "thes" (e.g., `publication:dissertations`)
- **MS**: `publication:theses` ONLY if `publication:dissertations` also exists (distinguishing split)
- **Explicit**: `degree_level:doctoral` → PhD, `degree_level:master` → MS (Columbia uses this)
- **Skipped**: Combined sets like `publication:theses-dissertations` are ambiguous

### 4. Type Field
Checks the Dublin Core `type` field:
- **PhD**: Contains "doctoral" or "dissertation" (without "thesis")
- **MS**: Contains "masters" or "master's thesis"
- Generic "Thesis" or "text" does NOT automatically mean MS

### 5. Relation Field
Some universities (Penn State) store degree type in the `relation` field.

### 6. Description Field (last resort)
Regex matching on the description text:
- **Skip BS first**: `s.b.` or `b.s.` patterns → bachelor's (filtered out)
- **PhD**: `ph.d` (with optional space), `doctor of philosophy`, `doctoral`, `dissertation`, `sc.d`
- **MS**: `s.m.`, `m.s.`, `m.eng`, `m.c.p`, `m.arch`, `m.b.a`, `master of science/arts/engineering`

### 7. Late OAI Set Fallback
If description had nothing, check `publication:theses` (only if no `publication:dissertations` exists — meaning the repo uses "theses" for everything including PhDs).

## Per-University Labeling Status

### Fully Labeled (>95%)
Universities where OAI metadata or enrichment provides clear degree info:
- UC system (100%) — bepress sets clearly split dissertations vs theses
- Caltech, Stanford, Duke, Dartmouth (100%) — `degree_label: phd` config
- Virginia Tech, Iowa State, Kansas State (99%+) — explicit type fields
- RPI, U Delaware (95%+) — REST API enrichment added degree fields

### Well Labeled (50-95%)
- MIT (51%) — `S.M.`, `M.Eng`, `Ph.D.` in descriptions, 49% descriptions too short
- NC State (64%) — REST API enrichment covers 60%, legacy handles return 404
- Rice, Boston U, Cornell (40-60%) — partial description matching

### Poorly Labeled (<20%) — Root Causes

| University | Records | Labeled | Root Cause | Fix |
|---|---|---|---|---|
| **CMU** | 2,985 | 10% | Figshare only enriched 517/4149 thesis records | Re-run figshare API with pagination |
| **SMU** | 487 | 16% | Type='text', combined OAI set, descriptions truncated | Re-scrape with `oai_etdms` prefix |
| **Binghamton** | 94 | 3% | Same as SMU — combined set, no degree fields | Re-scrape with `oai_etdms` prefix |
| **U Houston** | 3,466 | 19% | DSpace opaque sets, descriptions truncated at 500 chars | Test REST API or extend desc limit |
| **BYU** | 2,393 | 6% | Bepress, type='text', no degree OAI sets | Re-scrape with `oai_etdms` |
| **UIUC** | 4,508 | 5% | Custom IDEALS platform, 48K generic 'text' records | No API available — description only |
| **U Arkansas** | 2,332 | 9% | Bepress, truncated descriptions | Re-scrape with `oai_etdms` |
| **Mississippi State** | 2,389 | 7% | Bepress, combined 'theses-dissertations' set | Re-scrape with `oai_etdms` |

### The `oai_etdms` Fix
Many bepress repositories support the ETD Metadata Standard (`oai_etdms`) which includes:
- `degree.name` — e.g., "Doctor of Philosophy (PhD)", "Master of Science (MS)"
- `degree.level` — "Thesis" or "Dissertation"
- `degree.discipline` — Department name

Switching from `oai_dc` to `oai_etdms` in the scraper config would fix SMU, Binghamton,
BYU, U Arkansas, Mississippi State, and potentially others.

## Pipeline Integration

In the future pipeline, degree labeling happens in **Step 2: PROCESS**:
```
step2_process.py:
  1. Load raw CSV from data/raw/{key}.csv
  2. For each record: infer_degree_type(row, config) → 'phd', 'ms', 'bs', or ''
  3. Apply name classification, taxonomy normalization
  4. Output to data/processed/{key}.json with degree labels
```

The labeling function is pure (no side effects) and can be unit tested per university.
