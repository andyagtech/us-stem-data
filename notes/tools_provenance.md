# tools_provenance.py — coverage_for, caveats_for, cite

> **Superseded in part, 2026-08-22.** This is a point-in-time audit and is kept
> as written. One finding it records has since been resolved: the caveat
> `mit_lca_total_is_contaminated` has been **retired from the registry**. Its
> own stated test was whether MIT's LCA total still read near 565,883; the
> employer match is exact rather than substring, MIT's total now reads in the
> low thousands with academic job titles, and the caveat only made the
> assistant refuse a question it can answer. Every `565,883` below is therefore
> historical. See `data/h1b/LCA_ARCHIVE.md` for the current LCA read path,
> which was separately found to be dropping five whole files.


Module: `/Users/andy/usds_china/cloud/chat/tools_provenance.py` (1,611 lines; ~105 of them
are the embedded coverage table). Exports exactly `SCHEMAS` (3 dicts) and `IMPL`
(3 callables), plus a `run(name, args)` convenience runner mirroring
`tools.run_data_tool`. Nothing else in the repo was edited.

Imports `_fn`, `_clamp`, `UNTRUSTED` from `tools` and `data_store as ds`, with the
package/flat dual-import pattern `tools.py` uses. Both layouts tested.

## DEPLOYMENT NOTE FOR THE WIRING OWNER

`infra/chat/deploy.sh` line ~43 copies an explicit file list into the Lambda bundle:

    for f in handler.py prompt.py tools.py blocks.py data_store.py; do

`tools_provenance.py` must be added there or the module is absent at runtime. The
file's module docstring repeats this.

Related: `pipeline/manifest.json` is NOT bundled (deploy.sh copies only
`chat_data/*.{csv,csv.gz,json}`). The manifest fields are therefore embedded as a
dated snapshot in `_COVERAGE_ROWS` / `COVERAGE_SNAPSHOT`, with the regeneration
one-liner stored alongside. Snapshot is from the process run of 2026-08-18T23:31,
all 105 universities.

---

## 1. THE THREE SCHEMAS

### coverage_for

```
name: coverage_for
required: [university]
params:
  university : string — key, e.g. mit, njit, iowa_state
description:
  What this project holds for one university and, more usefully, what it does NOT,
  so a figure can be quoted with its completeness attached. Returns the dissertation
  record count, the PhD / master's / unlabelled split and the labelling rate, plus a
  held / not-held list across H-1B, OPT, LCA, PERM, enrolment, funding and department
  links, each absence with its reason. Call this before quoting a university-level
  count, before ranking universities on a federal source, and whenever a reader asks
  how complete the data is. Two things it will tell you that are easy to get wrong: a
  missing OPT figure means SEVP's Top-100 publication did not cover that campus, not
  that no students were on OPT; and a low labelling rate means the PhD / master's
  split is uncertain, not that records are missing.
```

### caveats_for

```
name: caveats_for
required: [topic]
params:
  topic    : string — metric, dataset, university key, or phrase
  severity : enum high|medium|all  (default all)
  limit    : integer 1-12 (default 6)
description:
  The registry of known, verified limitations, looked up by metric, dataset or
  university. Every entry names the code or data it was checked against, and a few
  carry a `correction` where a claim this project has written down elsewhere turned
  out not to hold. Call this before presenting a comparison across years, a
  federal-source figure, a name-origin percentage, or any number a sceptical reader
  would push back on, and put the relevant caveat in a show_notice rather than
  burying it. Topics that work: a metric (nra_share, completions_trend,
  foreign_name_pct, opt, h1b, lca, state_funding), a dataset (ipeds_completions,
  sevp, dol), a university key, or a phrase (award level, cip, name classification,
  labelling).
```

Matching: exact id / applies_to / keyword, then substring, then a university-key
branch that returns entries naming that university FIRST, then always-scope entries,
then dataset entries for sources it actually holds, then metric entries — sorted so
a truncated list never drops the campus-specific one.

