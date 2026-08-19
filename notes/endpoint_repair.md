# OAI-PMH endpoint repair — 2026-08-18

Scope: the 14 endpoints flagged unhealthy in `endpoint_health.json`.
All re-probes used a realistic browser User-Agent, a 60-90s timeout, and polite delays.
Only `Identify`, `ListSets`, `ListMetadataFormats`, `GetRecord`, and single `ListRecords`
pages were issued. Config file touched: `/Users/andy/usds_china/scripts/scrape_oai_etds.py`
(REPOS entries only).

## Summary

| repo | old endpoint | verdict | new endpoint | evidence |
|---|---|---|---|---|
| gatech | `https://repository.gatech.edu/server/oai/request` | was transient | unchanged | Identify HTTP 200 in 1.5s, `repositoryName=Georgia Tech Digital Repository` |
| uhouston | `https://uh-ir.tdl.org/server/oai/request` | was transient | unchanged | Identify HTTP 200 in 1.3s, `repositoryName=DSpace at UH` |
| utaustin | `https://repositories.lib.utexas.edu/server/oai/request` | was transient | unchanged | Identify HTTP 200 in 0.3s, `repositoryName=DSpace at UT Austin` |
| cu_boulder | `https://scholar.colorado.edu/catalog/oai` | was transient (User-Agent) | unchanged | 403 with our UA and the healthcheck UA; 200 with a browser UA |
| uiuc | `https://www.ideals.illinois.edu/oai-pmh` | was transient (User-Agent) | unchanged | 403 with our UA and the healthcheck UA; 200 with a browser UA |
| montana_state | `https://scholarworks.montana.edu/server/oai/request` | was transient (our IP is blocked) | unchanged | TCP+TLS succeed, HTTP response withheld from our egress; fetched from a second network the same URL returns `repositoryName=ScholarWorks`, `earliestDatestamp=2012-10-24` |
| ncstate | `https://repository.lib.ncsu.edu/server/oai/request` | still broken (blocked, not moved) | unchanged | Anubis 1.24.0 proof-of-work challenge for every UA tried, from two networks |
| gmu | `https://mars.gmu.edu/server/oai/request` | fixed | `https://digitalcollections.gmu.edu/oai2d` | mars.gmu.edu 301s to digitalcollections.gmu.edu; DSpace replaced by TIND/Invenio; Identify 200; set `gmu_lib:ir_collections` = 8,123 records |
| uwmadison | `https://minds.wisconsin.edu/oai/request` | fixed | `https://minds.wisc.edu/server/oai/request` | DSpace 6 to 7 path change plus host move; set `com_1793_82418` returns 100 records, `completeListSize=3037`, all `dc:type=Thesis` |
| uw_seattle | `https://digital.lib.washington.edu/researchworks/server/oai/request` | fixed | `https://digital.lib.washington.edu/server/oai/request` | `/researchworks` is the Angular UI base only; OAI is at host root. Set `com_1773_4888` "Dissertations and Theses" = `completeListSize=19695`, all `dc:type=Thesis` |
| ndsu | (none configured) | fixed, but gated | `https://library.ndsu.edu/server/oai/request` | DSpace 7.6.2 "DSpace at NDSU"; set `com_10365_26050` = `completeListSize=4810`, types Thesis 62 / Dissertation 31 / Master's paper 6 on page 1. Requires a bot-check cookie |
| nmtech | `https://nmt.edu/oai` | fixed | `https://zenodo.org/oai2d` (set `user-nmt`) | NMT has no local repository; Skeen Library uses Zenodo. Community `nmt` = "NMT Dissertations & Theses", 13 records |
| nmsu | `https://scholarworks.nmsu.edu/do/oai/` | host fixed, but **no ETDs published** | `https://digitalcommons.nmsu.edu/do/oai/` | Live bepress "Digital Commons @ NMSU"; ListSets returns 64 sets, none for ETDs; `publication:dissertations` and `publication:gradschool` both return `noRecordsMatch` |
| umaine | `https://digitalcommons.library.umaine.edu/do/oai/` | **permanently unavailable** | none | Host DNS removed; DigitalCommons@UMaine sunset 2026-06-30; migrated to Ex Libris Alma Specto; Alma OAI returns `error_code 21` unauthorized |

