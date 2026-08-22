# LCA archive — what is local, what is on S3, how to get it back

Verified 2026-08-22.

## Current state

| | local | S3 |
|---|---|---|
| 33 source `.xlsx` | present, 3.58 GB | present, verified byte-identical |
| `csv_cache/` | **deleted** | never uploaded, and never should be |
| `lca_by_university.json` | present, 0.7 MB | rebuilt off-box, see below |

S3 prefix: `s3://phd-demographics-raw-data/data/h1b/lca/`

## The dependency chain

```
LCA XLSX (3.58 GB) --one-time convert--> csv_cache --duckdb--> lca_by_university.json (0.7 MB) --> site
```

`csv_cache/` is **DERIVED and must never be backed up.** It reaches ~6 GB —
larger than the source it derives from — and `_parse_lca_duckdb()` in
`pipeline/step3_parse_federal.py` rebuilds any missing file automatically:

```python
csv_path = csv_dir / csv_name
if not csv_path.exists():
    need_convert.append(xlsx)
```

Delete it whenever space is needed. The cost is one conversion pass; the inputs
are local and also on S3.

Everything downstream reads `data/h1b/lca_by_university.json` and never the raw
files: `step4_enrich`, `scripts/enrich_university_json.py`, and the assistant's
provenance tools. Those derived fields (`total_lcas`, `top_titles`, `top_soc`,
`wage_median`, `wage_25th`, `wage_75th`) are already baked into the published
per-university JSONs and the Parquet exports. **Analysis, site builds, deploys,
the assistant and the bulk exports all work with `csv_cache/` absent.**

## Overlapping quarters: never delete, always deduplicate

An earlier version of this file said *"DOL quarterly files are cumulative — a Q3
file contains the year to date — so when a later quarter arrives, the earlier one
for the same fiscal year must be removed from both places."*

**That is wrong, and acting on it loses cases.** The files are not consistently
cumulative. Three files from one fiscal year, by their own `DECISION_DATE` spans:

| file | span | shape |
|---|---|---|
| `lca_fy2021_Q1` | 2020-10-01 → 2020-12-31 | one quarter |
| `lca_fy2021_Q3` | 2020-10-01 → 2021-03-25 | cumulative, and only to March |
| `lca_fy2021_Q4` | 2021-07-01 → 2021-09-30 | one quarter |

The file names do not describe the contents. Summing double-counts; deleting
"superseded" quarters silently drops the quarter-only files. Both are wrong, in
opposite directions.

The pipeline therefore **deduplicates on the case number** — one row per LCA,
whichever files it appears in. FY2013 names the column `LCA_CASE_NUMBER` and
FY2016 onward use `CASE_NUMBER`; `union_by_name` surfaces both and `COALESCE`
picks whichever a row carries:

```sql
CREATE VIEW lca_dedup AS SELECT * EXCLUDE (_rn) FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY {key_expr} ORDER BY filename DESC) AS _rn
    FROM lca_raw WHERE {key_expr} IS NOT NULL) WHERE _rn = 1
```

This makes the rule simple and safe:

> **Add every file DOL publishes. Never remove one because a later file appears
> to supersede it.** An unnecessary file costs nothing — dedup collapses it. A
> deleted file may be unrecoverable.

`lca_FY2026_Q1.xlsx` was removed from the active set on 2026-08-18 under the old
assumption, leaving FY2026 represented by Q3 alone. It was **restored on
2026-08-22**; a copy also remains at
`backups/2026-08-18/h1b/lca/superseded/`.

## Layout drift, and why the files are read one at a time

DOL has changed the disclosure layout repeatedly. Across the archive:

| layout | columns | key column | wage column | occupation name |
|---|---|---|---|---|
| FY2013 | 35 | `LCA_CASE_NUMBER` | `LCA_CASE_WAGE_RATE_FROM` | `LCA_CASE_SOC_NAME` |
| FY2015-FY2016 | 40 | `CASE_NUMBER` | `WAGE_RATE_OF_PAY` | `SOC_NAME` |
| FY2017-FY2019 | 52-260 | `CASE_NUMBER` | `WAGE_RATE_OF_PAY_FROM` | `SOC_NAME` |
| FY2020 onward | 96-98 | `CASE_NUMBER` | `WAGE_RATE_OF_PAY_FROM` | `SOC_TITLE` |

The parser used to read every CSV through a single `read_csv()` glob with
`union_by_name=true, auto_detect=true, ignore_errors=true`. Across that spread
of schemas DuckDB mis-sniffed the header on the older files: the union came
back with **506 columns whose names were data values** -- `I-200-09121-701936`,
`WITHDRAWN`, `"MEDTRONIC`, `INC."`. Those files then had a NULL case number on
every row and the dedup discarded them entirely. Five files and 1.6M rows
contributed nothing to the published totals, and nothing raised an error.

`_parse_lca_duckdb()` now reads each file separately with its own header,
projects it onto one canonical nine-column schema via an alias table, and
`UNION ALL`s the projections. Sniffing a single homogeneous file is reliable;
sniffing 33 heterogeneous ones is not.

Two guards make a recurrence loud rather than silent:

* a file whose case-number or employer column matches no known alias raises,
  naming the file -- add the alias to `CANON` rather than let it be dropped;
* any file that parses to zero keyed rows raises before anything is published.

Alias matching is **exact**, never substring. The modern layout carries both
`JOB_TITLE` and `EMPLOYER_POC_JOB_TITLE`, and a substring match can record the
HR contact's job title as the sponsored worker's. `tests/test_lca_parsing.py`
covers each of these.

## The orphan-CSV trap

`_parse_lca_duckdb()` builds its conversion list from the XLSX files but
aggregates `csv_cache/*.csv` **independently**. Removing an XLSX therefore does
not remove its CSV, and that file stays silently in the totals. Under the
add-everything rule above this is now a much smaller hazard, but if you ever do
remove a source file, remove its CSV too — or just delete the whole cache.

Verify after any refresh:

```bash
ls data/h1b/lca/*.xlsx | wc -l          # must equal
ls data/h1b/lca/csv_cache/*.csv | wc -l # this
```

## Quarterly refresh

```bash
# add the new quarter's .xlsx to data/h1b/lca/, then:
.venv/bin/python -m pipeline run --step parse_federal
```

Expect the conversion to use ~6 GB — check free space first.

If the XLSX are ever removed locally:

```bash
export AWS_PROFILE=personal
aws s3 sync s3://phd-demographics-raw-data/data/h1b/lca/ data/h1b/lca/ \
            --exclude "csv_cache/*"
```

## Rebuilding off-box when the disk is full

The ~6 GB cache does not fit on a full local disk. `scripts/aws_lca_rebuild.sh`
launches an EC2 instance that pulls the XLSX from S3, rebuilds the cache there,
runs the pipeline's own `_parse_lca_files()` (not a reimplementation), and
writes `lca_by_university.json` back to S3. The instance terminates itself.
See the script header for the exact invocation.
