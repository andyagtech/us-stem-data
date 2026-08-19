# Missing master's records — 16 universities investigated

Date: 2026-08-18. Scope: the 16 universities flagged as "well labeled but essentially
zero master's records, with no deliberate `degree_label: phd` override in CONFIGS".

Method: for each, (1) the configured endpoint/sets in `scripts/scrape_oai_etds.py`
`REPOS`, (2) a live OAI-PMH `ListSets` (and `ListIdentifiers` for sizes) against that
endpoint using `scrape_oai_etds.fetch_oai_page`, (3) the raw harvested CSV in
`data/western_us_dissertations/`. Step 3 is what separates "the master's records were
harvested and then thrown away at inference time" from "they were never requested".

## Headline

There is no single cause. The 16 split into three distinct failures:

1. **Dropped at inference** (records were in the CSV all along): `uutah`, `stony_brook`,
   `smu`, plus a brand-new regression at `dartmouth`.
2. **Never harvested** (the configured OAI set is genuinely dissertation-only, but the
   repository publishes a separate master's set we never asked for): `clemson`,
   `wayne_state`, `unh`, `usm`, `marquette`, `dartmouth`, `siu`, `duke`, `udel`.
3. **Genuinely PhD-only within the intended scope**: `caltech` (explicit, documented
   filter), `unl`, `yale`, `harvard` (with caveats recorded below).

## Per-university verdicts

### Dropped at inference — the records were already in the raw CSV

**uutah — SILENT LOSS (worst case in the list).**
`ir_etd` ("Institutional Repository - Theses & Dissertations") is a *single combined
set*: 8,092 harvested rows, of which `dc:description` carries a controlled type word —
`dissertation` 4,076, `thesis` 3,853, `honors thesis` 52, plus ~110 non-ETD items
(map, podcast, poster, portfolio). `infer_degree_type` read "dissertation" and returned
phd; nothing read "thesis", by design, because a bare "Thesis" means all graduate work
at most repositories. So 3,853 master's theses were harvested, parsed, and then
discarded as unlabeled.
Evidence that "thesis" = master's at Utah, not "graduate work": departments that appear
only under `thesis` and never under `dissertation` are exactly the ones Utah has no PhD
in — Architecture 84/0, Dance 73/0, Family & Consumer Studies 50/0, Art & Art History
32/0, College of Fine Arts 127/16 — and 180 creators appear once as `thesis` and again
later as `dissertation` (MS then PhD). Utah's undergraduate work is separately in
`ir_htoa`, so `ir_etd` is graduate-only.
Fix: `'thesis_vocab_field': 'description'` on the uutah CONFIGS entry, consumed by a new
opt-in controlled-vocabulary rule in `infer_degree_type`. No re-harvest needed.

**stony_brook — SILENT LOSS.**
`stony_brook_dspace_etds.csv` (REST harvest) holds `type` = `Dissertation` 2,269,
`Thesis` 1,667, `Text` 44. Only the first was labeled; 1,667 master's theses sat
unlabeled. Confirmed against the item pages: the deposited PDF keeps the ProQuest
filename, and `Dissertation` rows are `…_grad.sunysb_0771E_….pdf` (E = doctoral) while
`Thesis` rows are `…_grad.sunysb_0771M_….pdf` (M = master's) — e.g. handle 11401/71685
`Sagiv_grad.sunysb_0771M_10660.pdf` vs 11401/72376's doctoral counterpart.
Fix: `'thesis_vocab_field': 'type'`. No re-harvest needed.

**smu — SILENT LOSS.**
The configured set is the umbrella `publication:theses-and-dissertations`, so master's
theses *were* harvested: `type` = `Dissertation` 515, `Thesis` 196. SMU is configured
with `metadata_prefix: oai_etdms`, but a live `ListRecords` shows SMU's ETDMS records
carry no `thesis.degree.*` block at all — only `<type>Thesis</type>` /
`<type>Dissertation</type>` — which is why `degree_level`/`degree_name` are empty for
all 711 rows. The 196 `Thesis` rows are real master's work (e.g. `art_etds` MFA studio
theses).
Fix: `'thesis_vocab_field': 'type'`. No re-harvest needed.

**dartmouth — REGRESSION introduced today, now fixed.**
`data/etdms_degrees/dartmouth.json` (written 04:50 today by the ETDMS enrichment work)
sets `level: "Thesis (Ph.D.)"`, `name: ""` for all 454 records. `_etdms_lookup` checked
`name` for doctoral markers, found none, then fell through to "bare *Thesis* → MS" — so
a level string that literally says Ph.D. was being read as a master's. Measured live at
05:23: dartmouth 44 phd / 343 ms, where the manifest had 387 phd / 0 ms.
Fix: `_etdms_lookup` now checks the *level* string for `ph.d`/`phd`/`ed.d`/`doctor`
before the bare-"Thesis" fallback. This restores 387 phd / 0 ms — which is correct, not
a whitewash: the live `ListSets` name for the harvested set `publication:dissertations`
is verbatim **"Dartmouth College Ph.D Dissertations"**. Dartmouth's master's theses are
in a different set entirely (below).

### Never harvested — dissertation-only set configured, master's set exists

For all nine, the harvest is internally consistent (100% phd, 0 unlabeled) because the
configured set really does contain only dissertations. The loss is one level up: the
repository publishes a master's set that `REPOS` never asked for, and nothing in the
manifest distinguished "this university awards no master's" from "we never looked".

| key | configured set (setName from live ListSets) | master's set never harvested | size |
|---|---|---|---|
| clemson | `publication:all_dissertations` — All Dissertations | `publication:all_theses` — All Theses | 4,751 |
| wayne_state | `publication:oa_dissertations` — Wayne State University Dissertations | `publication:oa_theses` — Wayne State University Theses | 956 |
| unh | `publication:dissertation` — Doctoral Dissertations | `publication:thesis` — Master's Theses and Capstones | 1,971 |
| usm | `publication:dissertations` — Dissertations | `publication:masters_theses` — Master's Theses | 1,191 |
| marquette | `publication:dissertations_mu` — Dissertations (1934 -) | `publication:theses_open` — Master's Theses (2009 -) | 868 |
| dartmouth | `publication:dissertations` — Dartmouth College Ph.D Dissertations | `publication:masters_theses` — Dartmouth College Master's Theses | 312 |
| siu | `publication:dissertations` — Dissertations | `publication:theses` — Theses | 3,407 |
| duke | `col_10161_4` — Dissertations | `col_10161_2493` — Master's Theses | 1,370 |
| udel | `col_19716_12883` + `col_19716_20898` — Doctoral Dissertations | `col_19716_5010` — Master's Theses (Fall 2009 to Present) | 2,445 |

Fix: master's set added to each `REPOS` entry and harvested (background, resumable,
1.5s delay, append-only onto a backed-up CSV); the corresponding CONFIGS entries now
carry explicit `phd_sets` / `ms_sets` so each record is labeled from the curated
collection it came from rather than from a heuristic.

