# Session handoff — 2026-08-22

> **Archive.** Written 2026-08-22 and kept for the incident record and the
> reasoning behind it. Task status here is NOT current — several items
> have since been done or overtaken. Current working rules live in
> `CLAUDE.md`.

## The incident worth reading before touching the harvester

A DSpace re-harvest **destroyed degree metadata across fifteen repositories**
and reduced three more to 183-byte headers. Everything was recovered from S3.
Nothing was lost. The reason it was recoverable is that the backup had been
verified **byte-for-byte** before the run, not merely counted — fifteen minutes
later it would already have been stale for sixteen repos.

**What happened.** A full harvest opened each CSV in `"w"` and discarded it.
DSpace repos were re-fetched under `oai_dc`, which carries no degree fields, so
enriched files were replaced by unenriched ones. `mines` went from
`degree_level` 98.4% to 0% **while its row count rose**.

**Why the guard missed it.** It compared only row count and date fill, so
column loss walked straight past. And its first line read
`if not out_csv.exists() or not new_rows: return True` — an empty harvest was
explicitly ALLOWED. That is how three repos became header-only files with the
run still reporting `ok`.

**The principle that replaced it.** Retrieved data is APPEND-ONLY. A harvest
may add records and fill empty fields; it may never remove a record, drop a
column, or blank a field that already held a value. Derived artifacts
(`csv_cache`, Parquet, `distribution.json`) are regenerable and cheap to lose.
Retrieved data may be irreplaceable, because the source can change under you —
as Mines did, mid-project.

A guard must anticipate every shape loss can take. A merge makes loss
impossible to express. Prefer the merge.

**Two things only found by replaying the real failure**, not a synthetic one:

1. Mines now emits `oai:null:11124/178043` where it emitted
   `oai:repository.mines.edu:11124/178043`. Same records, different strings.
   Keying the merge on the raw identifier matched nothing and appended
   everything twice — 18,657 rows, every fill rate halved. It keys on the
   stable repository-local record path now.
2. The runner skipped every repo present in the manifest, so a failed or killed
   repo was never retried on resume. Resumable for interruptions, not for
   failures.

**Current safety.** `merge_into_existing()` with `_merge_key()`; a `.csv.prev`
generation before every promotion; abort if a merge yields fewer rows than it
started with; S3 verified before each run.


## STOP: the award-date re-harvest is not safe yet

A pilot re-harvest of one repository (binghamton) on 2026-08-20 **destroyed
every date in that CSV**, and the backup is the only reason nothing was lost.

    before   543 rows, `date` filled 543 (100.0%)
    after    561 rows, `date` filled   0 (  0.0%), `date_issued` also 0

Restored from `/tmp/binghamton_before.csv`; the working copy is intact at 543
rows with dates at 100%.

**Why.** binghamton is configured `metadata_prefix: "oai_etdms"` — chosen
because ETDMS exposes `degree.name`, `degree.level` and `degree.discipline`.
But the harvester reads dates with `get_text("date")`, a `dc:` namespace
lookup, and **the ETDMS schema has no `dc:date`**. Confirmed against the live
feed: under `oai_dc` a record carries
`<dc:date>2013-10-01T07:00:00Z</dc:date>`; under `oai_etdms` the root is
`<thesis>` with no `dc:` dates at all.

The existing CSVs were harvested under `oai_dc`. The prefix was later switched
to ETDMS for degree metadata and **nobody re-harvested — which is the only
reason the dates still exist.** So `_pick_issued_date()` works, but it never
runs on ETDMS repos, and re-harvesting them silently empties both date fields.

Running all 110 repositories would have destroyed the year series for every
ETDMS repository at once.

**Before any re-harvest, in this order:**

1. Teach the parser to read the ETDMS date (`etdms:date` under the `thesis`
   root) with a `dc:date` fallback, so both prefixes yield a date.
2. Add a harvester guard that **refuses to overwrite a CSV when date fill drops
   sharply** against the file it is replacing. This is the check that makes the
   process safe without depending on someone having taken a backup.