## Repositories that have permanently stopped publishing OAI-PMH

### umaine — University of Maine (hard stop)

DigitalCommons@UMaine is gone. `digitalcommons.library.umaine.edu` no longer resolves
(NXDOMAIN), and neither do `digitalcommons.umaine.edu` or `scholarworks.umaine.edu`.
The University of Maine System joined the Ex Libris **Alma Specto** Early Adopter Program
(announced November 2025); admin upload rights in Digital Commons were removed
2026-03-05 and the platform was sunset 2026-06-30. ETDs are now surfaced through Primo:

- ETD collection: `https://maine.primo.exlibrisgroup.com/nde/collectionDiscovery?collectionId=81524274960008681&vid=01MAINE_INST:DigCol&lang=en`
- Honors theses: `...collectionId=81524277600008681...`

The standard Alma OAI endpoint exists but is not published:

```
GET https://maine.alma.exlibrisgroup.com/view/oai/01MAINE_INST/request?verb=Identify
-> HTTP 403
<error><error_code>21</error_code>
<error_message>Unauthorized access to the OAI services - please contact the system
administrator for assistance</error_message></error>
```

`https://api-na.hosted.exlibrisgroup.com/oai/01MAINE_INST/request` returns
`SERVICE_NOT_FOUND`. **Alternative for a future scraper:** the Primo NDE REST API
(`maine.primo.exlibrisgroup.com/primaws/rest/pub/...`) backing the collectionDiscovery
view. Enabling Alma's OAI integration profile is a one-setting change on UMaine's side,
so asking the library is the cheaper fix.

### nmsu — New Mexico State University (repository alive, no ETDs in it)

The configured host is dead, but the repository itself moved rather than closed:
`digitalcommons.nmsu.edu/do/oai/` serves a healthy bepress Identify
(`repositoryName = Digital Commons @ NMSU`). It has **no ETD collection**. ListSets
returns 64 sets covering departments, datasets, faculty publications, OER and journals;
the closest is `publication:gradschool` ("Graduate School"), and both it and the old
`publication:dissertations` return `noRecordsMatch`. The gradschool landing page lists no
theses series. NMSU routes ETDs to ProQuest ETD Administrator
(`etdadmin.com/nmsuetd`) and the subscription "Dissertations@NMSU" database, so there is
no open-access ETD source to harvest. The old `publication:dissertations` setting was
never verified (the entry carried a "needs verification - DNS down" comment).

`oai_base` was updated to the live host and the entry marked `disabled: True`, so the
health sweep stops reporting a DNS failure while nothing gets harvested.

## Blocked, not moved

### ncstate — NC State (Anubis bot wall)

`https://repository.lib.ncsu.edu/server/oai/request` is still the right URL — `robots.txt`
is served as `text/plain` and is a stock DSpace robots.txt — but every other path returns
an Anubis 1.24.0 proof-of-work challenge page with HTTP 200. Tested User-Agents, all
challenged: Chrome browser string, `curl/8.7.1`, `python-urllib/3.11`, the project's own
`Western-US-PhD-Research/1.0`, `OAIHarvester/2.0`, and `Googlebot/2.1`. A fetch from a
different network was challenged too, so this is not IP reputation. Solving the challenge
requires executing the JS proof-of-work. No config change made; the entry now carries a
comment. **Fix path: ask NCSU Libraries to allowlist the harvester's User-Agent.**

### ndsu — NDSU (cookie bot-check)

Found and verified, but gated. `library.ndsu.edu` 302s any cookie-less request to
`/bcheck/?origurl=...`, which serves a "Check box if human" form. POSTing
`humancheck=yes` to `/bcheck/validate` sets `user_ok=ishuman` (about 6 months TTL), after
which `https://library.ndsu.edu/server/oai/request` answers normally. The harvester uses
bare `urllib` with no cookie jar, so it cannot get through. Entry configured correctly and
left `disabled: True` with the mechanism documented in a comment.

### montana_state — our own IP is blocked

