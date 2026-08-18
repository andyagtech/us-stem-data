# Degree Labeling Methodology

## How PhD vs Master's is Determined

Each thesis/dissertation record is classified as PhD, MS, or unlabeled using
the `infer_degree_type()` function in `scripts/generate_name_lists.py`.

The function checks fields in this priority order:

### 1. Config Override (`degree_label`)
If the university config specifies `degree_label: 'phd'` or `'ms'`, all records
get that label. Used for universities with separate PhD and MS collections
(e.g., Missouri S&T has two configs — one for each).

### 2. ETDMS Enrichment Lookup
Bepress repositories drop `thesis.degree.name` / `thesis.degree.level` from their
default `oai_dc` feed. `scripts/enrich_etdms_degrees.py` re-fetches those records with
`metadataPrefix=oai_etdms` and writes `data/etdms_degrees/{key}.json`, keyed by OAI
identifier. `_etdms_lookup()` consults that mapping before any other heuristic.
Degree **name** is checked before degree **level**, because some repositories (NIU)
label every record `"Dissertation/Thesis"` at the level field.

### 3. Explicit Degree Fields
Checks `degree_type`, `degree`, `degree_name`, `degree_level` columns (from
OAI metadata or REST API enrichment). Matches patterns like:
- **PhD**: "phd", "doctoral", "doctorate", "dissertation", "ph.d", "edd", "sjd", "dnp", "dma"
- **MS**: "masters", "master", "ms", "msc", "ma", "mfa", "master's thesis", starts with "m.s", "m.a"
- **BS**: "bs", "ba", "bsc" (filtered out — not graduate work)

### 4. ETD degree_level Field
The `degree_level` column is then checked on its own (oai_etdms semantics):
`"Dissertation"` → PhD, `"Thesis"` (without "dissertation") → MS.

### 5. OAI Set Membership
Checks the OAI-PMH set names for degree indicators:
- **PhD**: Individual set parts containing "dissertation" without "thes" (e.g., `publication:dissertations`)
- **MS**: `publication:theses` ONLY if `publication:dissertations` also exists (distinguishing split)
- **Explicit**: `degree_level:doctoral` → PhD, `degree_level:master` → MS (Columbia uses this)
- **Skipped**: Combined sets like `publication:theses-dissertations` are ambiguous

### 6. Type Field
Checks the Dublin Core `type` field:
- **PhD**: Contains "doctoral" or "dissertation" (without "thesis")
- **MS**: Contains "masters" or "master's thesis"
- Generic "Thesis" or "text" does NOT automatically mean MS

### 7. Relation Field
Some universities (Penn State) store degree type in the `relation` field.

### 8. Description Field (last resort)
Regex matching on the description text:
- **Skip BS first**: `s.b.` or `b.s.` patterns → bachelor's (filtered out)
- **PhD**: `ph.d` (with optional space), `doctor of philosophy`, `doctoral`, `dissertation`, `sc.d`
- **MS**: `s.m.`, `m.s.`, `m.eng`, `m.c.p`, `m.arch`, `m.b.a`, `master of science/arts/engineering`

### 9. Late OAI Set Fallback
If description had nothing, check `publication:theses` (only if no `publication:dissertations` exists — meaning the repo uses "theses" for everything including PhDs).

## Per-University Labeling Status

### Where labelling stands

Corpus-wide the labelling rate is 88.8% on the STEM track across 105 universities.

### Resolved

Every repository previously listed here as poorly labelled had the same
underlying cause: it *does* publish the degree, just not through `oai_dc`,
the format the harvester requests. None of them needed a heuristic.

