# Great Plains & Upper Midwest Scraping Plan

**States**: ND, SD, NE, KS, OK, MN, IA, MO, AR, LA (TX skipped)
**Institutions**: 88 PhD-granting (IPEDS 2015-2024, min 10 PhDs)
**Total PhDs**: 52,763 (2015-2024)

## Phase 1: OAI-PMH Harvests (LAUNCHED)

| Key | University | State | Platform | Set | Est. Records |
|---|---|---|---|---|---|
| `iowa_state` | Iowa State | IA | DSpace | col_20.500.12876_5 | ~15K? |
| `washu` | Wash U StL | MO | bepress | publication:etd | 5,864 |
| `missouri_st` | MO S&T | MO | bepress | doctoral_dissertations | 3,433 |
| `ukansas` | U Kansas | KS | DSpace | com_1808_1260 | 10,361 |
| `kstate` | Kansas State | KS | DSpace | com_2097_1 | ~8K? |
| `unl` | U Nebraska-Lincoln | NE | bepress | publication:dissertations | 16,151 |
| `und` | U North Dakota | ND | bepress | publication:etds | 8,175 |
| `sdsu` | SD State | SD | bepress | publication:etd | 7,872 |
| `usd` | U South Dakota | SD | bepress | publication:diss-thesis | 373 |
| `uarkansas` | U Arkansas | AR | bepress | publication:etd | 5,868 |
| `lsu` | LSU | LA | bepress | gradschool_dissertations + theses | 6,973+ |
| `la_tech` | LA Tech | LA | bepress | publication:dissertations | 1,015 |

## Phase 2: Needs Investigation

| University | State | STEM PhDs | Issue |
|---|---|---|---|
| U Minnesota | MN | 3,377 | OAI works but 0 ETD sets found. Conservancy has 100 sets, none match thesis/dissertation keywords |
| U Missouri-Columbia | MO | 1,104 | MOspace has 50 decade-based ETD sets. Need to harvest all or find umbrella |
| U Iowa | IA | 1,468 | Esploro-based IR, bepress OAI not responding |
| U Oklahoma / OSU | OK | 983+948 | ShareOK OAI set nearly empty (3 records). Need sitemap or REST API |
| NDSU | ND | 501 | OAI endpoint returns 404 |
| Wichita State | KS | 282 | Not probed yet |
| U Tulsa | OK | 270 | Not probed yet |
| UMKC | MO | 447 | bepress OAI not responding |
| SLU | MO | 343 | bepress OAI not responding |

## Phase 3: Small / Blocked

| University | State | STEM PhDs | Notes |
|---|---|---|---|
| Smaller LA schools | LA | various | ULL, UNO, Southern, Xavier, etc. |
| Smaller MN schools | MN | various | Duluth, Mankato, St Thomas, etc. |
| Smaller AR schools | AR | various | UALR, UAMS, etc. |
| Smaller OK schools | OK | various | OU Health Sci, Langston, etc. |

## Status Legend
- 🟢 Harvesting / Complete
- 🟡 Needs investigation
- 🔴 Blocked