3. Re-pilot one ETDMS repo and one DSpace repo. Assert date fill stays at
   ~100% and `date_issued` is populated.
4. Only then measure accession-vs-issued drift, and only then decide whether a
   full re-harvest is worth it. The drift is still UNMEASURED — the pilot could
   not measure it, because it produced no dates to compare.
5. Back up `data/western_us_dissertations/` before a bulk run regardless.

Repositories are configured with one of several metadata prefixes, so step 1
must be verified per platform (bepress, dspace, figshare, hyrax, blacklight),
not once.


Continues the 2026-08-19 session.

## Done this session

**The site had no raw-count chart.** Every figure on it was a proportion, which
cannot distinguish "more non-residents" from "fewer Americans". Two panels were
added to `/distributions.html`:

  * doctorates, 1995–2025, from `site/data/long_series.json`
  * master's, 2008–2025, summed from `site/data/live_bundle.json`

each plotting total, domestic and non-resident counts.

**A fabricated trend was live on the dashboard.** `scripts/build_live_bundle.py`
mapped `LEVELS = {"7": masters, "17": doctorate}` and never read award level 9,
the pre-2010 research-doctorate coding. The doctorate series therefore read:

    year   was        true      understated
    2005   0          24,884    100%
    2007   0          28,794    100%
    2008   6,202      29,498     79%
    2009   12,454     29,261     57%

which drew a five-fold ramp into 2010 that never happened. Level 9 is restored
and both codings are summed across the 2008–09 migration, per the rule in
`pipeline.models.bases_for()`. The bundle now matches `long_series` to within
0.45% worst-case. `scripts/test_site.py` asserts 2008 and 2009 against the long
series, and the assertion was verified to fail when the bug is reintroduced.

**`START_YEAR = 2005` was dead config.** `CTOTALT`/`CNRALT` first appear in the
2008 file; 1995–2007 carry residency as sex-split race columns, so those years
parsed to zero and were dropped. The bundle has always begun at 2008. Set to
2008 and documented; `scripts/build_long_series.py` reads the legacy columns if
a longer series is wanted.

**IPEDS published no 1999 completions file.** The counts chart breaks its line
across the gap and bridges it with a dashed stub rather than drawing a
fabricated 1999 value through it. Asserted in the tests.

**requirements.txt and a real `.venv` now exist.** This was the open item from
the last handoff. `duckdb` and `openpyxl` had only ever been installed into a
temporary scratchpad venv, which is why the Parquet exports silently shipped an
April snapshot for four months and why `build_live_bundle.py` could not run at
all. Rebuild with:

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

Core pins: duckdb, openpyxl, pandas, PyYAML, boto3, anthropic. The archive-only
deps (bs4, playwright, rapidfuzz, requests) are listed commented-out. `.venv/`
is gitignored.

**The 60.3% master's figure was baseline-sensitive.** It is measured 2012→2025,
which is disclosed on the page but is also the baseline that maximises it
(2008 gives 55.7%, 2018 gives 52.8%). The window is kept, and a robustness
statement was added: measured to 2025 from any baseline between 2008 and 2018 —
eleven windows — non-residents took the majority of new core-STEM master's
places every time, between 50.2% and 60.8%. Computed and asserted in the tests.

**The 2022 dip / 2023 jump in master's is real, not a reporting artefact.**
Checked because it has the shape of the Duke defect. Reporting institutions move
smoothly across it (6,042 → 5,960) as do level-7 row counts (44,466 → 44,927),
and the swing is confined to the non-resident line while the domestic line keeps
climbing. Those graduates enrolled in autumn 2020, under the travel
restrictions. Disclosed in the panel's note.

74/74 checks in `scripts/test_site.py` pass.

## What the raw numbers actually say

Worth knowing before presenting, because an opponent will run this arithmetic.
Core-STEM research doctorates, 1995→2025:

    domestic      14,809 → 25,794   +74.2%
    non-resident   7,209 → 15,480  +114.7%
    total         22,018 → 41,274   +87.5%

