# Methodology page update — 2026-08-18

Files changed: `site/data_sources.html`, `site/implementation.html`. Nothing deployed, nothing
committed. Both files parse clean (no unclosed tags, no duplicate ids, no dangling `#` anchors).

Every figure below was reproduced from a file in the repo before it was written to the page. The
one figure that did not reproduce is listed at the bottom.

---

## What changed, section by section — data_sources.html

### Immigration via Education Pipeline (top box)
- Thesis/dissertation universities 101 → **105**.
- OPT universities `59 (Top 100)` → `59 of 105 (Top 100 list)`.
- LCA coverage `CY 2014-2025` → `CY 2014-2026 (both ends part-years)`; universities 101 → **100**
  (`manifest.json` `data_sources.lca` is true for 100).
- Employer-name note now says matching is on **word boundaries, not bare substrings**, with 296
  patterns, and links to the new Corrections section.

Verified: `pipeline/manifest.json` (105 universities; h1b 101, opt 59, lca 100, perm 71,
enrollment 101, funding 80, dept_links 101), `pipeline/entity_map.json` (296 entries),
`data/h1b/lca_by_university.json` (calendar 2026 = 8,416 certifications vs ~14,000 for full years).

### 1. Federal Datasets
- Lede: "seven major federal data sources" → "ten major data sources… nine federal; the last,
  SHEEO SHEF, is the state-finance series".
- Added a coverage line to the existing DOL/USAspending card: USAspending covers **26 of 105**.
- **New card `#nsf-awards-amp-nih-reporter`** — NSF Award Search + NIH RePORTER, 2020–2025, joined
  to the 101 universities tracked before the August 2026 additions. 2020–2024: **$17.9B** NSF,
  **$64.9B** NIH; 2025 adds **$2.10B** and **$13.72B**. Notes that the four new campuses are not
  yet joined (NSF covers CU Boulder; NIH carries no dollars for CU Boulder or Montana State).
- **New card `#ncses-federal-support-survey`** — NSF 25-339 Table 17, FY2023, 101 matched
  universities, **$22.8B** all-agency obligations of which **$0.89B** is S&E fellowships,
  traineeships and training grants. Carries the LSU system-office note.
- **New card `#sheeo-shef-state-higher-education-finance`** — FY2010–FY2025, with a warning
  callout that it is a *state* figure joined as a proxy, never an institutional one.

Verified: `data/state_funding/nsf_awards/nsf_by_university.json` (102 keys; 2020–2024 sums to
$17.92B, 2025 $2.10B), `data/state_funding/nih_reporter/nih_by_university.json` (105 keys;
excluding the 4 new campuses, 2020–2024 = $64.86B, 2025 = $13.72B — matches the brief exactly on
that basis), `data/federal_support/federal_support_by_university.json` (`_metadata.matched` 101,
FY2023; sums to $22.83B and $0.89B; `system_level` true for `lsu` only),
`data/state_funding/sheeo_by_university.json` (101 universities, 2010–2025, `_meta` names the
SHEF FY25 report).

### 3. Dissertation Metadata Collection
- Removed the unverifiable "approximately 1.4 million theses across 107+ universities… about 80
  high-NRA institutions."
- Replaced with a new `#what-the-corpus-contains` subsection and table: **517,386** records across
  **105** universities — STEM 369,319, non-STEM 148,067, labelled PhD 312,248, labelled Master's
  145,379, **88.4%** labelled (range 24.8%–100%).
- Added the labelling-rate consequence in the registry's wording: unlabelled records are still
  counted and still classified, so a PhD share must never be computed as labelled PhDs ÷ total.
- OAI-PMH row `~100 universities` → `Most of the 105`.

Verified: summed directly from `pipeline/manifest.json` (`records` + `process_nonstem`). All six
of the brief's corpus figures reproduce to the digit.

### 4. Name Classification — rewritten from the measurement
Replaced the two assertion paragraphs with:
- What the classifier actually is (surname lists → 9 categories + confidence, no citizenship input
  or output), plus a warning callout that name origin is not visa status.
- **`#how-much-signal-names-actually-carry`** — the held-out-by-university study, stated as a
  measurement: 1,153 university × CIP-family cells, 5 folds, held out by whole university. Model
  table: field alone 0.639 (RMSE 0.131) → field + names 0.698 (0.120); field + institution's own
  published NRA share 0.713 (0.117) → + names 0.739 (0.112). **Names add 0.059 over field, 0.026
  over field + published NRA share.**
