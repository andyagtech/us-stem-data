# LCA archive — what is local, what is on S3, how to get it back

Verified 2026-08-20. An earlier version of this file described a state that was
planned but never reached: it said `csv_cache/` was on S3 at 6.0 GB and gave an
`aws s3 sync` command to restore it. **That prefix holds zero objects.** The
upload was abandoned part-way — correctly, as it turns out, because the cache is
derived — but the document was never corrected, so the restore command would
have silently fetched nothing.

## Current state

| | local | S3 |
|---|---|---|
| 32 source `.xlsx` | **present**, 3.5 GB | **present**, verified byte-identical |
| `csv_cache/` | **deleted** | never uploaded, and never should be |
| `lca_by_university.json` | present, 0.7 MB | — |

S3 prefix: `s3://phd-demographics-raw-data/data/h1b/lca/`

## The dependency chain

```
LCA XLSX (3.5 GB)  --one-time convert-->  csv_cache  --duckdb-->  lca_by_university.json (0.7 MB)  -->  site
```

`csv_cache/` is **DERIVED and must never be backed up.** It reached 5.9 GB —
larger than the source it derives from — and `_parse_lca_duckdb()` in
`pipeline/step3_parse_federal.py` rebuilds any missing file automatically:

```python
csv_path = csv_dir / csv_name
if not csv_path.exists():
    need_convert.append(xlsx)
```

It was deleted on 2026-08-20 to relieve a disk at 100% full. Delete it again
whenever space is needed. The cost is one conversion pass; the inputs are local
and also on S3.

Everything downstream reads `data/h1b/lca_by_university.json` and never the raw
files: `step4_enrich`, `scripts/enrich_university_json.py`, and the assistant's
provenance tools. Those derived fields (`total_lcas`, `top_titles`, `top_soc`,
`wage_median`, `wage_25th`, `wage_75th`) are already baked into the published
per-university JSONs and the Parquet exports.

**Analysis, site builds, deploys, the assistant and the bulk exports all work
with `csv_cache/` absent.** The only operation that rebuilds it is a quarterly
refresh.

## Quarterly refresh

The XLSX are local, so nothing needs downloading:

```bash
# add the new quarter's .xlsx to data/h1b/lca/, then:
.venv/bin/python -m pipeline run --step parse_federal
```

The converter notices which CSVs are missing, rebuilds them, and aggregates the
whole set. Expect the conversion to take a while and to use ~6 GB — check free
space first.

If the XLSX are ever removed locally:

```bash
export AWS_PROFILE=personal
aws s3 sync s3://phd-demographics-raw-data/data/h1b/lca/ data/h1b/lca/ \
            --exclude "csv_cache/*"
```

## The trap to avoid

`_parse_lca_duckdb()` builds its conversion list from the XLSX files but then
aggregates `csv_cache/*.csv` **independently**. Deleting a superseded XLSX
therefore does **not** remove its CSV, and that quarter stays silently in the
totals.

DOL quarterly files are cumulative — a Q3 file contains the year to date — so
when a later quarter arrives, the earlier one for the same fiscal year must be
removed from **both** places. FY2026 Q1 was handled this way: the XLSX went to
`backups/2026-08-18/h1b/lca/superseded/` and its CSV was removed.

With `csv_cache/` currently empty this trap cannot bite: the next run rebuilds
every CSV from exactly the 32 XLSX present, so there are no orphans by
construction. It returns as soon as the cache is rebuilt.

Verify after any refresh:

```bash
ls data/h1b/lca/*.xlsx | wc -l          # must equal
ls data/h1b/lca/csv_cache/*.csv | wc -l # this
```
