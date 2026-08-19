# tools_demographics.py — build notes (2026-08-18)

One new file: `/Users/andy/usds_china/cloud/chat/tools_demographics.py` (1,030 lines).
Exports exactly `SCHEMAS` (3 schemas) and `IMPL` (3 callables). No shared file was edited.

`_fn` / `_clamp` / `UNTRUSTED` are **replicated, not imported**. The registry lives in
`tools.py`/`handler.py`; if the registry imports this module and this module imports
`tools`, that is a cycle. Six lines of duplication beats a circular import.

Artifacts are rebuilt with `python3 cloud/chat/tools_demographics.py --build` — the
builder lives under a `__main__` guard inside the module rather than in `scripts/`,
so I stayed at one new file and the module cannot drift from the files it reads.

---

## 1. Data shipped to `chat_data/`

| file | size | rows | why |
| --- | --- | --- | --- |
| `doctoral_race_by_cip.csv.gz` | 2.452 MB | 297,360 | unitid x year x awlevel x cipcode, first majors, all 14 measures |
| `hd_states.csv.gz` | 0.023 MB | 6,072 | unitid -> STABBR, CONTROL from `hd2024.csv` |
| `sheeo_state_compact.json.gz` | 0.059 MB | 52 states | SHEEO 2010-2025 reduced to 11 fields |
| **my footprint** | **2.534 MB** | | |

**5 MB of ground truth down to 2.45 MB, provably losslessly.** I ship one of the three
ground-truth files. The other two are exact roll-ups of it, which I verified rather than
assumed: summing `doctoral_nra_by_cip.csv.gz` to the 2-digit family reproduced
`doctoral_nra_by_cip2.csv.gz` on all 14 measures with **0 mismatched cells of 135,238**,
and summing it to the institution reproduced `doctoral_inst_totals.csv.gz` with
**0 mismatched cells of 40,065**. `cip2` and institution levels are therefore computed
at query time (warm `by_state` call: 0.126 s). Second majors (`majornum=2`, 1,501 rows,
0.00–0.14% of first-major totals) are dropped at build time. Sorting rows by
(unitid, cipcode, year) before gzip -9 buys ~7%.

Cold parse: **0.57 s for 297,360 rows, 111 MB RSS** — the chat Lambda is 1024 MB / 45 s
(`infra/chat/template.yaml`), and the loader is lazy, so a question that touches none of
these tools pays nothing.

**Budget note for you.** `chat_data/` is now **8.9 MB**, over the ~6 MB target — but not
because of me: another agent added `search_index.bin` (3.89 MB) and grew
`universities_compact.json` from 0.66 to 1.52 MB while I worked. My 2.53 MB is the number
I control. If you need to claw back space from my share, the one clean cut is dropping the
four sex columns (`total_men/total_women/nra_men/nra_women`) from the race file: measured
at **1.95 MB**, taking my footprint to 2.03 MB, and costing the men/women split in every
result. I did not take that cut unasked because the sex split is real analytic content and
it is not recoverable from anywhere else in `chat_data/`.

---

## 2. The three schemas

### `completions_breakdown`
Race / ethnicity / citizenship breakdown of doctoral completions, 1996-2025 — the thing no
existing tool exposed.

| param | type | notes |
| --- | --- | --- |
| `level` | enum | `national`, `institution`, `cip2` (default), `cip`, `institution_cip` |
| `university` | string | site key (mit, stanford, …); resolved via `ds.universities()` |
| `unitid` | string[] | alternative / additive to `university` |
| `cip` | string[] | CIP prefixes, e.g. `["14"]` or `["14.10"]` |
| `year` | int | 1996-2025, default 2025 |
| `awlevel` | enum | `17`,`18`,`19`,`9`,`10`; defaults to 17 from 2010, else 9 |
| `min_total` | int | row floor; warns below 20 at department grain |
| `sort` | enum | `total` (default) or `nra_share` |
| `limit` | int | 1-40, default 20 |

Handled neutrally as instructed: the result names the nine categories as *IPEDS reporting
categories*, states in `definition` that 'Nonresident' is a visa status reported separately
from the eight race/ethnicity categories (so the race columns describe US citizens and
permanent residents), and states that 'Race and ethnicity unknown' is a real category that
is **not** redistributed. No commentary, no derived indices, no "diversity" framing.

