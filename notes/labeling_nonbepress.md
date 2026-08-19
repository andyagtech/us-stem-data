# Non-bepress degree labeling — findings

Scope: the non-bepress repositories with poor PhD/Master's labeling. Bepress repos
(`data/etdms_degrees/`, `scripts/enrich_etdms_degrees.py`) were left untouched — a
separate background job owns them. GMU was added at the main session's request.

## Summary of what was wrong

The root cause is the same one the bepress fix addresses, wearing a different
costume: **every one of these repositories does publish the degree, but not
through the `oai_dc` metadata format the harvester asks for.** The claims in
`pipeline/LABELING_METHODOLOGY.md` that CMU needed "pagination", that U Houston's
problem was a 500-character description limit, and that UIUC has "no API
available" are all incorrect.

| Repo | Platform | Where the degree actually lives |
|---|---|---|
| uiuc | DSpace (IDEALS) | OAI `metadataPrefix=native` → `thesis.degree.name` / `.level` |
| uhouston | DSpace 7 (TDL) | OAI `metadataPrefix=dim` → `thesis.degree.name` |
| uoregon | DSpace 7 | OAI `metadataPrefix=dim` → `thesis.degree.name` / `.level` |
| msu | MODS repository | OAI `metadataPrefix=mods` → `mods:note type="thesis"` |
| unt | UNT Aubrey | OAI `metadataPrefix=untl` → `untl:degree qualifier="name"/"level"` |
| gmu | TIND | OAI `metadataPrefix=marcxml` → MARC 502 `$b` |
| cmu | Figshare | REST `GET /v2/articles/{id}` → `custom_fields["Degree Type"]` |
| wsu | Ex Libris Esploro | asset type is already in the item URL path |

## Implementation

New script `scripts/enrich_degree_metadata.py`, modelled on
`scripts/enrich_etdms_degrees.py`:

- Per-repo config dict (`REPOS`) with OAI base, metadata prefix, set and parser.
- Writes `data/degree_enrichment/{key}.json` as
  `{identifier: {"level": "Dissertation"|"Thesis"|"Bachelor"|"", "name": raw}}` —
  deliberately the same shape as `data/etdms_degrees/`, so no new consumer logic
  is needed.
- `degree_level()` normalises raw degree names ("Ph. D.", "D.N.P.", "M.U.P.",
  "Doctor of Musical Arts", "Master's") to the ETDMS level vocabulary.
  Unrecognised names are left as `""` rather than guessed.
- User agents and the 403 fallback are imported from `scrape_oai_etds`
  (`PROJECT_UA` first, one retry with `BROWSER_UA` on a 403), so there is one
  behaviour across the codebase.
- Checkpointed to `data/degree_enrichment/{key}_checkpoint.json` (resumption token
  + set index for OAI; the set of already-checked article ids for Figshare) and
  the mapping file is flushed every page, so any run resumes where it stopped.
- 1.0 s request delay for OAI, 0.6 s for the Figshare per-article REST loop.
- Optional `identifier_re` / `identifier_template` rebuild the harvest key from
  the record body for repositories whose OAI identifiers do not match the
  harvested CSV (only GMU needs this).

`scripts/generate_name_lists.py`, two surgical changes:

1. `_etdms_lookup()` now merges `data/etdms_degrees/{key}.json` **and**
   `data/degree_enrichment/{key}.json` into its cache, and returns `'bs'` for
   `level == "Bachelor"` so undergraduate honours theses get filtered out
   (UIUC and MSU both mix them into the ETD collection).
2. `infer_degree_type()` gained an Esploro item-URL check (`/outputs/doctoral/`
   → phd, `/outputs/graduate/` → ms) for WSU.

`pipeline/LABELING_METHODOLOGY.md` — three stale root-cause rows corrected and a
section added describing the non-bepress enrichment.

`scripts/scrape_oai_etds.py` was **not** modified.

## Per-university results

Measured with the real `infer_degree_type()` chain over each university's
configured CSV, `years` window (2016-2026) and `type_filter`, before the STEM
department filter. (The main session quotes STEM-filtered percentages, which run a
few points different on the same data.)