### cite

```
name: cite
required: [metric]
params:
  metric     : string — nra_share, completions_trend, enrollment_ipeds, faculty,
               tuition, opt, h1b, lca, perm, funding, federal_support, nsf_awards,
               nih, state_funding, dissertation_records, foreign_name_pct,
               visa_issuances, sed, overstay … aliases resolve
  university : string — optional key, adds the institution and its UNITID
  year       : integer — optional; named in the citation, warns if out of coverage
description:
  A citation the reader can paste into a footnote: the publishing agency, the
  specific file or survey table, the survey / fiscal / calendar year, the retrieval
  date where this project recorded one, and a stable URL where one exists. …It also
  returns the ids of the caveats that attach to that metric, which you can expand
  with caveats_for.
```

25 citation entries. Each returns a formatted `citation` string plus structured
`publication / agency / file / period / retrieved / url / derivation / caveat_ids /
coverage_years`, and a `show_link_hint` where a URL exists.

---

## 2. WORKED RESULTS (real output)

### coverage_for("mit") — abridged

```json
{"source": "pipeline/manifest.json snapshot, process run 2026-08-18T23:31 …",
 "university": {"key":"mit","name":"MIT","unitid":"166683","url":"/universities/mit.html"},
 "records": {"stem_total":14203,"phd":3409,"ms":3374,"unlabelled":7420,
             "nonstem_total":2657,"record_years":[2016,2026]},
 "labelling": {"labelled":6783,"unlabelled":7420,"label_pct":47.8,
   "reading":"7,420 of 14,203 STEM records carry no degree label. Those records are
              present and counted in the total; only their PhD/master's split is
              unknown. Do NOT compute a PhD share as 3,409/14,203.",
   "warning":"label_pct is 47.8%. Quote the 14,203 total confidently; quote the 3,409
              PhD figure only as 'at least', with the labelling rate stated."},
 "held": [h1b (17y), opt (8y), lca (565,883 certs), perm, enrollment, funding, dept_links],
 "not_held": [],
 "coverage_notes": [
   "OPT covers 8 year(s). SEVP's source is a Top-100 list … only 59 of the 105 …",
   "Degree labelling is 47.8% against a corpus rate of 88.8%.",
   "record_years 2016-2026 is the range of the STORED year, which for most
    universities is the repository's ingest timestamp rather than the award date …",
   "MIT's shipped LCA total is wrong: a three-letter employer pattern swept in the
    national H-1B filers. (caveats_for 'mit_lca_total_is_contaminated')"],
 "corpus_context": {"universities":105,"stem_records":369319,"corpus_label_pct":88.8,
   "universities_with_opt":59,"universities_with_h1b":101,"universities_with_lca":100,
   "universities_with_perm":71,"universities_with_funding":80},
 "caveat_ids": [13 ids],
 "scope": "Record counts are the STEM track of this project's harvested dissertation
           corpus, not an IPEDS degree count and not an enrolment count. …",
 "_untrusted": "<standard banner>"}
```

`coverage_for("montana_state")` (a newly added university, all seven flags false)
additionally emits: "EVERY federal source is absent for this university, which almost
always means the enrichment step has not yet been run for it rather than that seven
separate matches failed."

`coverage_for("njit")` → 777 records, 100% labelled, `not_held: [perm]` with reason
"No PERM certification matched. Many universities sponsor few or no green cards
directly, so an absence here is often real, not a gap."

### caveats_for("nra_share") → 5 matched

`ipeds_award_level_break` (high, with correction) · `nra_is_a_reporting_category`
(high) · `awlevel17_is_not_the_sed_universe` (medium) ·
`completions_trend_is_all_fields` (medium) · `ipeds_cip_vintages` (medium)

`caveats_for("mit")` → `mit_lca_total_is_contaminated` first, then
`harvest_year_is_often_a_deposit_date`, `ipeds_award_level_break`,
`labelling_rate_uncertainty`, `lca_year_buckets_are_calendar`,
`name_origin_is_not_visa_status` (14 matched, 6 returned).

