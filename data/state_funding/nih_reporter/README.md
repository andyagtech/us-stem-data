# NIH RePORTER Grant Data (FY2020-2024)

NIH extramural research grant totals for the 101 universities tracked by the
PhD Demographics project, aggregated by institution and fiscal year.

## Source

- **API**: NIH RePORTER v2 — `https://api.reporter.nih.gov/v2/projects/search`
- **Docs / landing page**: https://reporter.nih.gov/exporter
- **Fiscal years fetched**: 2020, 2021, 2022, 2023, 2024
- **Fetched on**: 2026-04-05

Data was pulled via the search API (not the ExPORTER bulk CSVs) to avoid
downloading the full multi-GB corpus. Queries are filtered by `org_names`,
using institution name variants from `pipeline/entity_map.json` as the
canonical mapping between university keys (e.g. `mit`) and the ALL-CAPS
organization names NIH uses (e.g. `MASSACHUSETTS INSTITUTE OF TECHNOLOGY`).

## Files

- `fetch_nih.py` — resumable fetcher; reads entity map, paginates 500/page,
  saves incrementally. Run with no args for all universities, or with one or
  more keys (e.g. `python3 fetch_nih.py mit caltech`) to backfill specific
  ones.
- `nih_by_university.json` — final output, keyed by university short key.
- `fetch.log` — log from the most recent fetch run.

## Output schema

```json
{
  "mit": {
    "name": "MASSACHUSETTS INSTITUTE OF TECHNOLOGY",
    "org_name_variants": ["MASSACHUSETTS INSTITUTE OF TECHNOLOGY"],
    "by_year": {
      "2020": {"grant_count": 255, "total_dollars": 111307339},
      "2021": {"grant_count": 278, "total_dollars": 108475963},
      "2022": {"grant_count": 273, "total_dollars": 114773683},
      "2023": {"grant_count": 263, "total_dollars": 115495001},
      "2024": {"grant_count": 222, "total_dollars": 102857783}
    },
    "top_departments": [["ENGINEERING (ALL TYPES)", 339], ["BIOLOGY", 240], ...],
    "total_grants_2020_2024": 1291,
    "total_dollars_2020_2024": 552909769,
    "_complete": true
  }
}
```

- `grant_count` is distinct project numbers seen in that fiscal year
  (sub-awards and continuations are deduplicated within a year).
- `total_dollars` is the sum of `award_amount` across all project records
  returned for that fiscal year.

## Important caveats and limitations

1. **"Top departments" is coarse.** The NIH RePORTER public API does not
   expose the named academic department that administers a grant. What it
   does expose is the organization record's `dept_type` — an NIH-assigned
   coarse category such as `BIOLOGY`, `ENGINEERING (ALL TYPES)`,
   `MISCELLANEOUS`, `NONE`, or `UNSPECIFIED`. This is what we tally in
   `top_departments`. It is NOT equivalent to "Department of Chemistry at
   MIT" — a single institution typically has one or two dept_type values
   across all of its NIH records.

2. **Fiscal year, not calendar year.** NIH fiscal years run Oct 1 - Sep 30.
   FY2024 = Oct 2023 - Sep 2024.

3. **Award amount semantics.** `award_amount` is the NIH-reported total
   awarded for that project record in that fiscal year. It mixes direct and
   indirect costs and does not distinguish new awards from continuations.
   Project-level totals across multiple years will double-count continuation
   awards if naively summed; we sum within a year and report both by-year
   and total figures.

4. **Scope.** NIH funds primarily biomedical and behavioral research. For
   engineering-heavy institutions (e.g. Georgia Tech, Caltech, MIT) NIH is
   only a fraction of total federal research funding — NSF, DOE, and DoD
   are not included here.

5. **Pagination cap.** The API caps `offset` at 14,999 per query. We split
   queries by fiscal year, so each (institution, year) page runs well under
   the cap even for the largest research universities, but the script logs
   a warning if it is ever hit.

6. **Institution matching.** We rely on
   `pipeline/entity_map.json` for the NIH-org-name to university-key
   mapping. Affiliated medical centers that NIH lists under a distinct
   org_name (e.g. a separate hospital system) are only included if that
   org_name has an entry in the entity map. Missing variants will understate
   grant counts; check `org_name_variants` for each university to see which
   were queried.

7. **Rate limiting.** The fetcher sleeps 1 second between paginated requests
   and between fiscal years. A full run over all 101 universities takes
   roughly 15-25 minutes depending on institution size and network latency.

## Reproducing

```bash
cd /Users/andy/usds_china
python3 data/state_funding/nih_reporter/fetch_nih.py
```

The script is resumable: universities marked `_complete: true` in
`nih_by_university.json` are skipped on re-run. Delete that file (or the
specific key) to force a refetch.