- Explicitly does **not** claim the correlation vanishes: raw r = **0.729** (CI 0.677–0.772,
  cluster-bootstrapped), partial r = **0.382** after university + field + year fixed effects. The
  claim made is that essentially all the apparent signal is field composition, and that what
  survives is most parsimoniously finer-grained field composition.
- **`#where-the-signal-fails`** — ~11 pp RMSE on a quantity whose spread is ~22 points (40% is
  routinely 29% or 51%); by-field table showing Engineering weakest at **r = 0.311** and
  Psychology 0.711 / Education 0.583 strongest.
- Closing callout: this measurement is the reason name classification is kept off the public pages,
  and its legitimate use is as a negative control.

Verified: `scripts/name_signal_study.py` and its written-up output
`scratchpad/name_signal_study.md`. Every number above appears there; the same 0.059 / 0.026 /
0.112 triple is independently corroborated in `cloud/chat/tools_provenance.py`
(`name_origin_is_not_visa_status`), which records that it re-ran the study read-only and
reproduced them exactly.

### 5. Limitations & Caveats — expanded
New card **`#record-years-are-often-deposit-dates`**, placed first because it is the most
consequential: the harvester takes the first `dc:date`, `oai_dc` flattens accessioned/available/
issued, DSpace emits accession first. Measured: 407,462 of 1,035,726 in-window rows (39.3%) carry
a clock time; 72 of 105 universities are above 90%. Worked examples: an Iowa State record storing
2018-08-22T18:45:17 for a 1934 degree, an MIT record storing 2005-08-18T12:00:00Z for a 1996
degree. Warning callout: do not read record years as graduation years or build trends on them;
totals and name compositions are unaffected. Names Northwestern and UVA as known-bad.

Added to the federal-data card:
- IPEDS award-level break 2008–2010 — level 9 is the older, **broader** undifferentiated category,
  not equivalent to 17; a level-17 filter gives 12,347 in 2008 against 57,661 in 2010; figures must
  not be compared across the boundary.
- IPEDS level 17 is not the SED universe (82,438 vs ~57,900 in 2023).
- LCA buckets are calendar years from DECISION_DATE; **calendar 2026 is January–June only** and
  will read as a collapse if presented as annual; start series at 2015, end at the last complete
  year.
- OPT covers **59 of 105** because SEVP publishes a top-100 list; absence is absence of a
  publication, and a missing year is not a drop to zero.
- LSU appears only at system level in the federal support survey.
- USAspending 26 of 105; SHEEO is a state proxy; enrolment/faculty/tuition/aid are dated snapshots.

Added to the dissertation/name card:
- Name classification reproduces a reported NRA share only to within ~11 points (cross-links §4).
- Low labelling rate ⇒ uncertain PhD/Master's split, not missing records (88.4%, 24.8%–100%).
- **Two STEM definitions appear on the same page** — the narrow 8-family set behind the headline
  NRA figure, the broad 16-family set behind the completions chart. Wording below.
- "The 80+ universities shown" → "The 105 universities shown".

Verified: `cloud/chat/tools_provenance.py` CAVEATS registry, whose wording I preferred over the
brief throughout this section; award-level and label figures cross-checked against the registry's
own `verified` fields; the clock-time claim spot-checked directly — 35,588 of 35,589 dated Iowa
State rows and 64,118 of 64,120 MIT rows carry a clock time.

### 6. Corrections — NEW section (`#corrections`)
Sections 6/7/8 renumbered to 7/8/9. **Anchor ids are unchanged** (`#linking`, `#links`,
`#analytics`), and `anchors.js` `slugify()` strips a leading `N. ` from heading text, so no
existing link breaks. TOC updated.

- **`#correction-headline-nra-share`** — 37 of 103 universities were out by more than 5 points,
  21 too low and 16 too high, by as much as 32. Michigan State published at 16.7% against an IPEDS
  figure of 49.0% (1,045 of 2,132). Also names La Tech 22.5→54.3, WSU 18.0→47.2, UF 18.4→45.2 and
  Caltech moving the other way 64.9→41.2. The pinned basis is stated as a table: IPEDS Completions,
  CIP 2-digit families 11/14/15/26/27/30/40/42, 2015–2022, award level 17. Notes that the method
  was never wrong (MIT reproduced exactly, Missouri S&T to 1.1 points) and that CUNY and Mines do
  not resolve and keep their previous values.
- **`#correction-h1b-employer-matching`** — the bare-substring matcher credited every employer
  containing "MIT" to MIT (WIPRO / INFOSYS / TATA CONSULTANCY SERVICES LIMITED named). Total read
  **565,883** against a corpus median near 1,200, with Infosys-style top job titles; matching now
  requires word boundaries and the total reads **3,487**. Only MIT was affected — the only one of
  296 patterns shorter than six characters — and the highest total is now Penn at 5,935.

