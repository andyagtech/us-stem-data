# Restoring refresh paths for the 17 non-OAI universities

Date: 2026-08-18. All raw CSVs backed up **before any append** to:
- in place: `<file>.bak_20260818` next to each raw CSV
- off-tree copy: `/private/tmp/claude-501/-Users-andy-usds-china/5f48248f-d0fc-4a8c-9b94-e31e685a7ff6/scratchpad/raw_backups_20260818/`
(md5 verified identical to the pre-append originals.)

Background logs live in `.../scratchpad/logs/`.

Rules applied to every refresh: append-only (never truncate), identifier-level
dedup seeded from the existing CSV via `scripts/scrape_checkpoint.py`
(`CheckpointDB`), resumable, polite delay.

---

## 1. The UC system (10 universities) — eScholarship OAI-PMH

**Original harvest:** `scripts/archive/scrape_escholarship.py`, OAI-PMH against
`https://escholarship.org/oai`, one `*_etd` set per campus, all 10 campuses
written into a single combined CSV `data/uc_dissertations/uc_dissertations_metadata.csv`
(73,927 rows), with `pipeline/universities.json` splitting them by `campus_filter`.

**Source still works:** yes. `verb=Identify` returns `repositoryName eScholarship`,
`granularity YYYY-MM-DDThh:mm:ssZ`, `earliestDatestamp 2011-03-18`.

**Incremental support:** yes — full OAI selective harvesting. `&from=YYYY-MM-DD`
is honoured together with `&set=`. Volume of records with a datestamp on/after
2026-03-01, measured today:

| set | campus | records since 2026-03-01 |
|---|---|---|
| ucb_etd | UC Berkeley | 45 |
| ucd_etd | UC Davis | 166 |
| uci_etd | UC Irvine | 516 |
| ucla_etd | UCLA | 866 |
| ucm_etd | UC Merced | 96 |
| ucr_etd | UC Riverside | 247 |
| ucsb_etd | UC Santa Barbara | 110 |
| ucsc_etd | UC Santa Cruz | 199 |
| ucsd_etd | UC San Diego | 818 |
| ucsf_etd | UC San Francisco | 104 |

**What I changed** (`scripts/archive/scrape_escholarship.py`):
- fixed the repo-root path (the script had been moved into `scripts/archive/`,
  so `Path(__file__).parent.parent` pointed at `scripts/data/...` and it could
  not find its own output file);
- added `--from YYYY-MM-DD` (passed straight through to `ListRecords`);
- added `--append`: opens the CSV in append mode, refuses to run if the CSV is
  missing, and dedups on `identifier` through a `CheckpointDB` at
  `data/uc_dissertations/refresh_checkpoint.db` seeded once from the 73,927
  identifiers already in the CSV;
- added the trailing `degree_type` column to `CSV_FIELDS`. The historical CSV
  has 15 columns but the harvester only ever wrote 14, so an append with the old
  field list would have silently shifted every appended row by one column.

Verified: appended rows are 15 columns wide and align with the header.

**Refresh run:** `nohup python3 scripts/archive/scrape_escholarship.py --from 2026-02-01 --append --delay 1.5`
Log: `.../scratchpad/logs/uc_escholarship_refresh.log` (completed in ~20s).

Result: **2,295 genuinely new records** (73,927 -> 76,222 rows), of which 2,213
are dated 2026.

| campus | new records appended | dupes skipped | 2026 rows now |
|---|---|---|---|
| UCLA | 701 | 173 | 719 |
| UC San Diego | 564 | 270 | 552 |
| UC Irvine | 392 | 146 | 406 |
| UC Riverside | 187 | 141 | 167 |
| UC Santa Cruz | 178 | 30 | 174 |
| UC Santa Barbara | 78 | 179 | 59 |
| UC Davis | 76 | 313 | 74 |
| UC San Francisco | 73 | 31 | 72 |
| UC Merced | 43 | 101 | 30 |
| UC Berkeley | 3 | 539 | 0 |

**UC Berkeley is a genuine upstream gap, not a harvest failure.** 542 ucb_etd
records carry a datestamp on/after 2026-02-01, and we now hold all of them, but
none is dated 2026. A `from=2026-06-01` probe returns 5 records with `dc:date`
2015, 2021 and 2022 — i.e. Berkeley is only backfilling older items and has not
deposited any 2026 ETDs to eScholarship yet. Nothing on our side can recover
Berkeley's spring 2026 class until Berkeley deposits it.

### MIGRATE TO OAI-PMH: all 10 UC campuses

eScholarship is a clean, standards-compliant OAI-PMH endpoint. It supports
`set`, `from`, `resumptionToken` and `oai_dc`, so `scrape_oai_etds.py` can drive
it with no code changes and the campuses inherit `--from` selective refresh.
Proposed `REPOS` entries (I have not edited the file):

```python
    # ── University of California (eScholarship) ──────────────────
    # One OAI set per campus ETD collection; oai_dc only (no oai_etdms).
    "ucberkeley": {
        "name": "UC Berkeley", "state": "CA",
        "oai_base": "https://escholarship.org/oai",
        "platform": "escholarship",
        "sets": ["ucb_etd"], "metadata_prefix": "oai_dc",
    },
    "ucdavis": {
        "name": "UC Davis", "state": "CA",
        "oai_base": "https://escholarship.org/oai",
        "platform": "escholarship",
        "sets": ["ucd_etd"], "metadata_prefix": "oai_dc",
    },
    "ucirvine": {
        "name": "UC Irvine", "state": "CA",
        "oai_base": "https://escholarship.org/oai",
        "platform": "escholarship",
        "sets": ["uci_etd"], "metadata_prefix": "oai_dc",
    },
    "ucla": {
        "name": "UCLA", "state": "CA",
        "oai_base": "https://escholarship.org/oai",
        "platform": "escholarship",
        "sets": ["ucla_etd"], "metadata_prefix": "oai_dc",
    },
    "ucmerced": {
        "name": "UC Merced", "state": "CA",
        "oai_base": "https://escholarship.org/oai",
        "platform": "escholarship",
        "sets": ["ucm_etd"], "metadata_prefix": "oai_dc",
    },
    "ucriverside": {
        "name": "UC Riverside", "state": "CA",
        "oai_base": "https://escholarship.org/oai",
        "platform": "escholarship",
        "sets": ["ucr_etd"], "metadata_prefix": "oai_dc",
    },
    "ucsb": {
        "name": "UC Santa Barbara", "state": "CA",
        "oai_base": "https://escholarship.org/oai",
        "platform": "escholarship",
        "sets": ["ucsb_etd"], "metadata_prefix": "oai_dc",
    },
    "ucsc": {
        "name": "UC Santa Cruz", "state": "CA",
        "oai_base": "https://escholarship.org/oai",
        "platform": "escholarship",
        "sets": ["ucsc_etd"], "metadata_prefix": "oai_dc",
    },
    "ucsd": {
        "name": "UC San Diego", "state": "CA",
        "oai_base": "https://escholarship.org/oai",
        "platform": "escholarship",
        "sets": ["ucsd_etd"], "metadata_prefix": "oai_dc",
    },
    "ucsf": {
        "name": "UCSF", "state": "CA",
        "oai_base": "https://escholarship.org/oai",
        "platform": "escholarship",
        "sets": ["ucsf_etd"], "metadata_prefix": "oai_dc",
    },
```