| Repo | Records | Labeled before | Labeled after | PhD | MS | BS filtered |
|---|---|---|---|---|---|---|
| uiuc | 6,493 | 5.3% | 99.9% | 3,944 | 2,391 | 154 |
| uhouston | 5,907 | 18.6% | 100.0% | 4,167 | 1,739 | 0 |
| unt | 4,240 | 14.9% | 100.0% | 2,847 | 1,393 | 0 |
| wsu | 2,705 | 14.0% | 100.0% | 1,529 | 1,170 | 0 |
| msu | 6,771 | 30.5% | 100.0% | 5,124 | 1,647 | 0 |
| gmu | 3,200 | 50.1% | 99.8% | 2,039 | 1,155 | 0 |
| uoregon | 3,176 | 20.9% | 84.7% | 2,009 | 680 | 0 |
| cmu | 4,122 | 19.5% | 90.1% | 3,259 | 453 | 0 |

Three of these are correctness fixes as much as coverage fixes — the old chain was
not merely missing labels, it was systematically calling master's work PhD:

| Repo | PhD/MS before | PhD/MS after |
|---|---|---|
| msu | 2,067 / 1 | 5,124 / 1,647 |
| gmu | 1,604 / 0 | 2,039 / 1,155 |
| unt | 632 / 0 | 2,847 / 1,393 |

### uiuc — University of Illinois Urbana-Champaign
Root cause confirmed: **two stacked problems, neither of them the documented one.**
The IDEALS OAI endpoint returns HTTP 403 to non-browser User-Agents, which is why
it looked API-less. It answers normally otherwise and advertises
`metadataPrefix=native`, an IDEALS-specific format carrying `thesis.degree.name`
and `thesis.degree.level` on effectively every ETD record. Harvested 57,115
records: 48,131 Dissertation, 8,825 Thesis, 157 Bachelor, 2 unlabeled
("M.Sc.", since fixed in the normaliser). IDEALS mixes B.S. honours theses into the
collection; those are now labeled `bs` and filtered rather than counted.

### uhouston — University of Houston
Root cause confirmed: not the 500-char description truncation and not opaque sets.
The `oai_dc` crosswalk simply drops `thesis.degree.*`. The `etdms` prefix the
repository advertises is misconfigured (it emits an empty `<degree/>` element), but
`dim` exposes the full DSpace field list including `thesis.degree.name`
("Doctor of Philosophy", "Master of Science", "Doctor of Education") for 99 of 100
sampled records. 7,075 records mapped. The endpoint was healthy throughout — no
timeouts over several hundred requests, contrary to the health sweep.

### uoregon — University of Oregon
`dim` carries `thesis.degree.name` (Ph.D., M.A., M.S., D.Ed.) and
`thesis.degree.level` ("doctoral"/"masters") for 3,528 of 5,140 records.

### msu — Michigan State University
`mods` carries a MARC-style thesis note,
`Thesis (Ph. D.)--Michigan State University. Chemistry, 2019`; the parenthetical is
the degree abbreviation. 52,464 records mapped, only 6 with no usable level.

### unt — University of North Texas
The `untl` native format carries `untl:degree` with `name`, `level`, `discipline`
and `department`. 22,140 of 22,187 records, at 1,000 records per OAI page, so the
whole harvest took under two minutes.

### gmu — George Mason University (added at main session's request)
TIND `marcxml` carries MARC 502 with the degree level in `$b` ("Master's",
"Doctoral") — not the discipline. Two cautions:
- MARC 380 is **not** a safe ETD filter on its own: recid 70102 is a slide deck
  ("Mason Publishing - Presentation to Academic Council, 2014") filed as
  `380 = Thesis`. The parser therefore requires a 502 to be present and uses 380
  only as a level fallback.
- The TIND identifiers (`oai:digitalcollections.gmu.edu:70102`) bear no relation to
  the harvested MARS identifiers (`oai:MARS:1920/13181`). The MARS handle survives
  in MARC 024/035 on 8,121 of 8,123 records, so the mapping key is rebuilt as
  `oai:MARS:{handle}`.
