# Archived Scripts

These scripts were used during initial data collection and are kept for
reproducibility. They are **not called by the pipeline** — all data they
produced has been collected and is available on S3.

To re-run data collection from scratch, download raw data first:
```bash
aws s3 sync s3://phd-demographics-raw-data/data/ data/ --no-sign-request
```

## University-Specific Scrapers
- `scrape_caltech_theses.py` — Caltech EPrints thesis scraper
- `scrape_caltech_cms_alumni.py` — Caltech CMS alumni list
- `scrape_stanford_dissertations.py` — Stanford PURL/JSON scraper
- `scrape_escholarship.py` — UC eScholarship OAI-PMH
- `scrape_uw_dissertations.py` — UW ResearchWorks DSpace
- `scrape_uw_etd_collections.py` — UW ETD collections workaround
- `scrape_or_wa_dissertations.py` — Oregon/Washington universities
- `scrape_with_playwright.py` — Cloudflare-protected repositories

## Enrichment & Analysis
- `enrich_dspace_metadata.py` — Single-threaded DSpace REST enrichment (superseded by `enrich_concurrent.py`)
- `merge_sources.py` — IPEDS + NSF GSS fuzzy matching
- `ipeds_nra_asian_ranking.py` — University ranking by NRA count
- `run_ipeds_pipeline.py` — IPEDS pipeline orchestrator
- `archive_finished.py` — Archive completed scrape data