### `by_state`
`metric` (required): `doctorates` | `nra_share` | `majority_nra_departments`. All three are
returned on every row regardless; `metric` only sorts. Plus `year`, `top` (1-60),
`cip`, `min_total` (department cohort floor, default 20), `min_state_total` (default 20),
`awlevel`.

### `state_funding_vs_output`
`state` (required — name, two-letter code, or `US`), `start`, `end` (2010-2025).

Full JSON of all three is in `SCHEMAS` (5,103 bytes serialised).

---

## 3. Real worked results

**a) `completions_breakdown({level:'national', year:2024})`** — award level 17, 85,245 doctorates:

```
nra 21,909 (25.7%)   white 35,845 (42.0%)   black 9,174 (10.8%)   hispanic 6,456 (7.6%)
asian 5,156 (6.0%)   unknown 4,203 (4.9%)   two_or_more 2,133 (2.5%)
aian 263 (0.3%)      nhpi 106 (0.1%)
men 38,590   women 46,655   nra_men 13,322   nra_women 8,587
```

**b) `completions_breakdown({university:'mit', year:2024, level:'cip2'})`** — top row,
CIP 14 Engineering: total 289, nra 152 (52.6%), white 76, asian 28, hispanic 12,
two_or_more 7, unknown 7, black 6, aian 1, nhpi 0; men 190 / women 99.
Cross-checked by summing the untouched source `doctoral_nra_by_cip.csv.gz` independently:
total 289, nra 152, white 76, asian 28 — exact.

**c) `by_state({metric:'majority_nra_departments', year:2024, top:8})`**

```
CA  9,634 doctorates  24.2% NRA  80 institutions  27 majority-NRA departments
TX  6,457             29.8%      59              21
NY  5,108             33.9%      54              13
IL  3,365             34.4%      37              12
IN  2,186             37.5%      16              12
PA  3,693             31.2%      40              11
NC  2,466             29.0%      18              11
MA  3,721             34.6%      27              10
national: 85,245 doctorates, 21,909 NRA, 25.7%, 181 majority-NRA departments (53 states/territories)
```

**d) `state_funding_vs_output({state:'Michigan', start:2024, end:2024})`**
education_appropriations_real25 $3,179,731,130.14; output: 2,267 doctorates total,
2,118 public / 149 private, 740 NRA, 32.6% overall and 34.2% at public institutions.

**e) `state_funding_vs_output({state:'TX', 2022-2025})`** — FY2025 appropriations
$14,766,254,392 nominal (= real25, HECA multiplier 1 in the base year), $13,537.12 per net
FTE, 1,090,797 net FTE; output 6,131 doctorates (4,816 public, 1,315 private), 30.3% NRA
overall, 33.0% public.

---

## 4. Caveats wired into the results

`AWLEVEL_CAVEAT` rides on every result from all three tools, and I re-derived every number
in it from the files today rather than restating it:

* Level 17 is the research doctorate; pre-2010 doctorates were level 9; the two are not the
  same universe and must never be printed side by side without saying so.
* **Zero institution overlap in the transition, confirmed:** 2008 has 621 institutions on
  the legacy scheme vs 224 on the modern one, 2009 has 437 vs 416, 2010 has 850 modern and
  0 legacy — intersection empty in all three years. So any single-scheme count for 2008 or
  2009 is a partial count of the country; both tools emit an extra "treat this year as
  unusable" caveat when `year` is 2008 or 2009.
* **Level 9 was broader than 17:** in 2007 it recorded 8,359 health-professions doctorates
  (CIP 51) against 3,939 at level 17 in 2010, the balance having moved to level 18
  (53,385 there in 2010). Same pattern in theology (CIP 39: 1,881 → 961 + 878).

**One correction to the brief, and it matters.** The brief says level 9 "ALSO counted MD and
JD". The files say otherwise: MD and JD were **first-professional, award level 10**, not 9.
Level 9 in 1996 carried 91 law awards in total and 74 in 2000; CIP 51.12 (medicine) has
**zero** level-9 awards in any year. I kept the comparability warning — it is correct and
important — but restated its reason as the professional-practice migration above, and put
the MD/JD finding in the result as `AWLEVEL_MD_JD` so nobody re-derives it. Asserting
"level 9 includes MDs" to a user would have been a false statement of fact.

