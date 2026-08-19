# High-NRA subject / year index — build notes and findings

Built 2026-08-18 from IPEDS Completions (survey component C, part A) on disk in
`data/ipeds/`. No sibling ground-truth dataset existed under `data/ipeds/` when
this ran (only the raw `C*_A` files and the pre-existing
`ipeds_stem_phd_*.csv` STEM extracts, which cover only 9 CIP families and carry
no per-cell NRA counts), so the extraction was done directly here.

**What "NRA" means.** NRA is the IPEDS federal reporting category
"Nonresident alien" (renamed "U.S. Nonresident" in recent collections): a
residency/visa status reported by the institution for each completer. It is not
ethnicity, not race, and not country of origin, and nothing below should be read
as a statement about any of those.

## 1. Where the index lives

| File | Size | Contents |
|---|---|---|
| `data/ipeds/nra_index.csv.gz` | 1.2 MB | 260,170 rows: `year,unitid,cipcode,basis,total,nra` — one row per institution x CIP x year |
| `data/ipeds/cip_titles.csv` | 71 KB | 1,643 CIP 2020 titles + 2-digit family titles |
| `data/ipeds/nra_index_meta.json` | 7 KB | build date, per-year coverage, award-level rule, caveats |
| `scripts/build_nra_index.py` | — | builder (~26 s for all 30 years, streams the CSVs, reads `C2025_A.zip` in place) |
| `scripts/query_nra_index.py` | — | CLI |

Total disk footprint 1.3 MB (gzipped because the volume has <1 GB free).
No duckdb/pandas dependency — the builder and CLI are stdlib only (openpyxl is
used once for CIP titles and degrades gracefully). Rebuild with
`python3 scripts/build_nra_index.py`.

Coverage: **1995-2025**, 260,170 cells, 1,149 institutions. 1984-1994 are
excluded on purpose: those completions files carry only `CRACE15/CRACE16`
(grand totals by sex) with no residency detail, so no NRA share exists for them.
1990 and 1999 are missing upstream.

## 2. How to query it

```bash
# subjects with the highest NRA share in 2025, cohorts of 100+
python3 scripts/query_nra_index.py --level subject --year 2025 --min-total 100

# the most extreme university-subject-year cells since 2015
python3 scripts/query_nra_index.py --level cell --start 2015 --min-total 20

# one department across institutions, years pooled
python3 scripts/query_nra_index.py --level cell --cip 14.1001 --start 2020 --pooled --min-total 50

# one institution
python3 scripts/query_nra_index.py --level cell --inst "texas at dallas" --start 2022 --min-total 10

# how many cells survive at each cohort threshold
python3 scripts/query_nra_index.py --thresholds --level cell --start 2020

# 30-year trend, rolled up to CIP families
python3 scripts/query_nra_index.py --trend --cip 11 --cip 14 --cip 27 --family --min-total 100
```

Levels: `national`, `subject` (CIP x year), `institution` (institution x year),
`cell` (institution x CIP x year, the finest grain).
Filters: `--start/--end/--year`, `--cip` (prefix, repeatable), `--unitid`,
`--inst` (name substring), `--state`, `--min-total`, `--min-share`, `--basis`.
Modifiers: `--family` (2-digit rollup), `--pooled` (collapse the year range),
`--sort share|total|nra|year`, `--top N`, `--csv`.

Institution names resolve from `data/ipeds/HD2024.csv` first, then every other
`hd*.csv` newest-first so closed and retired reporting units still get a name.

## 3. Minimum cohort threshold

Small cells are the whole trap: 4,992 institution-CIP-year cells at 100% NRA in
2020-2025 are almost all cohorts of 1-3 people. Survival counts, per-year cells,
2020-2025:

| min cohort | cells | >=50% NRA | >=75% | >=90% | ==100% |
|---|---|---|---|---|---|
| 1 | 59,824 | 18,450 | 8,306 | 5,231 | 4,992 |
| 5 | 31,041 | 8,542 | 3,089 | 785 | 546 |
| 10 | 13,843 | 3,885 | 1,236 | 315 | 76 |
| **20** | **4,496** | **1,127** | **331** | **45** | **5** |
| 30 | 2,102 | 423 | 108 | 7 | 0 |
| 50 | 701 | 68 | 15 | 1 | 0 |
| 100 | 184 | 2 | 1 | 0 | 0 |

**Chosen default: `--min-total 20` for per-year cells**, because that is where
the 100%-NRA artefacts collapse from ~5,000 to 5 while still leaving 4,496 real
departments to rank. It is a CLI parameter, not a constant — every number below
states the threshold it used. For "most extreme department" claims, prefer the
pooled multi-year view at `--min-total 50`, which is far more stable.
At the national subject level the equivalent threshold is 50-100 completions
(2024: 741 CIP codes total, 380 survive at 20, 150 at 100).

