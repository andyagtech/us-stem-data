# IPEDS doctoral NRA ground truth — build and validation

Built 2026-08-18. Both required sanity checks PASS and the CIPCODE 99
reconciliation is exact (0 mismatching keys across all 30 years).

## Output paths

All under `/Users/andy/usds_china/data/ipeds/nra_ground_truth/` (5.1 MB total).

| file | grain | rows | size |
| --- | --- | --- | --- |
| `doctoral_nra_by_cip.csv.gz` | unitid x year x awlevel x cipcode x majornum | 298,861 | 3.0 MB |
| `doctoral_nra_by_cip2.csv.gz` | unitid x year x awlevel x 2-digit CIP family x majornum | 135,238 | 1.6 MB |
| `doctoral_inst_totals.csv.gz` | unitid x year x awlevel x majornum (the CIPCODE 99 aggregate) | 40,065 | 0.65 MB |
| `_metadata.md` | provenance, exclusions, scheme handling | — | 5 KB |

Builder: `/Users/andy/usds_china/scripts/build_ipeds_nra_ground_truth.py`

```
python3 scripts/build_ipeds_nra_ground_truth.py --validate
python3 scripts/build_ipeds_nra_ground_truth.py --validate-only
python3 scripts/build_ipeds_nra_ground_truth.py --years 2026     # when a new year lands
```

It streams each source CSV once, holds only per-year rollups in memory, writes
no intermediates, and does not touch the raw files.

### Format note

Gzipped CSV, not Parquet. Neither `duckdb`, `pandas`, nor `pyarrow` is
importable in this environment (`pip list` shows only pip/wheel/xlrd/uharfbuzz),
and the volume had ~500 MB free, so installing them was not viable. The script
is written so a Parquet writer can be swapped in at the three `csv.writer`
call sites without touching the extraction logic.

## Schema

Identical measure columns in all three files:

```
unitid, year, awlevel, [cipcode | cip2], majornum,
total, total_men, total_women,
nra, nra_men, nra_women,
asian, white, black, hispanic, aian, nhpi, two_or_more, unknown,
nra_share
```

* `year` is the end of the academic year (IPEDS collection year): 1996 = 1995-96,
  2025 = provisional 2024-25.
* `awlevel` values: 9 (doctor's, pre-2010 scheme), 10 (first-professional,
  pre-2010), 17 (research/scholarship), 18 (professional practice), 19 (other).
  Levels are never merged.
* `cipcode` is normalised to dotted `NN.NNNN`; `cip2` is the 2-digit family.
* `nra_share` = nra / total, blank when total is 0.
* Coverage: 1996-2025, 30 files.

## Validation results

### 1. Required sanity checks — both PASS

AWLEVEL 17, CIP families {11,14,15,26,27,30,40,42}, MAJORNUM 1, CIPCODE 99
excluded:

| institution | window | nra / total | share | expected |
| --- | --- | --- | --- | --- |
| Colorado School of Mines (126775) | 2015-2023 | 385 / 967 | **39.81%** | ~39.8% |
| Binghamton, SUNY (196079) | 2015-2022 | 388 / 682 | **56.89%** | ~56.9% |

One caveat on the Binghamton window that is worth pinning down, because it
determines whether a downstream number is judged right or wrong:

| window | Mines | Binghamton |
| --- | --- | --- |
| 2015-2023 inclusive | 39.81% | 56.37% |
| 2015-2022 inclusive (i.e. `range(2015, 2023)`) | 39.76% | **56.89%** |

Mines lands on 39.8% either way, so it does not discriminate. Binghamton only
reproduces 56.9% on the half-open window — the reference figure was almost
certainly computed with a Python `range(2015, 2023)`, whose last year is 2022.
The spec's "2015-2023" is therefore exclusive of 2023. The validation harness
encodes this explicitly (`SANITY_CASES` carries a first and last year per case)
so the discrepancy cannot silently reappear.

The result is invariant to two choices I checked: the base vs `_rv` file
variant, and whether MAJORNUM 2 is included. All four combinations give the
same figures for these two institutions.

### 2. Reconciliation vs the CIPCODE 99 aggregate — exact

