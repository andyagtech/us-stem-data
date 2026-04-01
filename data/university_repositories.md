# University Repository Access Guide

Last updated: 2026-03-30

## Summary

| Status | Count | Description |
|---|---|---|
| **On Site** | 103 | Harvested and live on phd-demographics.andy-barr.com |
| **In Progress** | 1 | UNC Chapel Hill — scraping via JSON API |
| **Blocked** | ~6 | Behind Cloudflare WAF or no programmatic access |
| **Not viable** | ~3 | NYU (ProQuest only), USC (custom DAM), Rutgers (Alma/no API) |

---

## On Site (98 universities)

Data already harvested, classified, and deployed. See `scripts/generate_name_lists.py` CONFIGS for full list.

### Harvesting Methods Used

| Method | Universities | Notes |
|---|---|---|
| OAI-PMH (bepress) | Missouri S&T, MTU, SD State, Stony Brook, NJIT, BYU, Clemson, LSU, Purdue, RIT, SMU, Syracuse, UCF, many more | Most common — `publication:dissertations` or `publication:etd` sets |
| OAI-PMH (DSpace) | Duke, Georgia Tech, Harvard, Iowa State, MIT, Cornell, Columbia, Penn State, Rice, UMD, MSU, U Utah | `/server/oai/request` or `/oai/request` endpoints |
| OAI-PMH (Hyrax) | Oregon State, CU Boulder | Samvera-based repositories |
| DSpace REST API | NC State, Rice, UMD | `/server/api/core/items/{uuid}` for degree/department enrichment |
| Custom JSON API | UVA (LibraETD) | `/api/works/{id}` — returns degree, department, author structured data |
| Solr JSON API | Northwestern (Arch) | `/catalog.json` with `resource_type_sim` facet for Dissertation/Masters Thesis |
| eScholarship OAI | All 10 UC campuses | UC-wide eScholarship repository |
| Cocina API | Stanford | Stanford-specific metadata API |
| DSpace SSR + Sitemap | UW Seattle | No API/OAI — scrape citation meta tags from SSR HTML pages |
| Caltech EPrints | Caltech | Custom scraper for department alumni pages |
| Figshare OAI | Carnegie Mellon | `api.figshare.com/v2/oai` with `portal_231` set (mixed content) |
| Esploro sitemap | WSU | Server-side rendered meta tags from sitemap URLs |

---

## Tier B: Accessible But Not Yet Harvested

### U Iowa — Iowa Research Online
- **Platform**: Esploro (Ex Libris), formerly bepress
- **URL**: https://iro.uiowa.edu/
- **OAI**: Not found at standard bepress paths
- **Esploro API**: Needs investigation — https://iro.uiowa.edu/esploro/outputs
- **NRA**: 14.0%, 920 PhDs/yr
- **Status**: Need to find API or sitemap

### UNC Chapel Hill — Carolina Digital Repository
- **Platform**: Hyrax/Samvera
- **URL**: https://cdr.lib.unc.edu/
- **OAI**: Not available
- **Sitemap**: ✅ Accessible at `https://cdr.lib.unc.edu/sitemap.xml` (4,096 sub-sitemaps)
- **NRA**: 9.0%, 1,167 PhDs/yr
- **Status**: Sitemap accessible but pages are SPA — need to check if SSR metadata exists
- **Approach**: Sitemap scrape like UW Seattle, or check for Solr/JSON API

### U Georgia — UGA Theses
- **Platform**: Esploro (Ex Libris)
- **URL**: https://esploro.libs.uga.edu/
- **OAI**: Redirects to HTML
- **NRA**: 20.2%, 1,024 PhDs/yr
- **Status**: Need to investigate Esploro API patterns

### Vanderbilt
- **Platform**: DSpace (likely)
- **URL**: https://ir.vanderbilt.edu/
- **OAI**: 403 Forbidden
- **REST API**: 403 Forbidden
- **NRA**: 9.5%, 857 PhDs/yr
- **Status**: Fully blocked

