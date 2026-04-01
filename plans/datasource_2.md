# Data Source 2: Individual-Level PhD Data

## Overview

We need individual-level PhD data (names, fields, institutions, country of origin) to complement
the aggregate IPEDS data already processed. Two main sources:

1. **NSF Survey of Earned Doctorates (SED)** — aggregate tables with country-of-origin breakdowns
2. **University dissertation archives** — individual PhD recipient names

---

## 1. NSF Survey of Earned Doctorates (SED)

**Status: Downloaded and parsed (96 Excel tables)**

- Source: https://ncses.nsf.gov/surveys/earned-doctorates/2024
- Publication: nsf25349
- Local: `data/nsf_sed/tables/` (96 .xlsx files)

### Key Findings

**Country of Origin (Table 7-7, 7-8):**
- China: 6,756 PhD recipients in 2024 (35.9% of all 18,819 temp visa holders)
- 90.5% of Chinese PhD recipients are in S&E fields
- China → India (2,649) → South Korea (1,061) → Bangladesh (593) → Saudi Arabia (502)
- Saved: `data/nsf_sed/sed_top10_countries_by_year.csv`

**Citizenship Trends (Table 1-6):**
- Temp visa share: 11.6% (1979) → 33.3% (2024)
- S&E temp visa share: 36.4% in 2024
- Saved: `data/nsf_sed/sed_citizenship_by_field.csv`

**Top Institutions for Temp Visa S&E PhDs (Table 7-3):**
- #1 U. Michigan (832), #5 UC Berkeley (678), #9 Stanford (638)
- #12 UW Seattle (600), #6 UCLA (655), #15 UC Davis (568)
- Saved: `data/nsf_sed/sed_top_institutions_temp_visa.csv`

### Limitations
- SED is aggregate — no individual names
- Country-of-origin data only for temporary visa holders (not naturalized citizens)
- Public tables only; restricted microdata requires NCSES data agreement

---

## 2. University Dissertation Archives

### UW Seattle — ResearchWorks (DSpace 7)

**Status: Scraper built and tested**

- Archive: https://digital.lib.washington.edu/researchworks/communities/6b84acce-b816-4d18-b41a-387c062aab76
- 36,205 items in sitemap (includes ALL repository items, not just dissertations)
- Departments organized as sub-communities (13 pages, ~120 departments)
- Metadata available via SSR HTML meta tags: `citation_author`, `citation_title`, `citation_publication_date`, `citation_keywords`
- Scraper: `scripts/scrape_uw_dissertations.py`
  - Tested: 20 items scraped successfully, 100% metadata extraction rate
  - Full scrape: ~36K items × 0.5s = ~5 hours
  - Output: `data/uw_dissertations/uw_dissertations_metadata.csv`
  - Supports resume from checkpoint

**To run full scrape:**
```bash
python scripts/scrape_uw_dissertations.py --all --delay 0.5
```

### UC Campuses — eScholarship (OAI-PMH)

**Status: COMPLETE — 73,927 records harvested**

- OAI-PMH endpoint: `https://escholarship.org/oai`
- Set IDs: `ucb_etd`, `ucd_etd`, `uci_etd`, `ucla_etd`, `ucm_etd`, `ucr_etd`, `ucsb_etd`, `ucsc_etd`, `ucsd_etd`, `ucsf_etd`
- Scraper: `scripts/scrape_escholarship.py`
- Output: `data/uc_dissertations/uc_dissertations_metadata.csv`
- STEM-filtered: `data/uc_dissertations/uc_stem_dissertations.csv` (40,993 records)
- Breakdown: UCSD (14,944), Berkeley (13,786), UCLA (13,744), Irvine (6,971), UCSF (6,094), Riverside (5,680), Santa Barbara (4,132), Davis (3,933), Santa Cruz (3,298), Merced (1,345)

### Stanford — Stanford Digital Repository (Cocina JSON API)

**Status: Scraper running (~3,400/30,830 checked, ~2,661 theses found)**

- Collection: https://purl.stanford.edu/xx313vx3974
- Sitemap: `https://purl.stanford.edu/system/sitemap/sitemap.xml.gz` (30,830 PURL items)
- 74.5% of SDR items are theses/dissertations
- SearchWorks blocks programmatic access; Cocina JSON API at `{purl}.json` works
- Scraper: `scripts/scrape_stanford_dissertations.py`
- Output: `data/stanford_dissertations/stanford_dissertations_metadata.csv`