## 4. Findings — subjects, nationally

### 4a. Highest-NRA subjects, 2020-2025 pooled, cohort >= 1,000 (the fields that actually matter by volume)

| CIP | Subject | Doctorates | NRA | NRA share |
|---|---|---|---|---|
| 27.0501 | Statistics, General | 2,873 | 2,077 | **72.3%** |
| 14.1001 | Electrical and Electronics Engineering | 12,936 | 9,242 | **71.4%** |
| 14.0901 | Computer Engineering, General | 2,287 | 1,629 | **71.2%** |
| 14.3501 | Industrial Engineering | 2,291 | 1,604 | **70.0%** |
| 14.0801 | Civil Engineering, General | 6,808 | 4,660 | **68.4%** |
| 45.0603 | Econometrics and Quantitative Economics | 6,498 | 4,293 | 66.1% |
| 11.0101 | Computer and Information Sciences, General | 4,947 | 3,240 | 65.5% |
| 11.0701 | Computer Science | 8,682 | 5,593 | 64.4% |
| 14.0101 | Engineering, General | 2,724 | 1,634 | 60.0% |
| 14.1901 | Mechanical Engineering | 10,660 | 6,278 | 58.9% |
| 45.0601 | Economics, General | 1,333 | 774 | 58.1% |
| 51.2010 | Pharmaceutical Sciences | 1,298 | 740 | 57.0% |
| 52.1301 | Management Science | 1,000 | 569 | 56.9% |
| 26.1102 | Biostatistics | 1,550 | 826 | 53.3% |
| 14.1801 | Materials Engineering | 4,338 | 2,228 | 51.4% |

### 4b. Highest-NRA subjects at any cohort >= 200, same window

Two small fields outrank everything above:
**22.0201 Advanced Legal Research/Studies (S.J.D./J.S.D.) 85.2%** (466
doctorates) and **14.2501 Petroleum Engineering 79.4%** (656). Also above 70%:
04.0902 Architectural and Building Sciences 70.3% (229), 14.3701 Operations
Research 70.2% (557), 01.0103 Agricultural Economics 68.2% (387), 14.4701
Electrical and Computer Engineering 65.9% (845), 11.0102 Artificial
Intelligence 62.0% (258 — a code that barely existed before 2021).

### 4c. Most extreme single subject-years, 1995-2025, cohort >= 50

| Year | CIP | Subject | Total | NRA share |
|---|---|---|---|---|
| 2011 | 14.2501 | Petroleum Engineering | 59 | 94.9% |
| 2023 | 22.0201 | Advanced Legal Research/Studies | 61 | 93.4% |
| 2011 | 22.0201 | Advanced Legal Research/Studies | 134 | 93.3% |
| 2009 | 22.0201 | Advanced Legal Research/Studies | 115 | 92.2% |
| 2016 | 14.2501 | Petroleum Engineering | 105 | 91.4% |
| 2015 | 22.0201 | Advanced Legal Research/Studies | 68 | 91.2% |
| 2012 | 22.0201 | Advanced Legal Research/Studies | 122 | 90.2% |
| 2020 | 27.0305 | Financial Mathematics | 59 | 88.1% |

The top of this list is dominated by two niche programs (research doctorates in
law, and petroleum engineering) that are almost entirely non-resident cohorts
every year. The volume story is 4a.

## 5. Findings — university x subject x year

### 5a. Pooled 2020-2025, cohort >= 50 (the robust list)

| Institution | ST | CIP | Subject | Total | NRA share |
|---|---|---|---|---|---|
| Case Western Reserve University | OH | 22.0203 | American/U.S. Law/Jurisprudence | 97 | 95.9% |
| Illinois Institute of Technology | IL | 14.1001 | Electrical and Electronics Eng. | 51 | 94.1% |
| Indiana University-Bloomington | IN | 22.0201 | Advanced Legal Research/Studies | 50 | 94.0% |
| Florida State University | FL | 27.0501 | Statistics, General | 103 | 93.2% |
| Washington University in St Louis | MO | 14.1001 | Electrical and Electronics Eng. | 54 | 92.6% |
| Pennsylvania State University | PA | 45.0603 | Econometrics and Quant. Economics | 66 | 92.4% |
| Florida International University | FL | 14.0801 | Civil Engineering, General | 86 | 91.9% |
| Widener University | PA | 22.0205 | Banking/Corporate/Finance Law | 57 | 91.2% |
| Washington University in St Louis | MO | 45.0603 | Econometrics and Quant. Economics | 65 | 89.2% |
| University of California-Riverside | CA | 14.1001 | Electrical and Electronics Eng. | 134 | 88.8% |
| Pennsylvania State University | PA | 11.0701 | Computer Science | 89 | 88.8% |
| Northwestern University | IL | 14.3501 | Industrial Engineering | 62 | 88.7% |
| Lamar University | TX | 14.0101 | Engineering, General | 53 | 88.7% |
| Washington State University | WA | 14.1001 | Electrical and Electronics Eng. | 79 | 88.6% |
| University of Akron | OH | 14.0701 | Chemical Engineering | 52 | 88.5% |
| Missouri S&T | MO | 14.1001 | Electrical and Electronics Eng. | 77 | 88.3% |
| Ohio State University | OH | 14.0901 | Computer Engineering, General | 153 | 86.3% |
| New York University | NY | 14.1001 | Electrical and Electronics Eng. | 145 | 86.9% |