`caveats_for("zzz")` → 0 matched, with: "Nothing registered for that topic. That means
no verified limitation is on file - not that the figure is unqualified." plus the id list.

### cite("nra_share", university="mit", year=2023)

> National Center for Education Statistics, U.S. Department of Education. IPEDS
> Completions survey, component C part A (awards by CIP x award level x
> race/ethnicity x sex). MIT (IPEDS UNITID 166683). Data year 2023 (source coverage:
> Data years 1995-2025; the year is the end of the academic year, so 2025 is the
> provisional 2024-25 release). File: data/ipeds/c{year}_a.csv (exact release
> preferred, _rv revised as fallback), aggregated into the bundled index
> nra_index.csv.gz by scripts/build_nra_index.py. Retrieved 2026-07-13 (data year
> 2025 added; earlier years 2026-03-08). https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx

caveat_ids: ipeds_award_level_break, ipeds_cip_vintages, nra_is_a_reporting_category,
awlevel17_is_not_the_sed_universe. derivation: "Research doctorates only: award level
17 from 2010, award level 9 before the recoding, per-institution basis in 2008-2009.
First majors only. CIPCODE 99 institution-aggregate rows excluded. nra_share =
CNRALT / CTOTALT."

`cite("opt", year=1800)` → full citation plus
`warning: "1800 is outside the coverage of this source (2017-2024). Do not cite it for
that year."`

---

## 3. CAVEAT REGISTRY — 20 entries, with what each was verified against

| id | sev | verified against |
|---|---|---|
| `ipeds_award_level_break` | high | `scripts/build_nra_index.py:165-211`; `data/ipeds/nra_index_meta.json`; `nra_ground_truth/_metadata.md`; my own AWLEVEL tabulation of c2006-c2010 (0 institutions in both blocks, any year) |
| `ipeds_cip_vintages` | med | `data/ipeds/nra_index_meta.json` cip_vintages |
| `nra_is_a_reporting_category` | high | `nra_index_meta.json` "measure"; `data/DATA_DICTIONARY.md` |
| `name_origin_is_not_visa_status` | high | `scripts/name_classifier.py` (no visa/citizenship field exists); `scripts/name_signal_study.py` re-run read-only, reproducing 0.059 / 0.026 / RMSE 0.112 exactly |
| `harvest_year_is_often_a_deposit_date` | high | `scrape_oai_etds.py:1274` takes first `dc:date`; live GetRecord vs iastate + MIT; clock-time census of all 105 CSVs (407,462 / 1,035,726 = 39.3%) |
| `northwestern_years_were_deposit_dates` | high | `refresh_frozen_etds.py`; `northwestern_etds.csv.bak_predatefix` joined to current file on id |
| `uva_2026_records_have_no_degree_date` | high | `refresh_frozen_etds.py` stores `publishedAt`; direct UVA API fetch; timestamp census of `uva_etds.csv` (15,162 rows) |
| `opt_top_100_only` | high | `opt_by_university.json` has 59 keys; source PDFs literally named `top100-*`; manifest opt true for 59/105 |
| `labelling_rate_uncertainty` | high | `LABELING_METHODOLOGY.md`; manifest summed: 327,802 labelled of 369,319; min 24.8 (montana_state), max 100.0 |
| `uscis_h1b_is_employer_level` | med | `entity_map.json`, `system_h1b_map.json`, manifest `h1b_system_note` |
| `sheeo_state_funding_is_a_state_proxy` | high | `scripts/build_sheeo_json.py` `_meta` note |
| `awlevel17_is_not_the_sed_universe` | med | `nra_ground_truth/_metadata.md` (82,438 vs ~57,900) |
| `lca_year_buckets_are_calendar` | high | `step3_parse_federal.py` `find_col("FISCAL_YEAR","DECISION_DATE")`; header scan (0 with FISCAL); **case-number containment measured on the sheet XML of FY2026 Q1 vs Q3 (83,120/83,120 contained, 0 absent) and FY2025 Q1 vs Q4 (595 shared, 0.55%)**, using each file's autoFilter ref for the true data extent |
| `mit_lca_total_is_contaminated` | high | `_match_employer()` docstring + word-boundary regex; `entity_map.json` "MIT"; `lca_by_university.json` mit=565,883 with Infosys job titles, next upenn=5,616; **bundled `universities_compact.json` still carries 565,883** |
| `overstay_report_off_by_one` | med | pdftotext of `dhs_overstay_fy2025.pdf` pp.1-6; its `/Title` objects are both "…FY25" and "…FY24"; identical CreationDate with the fy2024 file |
| `lsu_federal_support_is_system_office` | high | `build_federal_support_json.py` `NAME_OVERRIDES['lsu']` + `SYSTEM_LEVEL={'lsu'}`; tab017 has no Baton Rouge LSU row; `site/data/stem/lsu.json` `system_level: true` |
| `nra_site_figure_is_pinned` | high | `universities.json` carries `nra` with no basis fields; I recomputed MIT 43.8% = 2,175/4,962 (2015-2023), Mines 39.8% = 385/967, Binghamton 56.9% = 388/682 — exact; a sweep of 4 CIP bases × 35 windows leaves 49 of 105 unreproducible |
| `completions_trend_is_all_fields` | med | `build_chat_facts.py` `digest_university()`; `enrich_university_json.py` `load_ipeds_completions()` |
| `ipeds_panels_are_dated_snapshots` | med | `enrich_university_json.py` lines 257/433/452/475 — each opens one fixed-year file (Fall 2022 enrolment, Fall 2022 staff, AY2023 tuition, AY2022-23 aid) while ef2024a sits unused on disk |
| `usaspending_partial_coverage` | med | `usaspending_by_university.json` has 26 keys against 105 |