| University | Records | Now | Root cause | Fix |
|---|---|---|---|---|
| **UIUC** | 5,119 | 100% | OAI returned 403 to non-browser user agents, so it looked API-less | `native` prefix + user-agent fallback |
| **U Houston** | 3,905 | 100% | `oai_dc` crosswalk drops `thesis.degree.*` | `dim` prefix |
| **BYU** | 2,598 | 100% | bepress, type=text, no degree OAI sets | `oai_etdms` |
| **Mississippi State** | 3,419 | 100% | bepress, combined theses-dissertations set | `oai_etdms` |
| **U Arkansas** | 2,523 | 100% | bepress, truncated descriptions | `oai_etdms` |
| **CMU** | 3,312 | 96% | Figshare OAI carries no degree field in any of its six formats | Figshare REST `custom_fields` |
| **Binghamton** | 119 | 88% | combined set, no degree fields | `oai_etdms` |
| **SMU** | 510 | 100% | type=text, combined set | `type` field via `thesis_vocab_field` |

### Still incomplete

These are description-matching cases with no structured degree field to
recover, or repositories whose records grew after their enrichment ran and
need it re-run.

| University | Records | Labelled |
|---|---|---|
| montana_state | 1,248 | 25% |
| bu | 11,444 | 32% |
| gmu | 7,110 | 38% |
| cornell | 6,410 | 42% |
| mit | 14,203 | 48% |
| utk | 4,627 | 50% |
| ttu | 5,274 | 55% |
| rice | 4,911 | 56% |
| umass | 7,708 | 74% |
| ucf | 2,814 | 77% |

Note that re-harvesting a repository can *lower* its labelling rate until the
degree enrichment is re-run over the newly added records — the enrichment maps
identifiers, so records harvested after it ran are simply absent from the map.

### The `oai_etdms` Fix (applied)
Many bepress repositories support the ETD Metadata Standard (`oai_etdms`) which includes:
- `degree.name` — e.g., "Doctor of Philosophy (PhD)", "Master of Science (MS)"
- `degree.level` — "Thesis" or "Dissertation"
- `degree.discipline` — Department name

This is now used two ways:
1. `scripts/scrape_oai_etds.py` sets `"metadata_prefix": "oai_etdms"` in the repo
   config, so the harvest itself carries the degree fields (SMU, Binghamton, BYU,
   U Arkansas, Mississippi State and others).
2. `scripts/enrich_etdms_degrees.py` re-fetches an `oai_etdms` pass for repositories
   already harvested under `oai_dc` and writes `data/etdms_degrees/{key}.json`, which
   step 2 of the chain consults.

### The non-bepress equivalent (applied)
Non-bepress repositories publish the same information, but each under its own
metadata format, so `oai_etdms` does not apply. `scripts/enrich_degree_metadata.py`
harvests the right format per repository and writes `data/degree_enrichment/{key}.json`
in exactly the same `{identifier: {level, name}}` shape, which `_etdms_lookup()`
merges with `data/etdms_degrees/`:

| Repo | Format | Field |
|---|---|---|
| UIUC | `native` (needs a browser User-Agent — IDEALS 403s otherwise) | `thesis.degree.name` / `.level` |
| U Houston, U Oregon | `dim` | `thesis.degree.name` / `.level` |
| Michigan State | `mods` | `mods:note type="thesis"` → `Thesis (Ph. D.)--...` |
| U North Texas | `untl` | `untl:degree qualifier="name"/"level"` |
| CMU | Figshare REST `GET /v2/articles/{id}` | `custom_fields["Degree Type"]` |

WSU is an Ex Libris Esploro repository with no usable OAI degree route; its asset
type is carried in the item URL (`/outputs/doctoral/` vs `/outputs/graduate/`),
which `infer_degree_type()` reads directly.

## Pipeline Integration

Degree labeling happens in **Step 2: PROCESS**:
```
pipeline/step2_process.py:
  1. Load raw CSV from data/western_us_dissertations/{key}_etds.csv
  2. For each record: infer_degree_type(row, config) → 'phd', 'ms', 'bs', or ''
  3. Apply name classification, taxonomy normalization
  4. Output to data/processed/{stem,nonstem}/{key}.json with degree labels
```

The labeling function is pure (no side effects) and can be unit tested per university.
