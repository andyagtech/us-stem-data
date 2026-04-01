# California Dissertation Scraping Plan

## Priority Targets

### 1. Caltech — CaltechTHESIS (EPrints static site)
- **IPEDS 2024**: 400 total PhDs, 187 STEM, 42.5% NRA
- **Platform**: EPrints 3.3, currently served as **static HTML** (due to bot protection)
- **URL**: https://thesis.caltech.edu
- **Data available**: 1911–2026, browse by year/degree/author/advisor/option
- **Degree types**: PhD (Dissertation), Masters, Engineer, Bachelor's, Senior
- **Approach**: Scrape static HTML year-by-year pages (116 years)
  - Year index: `https://thesis.caltech.edu/view/year/YYYY.html`
  - Each year page lists all theses with author, title, and link
  - Individual thesis pages at `https://thesis.caltech.edu/NNNNN/` have full metadata
  - OAI-PMH endpoint (`/cgi/oai2`) is **down** (timeouts) — must use HTML scraping
- **Estimated records**: ~10,000+ total, ~200/year recent
- **Difficulty**: ⭐⭐ Easy — clean static HTML, well-structured
- **Key advantage**: Has degree type (PhD vs Masters separation!) and department/option field

### 2. USC — No Public Repository ❌
- **IPEDS 2024**: 1,764 total PhDs, 333 STEM, 28.5% NRA (BIGGEST gap)
- **Platform**: No open ETD repository found
  - `digitallibrary.usc.edu` — media/photo archive (OrangeLogic), not theses
  - `repository.usc.edu` — Drupal CMS for archive news articles
  - `usc.esploro.exlibrisgroup.com` — Esploro, but login-only (no public sitemap)
  - `usclibraries.usc.edu/thesis` — ETD submission portal, login-only
  - Primo catalog has library records but not structured ETD metadata
- **Status**: USC dissertations appear to be **ProQuest-only**
- **Workaround options**:
  - ProQuest Dissertations & Theses database (requires institutional access)
  - Could potentially use the Primo API to extract catalog records for USC dissertations
    (limited metadata: title, author, date — no subjects/departments)
- **Difficulty**: ⭐⭐⭐⭐⭐ Blocked — no public ETD repository

### 3. SDSU — CalState ScholarWorks (Hyrax/Samvera)
- **IPEDS 2024**: 284 total PhDs, 26 STEM, 12.7% NRA
- **Platform**: CalState ScholarWorks (shared across all 23 CSU campuses)
- **URL**: https://scholarworks.calstate.edu
- **Data available**: 2,482 "Dissertation" records across all CSU campuses
- **API options**:
  - **OAI-PMH**: `https://scholarworks.calstate.edu/catalog/oai` — has campus sets
    - Set: `campus:San Diego` (and other campuses)
  - **JSON API**: `https://scholarworks.calstate.edu/catalog.json?f[resource_type_sim][]=Dissertation`
    - Can filter by campus, paginate through results
    - Fields: title, creator, campus, date, keywords, resource_type
- **Approach**: OAI-PMH harvest with set filter, or JSON API pagination
  - OAI-PMH is simpler and well-tested (same as Portland State)
  - JSON API gives richer faceting
- **Estimated records**: ~200-300 for SDSU specifically
- **Difficulty**: ⭐⭐ Easy — OAI-PMH or JSON API, same as existing scrapers
- **Bonus**: Can grab ALL CSU campus dissertations in one go (2,482 total)

### 4. Santa Clara — ScholarCommons (bepress/Digital Commons)
- **IPEDS 2024**: 48 total PhDs, 7 STEM, 37.5% NRA
- **Platform**: bepress / Digital Commons
- **URL**: https://scholarcommons.scu.edu
- **OAI-PMH**: `https://scholarcommons.scu.edu/do/oai/`
- **Dissertation sets**:
  - `publication:ed_dissertations` — Ed.D. dissertations (~22)
  - `publication:jst_dissertations` — Jesuit School of Theology (~154)
  - `publication:eng_phd_theses` — Engineering PhDs
  - `publication:phil_doc` — Philosophy doctoral
- **Approach**: OAI-PMH harvest (same method as Portland State)
- **Estimated records**: ~200 total
- **Difficulty**: ⭐ Very easy — bepress OAI-PMH, same as PSU
- **Note**: Very small program, low priority for STEM analysis

## Execution Order

1. **Caltech** — Highest STEM value (187/yr), clean scraping, degree separation
2. **SDSU/CSU ScholarWorks** — Easy OAI-PMH, bonus: all 23 CSU campuses at once
3. **Santa Clara** — Trivial OAI-PMH but tiny (7 STEM PhDs/yr)
4. **USC** — Blocked; revisit if Primo API proves viable

## Notes
- USC is the single biggest gap (333 STEM PhDs/yr) but has no public repository
- CalState ScholarWorks covers SDSU, SF State, CSU Fullerton, CSU Long Beach, etc.
  — all CSU campuses with doctoral programs
- Caltech has explicit degree type separation (PhD vs Masters) which UC lacks