Of 19,256 net new doctorate places, 57% went to citizens and permanent
residents, and the domestic count is at its all-time high in 2025. The
raw-number argument lives at master's level, not doctorate level. The site
already concedes domestic growth in the `#opportunity` section and the tests
assert that concession stays.

---

# Session handoff — 2026-08-19

Continues the 2026-08-18 session. Both repos version-controlled; `usds_china`
tracks branch `assistant`, `usds_china_private` is local-only.

## Done this session

**OpenGraph cards — a live defect, now fixed.** 12 university pages carried an
`og:image` pointing at a card that did not exist (the previous session's
regeneration was killed mid-run on low battery). Anyone sharing those pages got
a broken preview. All 237 cards were regenerated on the corrected narrow-STEM
basis (CIP 11,14,15,26,27,30,40,42) and verified: zero pages reference a missing
file, and all 12 return HTTP 200 live. UNLV's card now reads 32.3%, matching its
page, rather than the 15.1% broad-basis figure.

**Parquet bulk exports — a silent failure since April 8.** `build_pages` was
emitting `WARNING: Parquet build failed: ModuleNotFoundError: No module named
'duckdb'` and reporting the step OK, so every deploy for four months shipped the
April snapshot. Rebuilt:

    stem_records      294,953 -> 371,145 rows   101 -> 105 universities
    nonstem_records   115,569 -> 149,170 rows    98 -> 102 universities

These are the bulk-download path for anyone wanting the underlying data rather
than the pages. **duckdb is not in the project environment** — it was installed
into a scratchpad venv, which is temporary. Add it to the real dependency set or
this regresses.

**Montana State completed.** Harvest finished at 12,269 unique records against
12,397 expected (99.0%) despite heavy rate-limiting. Reprocessed through
process -> enrich -> generate -> build_pages; its STEM page went from 2,203 to
3,074 records. Note the CSV shows 13,429 lines by `wc -l` but holds 12,269
records — embedded newlines in quoted title fields. It is not duplicated.

## Traffic readiness (asked: is this ready for a lot of views?)

Static serving is ready. Warm TTFB 40-130 ms from CloudFront; HTML gzipped with
`Vary: Accept-Encoding`; a first visit is ~34 KB compressed. The 20 MB
`data/stem/_search.json` is lazy — only `doSearch` and `applyDeptFilter` fetch
it, so ordinary visitors never do.

No cost leak on pageview. `warmUp()` fires only on panel open, guarded once per
page, and the live handler rejects its `{v:2, ping:true}` payload with a 400
before reaching any model.

AWS guards already exist (an earlier claim that none did was wrong): reserved
concurrency on `phd-chat` is 100 against an account pool of 1,000, and six
billing alarms sit at $20/40/50/70/100/200, notifying via SNS. They alert; they
do not enforce. **They do not see OpenAI spend**, which is billed directly and
is the actual uncapped exposure.

## Open decisions — these are the user's calls, not chores

1. ~~**Chat backend is still the April v1.**~~ **RESOLVED 2026-08-20.** The
   Lambda now runs 1024 MB / 45 s and has been redeployed several times since,
   carrying the current knowledge base and the level_rankings tool. This entry
   is kept struck through rather than deleted because it sat here contradicting
   the top of the file for a day.

2. ~~**JSON is served gzip unconditionally.**~~ **RESOLVED 2026-08-20** —
   pre-compression is now applied only above CloudFront's 9 MB on-the-fly
   ceiling, which is one file (`data/stem/_search.json`, 19.7 MB). The other
   225 JSONs upload plain and CloudFront negotiates encoding correctly, so
   `urllib` and bare `curl` read them. Original note follows.

   **JSON is served gzip unconditionally.** Pre-compressed S3 objects assert
   `content-encoding: gzip` even when the client sends `Accept-Encoding:
   identity`, so naive consumers get binary:

       json.load(urllib.request.urlopen('.../data/stem/msu.json'))
       -> UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8b

   Browsers and `requests` are fine; `urllib` and bare `curl` are not. HTML is
   unaffected (CloudFront compresses it on the fly and negotiates correctly).
   Fixing it means dropping pre-compression for the 214 JSONs while KEEPING it
   for `data/stem/_search.json` — at 20 MB that file is above CloudFront's
   on-the-fly ceiling and would otherwise ship uncompressed. Or simply document
   the `--compressed` requirement.