Seven of the twenty carry a `correction` field, used where a claim written down in
this project turned out to be wrong in part.

---

## 4. DOCUMENTED CLAIMS I COULD NOT CONFIRM

Four of the seven briefed caveats needed correcting; a fifth (LCA) was correct as briefed and my first attempt to correct it was itself wrong — see (c). All are recorded in the registry
as `correction` text rather than being repeated.

**(a) "Level 9 also counted MD and JD" — FALSE.** MD (CIP 51.1201), JD (22.0101),
DDS (51.0401), DVM, PharmD were AWLEVEL 10 "first-professional" before 2010 and
AWLEVEL 18 after — outside the research bucket in both schemes, zero under level 9 in
any year. (CIP family 22 does show 143 awards at level 9 in 2007: SJD research
doctorates in law, not JDs.) The caveat's real basis: level 9 was the
undifferentiated "Doctor's degree", split in 2010 into 17 and 18, with PharmD/DPT/AuD
moving to 18. Health CIP 51: 8,356 at level 9 in 2007 vs 3,955 at level 17 in 2010.
Zero overlap in 2008-2009 is confirmed, and stronger than briefed — it holds for the
whole `{9,10,11}` vs `{17,18,19}` blocks, in every year. Two institutions did revert
(new scheme 2008, old 2009), so "one-by-one" is not strictly monotone. Also: the
break distorts levels and counts far more than shares — national NRA share is 28.2%
(2007, aw09) → 27.3% (2010, aw17), and the recode moved share by only ~+2.2pp among
the 398 institutions switching 2009→2010.

**(b) Harvest lag figures — two of four do not reproduce.** Mechanism confirmed
(first `dc:date` is the DSpace accession timestamp; live GetRecord evidence).
MIT 22% outside window → measured **19.2%**, consistent. Iowa State median lag 24
years → **24.0**, exact. But Iowa State "84% outside window" → measured **59.9%**
(63.6% under the most generous definition), 4+ SE away, and no definition reached 84%.
MIT median lag 39 years → measured **49.5**. Additional finding: the harvester fix
computes an issued date but it never reaches disk, because a selective re-harvest
reuses the existing header with `extrasaction="ignore"`. No CSV in the repo has a
`date_issued` column. Northwestern and UVA both confirmed; the Northwestern fix is
uncommitted working-tree state, and commit 5213be1's stated justification ("real
graduation dates, not bulk imports") is contradicted by the pre-fix file, whose
newest rows are a repeated `2026-03-25T00:00:00Z` batch.