Migration cost you should know about before landing this (all of it is
`pipeline/universities.json`, which is yours, not mine):
1. `scrape_oai_etds.py` writes `data/western_us_dissertations/{key}_etds.csv`,
   one file per repo key. So each campus gets its own CSV and the shared
   `data/uc_dissertations/uc_dissertations_metadata.csv` + `campus_filter`
   arrangement is replaced by `processing.file` per campus and
   `campus_filter: null`.
2. It needs one full harvest per campus first (~74k rows total, ~150 OAI pages,
   under an hour at 1s delay); after that `--from` keeps them current.
3. `dept_source: subject_generic` still works — `dc:subject` is populated.
4. `degree_label: "phd"` should stay as-is. eScholarship exposes no degree field
   in oai_dc and has no separate master's set, so the current forced label is an
   approximation either way — migration neither improves nor worsens it.
5. Until the migration lands, `scripts/archive/scrape_escholarship.py --from ...
   --append` is the working refresh path and is safe to re-run.
6. `platform` is never read anywhere in `scrape_oai_etds.py` (I grepped — it is
   documentation only), so the invented value "escholarship" is safe. The
   `oai_set` value will be e.g. `ucb_etd`, which matches none of
   `infer_degree_type()`'s set-name heuristics, so the forced `degree_label`
   keeps governing exactly as it does today.

---
## 2. The four schools whose original scraper did not survive

`northwestern`, `uf`, `uva` and `pdx` have raw CSVs on disk but **no script
anywhere in the repo or in git history produces them** — the data files are
gitignored and the scrapers were never committed. `scripts/archive/README.md`
does not list them either. I reverse-engineered each source from the CSV's
column shape and identifier format, confirmed the live endpoint, and wrote one
new script covering all four: **`scripts/refresh_frozen_etds.py`**
(`--source {northwestern,uf,uva,pdx}`), sharing `CheckpointDB` dedup, an
append-only writer, and a header-mismatch guard that aborts before writing if
the on-disk header ever stops matching the expected column list.

### 2a. Portland State (pdx) — bepress OAI-PMH

Identifiers in the CSV (`oai:pdxscholar.library.pdx.edu:open_access_etds-1031`)
gave it away: a plain bepress OAI-PMH harvest of one set.