### UIC — INDIGO Repository
- **Platform**: DSpace
- **URL**: https://indigo.uic.edu/
- **OAI**: WAF blocking (202 challenge page)
- **NRA**: 10.6%, 1,469 PhDs/yr
- **Status**: Web Application Firewall blocks automated access

---

## Tier C: Blocked by Cloudflare/WAF

These universities use Cloudflare or similar WAFs that return challenge pages for all programmatic access, including sitemaps, OAI-PMH, and REST APIs.

### Texas A&M — OakTrust
- **Platform**: DSpace 7
- **URL**: https://oaktrust.library.tamu.edu/
- **OAI**: `https://oaktrust.library.tamu.edu/server/oai/request` → 403
- **REST API**: Cloudflare "Just a moment..." challenge
- **Sitemap**: 403
- **NRA**: 30.0%, 1,462 PhDs/yr
- **Priority**: HIGH (high NRA + high volume)
- **Approach needed**: Browser automation (Playwright/Selenium) to bypass Cloudflare

### U Michigan — Deep Blue
- **Platform**: DSpace
- **URL**: https://deepblue.lib.umich.edu/
- **OAI**: `https://deepblue.lib.umich.edu/oai/request` → 403
- **REST API**: Cloudflare challenge
- **Sitemap**: 403
- **NRA**: 21.7%, 1,630 PhDs/yr
- **Priority**: HIGH (large research university)
- **Approach needed**: Browser automation or institutional contact

### U Pittsburgh — D-Scholarship
- **Platform**: EPrints
- **URL**: https://d-scholarship.pitt.edu/
- **OAI**: `https://d-scholarship.pitt.edu/cgi/oai2` → 403
- **Sitemap**: Cloudflare challenge
- **NRA**: 17.2%, 1,133 PhDs/yr
- **Approach needed**: Browser automation

### Johns Hopkins — JScholarship
- **Platform**: DSpace
- **URL**: https://jscholarship.library.jhu.edu/
- **OAI**: 403 Forbidden
- **REST API**: 403 Forbidden (CDN-level block)
- **NRA**: 25.8%, 863 PhDs/yr
- **Priority**: HIGH (high NRA)
- **Approach needed**: Direct institutional contact or browser automation

### Arizona State — KEEP
- **Platform**: Custom (formerly bepress)
- **URL**: https://keep.lib.asu.edu/
- **OAI**: 403
- **Repository**: https://repository.asu.edu/ → redirects, no API
- **NRA**: 25.7%, 865 PhDs/yr
- **Priority**: MEDIUM-HIGH
- **Approach needed**: Investigate KEEP platform API or browser automation

---

## Tier D: Custom Platforms Needing Investigation

### U Florida — IR@UF / UFDC
- **Platform**: Islandora / SobekCM (custom)
- **URL**: https://ufdc.ufl.edu/ (React SPA)
- **OAI**: Returns HTML, not XML
- **NRA**: 18.4%, 1,906 PhDs/yr (LARGEST GAP)
- **Priority**: HIGHEST by volume
- **Notes**: Largest doctoral program in the US. UFDC is a custom digital collections platform. ETDs may be at a different URL. Check https://ir.ufl.edu/ or contact UF Libraries.

### USC — USC Digital Library
- **Platform**: Custom
- **URL**: https://digitallibrary.usc.edu/
- **OAI**: 404
- **NRA**: 15.5%, 1,796 PhDs/yr
- **Priority**: HIGH by volume
- **Notes**: May need to investigate USC's thesis submission system separately

### NYU
- **Platform**: Unknown (ProQuest?)
- **URL**: https://archive.nyu.edu/ → 400 Bad Request
- **OAI**: Not accessible
- **NRA**: 20.2%, 1,498 PhDs/yr
- **Notes**: NYU may only submit theses to ProQuest, not an institutional repository

