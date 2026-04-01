# Research into US Graduate Program Demographics and Funding

Thesis & dissertation records from 107 US research universities, enriched with government data from IPEDS, NSF, DOL, DHS, and Census.

**Live site**: https://phd-demographics.andy-barr.com

## Quick Start

```bash
# 1. Clone
git clone git@github.com:andyagtech/usds-china.git
cd usds-china

# 2. Download raw data from S3 (5.5 GB)
aws s3 sync s3://phd-demographics-raw-data/data/ data/ --no-sign-request

# 3. Generate the site
python scripts/generate_name_lists_html.py

# 4. Enrich with government data
python scripts/enrich_university_json.py

# 5. Normalize department names
python -c "
import json, os
lookup = json.load(open('data/taxonomy_lookup.json'))
for mode in ['stem', 'nonstem']:
    for fn in os.listdir(f'site/data/{mode}'):
        if not fn.endswith('.json') or fn.startswith('_'): continue
        d = json.load(open(f'site/data/{mode}/{fn}'))
        for r in d.get('records', []):
            c = lookup.get(r[0])
            if c: r[0] = c
        json.dump(d, open(f'site/data/{mode}/{fn}', 'w'), ensure_ascii=False, separators=(',', ':'))
"

# 6. Deploy to S3+CloudFront
aws s3 sync site/ s3://phd-demographics-andy-barr/ --profile personal
```

## Repository Structure

```
usds-china/
├── scripts/              # All data collection and processing scripts
│   ├── generate_name_lists.py       # Core: university CONFIGS, record loading, classification
│   ├── generate_name_lists_html.py  # Generates stem.html + non_stem.html + per-university JSONs
│   ├── scrape_oai_etds.py           # OAI-PMH harvester (90+ university configs)
│   ├── scrape_uw_etd_collections.py # UW Seattle DSpace collection scraper
│   ├── scrape_with_playwright.py    # Playwright scraper for Cloudflare-protected repos
│   ├── enrich_concurrent.py         # Concurrent REST API enrichment (degree/dept metadata)
│   ├── enrich_university_json.py    # Adds IPEDS/GSS/HERD data to per-university JSONs
│   ├── enrich_dspace_metadata.py    # DSpace REST API degree enrichment
│   ├── build_dept_links.py          # Department URL mapping
│   ├── qa_report.py                 # Data quality report
│   └── name_classifier.py          # Surname-based origin classification
├── site/                 # Static site (deployed to S3+CloudFront)
│   ├── stem.html                    # Main STEM thesis/dissertation page
│   ├── non_stem.html                # Non-STEM page
│   ├── overview.html                # National statistics dashboard
│   ├── data_sources.html            # Methodology and government sources
│   ├── webmcp.html                  # WebMCP integration documentation
│   ├── index.html                   # Landing page
│   ├── nav.js                       # Shared navigation drawer
│   ├── catalog.json                 # Machine-readable data catalog
│   ├── llms.txt                     # AI agent discovery guide
│   ├── robots.txt / sitemap.xml     # Standard web infrastructure
│   └── data/                        # Generated per-university JSONs (not in git)
│       ├── stem/{key}.json          # 107 STEM university data files
│       ├── nonstem/{key}.json       # 107 non-STEM university data files
│       └── taxonomy.json            # Department name taxonomy
├── infra/                # AWS infrastructure
│   └── analytics_lambda.py          # Analytics collection + dashboard API
├── data/                 # Curated data summaries (bulk data on S3)
│   ├── DATA_DICTIONARY.md           # Complete data documentation
│   ├── taxonomy.json                # 44 canonical department categories
│   ├── taxonomy_lookup.json         # 277 variant → canonical mappings
│   ├── university_repositories.md   # Repository access guide
│   ├── qa_report.csv                # Data quality metrics per university
│   ├── dept_links.json              # Department URL mappings
│   └── nsf_sed/parsed/             # Parsed NSF SED tables
├── plans/                # Scraping plans and implementation notes
└── .gitignore
```

## Data Storage

| Location | What | Size |
|---|---|---|
| **This repo (git)** | Scripts, site HTML, curated summaries, config | 15.6 MB |
| **s3://phd-demographics-raw-data** | All raw data (IPEDS, NSF, scraped CSVs, H-1B, SEVP) | 5.5 GB |
| **s3://phd-demographics-andy-barr** | Deployed static site (CloudFront origin) | ~110 MB |

The raw data bucket is **publicly readable** (`--no-sign-request`). To download:
```bash
aws s3 sync s3://phd-demographics-raw-data/data/ data/ --no-sign-request
```

## Key Numbers

- **107** universities (55 R1, 25 R2)
- **471,171** total records (334,788 STEM + 136,383 non-STEM)
- **44** canonical STEM/non-STEM department categories
- **8** federal data sources integrated
- **2016–2024** thesis record coverage

## Data Sources

All demographic and enrollment data comes from US federal agencies:

| Source | Agency | What |
|---|---|---|
| IPEDS | NCES (Dept of Education) | Completions, enrollment, finance, tuition, faculty |
| NSF SED | NSF NCSES | Survey of Earned Doctorates — trends, countries, funding |
| NSF GSS | NSF NCSES | Graduate enrollment by field × citizenship |
| NSF SDR | NSF NCSES | Doctorate recipient workforce — separates citizens from green card holders |
| NSF NSCG | NSF NCSES | College graduate survey with birth country codes |
| NSF HERD | NSF NCSES | Higher education R&D expenditures |
| H-1B | DOL ETA | Employer visa petitions |
| SEVP | DHS ICE | Foreign student tracking |
| USASpending | Treasury | Federal research grants |

Thesis/dissertation records are scraped from university institutional repositories via OAI-PMH, DSpace REST API, or HTML scraping.

## Key Finding

The NSF SDR is the **only public dataset** that separates US citizens from permanent residents among PhD holders:

| Category | Share |
|---|---|
| US Citizen (Native-born) | 63.5% |
| US Citizen (Naturalized) | 17.9% |
| Permanent Resident (Green Card) | 7.0% |
| Temporary Visa Holder | 3.1% |
| Outside US | 8.6% |

IPEDS groups the first three as "US citizen or permanent resident" — hiding that **28% of "domestic" PhD holders are foreign-born**.

## Infrastructure

- **Hosting**: S3 + CloudFront (auto-scaling, ~$5-15 for a viral day)
- **Analytics**: Custom Lambda + DynamoDB (no third-party tracking)
- **Domain**: phd-demographics.andy-barr.com (Route53 + ACM)
- **AI access**: WebMCP hooks, /llms.txt, /catalog.json
