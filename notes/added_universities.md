# Adding universities to the PhD Demographics corpus — 2026-08-18

## Summary table

| key | state | UNITID | computed NRA | rows on disk | in-window rows (2016-2026) | added | notes |
|---|---|---|---|---|---|---|---|
| cu_boulder | CO | 126614 | 22.6 | 22,754 | 14,292 raw / **3,136** after `type_filter='dissertation'` | **yes** | 2,477 STEM records after processing; years 2016-2025 evenly spread |
| uky | KY | 157085 | 43.5 | 5,334 | **3,334** | **yes** | 1,915 STEM records; years 2016-2026 evenly spread |
| uconn | CT | 129020 | 49.7 | 7,819 | **1,633** | **yes** | 1,103 STEM records; upstream series stops at 2020 — coverage is 2016-2020 only |
| oregon_state | OR | 209542 | 42.7 | 32,030 | **3** | no | `dc:date` absent from the OAI feed for 32,027/32,030 records — would render empty |
| uga | GA | 139959 | 35.3 | 20,398 | 20,398, but **94% dated 2024** | no | Deposit-date-only repository; this is the exact defect for which UGA was removed in 920d8b7 |
| osu | OH | 204796 | 46.9 | 3,985 | 2,355 | no | Configured OAI set is **"Undergraduate Research Theses and Honors Research Theses"** — not doctoral |
| uhawaii | HI | 141574 | 29.2 | 90 | **13** | no | Near-zero in-window count; would render an effectively empty page |
| uri | RI | 217484 | 17.1 | 104 | **0** | no | Harvest covers 1970-1996 only; zero in-window records |

Three universities added; corpus goes from 102 to 105.

---

## The NRA basis — a correction you should know about

You specified: AWLEVEL=17, CIP families {11,14,15,26,27,30,40,42}, CIPCODE '99'
excluded, `CNRALT`/`CTOTALT` summed over `data/ipeds/C{year}_A.csv`, **2015-2023
inclusive**, sanity-checked against mines=39.8 and binghamton=56.9.

Those two anchors are not both satisfied by a 2015-2023 window:

| basis | mines (stored 39.8) | binghamton (stored 56.9) |
|---|---|---|
| 2015-2023, BOM-aware read | 39.8 (385/967) | **56.4** (429/761) — MISS |
| 2015-2022 | 39.8 (334/840) | **56.9** (388/682) — match |

The reason is the same BOM gotcha you flagged for `hd2024.csv`, and it also
affects the completions files: `C2023_a.csv`, `C2024_a.csv` and `c2025_a.csv`
carry a UTF-8 BOM on the `UNITID` header (`ï»¿UNITID`), while `c2015_a.csv`
through `c2022_a.csv` do not. The idiom `row.get('UNITID')` used in
`scripts/archive/ipeds_nra_asian_ranking.py` therefore returns `None` for every
2023+ row, and those years silently contribute zero. A 2015-2023 loop executed
that way **is** a 2015-2022 sum. Mines rounds to 39.8 either way (39.76 vs
39.81), which is why it does not discriminate; Binghamton does.

Checked against the whole stored corpus (100 entries with a UNITID):

- 2015-2022: **38 exact matches**
- 2015-2023 BOM-aware: **8 exact matches**

So 2015-2022 is both the majority precedent and the only basis reproducing both
anchors you gave. **I used 2015-2022 and documented it in the CONFIGS comment.**

Alternative figures under a BOM-aware 2015-2023 read, if you decide you prefer
that basis instead: cu_boulder 22.9, uky 43.1, uconn 49.5.