2,589 institution-subject groups clear cohort 50 in this window.

### 5b. Most extreme single years, 1995-2025, cohort >= 20

100% NRA cells that clear the threshold are rare and worth naming exactly:
Iowa State 14.0501 Bioengineering 2020 (24/24); Case Western 22.0203 in 2024
(23/23); Penn State (UNITID 495767) 45.0603 Econometrics 2020 (22/22); Florida
State 27.0501 Statistics 2023 (22/22); Washington State 14.0301 Agricultural
Engineering 2020 (21/21). Just below: Stanford 22.0201 in 2005 (32/33, 97.0%),
NC State 14.1001 in 2007 (30/31, 96.8%), Ohio State 14.0901 in 2021 (27/28,
96.4%), Texas A&M 14.1001 in 2008 (26/27, 96.3%), UC-Riverside 14.1001 in 2023
(26/27, 96.3%).

Latest year (2025, cohort >= 20): Washington U. in St Louis CS 90.9%; Ohio State
Computer Engineering 90.0%; Northwestern Econometrics 89.3%; Virginia Tech EE
88.5%; Purdue Civil Engineering 87.5% (40 doctorates); UC-San Diego EE 87.5%;
Purdue Industrial Engineering 87.5%; Rice CIS 87.0%.

### 5c. Whole institutions, 2020-2025 pooled, >= 100 doctorates

Stevens Institute of Technology 74.1%, NJIT 72.2%, Missouri S&T 69.0%, South
Dakota State 66.1%, Illinois Tech 65.3%, Clarkson 64.5%, Michigan Tech 61.8%,
UT Dallas 60.8%, Worcester Polytechnic 59.0%, RIT 58.5%, Purdue 57.2% (4,830
doctorates — by far the largest institution above 55%), UT Arlington 56.1%,
Carnegie Mellon 56.0%, Georgia Tech 52.8%, Binghamton 52.0%, Iowa State 51.2%,
Rice 51.1%, RPI 51.0%. This independently reproduces the ordering the site
already uses for its high-NRA university list.

## 6. Trend over time

National NRA share of all US research doctorates is remarkably flat:
25.6% (1995) -> 23.2% (1998) -> 27.8% (2007) -> 27.1% (2014) -> 27.7% (2020) ->
27.5% (2022) -> **25.5% (2025)**, on a completions base that grew from 44.8k to
87.8k. The national aggregate is not the story, and a chart of it would
understate the case.

The story is concentration. By CIP family (NRA %, min 100 completions/year):

| Family | 1995 | 2000 | 2005 | 2010 | 2015 | 2020 | 2025 |
|---|---|---|---|---|---|---|---|
| 11 Computer and Information Sciences | 46 | 48 | 55 | 50 | 56 | 59 | 56 |
| 14 Engineering | 49 | 51 | 63 | 55 | 56 | 60 | 55 |
| 27 Mathematics and Statistics | 45 | 46 | 54 | 46 | 50 | 55 | 53 |
| 40 Physical Sciences | 35 | 36 | 43 | 41 | 39 | 39 | 38 |
| 45 Social Sciences | 24 | 21 | 36 | 33 | 30 | 36 | 40 |
| 26 Biological/Biomedical Sciences | 27 | 26 | 27 | 28 | 27 | 26 | 23 |

At the program level the leaders have climbed materially over 30 years
(NRA %, min 40 completions/year):

| CIP | Subject | 1995 | 2000 | 2005 | 2010 | 2015 | 2020 | 2025 |
|---|---|---|---|---|---|---|---|---|
| 14.1001 | Electrical and Electronics Eng. | 47 | 57 | 68 | 65 | 68 | 73 | 67 |
| 14.0801 | Civil Engineering, General | 62 | 52 | 67 | 61 | 59 | 68 | 68 |
| 11.0701 | Computer Science | 39 | 43 | 53 | 52 | 61 | 66 | 63 |
| 27.0501 | Statistics, General | 48 | 44 | 68 | 57 | 66 | 71 | 71 |
| 14.3501 | Industrial Engineering | . | . | 65 | 66 | 74 | 73 | 62 |
| 14.2501 | Petroleum Engineering | 59 | 77 | 82 | . | 89 | 79 | 73 |
| 22.0201 | Advanced Legal Research/Studies | . | . | 89 | 90 | 91 | 83 | 79 |
| 45.0603 | Econometrics and Quant. Economics | . | . | . | . | . | 65 | 65 |