**(c) LCA — the calendar-year half is true; my first attempt at the cumulative half
was WRONG and has been re-verified.** Confirmed true: 0 of the LCA files carry a
fiscal-year column, so buckets are calendar years from `DECISION_DATE`; and calendar
2014 is a one-quarter stub (13,909 vs 89,589 in 2015).

I initially wrote that FY2026 files are *not* cumulative, reasoning from row counts
(FY2026 Q1 = 1,042,437 rows vs FY2025 Q4 = 563,689). That was invalid twice over and
the conclusion was wrong. Row counts test whether one file is *larger*, not whether a
later file *contains* an earlier one; and the counts themselves were inflated by empty
style-only padding rows. Re-measured directly on the sheet XML of both releases, using
each file's `autoFilter` ref for the true data extent:

| release | real records | decision-date span |
|---|---|---|
| FY2026 Q1 | 83,120 | 2025-10 → 2025-12 |
| FY2026 Q3 | 437,496 | 2025-10 → 2026-06 |

**Q1 ∩ Q3 = 83,120 (100.000% of Q1); Q1 − Q3 = 0.** FY2026 files ARE cumulative
year-to-date, exactly as originally briefed. (The FY2026 Q1 file's 1,042,437 "rows"
are really 83,120 records plus 959,317 empty padding rows — `autoFilter ref="A1:CT83121"`.)

One thing the registry now adds that neither of us had: **this is a CHANGE in DOL
practice, not a standing one.** FY2025 quarters are discrete — FY2025 Q1 (2024-10 →
2024-12) and FY2025 Q4 (2025-07 → 2025-09) share only 595 case numbers, 0.55%. So
FY2013–FY2025 are unaffected and are not double-counted; only FY2026 needs the
one-file-on-disk rule. That is also why the change went unnoticed for thirteen fiscal
years.

Also recorded, per the coordinator: `lca_FY2026_Q1.xlsx` is now in
`data/h1b/lca/superseded/`, and moving the workbook is **not** sufficient —
`_parse_lca_duckdb()` derives its conversion list from the `.xlsx` files in `lca/` but
then aggregates `csv_dir.glob("*.csv")` independently, so a previously converted
`csv_cache/lca_FY2026_Q1.csv` would still be read and summed. The cache is keyed by
filename and never notices the source moved. (`csv_cache/` does not exist right now, so
nothing is stale today.) This is carried on the entry as a distinct `operational_note`
field, surfaced by `caveats_for`.

Consequence now live: with Q3 the newest file, **calendar 2026 covers January–June
only** and will read as a collapse if presented as an annual total — which is the risk
the original briefing flagged.

**(d) "Overstay PDFs are named by CBP reporting cycle, a year ahead" — FALSE as a
general rule.** `dhs_overstay_fy2023.pdf` carries FY2023 data and
`dhs_overstay_fy2024.pdf` carries FY2024 data; filename equals data year for both.
Only `dhs_overstay_fy2025.pdf` is misnamed — it is a second rendering of the FY2024
report (identical PDF CreationDate) with an FY2025 cover. `data/vwp/DATA_SOURCES.md`
states the general rule and its rows for the 2023 and 2024 files are wrong; anyone
following its "subtract one from the filename year" instruction would misdate two of
three files. (Note: nothing in the repo parses these PDFs; the published 0.43% /
2.22% rates are hardcoded in `build_og_cards.py` with no data year attached.)