Not a moved endpoint and not a slow one. From this network the TCP connect and TLS
handshake to `scholarworks.montana.edu:443` succeed (valid InCommon cert, HTTP/2
negotiated) and then the server closes without sending a response — `RemoteDisconnected`
on every one of 5 attempts spaced 15s apart, over both HTTP/2 and HTTP/1.1, with and
without a browser UA. The same URL fetched from a different network returns a normal
Identify. Consistent with a WAF ban triggered by the HTTP 429 the health sweep hit.
No config change. Needs a cool-off plus 429 backoff before the next harvest.

## The shared-code finding (for the main session, not changed here)

`cu_boulder` and `uiuc` are pure User-Agent rejections, not moved endpoints:

| host | `Western-US-PhD-Research/1.0 (academic research)` | `phd-demographics-healthcheck/1.0` | Chrome UA |
|---|---|---|---|
| scholar.colorado.edu | 403 | 403 | 200 |
| www.ideals.illinois.edu | 403 | 403 | 200 |

Both endpoints in REPOS are already correct. The durable fix is the `HEADERS` constant at
the top of `scrape_oai_etds.py` (a shared code path), which is the main session's to land.
Note this does *not* generalize to ncstate (challenges every UA including Googlebot) or
montana_state (IP-level).

## Timeout re-test detail

All three "read timeout" failures responded on the first retry, well under the original
30s budget:

```
repository.gatech.edu/server/oai/request        HTTP 200  1.5s
uh-ir.tdl.org/server/oai/request                HTTP 200  1.3s
repositories.lib.utexas.edu/server/oai/request  HTTP 200  0.3s
```

The health sweep's 30s timeout was not the problem; these were momentary. No config
change for any of them.

## GMU migration detail

`mars.gmu.edu` issues a 301 to `digitalcollections.gmu.edu`. The new platform is TIND
(Invenio-derived — `invenio.css`, `tind.js`, `unapi-server` link), not DSpace, so the
`/server/oai/request` and `/oai/request` paths 404. OAI-PMH is at the Invenio-standard
`/oai2d`, matching the existing `uga` entry's convention.

ListSets exposes exactly three sets:

```
gmu_lib:da_collections   SCRC Digital Collections
gmu_lib:ir_collections   MARS Digital Repository
gmu_lib                  gmu_lib
```

ETDs live inside `gmu_lib:ir_collections` alongside articles and reports — there is no
ETD-only set. Confirmed by GetRecord on two known GMU dissertations:

- record 81913 — setSpec `gmu_lib:ir_collections`, MARC `502 $b Doctoral $c George Mason
  University $g Cultural Studies`
- record 77773 — setSpec `gmu_lib:ir_collections`, MARC `502 $b Master's $g Earth Systems
  Science`

Note for whoever harvests it: in `oai_dc` every record reports `dc:type = Text`, so ETDs
cannot be separated by type. The `marcxml` prefix is also offered and carries field 502
with degree level and discipline, which is both the ETD filter and the degree labels.
The parent `gmu_lib` set is 74,333 records (mostly `980$a = DA`, digitized archives) and
should not be used.

## Note on uw_seattle's disabled flag

The entry's old comment, "General repository, no thesis-specific collection", is
demonstrably wrong now: `com_1773_4888` "Dissertations and Theses" holds 19,695 records
(and `com_1773_53079` "Dissertations, Theses, & Capstones" a further 525). The endpoint
and set are fixed and verified, but `disabled: True` was left in place because turning a
new ~20K-record repository on is a harvest-scope decision for the main session.

## Files changed

`/Users/andy/usds_china/scripts/scrape_oai_etds.py` — REPOS entries for gmu, nmtech,
nmsu, umaine, ndsu, uw_seattle, uwmadison, and a comment-only change on ncstate. Nothing
else touched. Post-edit `Identify` re-verification:

```
gmu          HTTP 200  Identify=True  repositoryName=George Mason University Libraries Digital Collections
nmtech       HTTP 403 from this network; 200 via a second network (Zenodo)
nmsu         HTTP 200  Identify=True  repositoryName=Digital Commons @ NMSU
umaine       no oai_base (recorded unavailable)
ndsu         HTTP 200  Identify=True  repositoryName=DSpace at NDSU
uw_seattle   HTTP 200  Identify=True  repositoryName=ResearchWorks
uwmadison    HTTP 200  Identify=True  repositoryName='MINDS@UW'
ncstate      HTTP 200  Identify=False (Anubis challenge, unchanged and expected)
```