**Independently corroborated mid-task.** While I was working, a concurrent
session committed `2489caa` ("montana_state: pin NRA to 15.3% using two anchors,
not one"), reaching the identical conclusion from the identical evidence:

```
  window      mines    binghamton   verdict
  2015-2022   39.76%      56.89%    both match (stored 39.8 / 56.9)
  2015-2023   39.81%      56.37%    binghamton off by 0.5pp
  2015-2024   38.69%      57.13%    neither matches
```

`montana_state` had been the one recent entry whose NRA (16.9) was not
comparable with the 38-entry majority; that commit re-pinned it to 15.3, so the
inconsistency I was going to flag here is already resolved. Two independent
reconstructions landing on 2015-2022 is reasonably strong evidence for it.

---

## What was added

### `pipeline/universities.json`
Three entries appended, following the `umt`/`mines` shape exactly (name, nra,
unitid, empty `harvest`, `processing` block with file/years/dept_source/
type_filter/exclude_type/degree_label/degree_filter/campus_filter,
empty `employer_names`).

### `scripts/generate_name_lists.py`
Three matching entries appended to the `CONFIGS` list literal, under a
"Phase 10" comment that records the NRA basis and the BOM caveat.

All three use `dept_source: 'subject_generic'`. I looked for a better extractor
and there is none: none of the three repositories exposes departmental OAI sets
that a `dept_map` could key on (CU Boulder is a whole-repository Hyrax harvest
with no sets at all; UKy and UConn each expose exactly one flat bepress
publication set), and no repository-specific extractor exists for them in the
`subject_*` family.

**cu_boulder** — `type_filter: 'dissertation'`, `degree_label: 'phd'`.
The CU Scholar harvest is set-less, so the CSV also holds 3,723 Articles,
2,881 Undergraduate Honors Theses, 2,504 Data Sets and 1,261 Masters Theses
in-window. `Dissertation` is CU's doctoral type; the URLs are all
`/concern/graduate_thesis_or_dissertations/`. Dates are genuine issue dates
(plain `YYYY` / `YYYY-MM-DD`, no accession timestamps).

**uky** — `degree_label: 'phd'`. OAI set `publication:gradschool_diss` is
UKnowledge's "Doctoral Dissertations". Bepress emits real publication dates
(`YYYY-01-01T08:00:00Z`).

**uconn** — `degree_label: 'phd'`. OAI set `publication:dissertations` is
opencommons' "Doctoral Dissertations". Real publication dates.

### Heads-up: my edits were swept into someone else's commit
I did not run `git commit` or `git push`. But a concurrent session in this repo
committed `2489caa` while my edits were sitting in the working tree, and that
commit picked them up: its diffstat is `pipeline/universities.json | 62 +` and
`scripts/generate_name_lists.py | 57 +`, which is its own montana_state change
*plus* my three universities. The commit message describes only the
montana_state fix, so the two files' history is now slightly misleading. Content
in HEAD and in the working tree is correct and complete — I verified all three
keys and the Phase 10 block are present in `HEAD`. Flagging it because you may
want to amend the message or note it in the next commit.

Also note that session left ~104 unrelated modified files in the tree
(`data/state_funding/**`, `scripts/refresh_frozen_etds.py`) that were not there
when I started. None of them are mine.

### Verification performed
Loaded all three through the real `load_records()` from
`generate_name_lists.py` (no pipeline run, no manifest edit):

```
cu_boulder: 2477 records, 100% phd, years 2016-2025
            top depts: Physics 359, Engineering 328, Aerospace Eng 213, CS 210
uky:        1915 records, 100% phd, years 2016-2026
            top depts: Mathematics/Statistics 188, Chemistry 151, Physics 138
uconn:      1103 records, 100% phd, years 2016-2020
            top depts: General 603, Physics 79, Health Sciences 58
```

`set(universities.json) == set(CONFIGS keys)` holds (105 keys, 109 CONFIGS rows
including the four `_merge` variants).

### Follow-ups for you (not done, per constraints)
- **`pipeline/entity_map.json` needs three entries for H-1B matching.** It
  currently has no key mapping to `cu_boulder`, `uky` or `uconn`, and no
  Colorado/Kentucky/Connecticut employer strings other than
  `COLORADO SCHOOL OF MINES` and `UNIVERSITY OF NORTHERN COLORADO`. Suggested:
  `UNIVERSITY OF COLORADO -> cu_boulder` (also `UNIVERSITY OF COLORADO AT
  BOULDER`, `REGENTS OF THE UNIVERSITY OF COLORADO`), `UNIVERSITY OF KENTUCKY ->
  uky`, `UNIVERSITY OF CONNECTICUT -> uconn`.
- `employer_names` is `[]` on all three, matching the `umt`/`mines` precedent.
- **UConn's 2021+ gap.** The harvest is complete (log reports "Total available:
  7819", all fetched), but the `publication:dissertations` series itself stops
  at 2020 upstream. The page will show 2016-2020 only. If you want 2021-2026 you
  will need a different UConn source — the ListSets output also exposes
  `publication:uchcgs_diss` ("UCHC Graduate School Dissertations") and a
  "Dissertations and Honors Papers" series, neither of which is currently
  harvested.

---

## Why the other five were not added

### oregon_state (OR) — 32,030 rows, 3 usable
The content is real and would be valuable: 11,724 `Dissertation` + 17,868
`Masters Thesis` records with `degree_type` already populated. But the `date`
column is empty for 32,027 of 32,030 rows.

I checked the source rather than assuming a scraper bug. `ir.library.oregonstate.edu`
runs Blacklight/Hyrax and its `oai_dc` records simply contain **no `<dc:date>`
element at all**:

```xml
<oai_dc:dc ...><dc:contributor>Horner, J.</dc:contributor>
<dc:creator>Williamson, Clyde Everett</dc:creator>
<dc:identifier>https://ir.library.oregonstate.edu/concern/...</dc:identifier>
<dc:language>English [eng]</dc:language><dc:rights>...</dc:rights>
<dc:subject>Penmanship</dc:subject><dc:title>...</dc:title>
<dc:type>Undergraduate Thesis</dc:type></oai_dc:dc>
```

`ListMetadataFormats` offers **only** `oai_dc`, so there is no richer prefix to
switch to. With `allow_no_date: False` every record is dropped (3 survive); with
`allow_no_date: True` all 32,030 collapse onto the year-0 placeholder. Either
way the page is unusable.

There is a second problem: the configured set `2b88qc16g` is not a clean
graduate collection — it returns `Undergraduate Thesis` records and bare image
files (`McGuire map.jpg`, `L71.jpg`) alongside dissertations.

Remediation would require pulling the issue year from outside OAI (the Hyrax
catalog/Blacklight JSON per record), which means changes to
`scripts/scrape_oai_etds.py` — off-limits for me here. This is the highest-value
recovery on the list: 11,724 dissertations are sitting on disk with no year.

### uga (GA) — 20,398 rows, all deposit-dated
Every record's `date` is an Invenio ingest timestamp: 19,148 at 2024, 989 at
2025, 261 at 2026 — 94% in a single year. Verified at the source that this is
upstream, not a harvester bug: the `oai_dc` feed carries exactly one `<dc:date>`
and it is the deposit stamp (`2024-12-05T14:54:59Z`), and the richer
`oai_openaire` prefix reports the *same* value as
`<datacite:date datetype="Issued">2024-12-05</datacite:date>`. UGA publishes no
graduation year in any OAI format it offers.

This is precisely the condition for which UGA was removed in commit `920d8b7`
("Invenio OAI returns deposit date (2024-12-05) for all 19K records, not actual
graduation date"). Nothing has changed; re-adding it would re-introduce the
defect that commit fixed.

### osu (OH) — wrong degree level, not a date problem
This one is a content-validity failure rather than an empty page, and it would
not have been caught by a year-distribution check — the distribution looks fine
(2004-2026, ~150-400/yr).

The configured set `com_1811_133` resolves, via kb.osu.edu's own `ListSets`, to:

```
com_1811_133 | Undergraduate Research Theses and Honors Research Theses
col_1811_134 | Arts and Sciences Undergraduate Research Theses and Honors Research Theses
```

`col_1811_134` alone accounts for 1,948 of the 3,985 rows. Sample descriptions
read "This honors thesis concerns…"; 393 records mention "undergraduate" and 49
mention "honors" explicitly, and `degree_type` is empty on all 3,985. Ohio
State's doctoral dissertations are not in the Knowledge Bank at all — they go to
the OhioLINK ETD Center. Adding this key would inject ~2,355 undergraduate
honors theses into a PhD demographics corpus.

Ohio remains an uncovered state. Filling it needs a different source (OhioLINK),
not this harvest.

Side note: kb.osu.edu does emit three `<dc:date>` values per record —
accessioned, available, then issued (`2007-02-21T19:30:10Z`, same,
`2007-03`) — and the harvester takes the first. For OSU the accession lag
happens to be small, so the misdating is mild here; it is the collection
identity that disqualifies it.

### uhawaii (HI) — 13 in-window records
90 rows total, latest 2016, only 13 falling in 2016-2026. Dates are DSpace
accession stamps. Even taken at face value this renders as an effectively empty
page. Hawaii remains uncovered; ScholarSpace holds far more than 90 ETDs, so the
configured set `com_10125_8002` is almost certainly capturing a small subset.

### uri (RI) — 0 in-window records
104 rows, spanning 1970-1996, **none** after 1996. Note also that the checkpoint
records only `uri:publication:theses` as completed, even though the REPOS entry
lists 41 sets — so 40 of the 41 configured sets were never harvested. Rhode
Island remains uncovered; this is a broken harvest, not a small school, but you
asked me not to add it and I have not.

---

## Verdicts on auburn, uwyoming, shareok

### auburn — the accessioned-date defect does NOT explain the removal

**The premise is off on two counts.** Commit `920d8b7` did not remove Auburn; it
removed **U Georgia**. Auburn was removed 21 minutes earlier, in commit
**`dfeb745`** ("Add data anomaly checker, fix UT Dallas, remove Auburn",
Apr 1 2026 16:51), and the recorded reason was not dates:

> Auburn: removed entirely (OAI contained only journal articles, zero theses).

and in the diff itself:

```python
-    {
-        'key': 'auburn', 'name': 'Auburn', 'nra': 25.6,
-        'file': 'data/western_us_dissertations/auburn_etds.csv',
-        'dept_source': 'subject_generic', 'dept_map': {},
-        'years': (2016, 2024),
-    },
+    # Auburn removed — OAI data contains only journal articles/reports, no theses
```

I verified that reason independently against the file on disk, and it holds
exactly. Of 3,790 rows, **zero** have a `type` mentioning "thesis" or
"dissertation". The type histogram is:

```
  2421  ''
   736  'Text; Journal Article, Academic Journal'
   109  'Text'
    90  'Collection; Journal Article, Academic Journal'
    68  'Text; Technical Report'
    65  'Dataset; Dataset'
    19  'Text; Presentation, Paper Presentation'
    18  'Image; Presentation, Poster Presentation'
```

Titles are things like "Performance of soybean cultivars in Alabama, 2014",
"Christmas tree production in eastern redcedar and Arizona cypress" and "Support
Scholars Who Share". The cause is visible in `scrape_oai_etds.py` REPOS: Auburn
is configured with `"sets": []` and the comment "Harvest all — set filtering
doesn't work on this repo", so the harvest is the entire institutional
repository with no ETD collection filter.

**The date defect is present too, but it is a second, independent problem.**
Auburn's dates are DSpace accession timestamps (`2020-09-23T21:55:06Z`) and
1,812 of 3,790 records — 47.8% — land in 2010, Auburn's DSpace bulk-ingest year.
That would absolutely have tripped the anomaly checker. But it is not the
recorded reason, it was not the blocking reason, and fixing it alone would not
make Auburn usable: you would still have 3,790 journal articles and zero theses.

**Verdict: no.** The accessioned-date defect does not explain Auburn's removal.
Re-adding Auburn requires a set-filtered re-harvest of its actual ETD collection
*and* an issued-date fix — and note that `https://aurora.auburn.edu/oai/request`
now times out with no response at all (verified today, both `Identify` and
`ListRecords`), so the base URL likely needs updating before any re-harvest is
even possible. Not re-added; that call is yours either way.

### uwyoming (WY) — broken OAI set membership, not a small school

WyoScholar holds **6,666 records**. The configured set returns one.

```
ListRecords?set=com_internal_109  ->  1 record, no resumptionToken
ListRecords (no set)              ->  completeListSize="6666"
```

The harvest is not truncated — the checkpoint shows the set completing normally
with a null token. The set genuinely contains one item at the OAI layer.

The cause is visible in the record headers: identifiers come back as
`oai:null:internal/1767` and setSpecs as `com_internal_109` / `col_internal_110`.
This is a DSpace 7 instance whose handle prefix was never configured (hence
`null`) and whose community/collection membership is not being propagated to
OAI set membership. `Identify` gives `earliestDatestamp 2024-02-06`, i.e. the
whole repository was stood up in Feb 2024 and the set mapping was never wired up.

A no-set sample of 100 records shows the content is there and mixed:
`figure` 45, `thesis` 16, `presentation` 10, `media` 9, `report` 5,
`journal contribution` 5. So the workable approach is the CU Boulder pattern:
harvest set-less and filter on `type`, ~6,666 records in, roughly a sixth theses.

That sample also **confirms the accessioned-date mechanism at source**. Records
carry multiple `<dc:date>` values with the accession stamp first and the issued
date last:

```
['2024-02-09T15:52:43Z', '2024-02-09T15:52:43Z', '2016-01-01...']
```

The harvester takes index 0. On a repository stood up in 2024 holding decades of
retrospective content, that maps every record to 2024 — which is exactly the
24-39 year median misdating you described. Any WyoScholar re-harvest must take
the last `dc:date`, not the first.

**Verdict:** broken set mapping upstream plus first-`dc:date` selection in the
harvester. Not added, as instructed. Wyoming remains uncovered.

### shareok (OK) — stale setSpec, collection no longer exposed

The configured set is simply gone:

```
ListRecords?set=col_11244_340716  ->  <error code="noRecordsMatch">No matches for the query</error>
```

The 3 records on disk all carry accession stamps of `2025-02-05T19:20:0*Z`,
seconds apart — they are the tail of a collection that was being ingested at the
moment of the harvest and has since been re-organised or withdrawn from OAI. The
checkpoint shows the set "completing" cleanly, so nothing surfaced the failure.

ShareOK does still serve OAI and exposes **222 sets** (`ListSets` is paged;
the first page of 100 already shows `com_11244_323718 | UCO - Graduate Works and
Theses`, `com_11244_329107 | OU - Undergraduate Student Publications`). The OU
and Oklahoma State PQETD collections are presumably among the remaining 122 sets
that the single-page `ListSets` never enumerated.

Note the same first-`dc:date` issue would apply here: ShareOK is DSpace and the
three captured records are accession-dated.

**Verdict:** stale/removed setSpec, silently swallowed by the checkpoint logic
because `noRecordsMatch` is treated as a completed set. Needs a fresh setSpec
discovered from a fully-paged `ListSets`. Not added, as instructed. Oklahoma
remains uncovered.

---

## Cross-cutting observation

Four separate repositories on this list (auburn, uwyoming, shareok, uri) show
the same failure signature: a harvest "completes" with a null resumption token
after 0-3 records because the configured setSpec is wrong, stale, or unpopulated,
and nothing downstream distinguishes that from a genuinely tiny school. A
post-harvest assertion — e.g. flag any set whose record count is under some
floor, or under some fraction of the repository's `completeListSize` — would
have caught all four at harvest time rather than months later. That belongs in
`scripts/scrape_oai_etds.py`, which I was told not to touch.

Separately, the first-`dc:date` selection affects every DSpace repository in
REPOS, not just the ones examined here. Confirmed instances of accession-first
ordering: auburn, uwyoming, osu (Ohio State), uhawaii. The right fix is to
prefer the last `dc:date` (issued) over the first (accessioned), or better, to
harvest `oai_etdms` / `qdc` where the repository offers it.