3. **Award-date defect — DO NOT RE-HARVEST YET. See the section below.**

   **Award-date defect, unchanged.** OAI harvests took `dc.date.accessioned`
   rather than `dc.date.issued`. The harvester now captures `date_issued` but no
   CSV has been re-harvested. Repairing it moves the published headline year
   series across many universities.

## Degree-metadata coverage — a source limitation, not a bug

Investigated and largely a false alarm. Three claims made during the
investigation were overturned by measurement; the record here is the corrected
version.

Coverage against each harvest:

    repo          harvested   mapped  covered     pct
    cmu              21,977    3,736    3,736   17.0%
    gmu              13,493    5,518    5,347   39.6%
    uoregon           5,140    3,528    3,415   66.4%
    msu              52,790   52,464   52,073   98.6%
    uhouston          6,844    7,075    6,842  100.0%
    uiuc             57,180   57,115   57,112   99.9%
    unt              22,187   22,140   21,964   99.0%

- **CMU's 17% is the wrong denominator.** Its Figshare repository holds 15,511
  journal contributions, 1,013 reports and 298 datasets alongside theses.
  `type_filter='thesis'` correctly excludes them; CMU covers ~90% of its 4,149
  actual theses. Nothing wrong.
- **GMU's counts are NOT inflated with articles.** The registry comment on
  `gmu_lib:ir_collections` says "ETDs mixed with articles", but sampling the
  uncovered titles shows genuine theses typed `Thesis`. Only the PhD/master's
  split is incomplete (~4,400 records), which is the long-documented labelling
  gap, not a counting defect.
- **The `done: true` / `checked: 0` pattern is not a bug.** `checked` is unused
  on the OAI path, which tracks progress by resumption token. msu, uhouston,
  uiuc and unt carry the same pattern at 98-100%.
- **Re-walking found nothing.** Three full repository walks (gmu, uoregon, cmu)
  returned zero additional records. The feeds do not publish degree level for
  the remainder.

The three `done` flags were left cleared (backups in
`data/degree_enrichment/_ckpt_backup/`). It costs ~6 min per enrichment run, but
the flag should mean "nothing further available for the current corpus", and the
corpus grows — that stickiness is what made GMU look broken for months.

**Montana State cannot be degree-enriched with current tooling.** Only seven
repos are configured (cmu, gmu, msu, uhouston, uiuc, unt, uoregon), each with a
hand-picked metadata prefix. Montana State has no entry, which is why it labels
at 18.2%. Adding one means identifying which prefix its repository exposes
degree level under, and testing it. That is new configuration, not a fix.

## The finding worth keeping

National NRA share of US research doctorates is **flat** — 27.2% in 2010, 25.5%
in 2025. What changed is concentration: departments of 20+ doctorates that are
majority non-resident went from 82 to 193, and the share of all US doctorates
awarded inside them from 4.2% to 7.1%. In STEM alone, 1996-2025: 30 departments
to 162, and 3.7% to 12.9%. Quote the STEM series or the post-2010 series — never
a pre-2010 figure against a post-2010 one, because IPEDS recoded award levels in
2010 and the comparison measures the recoding.

## Notes and scratch work

Agent findings, audits and studies are in the session scratchpad, which is
temporary. Worth copying out if any of it matters: `chat_contract.md`,
`anchor_scheme.md`, `og_cards.md`, `name_signal_study.md`, `tools_provenance.md`,
`methodology_update.md`.