### Portland State — PDXScholar (OAI-PMH)

**Status: COMPLETE — 12,299 records harvested**

- OAI-PMH endpoint: `https://pdxscholar.library.pdx.edu/do/oai/`
- Sets: `publication:open_access_etds` (6,899), `publication:etds` (6,899)
- Output: `data/or_wa_dissertations/pdxscholar_dissertations.csv`

### U. Oregon — Scholars' Bank (DSpace 8.1)

**Status: Scraper running (~29,084 items in sitemap)**

- Sitemap: `https://scholarsbank.uoregon.edu/sitemap0.xml`
- SSR HTML meta tags work (same approach as UW)
- Includes all repository items (not just dissertations) — needs post-filtering
- Scraper: `scripts/scrape_or_wa_dissertations.py --repo uoregon`
- Output: `data/or_wa_dissertations/uoregon_dissertations.csv`

### Washington State University — Research Exchange (Esploro)

**Status: Scraper running (~9,245 doctoral/graduate items)**

- Platform: Ex Libris Esploro (SPA, but serves SSR metadata to Googlebot UA)
- Sitemap: `https://rex.libraries.wsu.edu/view/google/siteindex.xml` (45,956 total items)
- Filtered to `/outputs/doctoral/` and `/outputs/graduate/` URLs (9,245)
- Scraper: `scripts/scrape_or_wa_dissertations.py --repo wsu`
- Output: `data/or_wa_dissertations/wsu_dissertations.csv`

### Oregon State — ScholarsArchive (Hyrax/Samvera)

**Status: BLOCKED — bot detection prevents scraping**

- Repository: https://ir.library.oregonstate.edu/
- 10,117 thesis URLs found in sitemap
- All requests redirect to bot challenge page
- OAI-PMH endpoint returns empty; JSON API returns empty
- May require institutional access or manual data request

### Other West Coast (Not Yet Explored)

- Caltech: CaltechTHESIS (https://thesis.library.caltech.edu/)
- OHSU: likely integrated with UO or has own repository

---

## 3. Other Sources (Not Yet Explored)

- **ProQuest Dissertations & Theses Global** — most comprehensive, requires institutional access
- **OATD.org** — indexes 7.5M theses/dissertations, no bulk download API
- **NSF GSS** — graduate student enrollment data (not completions), useful for pipeline analysis

---

## Current Status (Mar 8, 2026)

| Source | Records | Status | Script |
|---|---|---|---|
| UC eScholarship (10 campuses) | **73,927** | ✅ COMPLETE | `scrape_escholarship.py` |
| Portland State PDXScholar | **12,299** | ✅ COMPLETE | inline OAI harvest |
| UW ResearchWorks | ~1,920+ | 🔄 RUNNING (5%) | `scrape_uw_dissertations.py` |
| Stanford SDR | ~2,661+ | 🔄 RUNNING (11%) | `scrape_stanford_dissertations.py` |
| U. Oregon Scholars' Bank | ~26+ | 🔄 RUNNING (0.1%) | `scrape_or_wa_dissertations.py --repo uoregon` |
| WSU Research Exchange | ~30+ | 🔄 RUNNING (0.3%) | `scrape_or_wa_dissertations.py --repo wsu` |
| Oregon State ScholarsArchive | 0 | ❌ BLOCKED | bot detection |

## Priority Actions

1. [x] Download and parse NSF SED tables
2. [x] Build UW ResearchWorks scraper
3. [x] Build eScholarship scraper — DONE, 73,927 records
4. [x] Build Stanford scraper
5. [x] Build Portland State OAI harvester — DONE, 12,299 records
6. [x] Build U. Oregon scraper
7. [x] Build WSU scraper
8. [x] Apply STEM filter to UC data — 40,993 STEM dissertations
9. [~] Run full scrapes for UW, Stanford, U. Oregon, WSU (background)
10. [ ] Filter all scraped data for STEM PhD dissertations
11. [ ] Analyze name patterns in STEM PhD recipients
12. [ ] Investigate Oregon State manual data access