# Western US PhD Institution Scraping Plan

## Target States: WA, OR, CA, ID, WY, MT, CO, UT, NM, AZ, NV

## Status Legend: ✅ Done | 🟢 Running | 🔵 Ready (OAI/easy) | 🟡 Medium | 🔴 Hard/Blocked

---

## Already Scraped (16 institutions)
| University | STEM PhDs | Platform |
|---|---|---|
| ✅ UC System (10 campuses) | 27,595 | OAI-PMH (eScholarship) |
| ✅ Stanford | 5,694 | Cocina JSON API |
| ✅ Caltech | 1,864 | EPrints HTML (Phase 2 enriching) |
| ✅ UW Seattle | 4,212 | DSpace 7 sitemap+SSR (85%, needs resume) |
| ✅ WSU | 1,523 | Esploro sitemap+SSR |
| ✅ Portland State | 452 | OAI-PMH (bepress) |
| ✅ U Oregon | 909 | DSpace 8.1 sitemap+SSR (51%, needs resume) |

## Phase 1: OAI-PMH Harvests (fast, ~minutes each)
| # | University | State | STEM PhDs | Platform | OAI Endpoint | ETD Set |
|---|---|---|---|---|---|---|
| 🔵 1 | U Arizona | AZ | 2,340 | DSpace 5 | repository.arizona.edu/oai/request | com_10150_129649 (2,804 theses) |
| 🔵 2 | U New Mexico | NM | 963 | bepress | digitalrepository.unm.edu/do/oai/ | publication:etds + 42 dept sets |
| 🔵 3 | CO School of Mines | CO | 1,088 | DSpace | repository.mines.edu/oai/request | com_11124_7 (Theses & Dissertations) |
| 🔵 4 | Montana State | MT | 462 | DSpace | scholarworks.montana.edu/server/oai/request | com_1_732 |
| 🔵 5 | U Montana | MT | 297 | bepress | scholarworks.umt.edu/do/oai/ | publication:etd (38 dept sets) |
| 🔵 6 | NM Tech | NM | 133 | ? | needs probe | |

## Phase 2: DSpace REST API / Sitemap Scrapes (medium, ~hours)
| # | University | State | STEM PhDs | Platform | Approach |
|---|---|---|---|---|---|
| 🟡 7 | CSU Fort Collins | CO | 1,791 | DSpace 9 | mountainscholar.org sitemap (4,741 items) |
| 🟡 8 | U Wyoming | WY | 651 | DSpace 7 | wyoscholar.uwyo.edu REST API (6,476 items) |
| 🟡 9 | U Idaho | ID | 393 | ? | needs probe |
| 🟡 10 | Boise State | ID | 200 | ? | needs probe |
| 🟡 11 | Idaho State | ID | 168 | ? | needs probe |
| 🟡 12 | NM State | NM | 547 | DNS down | blocked — retry later |

## Phase 3: Larger / Harder Targets
| # | University | State | STEM PhDs | Platform | Approach |
|---|---|---|---|---|---|
| 🟡 13 | ASU | AZ | 3,000 | KEEP OAI | 47,753 records, filter to ETDs |
| 🔴 14 | CU Boulder | CO | 2,959 | Hyrax/Samvera | 403 blocked, needs workaround |
| 🟡 15 | USC | CA | 3,115 | ? | user researching |
| 🟡 16 | U Nevada Reno | NV | 881 | ? | needs probe |
| 🟡 17 | UNLV | NV | 559 | ? | needs probe |
| 🟡 18 | U Utah | UT | 2,340 | ? | needs probe |
| 🟡 19 | BYU | UT | 710 | ? | needs probe |
| 🟡 20 | Utah State | UT | 632 | ? | needs probe |
| 🟡 21 | Oregon State | OR | 1,533 | Hyrax/Samvera | previously blocked |
| 🟡 22 | OHSU | OR | 382 | ? | needs probe |
| 🟡 23 | CU Denver/Anschutz | CO | 960 | ? | needs probe |
| 🟡 24 | U Denver | CO | 464 | ? | needs probe |
| 🟡 25 | Northern Arizona | AZ | 221 | ? | needs probe |

## Smaller / Non-STEM Heavy (low priority)
- Claremont Graduate (443 STEM), San Diego State (400), Loma Linda (378)
- Northern Colorado (213), UCCS (183), Adams State (48)
- Montana Tech (16), Northwest Univ (91), Seattle Pacific (176)
- Palo Alto Univ, Cal Inst Integral Studies, Biola, etc.

## Resume Needed
- UW Seattle: crashed at 21,516/25,290 (85%)
- U Oregon: paused at 51%
- Caltech Phase 2: running (38% enriched)
