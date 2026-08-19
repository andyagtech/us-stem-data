# IPEDS doctoral non-resident-alien (NRA) ground truth

Built by `scripts/build_ipeds_nra_ground_truth.py`. Rebuild with:

    python3 scripts/build_ipeds_nra_ground_truth.py --validate

## Source

IPEDS Completions survey, component A (awards by CIP x award level x
race/ethnicity x sex), files `data/ipeds/c{year}_a.csv`. The revised
(`_rv`) release is preferred where it exists.

Data years: 1996-2025 (30 files).
Year = the end of the academic year in which the award was conferred
(the IPEDS collection year), so 1996 means 1995-96 and 2025 is the
provisional 2024-25 release.

## Files

| file | grain | rows |
| --- | --- | --- |
| `doctoral_nra_by_cip.csv.gz` | unitid x year x awlevel x cipcode x majornum | 298,861 |
| `doctoral_nra_by_cip2.csv.gz` | unitid x year x awlevel x 2-digit CIP family x majornum | 135,238 |
| `doctoral_inst_totals.csv.gz` | unitid x year x awlevel x majornum (IPEDS CIPCODE=99 aggregate) | 40,065 |

Measure columns (all integer counts): total, total_men, total_women, nra, nra_men, nra_women, asian, white, black, hispanic, aian, nhpi, two_or_more, unknown.
`nra_share` = nra / total, blank when total is 0.

## Exclusions applied

* **CIPCODE 99 is removed from the per-subject files** and written to
  `doctoral_inst_totals.csv.gz` instead. It is the institution-level
  aggregate; summing it alongside real CIP rows double-counts.
* **Award levels**: only doctoral levels are kept -- 17, 18, 19 in the
  modern scheme and 9, 10 in the pre-2010 scheme. AWLEVEL is a column
  and the levels are never merged. Legacy 11 (post-first-professional
  certificate) is excluded as not a doctorate.
* **1984-1994** (`c{year}_cip.csv`) are excluded entirely: those files
  carry only CRACE15/CRACE16 (total men / total women) and have no
  citizenship breakdown, so no NRA measure exists for them.
* Negative sentinel values are floored to 0.
* `MAJORNUM` is preserved rather than filtered. 1 = first major,
  2 = second major. Filter to `majornum == 1` for a degree count.
  Measured: second-major doctoral awards are 0.00-0.14% of first-major
  totals over 1996-2025, so the choice barely moves any share.
* Rows whose `total` is 0 are dropped. They carry no information and
  are not reported uniformly: the 1998 file emits explicit zero
  doctoral rows for ~3,000 institutions that award no doctorates,
  which 1997 and 1999 do not. 54,869 such rows were dropped.

## Race-scheme handling (the 2008-2010 transition)

IPEDS replaced the legacy `CRACE01`-`CRACE24` columns with named
columns (`CNRALT`, `CASIAT`, `CWHITT`, ...). Institutions converted
individually, so the 2008, 2009 and 2010 files contain BOTH schemes.

* Race-breakdown measures (asian, white, black, hispanic, aian, nhpi,
  two_or_more, unknown) are **summed** across the two schemes. They
  are complementary, not redundant. Verified: for every row of the
  2008, 2009 and 2010 files, legacy race totals + modern race totals
  + CNRALT + CUNKNT == CTOTALT exactly (0 exceptions), including the
  ~2,000 rows a year where both schemes are non-zero on the same row.
* Total and NRA measures are **not** summed. Legacy `CRACE24` was
  renamed `CTOTALT` and legacy `CRACE17` was renamed `CNRALT`; in
  2008-2010 only the new names appear and they are populated for
  100% of rows under either scheme. Verified on c2002:
  `CRACE17 == CRACE01 + CRACE02` and `CRACE24 == CRACE15 + CRACE16`
  for all 200,336 rows.
* Consequence: `nra_share` is unaffected by the race-scheme
  transition. Only the domestic race breakdown was ever at risk.
* `nhpi` and `two_or_more` do not exist before 2011 and are 0 for
  legacy-scheme rows; do not read that as a real trend.

## Award-level scheme transition

The 2008 and 2009 files also contain both AWLEVEL schemes. Verified:
no institution reports under both in the same year (0 overlap of
{9,10,11} with {17,18,19} in 2008 and 2009), so the two are
complementary at institution level. AWLEVEL 17 series counts are
therefore severely undercounted in 2008-2009 and absent before 2008.
For any series spanning 2010, filter on AWLEVEL 17 only from 2010
onward and treat 2008-2009 AWLEVEL 17 as partial coverage.

## Known source problems

* The first header cell has a UTF-8 BOM in the 2023-2025 files; the
  LAST header cell has a trailing space in 2002-2007 (`'CRACE24 '`).
* `CIPCODE` is space padded in several years (`'99     '`).
* Data year 2025 is provisional (no `_rv` release yet).
* 1990 and 1995 have no completions file on disk.
* The 1998 file (`c9798_a.csv`) lists 3,841 institutions with doctoral
  rows against 787 that actually award a doctorate; the surplus are
  all-zero placeholder rows unique to that year.
* Nine (unitid, awlevel) keys across 1996-1998 have real CIP rows but
  no CIPCODE 99 row. All nine carry zero completions, so the
  reconciliation is exact for every key with any awards.
* AWLEVEL 17 is NOT the NSF Survey of Earned Doctorates universe. It
  is broader (82,438 in 2023 vs ~57,900 SED research doctorates),
  because IPEDS classifies EdD/DBA/PsyD-type degrees under 17 at many
  institutions. Do not cross-cite the two without reconciling first.
