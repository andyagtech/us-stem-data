# Stevens Institute of Technology — Data Acquisition Plan

## Why Stevens Matters
- **68.3% NRA** — 3rd highest among all institutions tracked
- ~67 STEM PhDs/year (2022 IPEDS), ~670 over 2015-2024
- UNITID: 186867, Hoboken NJ
- Departments: Mechanical Eng, Computer Science, Electrical Eng, Chemical Eng,
  Biomedical Eng, Physics, Math, Systems Engineering

## Current Status
- **No open institutional repository** — `scholar.stevens.edu` DNS is dead (decommissioned)
- **No OAI-PMH endpoint** available
- Theses submitted exclusively via **ProQuest ETD Administrator** (siteId=320)
- ProQuest hosts Stevens dissertations 1955-present, master's theses 2017-present
- Stevens' library page (library.stevens.edu/td) directs users to ProQuest

## Options (ranked by feasibility)

### Option A: OATD Metadata Harvest
- **OATD.org** indexes open-access theses from ProQuest and other sources
- Stevens dissertations that authors opted into open access should appear here
- OATD has an OAI-PMH endpoint: `https://oatd.org/oai?verb=Identify`
- Can filter by institution: `set=Stevens+Institute+of+Technology` (needs probing)
- **Coverage**: Partial — only open-access submissions (likely 30-50% of total)
- **Fields available**: title, author, date, subject, abstract
- **Effort**: Low — standard OAI harvest
- **Status**: OATD OAI returns 403 Forbidden (blocked as of Mar 2026)
- **Fallback**: Could try OATD web search + scrape instead of OAI

### Option B: ProQuest PQTD Open Scrape
- **PQTD Open** (pqdtopen.proquest.com) hosts dissertations where authors paid
  the open-access fee
- Can search by institution and scrape metadata
- **Coverage**: Very partial — only authors who paid ~$100 for open access
- **Fields available**: title, author, date, subject, abstract
- **Effort**: Medium — need custom scraper for ProQuest search results page

### Option C: ProQuest Central via Library Proxy
- Full ProQuest Dissertations & Theses database has ALL Stevens theses
- Requires institutional subscription access
- Could potentially access via a subscribing library's proxy
- **Coverage**: Complete
- **Legal concern**: Terms of service may prohibit bulk downloading
- **Effort**: High — need proxy access + careful scraping within ToS
- **Not recommended** for this project

### Option D: Stevens Library Direct Request
- Contact Stevens' Archives & Special Collections
- Request metadata export of dissertation records (title, author, date, department)
- Academic research use case is legitimate
- **Coverage**: Complete
- **Effort**: Low technical, but depends on library cooperation
- **Timeline**: Weeks to months

### Option E: Manual Construction from Commencement Programs
- Stevens publishes commencement programs listing PhD recipients
- Could extract names + departments from PDFs
- **Coverage**: Complete for recent years
- **Effort**: High — manual PDF parsing
- **Not recommended** unless other options fail

## Recommended Approach
1. **Probe OATD OAI** for Stevens records (Option A) — quick win, partial data
2. **Scrape PQTD Open** for additional open-access records (Option B)
3. If coverage insufficient, **email Stevens library** (Option D)

## Probe Commands
```bash
# Check if OATD OAI has Stevens data
python3 -c "
import urllib.request
url = 'https://oatd.org/oai?verb=ListSets'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=30)
data = resp.read().decode()
# Look for Stevens in set list
if 'Stevens' in data:
    print('Stevens set found in OATD')
"

# Try OATD direct search
python3 -c "
import urllib.request
url = 'https://oatd.org/oai?verb=ListRecords&metadataPrefix=oai_dc&set=Stevens+Institute+of+Technology'
..."
```

## Expected Yield
- OATD + PQTD Open: ~200-400 records (partial coverage)
- Library request: ~670 records (complete 2015-2024)
- Net impact on analysis: Moderate — 68.3% NRA makes even partial data valuable