Also carried:
* `SOURCE_QUIRKS` — 2002-2007 last header cell is `'CRACE24 '` with a trailing space
  (verified: `head -1` on c2002/c2005_rv/c2007_rv all end `CRACE24 `); 1996-2001 files stop
  at CRACE16 and have no combined-sex total columns at all, so total and nra for those years
  are men+women, which IPEDS' own later files confirm as an identity
  (`CRACE24 == CRACE15 + CRACE16`, 0 exceptions in 200,336 rows of c2002). Nothing
  interpolated. Both quirks are handled upstream in `build_ipeds_nra_ground_truth.py`; I
  state them because the figures are downstream of them.
* `PROVISIONAL_2025`, `UNIVERSE_CAVEAT` (level 17 is not the NSF SED universe: 82,438 in
  2023 vs ~57,900 SED).
* `state_funding_vs_output` leads with `join_caveat` (SHEEO is a **state total for public
  higher education**, not a grant to any university) and `coverage_mismatch` (appropriations
  fund public institutions; the output column counts private ones too — hence the
  public/private split via hd2024 CONTROL), plus an explicit "no causal claim is available
  from this join".

## 5. Explicit nulls, never interpolation

* `by_state` puts institutions absent from hd2024 in an `unmapped` block with a reason
  instead of a guessed state — 0 of them in 2024, but 73 institutions / 1,866 doctorates in
  1998. `state_funding_vs_output` reports the same as `excluded_unmapped_institutions`
  (62 institutions, 5,415 doctorates over 2010-2012).
* SHEEO has no D.C. row for FY2010 → `funding: null` + `funding_missing_reason`, not a
  carried-forward 2011 figure.
* Puerto Rico, Guam and the other territories resolve to a named error saying SHEEO does not
  survey territories and pointing at `by_state` for the output side alone — they are *in*
  the completions data.
* `nra_share_public: null` when a state has no public doctorates (D.C.).
* Five 1996 rows (24 awards) where the nine categories do not sum to the total surface as
  `unallocated_residual` + a note; nothing is redistributed.
* Requesting level 17 for 1996 returns `rows: []`, `value: null`, and a reason naming
  level 9.

## 6. Small-cohort guards

`nra_share` ranked by state with `cip:['14']` put Hawaii first on 14 doctorates. States below
`min_state_total` (default 20) are now held out of the ranking into
`states_below_cohort_floor` with a note, still counted in `national`. Department-grain
breakdowns below `min_total` 20 emit a warning that says quote counts, not percentages —
these cells can be single individuals.

## 7. Things to know before you wire it

1. **Ledger interaction.** `blocks.Ledger.add` walks strings with a regex, so the evidence
   numbers inside my `caveats` (8,359 / 3,939 / 621 / 224 / 82,438 …) enter the ledger as
   grounded values. It is a mild loosening of the anti-fabrication check. If you want it
   tight, strip `caveats` from the payload before `ledger.add` in `handler.py` — that is
   your file, not mine.
2. `test_local.py` currently reports **1 FAILED: "fabricated chart was rejected" (rejected=0)**
   in the end-to-end scenario. Not mine — my module is not imported anywhere yet, and
   `handler.py` and `prompt.py` are both modified in the working tree by other agents.
3. `chat_data/.gitignore` lists only `nra_index.csv.gz` and `cip_titles.csv`; my three
   artifacts are currently un-ignored. Add them if generated files should stay out of git —
   I did not edit that shared file.
4. Nothing was deployed, committed or pushed; `pipeline/` untouched.

## 8. Could not source

Nothing was left unsourced. Every figure in every result comes from
`doctoral_nra_by_cip.csv.gz`, `hd2024.csv` or `sheeo_by_state.json`. The only intentionally
hard-coded table is the state abbreviation → name map (a naming convention, not a
measurement), and SHEEO's `'D.C.'` key spelling is handled there.