### Rutgers — RUcore
- **Platform**: Fedora (custom frontend)
- **URL**: https://rucore.libraries.rutgers.edu/
- **OAI**: 404
- **NRA**: 15.0%, 1,403 PhDs/yr
- **Notes**: Custom Fedora-based system. May have an API but not at standard paths.

---

## Access Pattern Reference

### OAI-PMH Endpoints (most common)
```
# bepress
https://{domain}/do/oai/?verb=ListSets

# DSpace 5
https://{domain}/oai/request?verb=ListSets

# DSpace 7
https://{domain}/server/oai/request?verb=ListSets

# Hyrax
https://{domain}/catalog/oai?verb=ListSets

# Blacklight
https://{domain}/catalog/oai?verb=ListRecords&metadataPrefix=oai_dc
```

### DSpace 7 REST API
```
# Find ETD community/collection
GET {domain}/server/api/core/communities?size=100
GET {domain}/server/api/core/collections?size=100

# Resolve handle to UUID
GET {domain}/server/api/pid/find?id={handle}

# Get item metadata (includes dc.degree.discipline, thesis.degree.department, etc.)
GET {domain}/server/api/core/items/{uuid}
```

### Solr/Blacklight JSON API
```
# Search with facets
GET {domain}/catalog.json?per_page=100&page=1&f[resource_type_sim][]=Dissertation
```

### Degree Type Fields by Platform

| Platform | PhD Field | MS Field | Department Field |
|---|---|---|---|
| bepress OAI | `oai_set` contains `dissertation` | `oai_set` contains `theses` | `subject` or `oai_set` dept codes |
| DSpace OAI | `dc:type` = "Doctoral" | `dc:type` = "Masters" | `dc:subject` |
| DSpace REST | `dc.degree.level` = "dissertation" | `dc.degree.level` = "thesis" | `dc.degree.discipline` or `dc.contributor.department` |
| Blacklight | `relation` = "PHD" | `relation` = "MASTERS" | From web scrape |
| UVA API | `degree` starts with "PHD" | `degree` starts with "MS"/"MA" | `program` field |
| Northwestern Solr | `resource_type_tesim` = "Dissertation" | `resource_type_tesim` = "Masters Thesis" | `subject_tesim` |

---

## Enrichment Approach

For universities where OAI metadata lacks department/degree info, use the DSpace REST API to fetch richer metadata per record:

1. Extract handle from OAI identifier (e.g., `oai:repository.edu:1840.20/39933` → `1840.20/39933`)
2. Resolve handle to UUID: `GET /server/api/pid/find?id={handle}`
3. Fetch metadata: `GET /server/api/core/items/{uuid}`
4. Extract `dc.degree.discipline`, `dc.degree.level`, `thesis.degree.department`
5. Use concurrent requests (15 threads) for speed — completes 19K records in ~12 minutes vs 5+ hours serial

See `scripts/enrich_concurrent.py` for implementation.

## Latest Findings (2026-03-30)

### Playwright Results

**Cloudflare bypass**: Works with `headless=False` (headed mode). Headless Chrome is detected.

**U Michigan (Deep Blue)**:
- Cloudflare bypassed successfully in headed mode
- 98,560 items in sitemap, but no ETD-specific community or collection
- OAI-PMH and REST API both disabled/404
- SSR pages have citation meta tags (citation_title, citation_author, etc.)
- Approach: need to scrape all 98K items, identify ETDs by type, then extract metadata
- Estimated effort: 98K items × 5s delay = ~5.5 days serial, or ~12 hours with headed Playwright + delays

**UNC Chapel Hill**:
- Sitemap scan complete: 3,541 dissertations + 1,630 masters papers
- JSON API at /concern/dissertations/{id}.json works but rate-limited aggressively
- Playwright with headed mode should handle rate limiting better
- Needs resumed scrape with checkpoint support

### Recommended Next Steps
1. Run UNC Playwright scraper overnight (~3-4 hours)
2. Run U Michigan Playwright scraper over a weekend (~12+ hours)  
3. Try Texas A&M with same Playwright approach

