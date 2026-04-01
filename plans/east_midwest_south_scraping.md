# East Midwest & Upper South Scraping Plan

**States**: WI, IL, IN, KY, TN, MS, AL
**Institutions**: 110 PhD-granting (IPEDS 2015-2024, min 10 PhDs)
**Total PhDs**: 79,431 (2015-2024)

## Phase 1: OAI-PMH Harvests (LAUNCHED)

| Key | University | State | Platform | Set | Est. Records |
|---|---|---|---|---|---|
| `marquette` | Marquette U | WI | bepress | publication:dissertations_mu | ~2K? |
| `siu` | SIU Carbondale | IL | bepress | publication:dissertations | 2,321 |
| `niu` | Northern Illinois | IL | bepress | allgraduate-thesesdissertations | 8,163 |
| `purdue` | Purdue | IN | bepress | open_access_dissertations + etd | 2,123 |
| `uky` | U Kentucky | KY | bepress | publication:gradschool_diss | 5,159 |
| `ulouisville` | U Louisville | KY | bepress | publication:etd | 4,638 |
| `umemphis` | U Memphis | TN | bepress | publication:etd | 3,836 |
| `msstate` | Mississippi State | MS | bepress | publication:td | ~5K? |
| `olemiss` | Ole Miss | MS | bepress | publication:etd | ~3K? |
| `usm` | U Southern Miss | MS | bepress | publication:dissertations | ~2K? |

## Phase 2: Needs Investigation (Big Schools)

| University | State | STEM PhDs | Issue |
|---|---|---|---|
| **UW-Madison** | WI | 3,616 | DSpace minds.wisconsin.edu, OAI 404. Needs sitemap/API |
| **UIUC** | IL | 4,027 | IDEALS DSpace, OAI 404 everywhere. Huge target |
| **Northwestern** | IL | 2,393 | No accessible OAI. Needs investigation |
| **U Chicago** | IL | 1,581 | knowledge.uchicago.edu DSpace, OAI 404 |
| **UIC** | IL | 1,419 | indigo.uic.edu returns HTTP 202. Needs investigation |
| **IIT** | IL | 599 | digitalcommons.iit.edu not responding |
| **Purdue** | IN | 4,347 | bepress has limited ETDs; main collection may be elsewhere |
| **IU Bloomington** | IN | 1,315 | scholarworks.iu.edu returns 502 |
| **Notre Dame** | IN | 1,379 | curate.nd.edu returns 202. Needs investigation |
| **UT Knoxville** | TN | 1,776 | TRACE bepress, OAI 404 |
| **Vanderbilt** | TN | 1,713 | ir.vanderbilt.edu returns 403 |
| **Auburn** | AL | 1,175 | etd.auburn.edu exists but OAI 500. Needs scraper |
| **U Alabama** | AL | 755 | ir.ua.edu + acumen.lib.ua.edu, no OAI sets |
| **UAB** | AL | 953 | No accessible repository found |
| **UW-Milwaukee** | WI | 631 | dc.uwm.edu bepress not responding |

## Status Legend
- 🟢 Harvesting / Complete
- 🟡 Needs investigation
- 🔴 Blocked