`udel` also had a second, unrelated defect: 244 of its 250 unlabeled rows were
*doctorates* whose `degree_level` is `D.Ed.` (187), `D.N.P.` (31) or `D.Eng.` (6) —
abbreviations the doctoral prefix list did not contain. Added.

### Genuinely PhD-only within the intended scope

**caltech — LEGITIMATELY PhD-only, and it is already explicit.** Not an OAI harvest at
all: `data/caltech_dissertations/caltech_dept_alumni_combined.csv` holds 3,171 rows,
`degree_type` = phd 2,927 / masters 244, and CONFIGS carries
`'degree_filter': 'phd'`, which `load_records` applies with the comment "Caltech has
phd + masters". The master's records are excluded deliberately and visibly. No change
made — reversing that filter would be a scope decision, not a bug fix.

**unl — effectively PhD-only; no change to labels, but flagged.** The single configured
set `publication:dissertations` is named "ETD Collection for University of
Nebraska-Lincoln" — a ProQuest-fed feed (AAI identifiers) that in principle covers
theses as well as dissertations. Neither the OAI record nor the bepress item page
carries any degree field, so the degree is unknowable from this source; the CSV's
`degree_type: phd` is a backfilled assumption. The volume supports it: 259-323 records
per year for 2010-2023, which matches UNL's doctoral output, not doctoral + master's.
UNL's master's theses live in ~100 departmental sets ("Department of X: Dissertations,
Theses, and Student Research", "Embargoed Master's Theses", "Archival Master's Theses"),
with no umbrella. Recorded intent as `'phd_sets': ['publication:dissertations']`; did
not attempt the departmental sets — that needs a curated list, not a heuristic.

**yale — PhD-only as configured; master's theses are out of the configured scope.**
`publication:gsas_dissertations` = "Yale Graduate School of Arts and Sciences
Dissertations" is doctoral-only, and all 1,444 rows label cleanly. Yale's master's-level
theses are scattered across professional-school sets that we do not harvest:
`ysphtdl` Public Health 1,119, `ysmpa_theses` PA program 215, `ysndt` Nursing 206,
`divinity_theses` 23, `envdesign` 15, `publicpolicy_theses` 11, plus `ymtdl` Yale
Medicine 3,261 (MD theses — neither PhD nor master's). Adding these is a scoping
decision about whether "Yale" means GSAS; not taken here. Recorded
`'phd_sets': ['publication:gsas_dissertations']`.

**harvard — PhD-only for master's purposes, but the collection is contaminated with
undergraduate theses.** The configured `col_1_4927603` is "FAS Theses and
Dissertations"; of 9,505 harvested rows, `degree_level` is Doctoral 8,529, Bachelor's
490, Undergraduate 442, UNDERGRADUATE 30, MASTERS 6. So the 967 unlabeled rows were
never master's — they are *undergraduate* AB/SB theses that were being carried in a PhD
dataset as unlabeled records. Harvard master's work is in other schools' collections we
do not harvest (`col_1_14557739` DCE/ALM 2,206, `col_1_13398958` GSD 550,
`col_1_13056148` GSE 448, `col_1_13398961` SPH 429, `col_1_11407445` HSDM 132,
`col_1_13398959` HBS 89, `col_1_13398960` HDS 63; plus `col_1_11407446` HMS 1,396 MD
theses) — again a scoping decision, not taken here.
Fix applied: `degree_level` containing "bachelor"/"undergraduate" now returns `bs`, so
those 739 in-window undergraduate theses are excluded rather than counted as unlabeled.

## Changes made

`scripts/generate_name_lists.py` (surgical; four edits in `infer_degree_type` /
`_etdms_lookup`, plus per-university CONFIGS keys):

1. `_etdms_lookup`: a `level` containing `ph.d` / `phd` / `ed.d` / `doctor` returns phd
   before the bare-"Thesis" fallback. Fixes dartmouth's "Thesis (Ph.D.)".
2. `infer_degree_type`: new `ms_sets` / `phd_sets` config lists, matched against the
   record's own `oai_set`, so curated collections give a deterministic answer (needed
   for DSpace, whose set specs are opaque handles like `col_10161_2493`). A record whose
   own `type` says master's outranks the collection it was filed in.
3. `infer_degree_type`: new opt-in `thesis_vocab_field` for repositories that publish a
   controlled `dissertation` / `thesis` / `honors thesis` vocabulary (uutah in
   `description`, smu and stony_brook in `type`). Deliberately opt-in — a bare "Thesis"
   still means nothing at repositories that use it for all graduate work.
4. `infer_degree_type`: `degree_level` containing "bachelor"/"undergraduate" returns
   `bs`; `d.ed` / `d.eng` / `d.n.p` added to the doctoral abbreviation prefixes.

`scripts/scrape_oai_etds.py`:

5. Master's sets added to the `REPOS` entries for clemson, wayne_state, unh, usm,
   marquette, dartmouth, siu, duke, udel.
6. **Append bug fixed** (would have corrupted every CSV otherwise): `main()` opened the
   existing CSV in append mode but wrote through a `DictWriter` bound to `CSV_FIELDS`.
   The files on disk do not all have those columns — clemson/unl/wayne_state/siu/unh/
   usm/dartmouth/marquette have 17 (an extra `degree_type`), yale/uutah 16, duke 19,
   harvard 20, udel 21 — so every appended row would have landed shifted against the
   header. It now reads the existing header and appends in the file's own column order.
   This also affects the existing `--from` selective-harvest path.

Not touched: `pipeline/manifest.json`, `pipeline run`, the ETDMS enrichment scripts and
data, and the universities owned by other agents.

## Side effects outside the 16

The `degree_level` bachelor/undergraduate rule also drops previously-unlabeled
undergraduate theses at five other universities. No phd or ms count changes anywhere:
rpi 1,588 -> 1,580 records, bu 11,627 -> 11,444, upenn 5,631 -> 5,619,
mines 8,276 -> 8,250, utaustin unchanged.

## Before / after

Measured with `load_records()` — the same level the manifest's `records` block reports;
the "before" column reproduces the manifest figures exactly. Format: total / phd / ms /
unlabeled.

| university | before | after | what changed |
|---|---|---|---|
| harvard | 4873 / 4126 / 3 / 744 | 4134 / 4125 / 3 / 6 | 739 undergraduate theses now excluded, not counted as unlabeled; still no master's (out of scope) |
| udel | 2690 / 2446 / 23 / 221 | 3977 / 2667 / 1310 / 0 | master's collection harvested; D.Ed./D.N.P./D.Eng. now labeled |
| caltech | 2435 / 2435 / 0 / 0 | 2435 / 2435 / 0 / 0 | no change — deliberate `degree_filter: phd` |
| duke | 2261 / 2260 / 1 / 0 | 2934 / 2260 / 674 / 0 | master's collection harvested |
| clemson | 1758 / 1758 / 0 / 0 | 3360 / 1758 / 1602 / 0 | master's collection harvested |
| uutah | 1569 / 1064 / 0 / 505 | 1569 / 1064 / 490 / 15 | no re-harvest — the master's were already in the CSV |
| unl | 1349 / 1349 / 0 / 0 | 1349 / 1349 / 0 / 0 | no change — intent recorded, gap documented |
| wayne_state | 1138 / 1138 / 0 / 0 | 1454 / 1138 / 316 / 0 | master's collection harvested |
| yale | 919 / 919 / 0 / 0 | 919 / 919 / 0 / 0 | no change — intent recorded, gap documented |
| siu | 667 / 667 / 0 / 0 | 1797 / 667 / 1130 / 0 | master's collection harvested |
| stony_brook | 561 / 397 / 0 / 164 | 561 / 397 / 139 / 25 | no re-harvest — the master's were already in the CSV |
| unh | 506 / 506 / 0 / 0 | 1211 / 506 / 705 / 0 | master's collection harvested |
| smu | 473 / 361 / 0 / 112 | 473 / 361 / 112 / 0 | no re-harvest — the master's were already in the CSV |
| usm | 443 / 443 / 0 / 0 | 832 / 443 / 389 / 0 | master's collection harvested |
| dartmouth | 387 / 44 / 343 / 0 | 558 / 387 / 171 / 0 | ETDMS "Thesis (Ph.D.)" regression fixed; master's collection harvested |
| marquette | 346 / 346 / 0 / 0 | 767 / 346 / 421 / 0 | master's collection harvested |

Two notes on the dartmouth row. Its "before" is the *live* state at 05:23 today
(44 phd / 343 ms), not the manifest's 387 / 0 — the ETDMS enrichment written at 04:50
had already flipped it. The "after" 387 phd is not a fallback-to-PhD: the harvested set
is named "Dartmouth College Ph.D Dissertations", every ETDMS level says
"Thesis (Ph.D.)", and Dartmouth's actual master's theses arrived from the separate
`publication:masters_theses` set as the 171 ms.

Master's records recovered in-window across the 16: 0 -> 7,459.
Records added to the raw CSVs: 4,751 clemson, 3,407 siu, 2,445 udel, 1,971 unh,
1,370 duke, 1,191 usm, 956 wayne_state, 868 marquette, 300 dartmouth (17,259 total,
each matching the set's `completeListSize` exactly, appended with per-identifier dedup).

### One master's collection deliberately left out

UDel's `col_19716_21710` ("Master's Theses (before Fall 2009 -- partial holdings)", 606
records) was harvested and then removed again. Its `dc:date` is the 2020 bulk-ingest
timestamp, not the degree year — the real year is a *third* `dc:date` value that the
parser (which takes the first) drops. Left in, it put 525 pre-2009 theses into 2020.
The set is now excluded in `REPOS` with that reason recorded in a comment, its rows were
removed from the CSV (all other rows untouched, `.pre_masters.bak` intact), and its
checkpoint entry was cleared. The general defect — bepress/DSpace records whose first
`dc:date` is an accession timestamp — is not fixed here; it is a separate scraper
change with a much wider blast radius.

## Logs and artifacts

- Master's harvest log: `/private/tmp/claude-501/-Users-andy-usds-china/5f48248f-d0fc-4a8c-9b94-e31e685a7ff6/scratchpad/harvest_masters.log` (runner: `/private/tmp/claude-501/-Users-andy-usds-china/5f48248f-d0fc-4a8c-9b94-e31e685a7ff6/scratchpad/harvest_masters.sh`)
- Live `ListSets` dumps: `/private/tmp/claude-501/-Users-andy-usds-china/5f48248f-d0fc-4a8c-9b94-e31e685a7ff6/scratchpad/sets_bepress.txt`, `/private/tmp/claude-501/-Users-andy-usds-china/5f48248f-d0fc-4a8c-9b94-e31e685a7ff6/scratchpad/sets_dspace.txt`
- Pre-append CSV backups: `data/western_us_dissertations/{key}_etds.csv.pre_masters.bak`
  for the nine re-harvested repositories.