**(e) "LSU appears only at system level in the NCSES federal support survey AND in
USCIS H-1B data" — half false.** Federal support: true and verified. USCIS H-1B:
false. `system_h1b_map.json` has no LSU entry (its only key is `missouri_st`), no
system note is attached to `site/data/stem/lsu.json`, and 85 of LSU's 87 FY2025
approvals are Baton Rouge rows. What is actually wrong with that series is different:
the employer variant "LOUISIANA STATE UNIV" matches no pattern, so 2015/2016/2018 read
as 1-2 approvals against real Baton Rouge filings in the dozens — matcher misses, not
declines. Also "only LSU" is false: UNH is matched to "U. System New Hampshire" and is
NOT flagged `system_level`, and Table 17 carries 15 system-office rows.

**Confirmed without correction:** the name-classification numbers (0.059 / 0.026 /
RMSE 0.112, reproduced exactly by re-running `name_signal_study.py` read-only) and
"NRA is a federal reporting category for visa holders, not ethnicity or national
origin". Two honest qualifiers recorded on the name entry: those are the pooled panel
(the by-year panel gives +0.055 / +0.038 with RMSE 0.150), and on the current
`data/processed` corpus the increments are +0.073 / +0.033 with RMSE 0.109 — same
conclusion, snapshot-bound decimals. Also recorded: RMSE is a typical error, not a
bound, so "could be 29% or 51%" describes typical error, not a range.

---

## 5. THINGS FOUND ALONG THE WAY THAT ARE NOT MY FILE'S PROBLEM

1. **MIT's LCA figures are wrong in the currently shipped data.** The matcher was
   fixed to require word boundaries; `data/h1b/lca_by_university.json`,
   `pipeline/manifest.json` and `cloud/chat/chat_data/universities_compact.json` were
   never rebuilt. `get_university_facts('mit')` returns `lca.total_lcas = 565883`
   today. The registry warns about it; regenerating the artefacts would fix it.
2. **`infra/chat/deploy.sh` needs `tools_provenance.py` added to its copy list.**
3. `cloud/chat/test_local.py` currently fails one assertion —
   "fabricated chart was rejected" (`blocks_rejected == 1`). This is in the in-flight
   `handler.py` / `prompt.py` rewrite, not mine: nothing imports `tools_provenance`
   yet, and my module touches no block, ledger or chart code.
4. `data/DATA_DICTIONARY.md` documents AWLEVEL as "9 = Doctor's - research/
   scholarship, 10 = professional practice, 11 = other". That is wrong for every
   vintage: pre-2008 it is 9 doctor's / 10 first-professional / 11 first-professional
   certificate, and from 2010 it is 17 / 18 / 19.
5. `data/vwp/DATA_SOURCES.md`'s off-by-one blockquote is inserted *inside* a markdown
   table, orphaning the two rows that follow it.

6. **One entry in this registry was wrong and has been fixed.** My first LCA entry
   denied that FY2026 DOL files are cumulative, inferring it from row counts. The
   coordinator challenged it; direct case-number containment on the sheet XML showed
   full containment, and the row counts I used were padding-inflated. The entry now
   records the true finding plus a `correction` field naming my own error, so the bad
   inference cannot be re-derived from the registry. Method note for anyone extending
   this: for these workbooks, read `autoFilter ref` for the real data extent — the
   `dimension ref` includes empty padding rows and overstates FY2026 Q1 by 12x.

## 6. TESTING

- All 3 tools exercised over: every one of the 25 citation keys, every one of the 20
  caveat ids, and all 105 university keys — no errors, no dangling caveat ids, no
  alias collisions.
- Hostile inputs: empty/None/500-char/NUL-and-ANSI-escape topics and keys, non-int
  years and limits, non-dict args, unknown tool name. All return structured errors;
  nothing raises. Control characters are stripped by `ds.clean_text` before matching,
  so an injected string fails to resolve rather than propagating.
- Imports verified under both the package layout (`chat.tools_provenance`) and the
  flat Lambda layout (`import tools_provenance`).