("." = fewer than 40 completions nationally that year. 45.0603 only becomes a
populated code in 2017; before that those doctorates sat in 45.0601.)

The sharpest measurable trend is the **spread** of extreme departments. Counting
institution-CIP cells with at least 20 doctorates:

| Year | cells >=20 | of which >=50% NRA | >=75% NRA | doctorates in the >=50% cells | share of all US research doctorates |
|---|---|---|---|---|---|
| 1995 | 350 | 48 | 3 | 1,263 | 2.8% |
| 2000 | 328 | 42 | 6 | 1,233 | 2.7% |
| 2005 | 412 | 70 | 33 | 2,050 | 3.8% |
| 2010 | 442 | 86 | 15 | 2,571 | 4.5% |
| 2015 | 584 | 133 | 28 | 4,001 | 5.8% |
| 2020 | 642 | 166 | 56 | 4,960 | 6.7% |
| 2022 | 756 | 207 | 61 | 6,130 | 7.6% |
| 2025 | 875 | 202 | 47 | 6,418 | 7.3% |

Majority-non-resident departments (>=20 doctorates) went from 48 to ~200 over
30 years, and the share of all US research doctorates produced inside such
departments went from 2.8% to 7.3% — while the national NRA share barely moved.
That is the data-supported version of the project's claim: not that the country
as a whole shifted, but that the fields and departments where it is concentrated
grew.

## 7. Method, gotchas handled, and caveats

Verified against the files today, all encoded in `build_nra_index.py`:

* The first column name carries a UTF-8 BOM in every IPEDS CSV — files are read
  with `utf-8-sig` and headers normalised, so `UNITID` resolves.
* **CIPCODE '99' is the institution-level grand total** and is excluded.
  Cross-check: UT Dallas 2024, sum over real CIP rows = 239 doctorates /161 NRA,
  identical to the CIPCODE-99 row, and identical to what the index returns.
* CIPCODE values are space-padded in the 2008-2010 files (`'99     '`) and
  quoted before 2008; both are stripped before comparison. Missing this silently
  leaves the aggregate rows in and doubles every institution.
* AWLEVEL is zero-padded (`'09'`), compared as an integer.
* MAJORNUM is absent before 2003; where present only first majors count (second
  majors are 356 of 170,846 doctorate completions in 2024, ~0.2%).
* Residency columns: legacy `CRACE01+CRACE02` = NRA and `CRACE15+CRACE16` =
  grand total before 2008; `CNRALT`/`CTOTALT` from 2008 on. In 2008-2010 the
  legacy and modern *race-detail* columns do coexist row by row, but
  `CNRALT`/`CTOTALT` are populated on every row under either scheme (verified:
  zero blanks across all three years), so the residency and total measures used
  here need no cross-scheme summing.
* Award level: AWLEVEL 9 for 1995-2007 (first-professional was AWLEVEL 10, so
  code 9 is research-only); 2008-2009 is a transition — institutions using
  17/18/19 get 17, institutions still on 9 get 9 (verified: zero institutions
  use both). 2010+ is AWLEVEL 17 only. The `basis` column records which rule
  produced each row (`--basis aw09|aw17` filters on it). Transition-year
  institutions still on code 9 run ~5 points lower on NRA share than their
  17-coded peers (2009: 24.3% vs 30.9%), so treat 2008-2009 comparisons with
  care; the family-level trends move smoothly across the break.
* CIP vintages differ (CIP1990 1995-99, CIP2000 2000-09, CIP2010 2010-19,
  CIP2020 2020+). Six-digit codes are not perfectly comparable across the
  boundaries — 45.0603 and 11.0102 are recent codes carved out of older ones.
  Two-digit family rollups (`--family`) are comparable throughout. Titles come
  from the CIP2020 dictionary shipped with C2023; retired codes render as
  "(title not in CIP2020 list)".
* Reporting-unit changes split some institutions across UNITIDs: Penn State
  reported under 495767 in 2020-2021 and 214777 otherwise. The index keeps
  UNITIDs exactly as reported and does not merge them.
* Revised (`_RV`) files are used only when the unrevised file is absent, which
  matches `scripts/ipeds_filter.py` so this index agrees with the rest of the
  repo. 2025 is read directly out of `C2025_A.zip`.
* NRA counts are capped at the reported total (`min(nra, total)`) — this never
  binds in the current data, it just guarantees shares are within 0-100%.
