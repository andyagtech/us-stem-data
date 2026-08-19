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

1. **Chat backend is still the April v1.** Confirmed by config: 256 MB, 30 s
   timeout, last modified 2026-04-07, versus the built 1024 MB / 45 s version.
   Its prompt carries hardcoded statistics that yesterday's corrections
   contradict, so under attention it will state numbers the pages disagree with.
   Deploy with `infra/chat/deploy.sh`. 81 offline tests pass. Never deployed.

2. **JSON is served gzip unconditionally.** Pre-compressed S3 objects assert
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

3. **Award-date defect, unchanged.** OAI harvests took `dc.date.accessioned`
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