For every year, I summed all real-CIP doctoral rows per
(unitid, awlevel, majornum) and compared with that institution's CIPCODE 99 row.

**Zero mismatches on `total` and zero on `nra`, in all 30 years, across
44,000+ keys.** IPEDS's institution aggregate is fully consistent with the
per-CIP detail at doctoral levels.

The only imperfection: nine (unitid, awlevel) keys in 1996-1998 have real CIP
rows but no CIPCODE 99 row (1996: 166656, 190734, 194718, 198136; 1997: 193061,
230898; 1998: 247056, 217040, 194718). **All nine carry zero completions**, so
the reconciliation is exact for every key with any awards.

### 3. Year-over-year discontinuities

The all-doctoral series (9+10+17+18+19) shows **no jump above 15% anywhere in
1996-2025**, including across the transition. The discontinuity is entirely a
reallocation between award-level codes, not a change in the underlying count:

| year | aw9 | aw10 | aw17 | aw18 | aw19 | all doctoral | aw17 NRA% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2007 | 61,370 | 91,680 | 0 | 0 | 0 | 153,050 | — |
| 2008 | 49,769 | 69,520 | 12,347 | 23,857 | 254 | 155,747 | 31.89% |
| 2009 | 37,463 | 50,534 | 24,814 | 46,084 | 892 | 159,787 | 30.78% |
| 2010 | 0 | 0 | 57,661 | 100,972 | 1,778 | 160,411 | 27.35% |
| 2011 | 0 | 0 | 60,075 | 104,288 | 1,382 | 165,745 | 27.28% |

**The critical trap is 2008-2009, not 2010-2011.** The AWLEVEL scheme changed
institution by institution, exactly like the race scheme. Institutions using
{9,10,11} in 2008-2009: 621 and 437. Institutions using {17,18,19}: 224 and
416. **Overlap: zero, in both years.** So an AWLEVEL-17-only series reads
12,347 in 2008 and 24,814 in 2010, +101% and +132% year over year — pure
artifact, since those are 122 and 243 reporting institutions against 548 in
2010. Anything filtering on AWLEVEL 17 must start at 2010; before that,
splice onto legacy AWLEVEL 9.

For NRA share specifically the splice is well behaved. The legacy 9 series
runs 28.17% (2007) and the modern 17 series 27.35% (2010) — a level shift of
under a point, because 9→17 and 10→18 map cleanly. The count level shifts more
(aw9 61,370 in 2007 vs aw17 57,661 in 2010, about -6%) as some professional-
practice doctorates moved from 9 to 18, so splice the *share*, not the count.

2010-2011 itself is clean: both years are fully modern, and share moves
27.35% → 27.28%.

**Structurally absent columns that must not be read as trend.** `nhpi` and
`two_or_more` are 0 before 2008 and near-zero through 2010 (nhpi 0 → 40 → 16 →
156 → 323; two_or_more 0 → 13 → 74 → 474 → 1,155). The legacy race scheme has
no such categories at all. Any "rise in multiracial doctorates" before 2012 is
a reporting artifact. `unknown` also steps up around 2001-2002 (4,411 → 6,406).
`nra`, `total` and the other race categories exist in both schemes and are
continuous.

### 4. Second majors

MAJORNUM 2 doctoral awards are 0.00%-0.14% of first-major totals over the whole
range — negligible at doctoral level, unlike at bachelor's. `majornum` is kept
as a column; filter to 1 for a degree count.

## Data-quality problems found in the source

1. **BOM on the first header cell** in the 2023-2025 files (the known gotcha),
   **and a trailing space on the LAST header cell in 2002-2007** — the field is
   literally named `'CRACE24 '`. This one is not documented anywhere and silently
   zeroes the grand-total and NRA-total columns for six years if you do a plain
   `row['CRACE24']`. The reader strips and upper-cases every header cell.

2. **The AWLEVEL scheme transition is institution-by-institution in 2008-2009**,
   with zero overlap — structurally the same problem as the race scheme, and it
   bites harder because AWLEVEL 17 is the primary filter for this project.
   I did not find it noted in the existing code; `build_dashboard.py` documents
   the race-scheme merge but not this.