Verified: `scripts/compute_nra_shares.py --report` run read-only (now reports 0 universities
differing by >5 points, 2 unresolved: cuny, mines); the 37/103, the direction split, the 32.3-point
max and every named pair recomputed by diffing `pipeline/universities.json` across commit
`bf5936c`; `pipeline/universities.json` carries an `nra_basis` block for 103 universities;
`data/h1b/lca_by_university.json` gives mit 3,487, upenn 5,935 highest, median 1,167.

### 8. Links to Original Sources
- LCA `FY2026 Q1` → **`FY2026 Q3 (through June 2026)`**.
- Added rows: NSF Award Search (2020–2025), NIH RePORTER (2020–2025), Federal Support Survey Table
  17 / NSF 25-339 (FY2023), SHEEO SHEF (FY2025).
- Footer date April 1, 2026 → **August 18, 2026**.

Verified: `data/h1b/lca/` holds 32 xlsx with `lca_FY2026_Q3.xlsx` newest and FY2026 Q1 moved to
`superseded/`.

---

## implementation.html — brought into agreement

It was internally inconsistent before this pass (105 configs in two places, 101 in five others).

| Was | Now | Source |
|---|---|---|
| 101 universities / repositories / configs (7 places incl. og+twitter description) | 105 | manifest.json |
| 294K records (top chip) | 517K | manifest.json |
| 294K records (harvest chip) | 1.25M "Harvested Rows" | counted 1,245,380 rows over 108 `*_etds.csv` |
| 292 employer name mappings (4 places) | 296 | entity_map.json |
| Labeling rate ~82% | 88.4%, range 24.8%–100% | manifest.json |
| PERM 72 universities (2 places) | 71 | manifest.json |
| H-1B 98 / LCA 78 chips | 101 / 100 | manifest.json |
| 7 "Gov Data Sources" chip | 10 "Data Sources" | matches the new §1 count |
| LCA FY2015–2025 | FY2013–FY2026 Q3 | files on disk |
| — | new paragraph: employer matching is on word boundaries, was a bare substring, MIT 565,883 → 3,487, links to `/data_sources.html#corrections` | as above |

Left alone deliberately: `og:image:alt` / `twitter:image:alt` on implementation.html still say
"101 repositories" because they describe the *rendered PNG*, which I did not regenerate. Updating
the alt text without the image would make the two disagree. The `og:description` and
`twitter:description` text, which is not tied to the image, was updated to 105.

---

## Figures from the brief I could NOT reproduce

**One.** The accession-date measurement: "59.9% of Iowa State's in-window records and 19.2% of
MIT's were awarded outside the window, median lag 24 and 49.5 years."

Nothing on disk supports it. Comparing a stored deposit date against a true issued date requires a
`date_issued` column, and neither `data/western_us_dissertations/iowa_state_etds.csv` nor
`mit_etds.csv` has one — both carry only the single `date` column. The harvester has since grown a
`_pick_issued_date()` / `date_issued` field (`scripts/scrape_oai_etds.py`), but no shipped CSV has
been reharvested with it, so the comparison cannot be made without a live OAI sweep of both
repositories. **I left those four numbers out.**

What I published instead is the registry's verified version — 39.3% of in-window rows clock-
timestamped corpus-wide, 72 of 105 universities above 90%, and the two live worked examples — plus
my own spot-check confirming the direction is if anything understated: 100.0% of dated Iowa State
rows and 100.0% of dated MIT rows carry a clock time.

## Two places where I measured something different from what I was told

Both are published as measured, not as briefed.

1. **Corpus median LCA total.** The brief said MIT's 565,883 stood "against a corpus median of
   1,035". Post-reparse the median over 104 universities is **1,167**, so the page says "a corpus
   median near 1,200". The registry's "near 1,000" is also pre-reparse.

2. **How far the two STEM definitions diverge.** The mid-task note said "up to about 3 points" and
   `compute_nra_shares.py` says "about a point". On the pinned 2015–2022 / level-17 window the
   median absolute gap is **1.9 points**, but the tail is much longer than either estimate: UNLV is
   32.3% narrow against 15.1% broad (**17.3 points**), Missouri 50.2 vs 35.1, USC Columbia 47.0 vs
   37.8. The page states the median and names UNLV as the worst case. **Worth knowing before that
   "one honest sentence" is written anywhere else** — the divergence is not a rounding-scale issue
   for every university.