5,518 records mapped from `gmu_lib:ir_collections` (5,519 of 8,123 records carry a
502). `gmu_lib:da_collections` returns HTTP 503; not pursued.

### cmu — Carnegie Mellon University
Root cause confirmed, and it is **not** missing pagination. Figshare's OAI feed
carries no degree field in any of its advertised formats — `oai_dc`, `qdc`, `rdf`,
`cerif`, `mets` and `uketd_dc` were all checked; `uketd_dc` has
`uketdterms:department` and `:institution` but no qualification level. The value
exists only as a portal custom field on the article detail endpoint:
`custom_fields` → `{"name": "Degree Type", "value": ["Dissertation"]}` (the only
two options are "Dissertation" and "Master's Thesis"). That means one HTTP request
per article for 4,149 thesis records. All 4,149 were fetched; 3,736 carry a Degree
Type value. Figshare rate-limits with a transient 403, so the loop skips a failing
id (leaving it unchecked for the next run) rather than aborting.

### wsu — Washington State University
(Numbers above are against the WSU CSV as it stood at 06:18; another agent
re-scraped it mid-task, growing it from 2,549 to 6,029 rows. The rule labels 100%
of both versions.)

Not in `scrape_oai_etds.REPOS` at all; it is an Ex Libris Esploro repository
scraped by `scripts/archive/scrape_or_wa_dissertations.py`. Its Alma OAI endpoint
(`/view/oai/01ALLIANCE_WSU/request`) advertises `etdms` and an `ETD_Grad` set, but
the publishing profile pairing them does not exist (`noRecordsMatch`), and the
`ETD_Grad` set under `oai_dc` contains exactly one record — the OAI route is a dead
end. The repository's own asset type is instead encoded in every item URL that the
existing scraper already stored: `etd.doctoral` → `/outputs/doctoral/`,
`etd.graduate` → `/outputs/graduate/`. Validated by fetching 50 randomly sampled
item pages (25 per class) and reading the degree printed on the page: 25/25
doctoral pages said "Doctor of ...", 25/25 graduate pages said "Master of ...",
0 mismatches. This is a repository-assigned classification, not a text heuristic.

## Not fixed

- **uoregon, ~487 in-window records (15%).** Retro-digitised legacy theses (e.g.
  handle 1794/29332, issued 1935) whose DSpace items carry no `thesis.degree.*`
  fields at all, no degree text in the description (it reads "166 pages"), and only
  `dc.type = "Thesis / Dissertation"`. There is no degree signal to obtain, so
  nothing was invented. Side observation, out of scope: these land in the 2016-2026
  window only because the pipeline reads the accession date rather than the issue
  date.
- **Small unmatched tails.** MSU 6 records ("Research Project", "Dept. of
  Forestry"), GMU 2 ("D.A."), UIUC 2 ("M.Sc." — the normaliser now handles this,
  but the harvested mapping predates the fix). Left unlabeled rather than guessed.
- **cmu, 410 in-window records (10%).** All 4,149 Figshare thesis articles were
  fetched; 413 of them have an empty "Degree Type" dropdown, i.e. the depositor
  never filled it in. There is no other degree field on the article, so these stay
  unlabeled.
- **gmu_lib:da_collections** returns HTTP 503 and was not harvested.

## Background jobs

All started with `nohup`, checkpointed, resumable by re-running the same command.
**All are now finished — nothing of mine is still running.**

| Repo | Status | Log | Resume command |
|---|---|---|---|
| cmu | complete | `data/degree_enrichment/_run_cmu.log` | — |
| uiuc | complete | `data/degree_enrichment/_run_uiuc.log` | — |
| msu | complete | `data/degree_enrichment/_run_msu.log` | — |
| uhouston | complete | `data/degree_enrichment/_run_uhouston.log` | — |
| uoregon | complete | `data/degree_enrichment/_run_uoregon.log` | — |
| unt | complete | `data/degree_enrichment/_run_unt.log` | — |
| gmu | complete | `data/degree_enrichment/_run_gmu.log` | — |