3. **The race-scheme merge is provably a sum, and it does not affect NRA.**
   Verified at row level: for every row of the 2008, 2009 and 2010 files,
   `legacy race totals (CRACE18-22) + modern race totals (CHISPT/CAIANT/CASIAT/
   CBKAAT/CNHPIT/CWHITT/C2MORT) + CNRALT + CUNKNT == CTOTALT`, with **0
   exceptions** out of 247k / 256k / 266k rows — including the ~1,000-2,000
   rows a year where both schemes are non-zero *on the same row*. So summing is
   correct even at row grain, not merely across institutions.

   But `CTOTALT` and `CNRALT` are **blank in 0 rows** in all three years, under
   either scheme. They are the renamed legacy `CRACE24` and `CRACE17`, common
   to both schemes. **Therefore `nra_share` was never at risk from the race
   transition** — only the domestic race breakdown was. The script takes
   total/NRA from the single shared column and sums only the race breakdown;
   summing total or NRA would double-count in 2008-2010.

4. **Legacy code identities confirmed, contrary to a natural reading.**
   `CRACE17` is the non-resident-alien TOTAL and `CRACE24` is the GRAND total —
   not the other way round, and not 23/24. Verified on c2002: `CRACE17 ==
   CRACE01 + CRACE02` and `CRACE24 == CRACE15 + CRACE16` for all 200,336 rows,
   0 exceptions.

5. **1996-2001 files stop at CRACE16.** They carry only the men/women columns
   and none of `CRACE17`-`CRACE24`. My first build silently produced total=0
   and nra=0 for 1996-2001 as a result. The script now falls back to the legacy
   men/women pair per measure, but only when the legacy total column is absent
   from the file — so 2002-2010, which have both, never double-count.

6. **The 1998 file is padded with all-zero rows.** `c9798_a.csv` lists 3,841
   institutions with doctoral rows against 787 that actually award a doctorate;
   1997 and 1999 do not do this. Zero-total rows are dropped from the outputs,
   which also keeps institution counts comparable across years.

7. **CIPCODE is space-padded** in several years (`'99     '`) and appears as
   `'99'`, `'99.0000'` and `'990000'` depending on vintage — all normalised.

8. **AWLEVEL 17 is not the NSF SED universe.** 82,438 in 2023 vs ~57,900 SED
   research doctorates. IPEDS puts many EdD/DBA/PsyD-type degrees under 17.
   Relevant if this dataset is used as a calibration target against anything
   SED-derived — reconcile before cross-citing.

## Exclusions applied

* **CIPCODE 99 removed from the per-subject files** and written separately;
  including it alongside real CIP rows exactly doubles every institution total.
* **Doctoral award levels only** — 9, 10, 17, 18, 19. Legacy 11
  (post-first-professional certificate) excluded as not a doctorate.
  Restricting to doctoral levels is what keeps the output at 5 MB; the full
  award-level grain would be roughly 30x larger.
* **1984-1994 excluded entirely** (`c{year}_cip.csv`). Those files carry only
  `crace15`/`crace16` — total men and total women — with **no citizenship
  breakdown at all**, so no NRA measure can exist for them. The task brief said
  years run 1984-2025; for NRA purposes the usable range is 1996-2025. 1990 and
  1995 have no file on disk either way.
* Revised (`_rv`) releases preferred over the initial release where both exist.
  2025 is provisional (no `_rv` yet).
* Negative sentinel values floored to 0; zero-total rows dropped.

## Scoped out under the disk constraint

Nothing material. The full per-CIP grain is present for all 30 years at 3.0 MB
gzipped because the doctoral filter does the heavy lifting. What is *not*
built: sub-doctoral award levels (bachelor's, master's), the 1984-1994 files
(no NRA measure exists), and any derived high-NRA cell index — the cip2 rollup
is the input for that and can be queried directly.

## Constraints observed

No `python -m pipeline run`; no edits to `pipeline/manifest.json`,
`pipeline/universities.json`, or `scripts/generate_name_lists.py`; no git
commit or push; no raw CSV copied or re-extracted; no intermediate files left
behind. Net disk added: 5.1 MB.
