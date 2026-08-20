# LCA archive — what is local, what is on S3, how to get it back

The DOL LCA disclosure files are 9.6 GB, which was most of this machine's free
disk. They are archived to S3 and removed locally. Nothing in normal operation
needs them.

## The dependency chain

```
LCA XLSX (3.6 GB)  --one-time convert-->  csv_cache (6.0 GB)  --duckdb-->  lca_by_university.json (0.7 MB)  -->  site
```

`_parse_lca_duckdb()` builds its conversion list by checking which CSVs are
**missing**. With every CSV present it converts nothing and never opens an
XLSX. With both archived it has no work to do at all — which is why removing
them is safe only while the derived JSON is current.

Everything downstream reads `data/h1b/lca_by_university.json` and never the raw
files: `step4_enrich`, `scripts/enrich_university_json.py`, and the assistant's
provenance tools. Those derived fields (`total_lcas`, `top_titles`, `top_soc`,
`wage_median`, `wage_25th`, `wage_75th`) are already baked into the published
per-university JSONs and the Parquet exports.

**So analysis, site builds, deploys, the assistant and the bulk exports all work
with the archive removed.** The only operation that needs it back is
regenerating `lca_by_university.json` — which happens when DOL publishes a new
quarter.

## Where it is

```
s3://phd-demographics-raw-data/data/h1b/lca/*.xlsx        originals, 3.6 GB
s3://phd-demographics-raw-data/data/h1b/lca/csv_cache/    converted, 6.0 GB
```

Kept locally: `data/h1b/lca_by_university.json` (0.7 MB), the only artifact
anything reads.

## Restoring for a quarterly refresh

Pull the converted CSVs — not the XLSX. The CSVs are what duckdb aggregates,
and skipping the XLSX avoids re-running a conversion that has already happened.

```bash
export AWS_PROFILE=personal
aws s3 sync s3://phd-demographics-raw-data/data/h1b/lca/csv_cache/ \
            data/h1b/lca/csv_cache/
# add the new quarter's .xlsx to data/h1b/lca/, then:
python3 -m pipeline run --step parse_federal
```

The converter will notice the one new XLSX has no CSV, convert just that file,
and aggregate the whole set.

## The trap to avoid

`_parse_lca_duckdb()` builds its conversion list from the XLSX files but then
aggregates `csv_cache/*.csv` **independently**. Deleting a superseded XLSX
therefore does **not** remove its CSV, and that quarter stays silently in the
totals.

DOL quarterly files are cumulative — a Q3 file contains the year to date — so
when a later quarter arrives, the earlier one for the same fiscal year must be
removed from **both** places. FY2026 Q1 was handled this way already: the XLSX
went to `backups/2026-08-18/h1b/lca/superseded/` and its CSV was removed, which
is why 32 XLSX and 32 CSVs currently match with no orphans.

Verify before any refresh:

```bash
for c in data/h1b/lca/csv_cache/*.csv; do
  b=$(basename "$c" .csv)
  [ -f "data/h1b/lca/$b.xlsx" ] || echo "ORPHAN: $b.csv"
done
```

## Why the originals were kept at all

The XLSX are re-downloadable from DOL, so keeping them on S3 is belt-and-braces
rather than necessity. They cost about eight cents a month and they are the only
copy that is byte-identical to what the agency published, which matters if a
figure is ever challenged.