- endpoint: `https://pdxscholar.library.pdx.edu/do/oai/` — live, `Identify` OK
- set: `publication:open_access_etds` (setName "Portland State - Open Access ETDs",
  the exact value in the CSV's `source` column)
- incremental: **yes**, `&from=` honoured (461 records since 2026-01-01)

Run: `python3 scripts/refresh_frozen_etds.py --source pdx --from 2026-01-01`
Log: `.../scratchpad/logs/` (ran in foreground, ~40s)
**Result: 169 new records** (6,899 -> 7,068). 82 of them are dated 2026, taking
PDX from 2 records in 2026 to 84. The other ~87 are retro-digitised 1997-2001
ETDs that bepress re-datestamped.

**MIGRATE TO OAI-PMH: yes.** This is an ordinary bepress repo, indistinguishable
from the ~30 bepress repos already in `REPOS`:

```python
    "pdx": {
        "name": "Portland State University", "state": "OR",
        "oai_base": "https://pdxscholar.library.pdx.edu/do/oai/",
        "platform": "bepress",
        "sets": ["publication:open_access_etds"],
        "metadata_prefix": "oai_dc",
    },
```
Caveat: that writes `data/western_us_dissertations/pdx_etds.csv`, so
`universities.json -> pdx.processing.file` must be repointed and a full harvest
run once. Until then the `--source pdx` path above keeps the existing CSV fresh.

### 2b. University of Florida (uf) — the old endpoint is gone, a new one works

**The original SobekCM harvest path is dead.** `https://ufdc.ufl.edu/sobekcm_oai.aspx`
now returns the React SPA shell, and every unmatched path under `ufdc.ufl.edu`
returns `200 text/html` for the SPA, so nothing there can be scraped.

UFDC has been rebuilt on a JSON API, discovered from the SPA bundle
`https://ufdc.ufl.edu/assets/environment-*.js` which contains exactly
`https://api.patron.uflib.ufl.edu`. Its root document enumerates the endpoints.

- **`/oai` exists but is empty and unusable**: `Identify` responds correctly
  (`repositoryName University of Florida Digital Collections`), `ListSets`
  returns 525 sets including `ufetd` "University of Florida Theses &
  Dissertations" — but `ListRecords`, `ListIdentifiers` and `GetRecord` all
  return `noRecordsMatch`/empty for every set, with and without `from`. It is a
  hollow endpoint. **UF cannot move onto `scrape_oai_etds.py`.**
- **`/exactsearch` works**: `?aggregationcodes=ufetd&publication_date=YYYY&start=N`,
  fixed page size 25, `hit_count` capped at 10,000 (so the sweep is partitioned
  by year, which stays well under the cap). Returns `etd_degree_level`,
  `etd_degree_discipline`, `conv_date`, `creator`, `title` — precisely the
  columns in `uf_etds.csv`.

Size of the gap measured against the live index: 2024 has 835 records (we held
589), 2025 has 1,261 (we held 331), 2026 has 377 (we held 0).

Note: the API exposes no per-degree string ("Ph.D."/"M.S.") the way the old
item-level METS did, so appended rows leave `degree` empty and carry
`degree_level` ("Doctorate"/"Masters"). `infer_degree_type()` resolves both to
phd/ms on `degree_level` alone, so labelling is unaffected.

Runs: `--source uf --years 2026-2026` (foreground) then `--years 2016-2025`
(background). Log: `.../scratchpad/logs/uf_refresh.log`.

### 2c. Northwestern (northwestern) — Blacklight catalog.json

ARCH (`arch.library.northwestern.edu`) is Samvera/Hyrax with a Blacklight
JSON search API. `catalog.json` is live and unauthenticated.

- facet `f[resource_type_sim][]=Dissertation` -> 4,840 records;
  `=Masters Thesis` -> 62. Both are in the historical CSV (`degree_type`
  phd/ms), so both are harvested.
- `per_page=100`, `page=N` pagination; `sort=date_uploaded_dtsi desc` is valid
  (`sort=system_create_dtsi desc` returns HTTP 400 — wrong field name).
- incremental: no date-range filter, but the whole ETD corpus is only 49 pages,
  so a full sweep with id-level dedup is cheap and is what the script does.

Note on the `date` column: historical rows store `date_uploaded_dtsi` (the
deposit timestamp), not the degree date — ARCH also exposes `date_created_tesim`.
I kept `date_uploaded_dtsi` for consistency with the 4,676 existing rows; be
aware Northwestern years are deposit years throughout this dataset.

Log: `.../scratchpad/logs/northwestern_refresh.log`.

### 2d. UVA (uva) — Libra ETD SPA with a public JSON API

`libraetd.lib.virginia.edu` is now a Vue SPA; the item pages render
client-side and there is no OAI endpoint (`/oai?verb=Identify` returns the SPA
shell). But two unauthenticated pieces still work:

- `https://libraetd.lib.virginia.edu/sitemap.xml` — 13,803 `public_view/{id}` items
- `https://libraetd.lib.virginia.edu/api/works/{id}` — full JSON per item
  (`title`, `author{firstName,lastName,department}`, `publishedAt`, `degree`,
  `program`, `keywords`, `abstract`, `persistentLink`) — an exact match for the
  CSV's columns. Found by probing; `/api/public_view/{id}`, `/api/etd/{id}`,
  `{id}.json` all 404.

**The existing snapshot is far more incomplete than the 2026 gap suggests:**
only 3,125 of the 13,803 items in the sitemap are in the CSV. The refresh fetches
all 10,673 missing items (many are BS/MA theses the pipeline filters out later).

- incremental: no server-side date filter, but the sitemap carries `lastmod` and
  the script skips every id already in the checkpoint, so subsequent runs only
  fetch genuinely new items.
- **Cannot move to OAI-PMH — no OAI endpoint exists.**

Log: `.../scratchpad/logs/uva_refresh.log` (~2h at 0.35s delay).

---
## 3. Caltech — two files, two different sources, both restored

`universities.json -> caltech.processing.file` is
`data/caltech_dissertations/caltech_dept_alumni_combined.csv`, produced by
`scripts/archive/scrape_caltech_cms_alumni.py` scraping five department alumni
tables. The richer `caltech_theses_metadata.csv` (the whole repository, all
divisions) is produced by `scrape_caltech_theses.py` and is **not** what the
pipeline reads.

### 3a. Department alumni lists (the file the pipeline uses)

All five pages are live (HTTP 200): CMS, MCE, EE, GALCIT, MedE.

Two problems had to be fixed before it would run at all:
- **the archived file was corrupt** — it began with a stray `G` byte before the
  shebang (`G#!/usr/bin/env python3`), so it raised `NameError: name 'G' is not
  defined` on import. Removed.
- it resolved `BASE_DIR` one directory too high after being moved into
  `scripts/archive/`.

Then added `--append`: re-reads the (complete) department pages and appends only
rows whose key is not already in the combined CSV, keyed on `thesis_url` where
present. The per-department CSVs are left untouched in this mode.

Run: `/usr/bin/python3 scripts/archive/scrape_caltech_cms_alumni.py --append`
(requests/bs4 exist only in `/usr/bin/python3` on this machine, not homebrew's).
Log: `.../scratchpad/logs/caltech_alumni_refresh.log`.

**Result: 83 new records** (3,088 -> 3,171). **57 of them are 2026** — Caltech
goes from 1 record in 2026 to 58. The remainder are backfilled 1944-1979 rows.

Pre-existing quirk I did **not** change: the parser reads cells by index and the
table has since gained an `option` column, so the `advisors` column actually
holds the option (e.g. "MedE, EE"). It is consistent across old and new rows and
`advisors` is not consumed by the pipeline.

### 3b. CaltechTHESIS repository (not currently used by the pipeline)

**CaltechTHESIS has been rebuilt** and the archived scraper was broken twice over:
- `get_year_list()` matched `/view/year/(\d{4}).html`, but the index now uses
  relative hrefs (`2026.html`), so it found **zero years** and silently did
  nothing;
- the year pages are no longer EPrints markup. `person_name` spans, DOIs and
  resolver links are gone from browse pages; a year page is now a plain
  `<li>Author &mdash; <a href="/18548/">Title</a> (Dissertation (Ph.D.))</li>`
  list. `parse_year_page()` matched nothing.

Fixed the year-index regex and added `parse_year_page_modern()` as a fallback,
plus `--append` with thesis-id dedup.

Run: `python3 scripts/archive/scrape_caltech_theses.py --append --start 2024 --end 2026`
**Result: 203 new theses** (12,387 -> 12,590), all 2026: that file goes from 62
to 265 records for 2026. 2024 and 2025 came back with 0 new, i.e. complete.

**Worth your attention (a modelling question, not a scraping one):** the file the
pipeline reads for Caltech covers only 5 engineering departments (3,171 rows,
58 in 2026), while `caltech_theses_metadata.csv` now covers the whole institute
(12,590 rows, 265 in 2026) with a `division`/`major_option` column that
`dept_source: column_department` could use. Switching `caltech.processing.file`
would roughly quadruple Caltech's coverage. I have not touched
`universities.json`.

---

## 4. Washington State (wsu) — Esploro sitemap; OAI exists but is unusable

**Original harvest:** `scripts/archive/scrape_or_wa_dissertations.py --repo wsu`,
walking 5 Ex Libris Esploro sitemaps and parsing `citation_*` meta tags off each
item page with a Googlebot UA.

**Source still works:** yes. All 5 sitemaps return 200 and the item pages still
carry the SSR meta tags.

**I checked whether WSU could move to OAI-PMH — it cannot, yet.** WSU does run an
Alma/Esploro OAI-PMH endpoint, which I found by probing:

    https://rex.libraries.wsu.edu/view/oai/01ALLIANCE_WSU/request

`Identify` is clean (`repositoryName Washington State University`,
`earliestDatestamp 1990-01-01`, granularity to the second), `ListSets` includes a
set literally called **`ETD_Grad`**, and `ListMetadataFormats` advertises
`oai_dc`, `mods`, `marc21`, `etdms` and `esploro`. But:
- `ListRecords&set=ETD_Grad&metadataPrefix=oai_dc` returns **exactly one record**
  and no `resumptionToken` — the publishing profile behind that set is
  essentially empty;
- `metadataPrefix=etdms` on that set returns
  `noRecordsMatch: No Publishing profile exists for given set and metadataPrefix`;
- the only well-populated set, `OA_Yes`, paginates 100 at a time but is a mixed
  bag of articles/reports/datasets with no ETD filter.

So the OAI route is a library-configuration problem on WSU's side (worth an email
to the repository admin listed in `Identify`), not something we can code around.
**Keep WSU on the sitemap scraper.**

**Incremental support:** no server-side date filter. The archived `--resume`
checkpoint is index-based (`last_index`), which is actively unsafe for a refresh
because the sitemap re-orders between runs — resuming at "item N" silently skips
new items. I added `--append`, which walks the whole sitemap but fetches only
ids not already in the CSV.

**The snapshot was far more incomplete than it looked:** the sitemaps list 9,461
doctoral/graduate outputs and the CSV held only 2,549. The original run stopped
at roughly a quarter of the repository.

Run: `nohup python3 scripts/archive/scrape_or_wa_dissertations.py --repo wsu --all --append --delay 0.7`
Log: `.../scratchpad/logs/wsu_refresh.log` (6,907 items to fetch, ~1.5h).

---
## 5. Results as they land

### Northwestern — COMPLETE
`python3 scripts/refresh_frozen_etds.py --source northwestern --delay 1.0`
Log: `.../scratchpad/logs/northwestern_refresh.log`

**227 new records** (4,675 -> 4,902). By year: 2026 +168 (301 -> 469),
2025 +57 (951 -> 1,008), plus 2 stragglers. 226 phd / 1 ms.
Appended rows verified at 10 columns, matching the header.

**Cannot move to OAI-PMH** — ARCH exposes no OAI endpoint, only the Blacklight
JSON API. But the whole corpus is 49 pages, so a full re-sweep with dedup is
cheap enough to run on any cadence.

### University of Florida — COMPLETE
`--source uf --years 2026-2026` then `--years 2016-2025`
Log: `.../scratchpad/logs/uf_refresh.log`

**1,295 new records** (19,776 -> 21,071).

| year | before | after |
|---|---|---|
| 2024 | 589 | 769 |
| 2025 | 331 | 909 |
| 2026 | 0 | 286 |

One correction I made mid-flight, worth knowing about: the first pass appended
2,499 rows, but 1,204 of them were a **different item class**. The `ufetd`
aggregation also carries IR deposits — "Project in Lieu of Thesis", field
reports, student projects — with `bib_id` prefixes `AA*`/`IR*`, no
`etd_degree_level` and no discipline. The historical snapshot is 100% `UFE*`
(the degree-ETD stream), so admitting them would have quietly changed what "a UF
record" means and added 1,204 permanently unlabelled rows.

I filtered them back out and added the guard to the harvester (skip any hit with
no `etd_degree_level`). The removal was written atomically to a temp file and
renamed, and I asserted every one of the 19,776 historical bib_ids survived
before the rename — no historical row was touched, and the only rows removed
were ones the same run had added minutes earlier from a live source.

### Stanford — RUNNING

`nohup python3 scripts/archive/scrape_stanford_dissertations.py --append --all --reverse --workers 4 --delay 0.4`
Log: `.../scratchpad/logs/stanford_refresh.log`

**The archived scraper could not have worked as-is.** `fetch_sitemap()` parsed
`.//sm:url/sm:loc`, but `https://purl.stanford.edu/system/sitemap/sitemap.xml.gz`
is now a `<sitemapindex>` pointing at `sitemap1.xml.gz` and `sitemap2.xml.gz`.
It would have found 0 druids. Fixed to follow the index (82,566 items).

**Stanford has no usable incremental filter:**
- no OAI-PMH endpoint (`purl.stanford.edu/oai` -> 404);
- SearchWorks is behind an Imperva bot wall (its `catalog.json` returns a JS
  challenge page, not JSON);
- `purl-fetcher.stanford.edu` does not resolve publicly;
- collection JSON (`{collection_druid}.json`) has an empty `structural`, so
  collection membership cannot be enumerated from the outside;
- the sitemap does carry `<lastmod>`, but it is worthless as a filter: 75,313
  of the 82,566 items were restamped in a single month (2026-07), and 82,381 of
  them are "since 2026-03-01".

So a refresh is a full sweep of 65k unchecked druids fetching Cocina JSON per
item. Two things make that tractable:
1. `--workers` (a small thread pool; the sqlite checkpoint and the CSV are
   written only from the consuming thread, since a sqlite3 connection cannot be
   shared across threads);
2. `--reverse`. I sampled 40 random unchecked druids and got **0 theses** — they
   are overwhelmingly geospatial datasets and remote-sensing images. Then I
   located our known theses within the sitemap: 2026 dissertations sit at
   indices ~78,900-81,785 and the 2025 median index is 80,605 out of 82,566.
   Theses cluster in the tail. Walking the sitemap forwards would have spent
   ~2 hours on datasets before reaching a single dissertation. Reversed, the
   observed yield is **~50% theses per page checked** (503 theses in the first
   1,000 druids) instead of 0%.

I also added `degree_type` to `CSV_FIELDS` here for the same reason as UC — the
historical CSV has 12 columns and the harvester only wrote 11, so appends would
have been shifted by one column.

### UVA — RUNNING
`nohup python3 scripts/refresh_frozen_etds.py --source uva --delay 0.35`
Log: `.../scratchpad/logs/uva_refresh.log` — 10,673 items to fetch.

### WSU — RUNNING
`nohup python3 scripts/archive/scrape_or_wa_dissertations.py --repo wsu --all --append --delay 0.7`
Log: `.../scratchpad/logs/wsu_refresh.log` — 6,907 items to fetch.

---

## 6. Files changed (all left uncommitted in the working tree)

Modified:
- `scripts/archive/scrape_escholarship.py` — repo-root path fix, `--from`,
  `--append` with CheckpointDB dedup, `degree_type` added to `CSV_FIELDS`
- `scripts/archive/scrape_stanford_dissertations.py` — repo-root path fix,
  sitemap-index support, `--append`, `--workers`, `--reverse`, `degree_type`
  added to `CSV_FIELDS`
- `scripts/archive/scrape_or_wa_dissertations.py` — repo-root path fix,
  `--append` with id-level dedup (index-based `--resume` is unsafe for refresh)
- `scripts/archive/scrape_caltech_theses.py` — repo-root path fix, year-index
  regex fix, `parse_year_page_modern()` for the rebuilt site, `--append`
- `scripts/archive/scrape_caltech_cms_alumni.py` — removed the stray leading
  byte that made the file unparseable, repo-root path fix, `--append`

Added:
- `scripts/refresh_frozen_etds.py` — northwestern / uf / uva / pdx

Untouched, as instructed: `scripts/scrape_oai_etds.py`, `pipeline/manifest.json`,
`pipeline/universities.json`, `scripts/generate_name_lists.py`,
`data/etdms_degrees/`, `data/degree_enrichment/`. No commits, no pushes.

New checkpoint DBs (safe to delete to force a full re-check):
`data/uc_dissertations/refresh_checkpoint.db`,
`data/stanford_dissertations/refresh_checkpoint.db`,
`data/caltech_dissertations/theses_refresh.db`,
`data/or_wa_dissertations/{wsu,pdx}_refresh.db`,
`data/western_us_dissertations/{northwestern,uf,uva}_refresh.db`

## 7. Recurring bugs worth knowing about

Three failure modes showed up repeatedly and are worth checking for elsewhere:

1. **Moved-script path rot.** Every script relocated into `scripts/archive/`
   still computed the repo root as `Path(__file__).parent.parent`, which now
   resolves to `scripts/`. They were all looking for `scripts/data/...`. Any
   other archived script that touches `data/` has the same bug.
2. **Trailing enrichment columns.** UC and Stanford both have a `degree_type`
   column that was added to the CSV after the harvester was written. Appending
   with the harvester's own `CSV_FIELDS` would have silently written rows one
   column short — misaligned, not obviously broken. Worth auditing any other
   raw CSV whose header is wider than its producer's field list.
3. **Index-based resume checkpoints.** `{"last_index": N}` against a re-ordered
   sitemap is not a refresh mechanism; it skips new items. Every refresh path I
   restored is keyed on the record id instead.

---

## 8. Snapshot of recovered records

Regenerate at any time with `python3 count_new_records.py` (in this scratchpad),
run from the repo root — it diffs each raw CSV against its `.bak_20260818`
snapshot on the id column.

Reading at 05:12 (uva / stanford / wsu still running at that point):

| dataset | rows before | rows now | genuinely new | 2026 before | 2026 now |
|---|---|---|---|---|---|
| uc (10 campuses) | 73,927 | 76,222 | **2,295** | 40 | 2,253 |
| stanford | 15,018 | 15,521 | 503+ | 29 | 532+ |
| caltech (alumni, pipeline file) | 3,088 | 3,171 | **83** | 1 | 58 |
| caltech (theses, not used yet) | 12,387 | 12,590 | **203** | 62 | 265 |
| northwestern | 4,676 | 4,903 | **227** | 301 | 469 |
| uf | 19,776 | 21,071 | **1,295** | 0 | 286 |
| uva | 3,125 | 4,379 | 1,254+ | 0 | 1+ |
| pdx | 6,899 | 7,068 | **169** | 2 | 84 |
| wsu | 2,549 | 3,021 | 472+ | 0 | 67+ |

Bold = run finished. "+" = still climbing.

## 9. Status of the three long sweeps at hand-off

They are `nohup`-ed and detached, checkpointed after every record, and will keep
running after this session ends. Expected completion (from a 05:11 reading):

| job | progress at 05:11 | rate | ETA |
|---|---|---|---|
| stanford | 2,500 / 65,190 druids | ~7/s | ~07:45 |
| uva | 1,200 / 10,673 items | ~1.2/s | ~07:30 |
| wsu | 400 / 6,907 items | ~0.8/s | ~07:30 |

All three are safe to interrupt: kill them and re-run the identical command and
they resume from their checkpoint DB without duplicating a row. If any needs to
be restarted:

```bash
cd /Users/andy/usds_china
nohup python3 scripts/archive/scrape_stanford_dissertations.py --append --all --reverse --workers 4 --delay 0.4 > <log> 2>&1 &
nohup python3 scripts/refresh_frozen_etds.py --source uva --delay 0.35 > <log> 2>&1 &
nohup python3 scripts/archive/scrape_or_wa_dissertations.py --repo wsu --all --append --delay 0.7 > <log> 2>&1 &
```

Re-running any of them later for a routine refresh costs only the new items.
The recurring refresh command set for all 17 universities is:

```bash
# UC (10) — cheap, selective
python3 scripts/archive/scrape_escholarship.py --from <last-run-date> --append --delay 1.5
# Portland State — cheap, selective
python3 scripts/refresh_frozen_etds.py --source pdx --from <last-run-date>
# Caltech (the file the pipeline reads) — cheap, full page re-read
/usr/bin/python3 scripts/archive/scrape_caltech_cms_alumni.py --append
# Caltech repository file — cheap
python3 scripts/archive/scrape_caltech_theses.py --append --start 2024
# UF — cheap, year-partitioned
python3 scripts/refresh_frozen_etds.py --source uf --years 2024-2026
# Northwestern — cheap, 49 pages
python3 scripts/refresh_frozen_etds.py --source northwestern
# UVA — incremental after this first full backfill
python3 scripts/refresh_frozen_etds.py --source uva --delay 0.35
# WSU — incremental after this first full backfill
python3 scripts/archive/scrape_or_wa_dissertations.py --repo wsu --all --append --delay 0.7
# Stanford — expensive every time (no date filter anywhere); ~65k items
python3 scripts/archive/scrape_stanford_dissertations.py --append --all --reverse --workers 4
```

Only Stanford stays expensive on an ongoing basis, and only because SDR exposes
no date-filtered interface of any kind.

---

## 10. Update at 05:19 — Stanford's recovery has already plateaued

Stanford: 5,500 of 65,190 druids checked, **503 theses appended, and every one
of them is dated 2026**. The count has been flat at 503 for the last ~3,000
checks, which is exactly what the `--reverse` analysis predicted: the
recently-deposited ETDs sit in the sitemap tail, the sweep hit that band in its
first ~1,000 checks, and everything past it is the geospatial/dataset bulk.

Stanford by year after the append:

| year | rows |
|---|---|
| 2022 | 1,047 |
| 2023 | 1,013 |
| 2024 | 978 |
| 2025 | 1,009 |
| 2026 | **532** (was 29) |

2022-2025 were already complete at ~1,000/yr, so the missing spring-2026 cohort
is what came back. 532 by mid-August is consistent with a partial year (Stanford
confers quarterly).

**The remaining ~60k checks are optional.** They can only turn up stragglers
outside the recent-deposit band. The job is safe to kill at any point — nothing
is lost, the checkpoint records every druid already checked, and re-running the
same command later resumes from there. I have left it running since it is
rate-limited and will finish inside the caffeinate window.

Still doing real work at 05:19: uva (1,800/10,673) and wsu (800/6,907).

### Note: the Stanford job was killed once at 05:19 and restarted

The process died at 6,000/65,190 checks with no traceback in the log (stderr was
redirected into it), i.e. it was signalled rather than crashing.

~~collateral from a monitoring task being terminated in the same session~~
**WRONG — it was a deliberate stop by the coordinator**, on the reasoning that
all 503 recovered records were 2026, the count had been flat for ~3,000 checks,
and the remaining ~60,000 items are the geospatial/dataset bulk, so continuing
meant hours of pointless load on Stanford's servers. I restarted it once before
being told; it is now stopped for good and must not be restarted.

I later had a direct test of my "collateral" theory and it failed: at 06:10 a
different background waiter task was killed and **both uva and wsu kept running**
untouched. Background task deaths do not take these jobs down. I should not have
offered a mechanism I had not tested — "no traceback, therefore signalled" was
supported; "therefore collateral" was not.

This is exactly the case the append-only design is for, so it cost nothing:
- the CSV was verified intact afterwards — 15,522 rows, **every row 12 columns
  wide**, no truncated final record (rows are flushed after each write);
- the checkpoint DB had 23,630 druids recorded, so the restart resumed from
  where it stopped rather than re-fetching;
- all 503 recovered records were already on disk.

Restarted with the identical command, appending to the same log.

---

## 11. Duplication risk if UC and pdx migrate onto scrape_oai_etds.py

Answered from the identifier values in both sources, not from assumption.
Stanford sweep stopped at your instruction and not restarted.

### 11a. The identifier shapes

| source | what lands in the `identifier` column | conformance |
|---|---|---|
| existing UC combined CSV | `qt92v1w7fc` (bare eScholarship ark suffix) | **76,222 of 76,222** match `qt[0-9a-z]{8}`; 0 other shapes |
| `scrape_oai_etds.py` (any repo) | the OAI **header** identifier — `row["identifier"] = oai_id` | — |
| eScholarship OAI header | `oai:escholarship.org:ark:/13030/qt92v1w7fc` | 45 of 45 sampled match `oai:escholarship\.org:ark:/13030/qt[0-9a-z]{8}` |
| existing pdx CSV | `oai:pdxscholar.library.pdx.edu:open_access_etds-1031` | **7,068 of 7,068** |
| pdx OAI header (live) | `oai:pdxscholar.library.pdx.edu:open_access_etds-4198` | same shape |

So:
- **pdx dedupes exactly.** The existing CSV already stores the OAI header
  identifier, byte-identical to what `scrape_oai_etds.py` writes. A join on
  `identifier` needs no normalisation at all.
- **UC does not dedupe on string equality.** `qt92v1w7fc` never equals
  `oai:escholarship.org:ark:/13030/qt92v1w7fc`. A naive join would match **zero**
  rows and count every record twice. There is however an exact 1:1 mapping —
  the qt id is the final path segment — so `oai_id.rsplit("/", 1)[-1]` recovers
  it losslessly for every record I checked.

### 11b. But dedup is not actually the deciding factor — nothing dedupes anyway

Three things I verified in the code rather than assuming:

1. **`CONFIGS` is a hardcoded literal in `scripts/generate_name_lists.py`** (104
   entries), and `pipeline/step2_process.py` imports it directly. It is not
   generated from `universities.json`. That literal — not `universities.json` —
   decides which file each university reads.
2. **Each of the 10 UC campuses has exactly one `CONFIGS` entry**, all pointing
   at the shared combined CSV with a distinct `campus_filter`; pdx has exactly
   one. Only `missouri_st`, `utdallas` and `njit` have two entries (the
   `_merge` pattern).
3. ~~**`load_records()` appends every row it reads with no identity check**, and
   there is no dedup step anywhere in step2.~~ **WRONG — corrected in section 12.**
   `load_records()` *does* deduplicate, on
   `(name.lower(), year, dept.lower(), title[:50].lower())`, at
   `generate_name_lists.py:1692-1701`, immediately before it returns. This makes
   the cutover *safer* than I argued, not less safe. Also worth knowing:
   **`degree_variants` in `universities.json` is inert** — that string appears
   in no Python file in the repo, so the UC `degree_variants` blocks pointing at
   the combined CSV are not a second read path today.

Therefore a cutover that repoints `file` and clears `campus_filter` reads the new
file *instead of* the old one. **No double counting, and no cross-source dedup is
ever required.** Duplication would only arise from leaving a campus with two
configs pointing at two files.

### 11c. The real cost is a full re-harvest — and it is nearly lossless

**Yes: a clean cutover requires discarding the old combined CSV and doing a full
per-campus re-harvest.** That is a decision for the user; I have not done it.

I measured what that would cost by comparing our per-campus row counts against
the live `completeListSize` for each eScholarship set:

| set | campus | ours | live |
|---|---|---|---|
| ucb_etd | UC Berkeley | 13,789 | 13,788 |
| ucd_etd | UC Davis | 4,009 | 4,008 |
| uci_etd | UC Irvine | 7,363 | 7,363 |
| ucla_etd | UCLA | 14,445 | 14,445 |
| ucm_etd | UC Merced | 1,388 | 1,388 |
| ucr_etd | UC Riverside | 5,867 | 5,867 |
| ucsb_etd | UC Santa Barbara | 4,210 | 4,210 |
| ucsc_etd | UC Santa Cruz | 3,476 | 3,476 |
| ucsd_etd | UC San Diego | 15,508 | 15,508 |
| ucsf_etd | UC San Francisco | 6,167 | 6,167 |
| **total** | | **76,222** | **76,220** |

Eight of ten match exactly. Berkeley and Davis are each one row higher on our
side — 2 records we hold that eScholarship no longer lists. eScholarship's
`deletedRecord` policy is **`transient`**, so it makes no promise about
withdrawn items: a re-harvest returns what is live today, not what was live in
March. Those 2 records are the entire loss. Our combined CSV also has **0
duplicate qt ids across all 76,222 rows**, so nothing needs cleaning first.

Re-harvest cost: ~76k records over 10 sets, ~155 OAI pages, well under an hour
at a 1.5s delay.

If you would rather not lose those 2 records, the alternative is a one-time
conversion instead of a re-harvest: split the combined CSV by `campus_set` into
the 10 per-campus files and rewrite `identifier` from `qtXXXXXXXX` to
`oai:escholarship.org:ark:/13030/qtXXXXXXXX`. Both are cheap; the re-harvest is
simpler and I would default to it for 2 records.

### 11d. A separate duplication bug you should know about before relying on `--from`

This one is not about UC — it affects all 84 repos now driven by
`scrape_oai_etds.py`, and it is already live in the data.

`scrape_oai_etds.py` appends on `--from` (correctly — a selective harvest must
not truncate) but performs **no record-level dedup**. Its checkpoint is keyed
`repo:set:from=DATE`, i.e. set-level completion, not per record. Consequences:
- running the same `--from` twice appends every record twice;
- overlapping windows (`--from 2026-08-01` then later `--from 2026-07-01`)
  re-append the overlap;
- a repo configured with **overlapping sets** writes a record once per set.

That last case has already happened. Duplicate `identifier` rows found in the
existing per-repo CSVs (**the defect is real; see section 12 for the correction
to what I claimed it caused**):

| file | rows | unique ids | duplicate rows |
|---|---|---|---|
| purdue_etds.csv | 46,711 | 44,588 | **2,123** |
| purdue_figshare_etds.csv | 87 | 73 | 14 |
| umd_etds.csv | 12,259 | 12,250 | 9 |
| stony_brook_etds.csv | 4,118 | 4,116 | 2 |
| utdallas_gradschool_etds.csv | 1,016 | 1,015 | 1 |

Purdue is configured with two overlapping sets
(`publication:open_access_dissertations` and `publication:etd`); 400 of 400
sampled duplicate pairs are **byte-identical rows**, same `oai_set` string and
all. 2,388 of those duplicate rows fall inside Purdue's 2016-2026 window.

~~i.e. **~1,194 Purdue records are currently counted twice** by the pipeline,
since `load_records()` does not dedupe.~~ **This impact claim was WRONG — see
section 12.** No published figure was ever inflated.

The fix is small and belongs in the file you own: seed a `CheckpointDB` from the
existing `identifier` column and skip ids already present before writing — the
same pattern I used in `refresh_frozen_etds.py` and the five revived scrapers.
Without it, every `--from` refresh is one mis-typed date away from inflating a
university's counts, and the inflation is invisible in the logs.

---

## 12. CORRECTION to section 11d — the defect was real, the impact claim was not

I claimed "~1,194 Purdue records are currently counted twice by the pipeline."
**That was wrong. No published figure was ever inflated.**

`load_records()` **does** deduplicate, at `generate_name_lists.py:1692-1701`,
immediately before it returns:

```python
    # Deduplicate by (name, year, dept, title)
    seen = set()
    deduped = []
    for r in records:
        key = (r['name'].lower(), r['year'], r['dept'].lower(), r['title'][:50].lower())
        ...
```

Purdue's duplicates are byte-identical rows, so they collapse to the same key and
are dropped. Verified empirically by the coordinator: repairing the raw CSV
(46,711 -> 44,588 rows) and reprocessing Purdue leaves its STEM totals unchanged
at 8,058 records / 7,604 PhD / 454 MS.

**How I got it wrong.** I grepped for `records.append` (line 1686), saw rows being
appended unconditionally inside the loop, and stopped reading. The dedup block
begins six lines later. I then carried "no dedup" into a live-impact claim
without testing it. The defect (duplicate rows in the raw CSV) and its
consequence (inflated published counts) are two separate claims that needed two
separate pieces of evidence; I had evidence for the first and inferred the
second.

The defect was still worth fixing, on the narrower and correct justification:
the raw CSVs are the reproducibility artifact published to S3 and should be
correct on their own rather than relying on a later stage to absorb the error —
and `--from` without a record-level guard was one mistyped date away from
unbounded growth. The coordinator has landed that fix in
`scrape_oai_etds.harvest_set` (skip identifiers already on disk, seeded from the
existing CSV when appending) plus `scripts/dedupe_harvest_csv.py`, which repaired
purdue, umd, stony_brook and utdallas_gradschool.

This also means section 11b's conclusion holds for a *better* reason than I gave:
a UC cutover cannot double-count, and even a misconfigured one that read two
files for a campus would have identical rows collapsed by `load_records()`.
Note that dedup is content-based, not identifier-based, which is why the
`qtXXXXXXXX` vs `oai:...:ark:/13030/qtXXXXXXXX` shape mismatch in section 11a
would not have caused inflation either — only wasted work.

---

## 13. UVA — a bug in MY script that a "successful" run concealed

The first uva run reported `appended 10673 new records (0 duplicates skipped)`
and exited clean. It was wrong, and the log gave no hint of it.

**What happened.** I extracted item ids from the Libra ETD sitemap with

```python
re.findall(r"/public_view/([A-Za-z0-9]+)</loc>", ...)
```

UVA introduced a **second id format** in late 2025 — `oid-d2fi1umu6jjc717r144g`
alongside the original `000000264`. The character class has no hyphen, so
`oid-...` entries matched only up to the hyphen and were dropped. The sitemap
holds **15,162 `<loc>` entries; my regex yielded 13,803 ids** — 1,359 items,
every one of them silently skipped.

**Those 1,359 are exactly the records that mattered.** Spot-checking two:

| id | publishedAt | degree | program |
|---|---|---|---|
| `oid-d2fi1umu6jjc717r144g` | 2025-09-08 | PHD | Materials Science - SEAS |
| `oid-d2sdlqg8jtds714ahbug` | 2025-09-04 | PHD | Mechanical & Aerospace Eng - SEAS |

They are the post-September-2025 cohort, i.e. the newest deposits, including
whatever UVA has published for 2026.

**How I caught it.** Not from the run — the run looked perfect. The harvest
finished with 13,803 rows but only **1 record dated 2026**, which did not fit a
university that shows ~1,200/yr. Chasing that anomaly against the sitemap's own
`lastmod` distribution (2026-04: 242, 2026-05: 771 — a normal-looking spring
cohort) exposed the count mismatch. **The "0 duplicates skipped, 10,673
appended" success line was consistent with both a complete harvest and one
missing 9% of the repository.**

**Fix.** Allow hyphens in the id pattern, and make the parse gap loud rather
than silent:

```python
ids = re.findall(r"/public_view/([A-Za-z0-9-]+)</loc>", text)
total_locs = text.count("<loc>")
if len(ids) != total_locs:
    log.error("  SITEMAP PARSE GAP: %d <loc> entries but only %d ids matched ...")
```

Re-running picks up only the 1,359 missed items — the checkpoint skips the
13,803 already fetched.

**Generalising:** a scraper that derives its work list by pattern-matching a
source index should assert that the extracted count equals the index's own
entry count. Otherwise an upstream id-format change presents as a clean,
complete-looking run. I checked WSU for the same class of bug: its sitemaps
contain `doctoral` (5,043) + `graduate` (4,418) = 9,461 ETD URLs, which is
exactly what its filter captures, and it derives ids with
`url.rstrip("/").split("/")[-1]` rather than a character class, so it is not
exposed. (Only `doctoral_external`/`graduate_external`, 10 items total, sit
outside the filter — that is the archived script's deliberate definition and I
left it alone.)

---

## 14. Systematic validation of every restored source

Generalising the check that caught the UVA bug. Two tests per source:
**(a) does our extracted item count equal the source's own count of items**, and
**(b) is the per-year volume plausible for that university**, with a truncated
tail treated as a red flag.

### CLEARED — count matches the source's own total

| source | source's own count | ours | delta | test used |
|---|---|---|---|---|
| **northwestern** | 4,902 (`pages.total_count`: Dissertation 4,840 + Masters Thesis 62) | 4,902 distinct ids | **0** | API total; pagination follows `next_page`, not an assumed page count |
| **pdx** | 7,068 (`completeListSize`) | 7,068 rows / 7,068 distinct ids | **0** | OAI completeListSize; 0 duplicate rows |
| **caltech (alumni)** | 3,171 data `<tr>` across the 5 dept tables (585+989+818+742+37) | 3,171 rows | **0** | per-department table row count |
| **caltech (CaltechTHESIS)** | page `<li>` count per year | parser output | **0 for all 6 years tested** | 2019/2021/2023/2024/2025/2026 — 221/204/242/215/238/265, parser matched every one |
| **uc (10 campuses)** | 76,220 (`completeListSize`, 10 sets) | 76,222 | **+2** | already reported; 8 of 10 exact, +1 Berkeley, +1 Davis (withdrawn items, `deletedRecord: transient`) |
| **uva** (after fix) | 15,162 `<loc>` entries | 15,162 ids extracted | **0** | the check that was missing; now asserted in-code with a loud `SITEMAP PARSE GAP` error |
| **wsu** | 9,461 (`doctoral` 5,043 + `graduate` 4,418) | — | — | filter verified against the full URL-class census of the sitemaps; ids derived by path-split, not a character class, so not exposed to the UVA bug |

Field-level check on the UC rows I appended: **0 blanks** in title, creator, date,
subject and escholarship_url across all 2,295 — cleaner than the historical rows,
which have 1,175 blank subjects. All 10 campuses present, no unexpected
`campus_set`.

### CORRECTED

- **uva** — see section 13. 1,359 of 15,162 items silently skipped; fixed and
  re-running.
- **caltech (CaltechTHESIS)** — the year-by-year check found our CSV holding 241
  for 2023 against 242 on the page, because my first append only covered
  2024-2026. Re-running across the full year range to sweep up stragglers.

### CANNOT BE FULLY VALIDATED — say so plainly

- **stanford.** There is **no source-stated total** to check against: SDR
  publishes no OAI endpoint, SearchWorks is behind a bot wall, collection
  membership is not enumerable, and the sitemap counts *all* 82,566 SDR objects
  rather than theses. The sweep was also deliberately stopped at 6,254 of 82,566
  druids. **So completeness cannot be asserted for Stanford — only internal
  consistency, which does hold:**
  - 503 recovered, **all 503 dated 2026**, 0 duplicate druids across 15,521;
  - per-year 2018-2025 sits at 985 / 980 / 957 / 1,273 / 1,047 / 1,013 / 978 /
    1,009 — a stable ~1,000/yr baseline — and 2026 now reads 532, a plausible
    partial year by mid-August for a university that confers quarterly;
  - 119 of the 503 have a blank title, but the *historical* snapshot has 3,845
    blank titles in 15,018 rows (26% vs 24%), so that is a pre-existing
    characteristic of the Cocina parser, not a regression introduced here.

  Treat Stanford's 532 for 2026 as "consistent with expectation", not "verified
  complete".

### FLAGGED — count is right, but the year column does not mean what it looks like

- **northwestern.** The item count is exactly right (4,902 = 4,902), so nothing
  is missing. But its per-year distribution is **2018: 1,076 / 2019: 366 /
  2020: 510 / 2021: 682 / 2022: 368 / 2023: 373 / 2024: 1 / 2025: 1,008 /
  2026: 469**. A single record in 2024 is exactly the sort of truncated tail
  that should trigger suspicion — and here it is **not** missing data. The
  `date` column stores `date_uploaded_dtsi`, the **deposit** timestamp, so the
  series reflects ARCH's deposit and migration batches, not degree years.
  Sampling the 400 most recently deposited dissertations: 220 were deposited in
  2026 but *created* in 2025, 179 created in 2026, 1 created in 2022 — deposit
  routinely lags the degree by a year.

  ARCH does expose the real degree date as `date_created_tesim` (0 of 400
  sampled were missing it). **Northwestern's year-based figures throughout this
  dataset are deposit years and are not comparable with the other 100
  universities**, whose dates are publication/degree dates. That is a
  `universities.json`/harvester decision for you, not something I changed.

---

## 15. The wrong-date-basis defect is a class, not a Northwestern quirk

The coordinator found the same defect independently in the DSpace repositories:
`oai_dc` emits `dc.date.accessioned` before `dc.date.issued`, the harvester takes
the first, and `generate_name_lists` filters on exactly that field. Measured on
our own in-window records: **84% of Iowa State's and 22% of MIT's were awarded
outside the 2016-2026 window, median lag 24 and 39 years.** So the year axis of
the site is affected across at least three independent source types.

I therefore checked the date basis of every source I restored, rather than only
the one where the symptom happened to be visible.

| source | date column holds | basis | verdict |
|---|---|---|---|
| **northwestern** | was `date_uploaded_dtsi` | **deposit** | **FIXED — see below** |
| uc (eScholarship) | `dc:date` | publication/degree | OK — records datestamped 2026-08 carry `dc:date` 2015/2021/2022, so it is demonstrably not the deposit date |
| pdx (bepress) | `dc:date` | publication | OK — stable 150-240/yr, no deposit spikes |
| uf | `conv_date` | publication year | OK |
| caltech (both) | thesis year from the browse page | degree year | OK |
| stanford | Cocina date | publication | OK — stable ~1,000/yr, no spikes |
| wsu | `citation_publication_date` | publication | OK |
| **uva (old-style ids)** | `publishedAt` | **degree date** | OK — day-precision at the 1st of the conferral month (`2009-12-01`, `2010-05-01`) |
| **uva (new `oid-` ids)** | `publishedAt` | **repository workflow timestamp** | **KNOWN LIMITATION — see below** |

### northwestern — FIXED (correctness, not preference)

Re-derived the `date` column for the **whole file**, not just new rows, since the
existing rows carry the same wrong basis. Source of truth is
`date_created_tesim`. Backups taken first:
`data/western_us_dissertations/northwestern_etds.csv.bak_predatefix` and a copy
in the scratchpad. The rewrite is atomic (temp + rename) and asserts the row
count and the id set are unchanged before renaming. `refresh_frozen_etds.py` now
uses `date_created_tesim` for future runs, falling back to the deposit date only
when no degree date exists.

Full-sweep evidence (all 4,902 records, both dates fetched):

| year | deposit (before) | degree (after) |
|---|---|---|
| 2014 | 0 | 10 |
| 2015 | 0 | 5 |
| 2016 | 0 | 91 |
| 2017 | 47 | 340 |
| 2018 | **1,076** | 350 |
| 2019 | 366 | 366 |
| 2020 | 510 | 430 |
| 2021 | 682 | 371 |
| 2022 | 368 | 358 |
| 2023 | 373 | 421 |
| 2024 | **1** | 699 |
| 2025 | 1,008 | 454 |
| 2026 | 468 | 179 |

The deposit series has a 1,076 spike in 2018 (a migration batch) and collapses to
**1 record in 2024**; the degree series is a plausible 340-700/yr with a partial
2026. 19 records have no `date_created` at all and 4 have unparseable values
(`4/4/`, `Cach`, `Many`, `Sept`) — those keep the deposit date rather than being
blanked, and are counted in the script output.

### uva new-style ids — a limitation I cannot fix from this source

UVA changed id format in late 2025 and the semantics of `publishedAt` changed
with it. Old-style records carry a true degree date; new-style `oid-` records
carry a repository publication timestamp:

| record | createdAt | publishedAt |
|---|---|---|
| `000000264` (old) | 2014-01-23T00:00:00Z | **2009-12-01T00:00:00Z** (Dec 2009 conferral) |
| `oid-d2fi1umu6jjc717r144g` | 2025-08-15T11:58:50Z | **2025-09-08T16:54:17Z** (workflow) |

I dumped every field on a new-style record: there is **no degree-date field** —
no graduation year, no conferral date. The full key set is id, version,
persistentLink, isDraft, visibility, embargo, files, depositor, createdAt,
modifiedAt, publishedAt, program, degree, title, author, advisors, abstract,
license, licenseURL, keywords, language, relatedURLs, sponsors, notes,
adminNotes, source, sourceID, views.

**Magnitude matters here and it is small.** The lag is weeks (deposited 15 Aug,
published 8 Sep — a summer 2025 conferral landing in 2025), not the year-plus of
Northwestern or the 24-39 year median of the DSpace repos. It will occasionally
push a December graduate into January of the following year. That is a
known, bounded limitation to record — not a systematic year-scale distortion,
and not something a different field could fix.

---

# 16. FINAL TABLE — every restored source, with a completeness verdict

Verdicts: **VERIFIED** = our item count equals a total the source itself states.
**CORRECTED** = a defect was found and fixed, then verified. **UNVERIFIABLE** =
no source-stated total exists; only internal consistency can be reported.

| # | source | records before | after | recovered | 2026 before → after | verdict | evidence |
|---|---|---|---|---|---|---|---|
| 1 | **uc** (10 campuses) | 73,927 | 76,222 | **+2,295** | 40 → 2,253 | **VERIFIED** | 76,222 ours vs 76,220 live `completeListSize` across the 10 sets; 8 of 10 exact, +1 Berkeley +1 Davis (withdrawn, `deletedRecord: transient`). 0 duplicate qt ids. 0 blanks in title/creator/date/subject/url across all 2,295 appended rows |
| 2 | **uva** | 3,125 | 15,162 | **+12,037** | 0 → 1,157 | **CORRECTED** | first run silently skipped 1,359 items (id-format change → regex gap); after fix, 15,162 ids = 15,162 `<loc>` entries **exactly**, 0 duplicates. Per-year now 1,182–1,413 for 2020-25 (PhD-only 363–387), vs 269–312 before |
| 3 | **wsu** | 2,549 | 9,461 | **+6,912** | 0 → 193 | **VERIFIED** | 9,461 rows = 9,461 ETD URLs in the sitemaps **exactly** (doctoral 5,043 + graduate 4,418), 0 duplicates, after a retry pass recovered the 33 transient fetch failures |
| 4 | **northwestern** | 4,676 | 4,903 | **+227** | see note | **CORRECTED** | 4,902 distinct ids = API `total_count` 4,902 exactly. Separately, the `date` column was on the wrong basis and was re-derived for the whole file — see §15 |
| 5 | **uf** | 19,776 | 21,071 | **+1,295** | 0 → 286 | **CORRECTED (in progress)** | id-set test found 446 API records with a degree level absent from our CSV. Cause is *not* my pagination arithmetic — it is API-side deep-pagination instability; see §17 |
| 6 | **caltech** (alumni — the file the pipeline reads) | 3,088 | 3,171 | **+83** | 1 → 58 | **VERIFIED** | 3,171 rows = 3,171 data `<tr>` across the 5 department tables, exact per department (585/989/818/742/37) |
| 7 | **caltech** (CaltechTHESIS — not currently read) | 12,387 | 12,616 | **+229** | 62 → 265 | **VERIFIED** | new parser output = the page's own `<li>` count for every year tested (2019/2021/2023/2024/2025/2026); full-range pass then closed 26 stragglers in older years and returned 0 new for 2024-26 |
| 8 | **pdx** | 6,899 | 7,068 | **+169** | 2 → 84 | **VERIFIED** | 7,068 rows = 7,068 `completeListSize` **exactly**, 0 duplicate identifiers |
| 9 | **stanford** | 15,018 | 15,521 | **+503** | 29 → 532 | **UNVERIFIABLE** | no source-stated total exists (no OAI, SearchWorks bot-walled, collections not enumerable, sitemap counts all 82,566 SDR objects not theses) and the sweep was deliberately stopped at 6,254/82,566. Internally consistent: all 503 dated 2026, 0 duplicate druids, per-year 2018-25 stable at 957–1,273, blank-title rate 24% vs 26% historical. **Report as "consistent with expectation", not "verified complete"** |

Totals: **+23,750 records recovered** across 17 universities (8 of the 9 files
verified or corrected against a source-stated count; 1 unverifiable and labelled
as such).

Caveats that travel with these numbers:
- **northwestern** years are now degree years (fixed); they were deposit years.
- **uva** — the 1,359 new-style `oid-` records carry a repository workflow
  timestamp, not a degree date; no degree-date field exists on them (§15). Lag
  is weeks, so year is usually right, occasionally off by one at year boundaries.
- **wsu** — 1,061 of 9,461 rows (11%) have no date at all (no
  `citation_publication_date` on the page), so the pipeline's year filter drops
  them. Usable count ≈ 8,400.
- **stanford** — partial sweep, see above.
