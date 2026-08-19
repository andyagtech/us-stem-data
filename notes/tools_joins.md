# tools_joins.py — four join tools for the PhD Demographics chat assistant

Owned files (nothing else touched in cloud/chat):

| file | change |
|---|---|
| `cloud/chat/tools_joins.py` | NEW. Exports `SCHEMAS` (4 schemas) and `IMPL` (4 callables). Runnable self-test. |
| `scripts/build_chat_facts.py` | extended: three new fields in the per-university digest + a new `federal_context.json` artifact. |
| `cloud/chat/chat_data/universities_compact.json` | rebuilt: 655 KB -> 1,483 KB |
| `cloud/chat/chat_data/federal_context.json` | NEW, 8 KB |

`chat_data` total: **2.0 MB -> 2.80 MB** (budget ~6 MB).

Not edited: tools.py, blocks.py, handler.py, prompt.py, data_store.py, chat-widget.js,
pipeline/manifest.json, universities.json, entity_map.json, generate_name_lists.py.
Nothing deployed, nothing committed.

## Conventions followed

* schemas built with `tools._fn`; ints clamped with `tools._clamp` (imported, tools.py unmodified)
* per-university data through `data_store.universities()`; doctorate counts through
  `data_store.nra_query()`; free text through `data_store.clean_text()`
* every result carries `source` (the string the render tools must copy), a `scope`/
  `caveats`/`not_a_funnel` note, and `_untrusted` where the payload contains federal or
  scraped free text (job titles, SOC titles, institution names)
* errors returned, never raised: unknown key -> `{"error", "did_you_mean", "hint"}`;
  a value that is not on disk -> explicit `null` plus a `reason`. Nothing interpolated.
* imports work in both layouts (`from . import data_store` / flat Lambda `import data_store`)

## Data added to the digest, and what it cost

| field | source | bytes across 105 universities |
|---|---|---|
| `lca.title_wages` (whole map, per-title count/min/median/max/avg) | `site/data/stem/{key}.json` | ~778 KB |
| `lca.top_soc` (top 10) | same | ~53 KB |
| `lca.top_titles` raised 5 -> 10 | same | ~30 KB |
| `perm.top_titles` (top 10; previously dropped by the scalars-only filter) | same | ~9 KB |
| `federal_context.json` | `data/federal_support/nsf25339-tab017.xlsx` | 8 KB (new file) |

`title_wages` is kept whole rather than trimmed to a top-N: `wages_for(university, title=...)`
must answer for a title the reader names, and a trimmed list silently cannot. 778 KB buys that.

`federal_context.json` is built by a new `build_federal_context()` in
`scripts/build_chat_facts.py` that reads NSF 25-339 Table 17 directly (xlsx parsed with the
standard library — zipfile + ElementTree — so the build gains no openpyxl dependency).
It holds the FY2023 "All institutions" row (all federal obligations $48,961,658,000;
fellowships/traineeships/training $2,456,890,000), the count of ranked institutions (1,110),
the full descending list of the 1,110 training-grant values (for an exact national rank),
recipient percentiles, and the top 10 recipients. Rebuild with
`python3 scripts/build_chat_facts.py --only universities --only federal`.

## The four schemas

1. **`pipeline_for(university, start=2010, end=2025)`** — doctorates -> OPT -> H-1B -> PERM
   on a shared year axis. Returns `stages[]` (each with `unit`, `year_basis`, `agency`,
   `series`), `aligned_by_year[]`, `year_basis_by_column`, `missing[]` and `not_a_funnel[]`.
2. **`funding_per_doctorate(university, year=2023)`** — FY2023 all-agency federal obligations
   and HERD R&D, each per doctorate and per NRA doctorate; plus `fiscal_year_mismatch[]`,
   `interpretation_limits[]`, `nulls[]`.
3. **`training_grants(university)`** — FY2023 S&E fellowships/traineeships/training grants,
   with `national_context` (national total, rank among 1,110, recipient median/p75/p90,
   top 5 recipients) and `site_context` (rank among the 105 site universities).
4. **`wages_for(university, title=None, limit=10)`** — LCA median/quartiles, `top_titles`,
   `top_soc`, per-title wage stats or a title lookup; five `caveats` including the two
   mandated ones; `employer_match_warning` when LCA volume is >10x the site median.

## Worked results

### `pipeline_for("purdue", 2018, 2024)`
`aligned_by_year` (year / doctorates / NRA doctorates / OPT / STEM-OPT / H-1B petitions / approvals):

```
2018  745  395  2353  1197  239   5
2019  730  417  1928  1133  304   5
2020  796  458  1892  1332  155   4
2021  786  450  1670  1391  155   2
2022  804  453  1797  1437  616  20
2023  817  465  2263  1657  177   3
2024  833  481  2445  2014  160   3
```
PERM stage: certified 9, denied 0, total 9 (FY2024 only); top titles Staff Therapist 3,
Assistant Professor 3. `year_basis_by_column` marks doctorates = IPEDS award year,
OPT = calendar year, H-1B = federal fiscal year. `missing` is empty for Purdue; for
Stanford it returns `4_perm` with the reason that no FY2024 PERM filings matched
(71 of 105 universities have any).

### `funding_per_doctorate("purdue")`
doctorates 2023: 817 total / 465 NRA (56.9%) — from the NRA index, UNITID 243780.
Federal obligations FY2023: $301,394,000 all agencies (R&D component $277,977,000, rank 48).
HERD R&D 2023: $844,570,000 (rank 39; stored in thousands in the digest, converted here).

```
federal obligations per doctorate       $368,903
federal obligations per NRA doctorate   $648,159
HERD R&D per doctorate                $1,033,745
HERD R&D per NRA doctorate            $1,816,280
```
`fiscal_year_mismatch` states all three windows explicitly (federal FY Oct-Sep;
institution FY for HERD, an expenditure not an obligation; IPEDS award year ending in June),
and `interpretation_limits` says the NRA denominator is a per-capita index, not spending
on international students.

### `training_grants("purdue")`
$8,737,000 in FY2023 — 2.9% of Purdue's own federal obligations; rank **81 of 1,110**
institutions nationally; 0.356% of the $2,456,890,000 national total; national training
money is 5.02% of all federal S&E obligations to universities. 784 of the 1,110 receive
any; median among recipients $791,000, p75 $2,745,000, p90 $8,869,000. Among the 101 site
universities with a figure Purdue ranks 34th (site median $4,420,000).

### `wages_for("purdue", title="postdoctoral")`
Overall: 4,254 LCAs, median offered wage $72,000 (25th $56,779, 75th $98,703).
Title matches:

```
Postdoctoral Research Associate   562 apps  median $53,000  ($28,870-$78,187)
Postdoctoral Research Assistant   228 apps  median $54,625  ($37,173-$75,000)
Postdoctoral Fellow               172 apps  median $56,160  ($46,530-$75,000)
Postdoctoral Research Associagte    3 apps  median $60,000   [small_sample]
Postdoctoral Appointee              3 apps  median $53,760   [small_sample]
```
(the typo'd title is verbatim federal text, left as-is.) Both mandated caveats are in
`caveats` on every result: calendar years from DECISION_DATE, and "an LCA is an
APPLICATION TO EMPLOY, not a grant / visa / hire".

## Figures I could not source

* **No stage-to-stage linkage anywhere.** No file on disk carries a person-level key, so
  "of N doctorates, M went to OPT" cannot be computed. `pipeline_for` says so in
  `not_a_funnel` and offers no ratios.
* **OPT for 46 of 105 universities.** Only 59 campuses appear in the SEVP Top-100 tables.
  Returned as an explicit `missing` entry with "do not infer zero".
* **PERM is FY2024 only**, and only 71 universities have any — no PERM time series exists.
* **HERD/federal support for `cu_boulder` and `montana_state`** — unmatched in Table 17
  (101 of 105 matched). Those two also lack an IPEDS UNITID in the site index, so
  `funding_per_doctorate` returns three explicit nulls with reasons for them.
* **LCA for 5 universities** (e.g. `uconn`, `uiuc`) — no matched filings; `wages_for`
  returns `wages: null` + reason.
* **Fiscal-year alignment for training grants** — Table 17 publishes the
  fellowships/traineeships/training breakout for the survey year only, so there is no
  trend to show; stated in `caveats`.
* **MIT's LCA and H-1B volumes are contaminated.** MIT shows 565,883 LCAs (site median
  1,029.5) with Infosys-style titles ("Technology Lead - Us"), i.e. employer-name matching
  swept in an unrelated filer. Rather than silently serving it, `wages_for` attaches
  `employer_match_warning` with both numbers. Worth a fix in the LCA/H-1B entity matching
  upstream — outside this task's scope.

## Self-test

`python3 cloud/chat/tools_joins.py [university]` (default `purdue`). Prints a real result
for each tool, walks six negative paths (unknown key, no UNITID, unmatched in Table 17,
no LCA rows, unmatched title, missing PERM stage), and asserts every result carries a
`source` and that the two mandated LCA caveat phrases are present.

```
14 checks, 0 failures
```
Also verified: import works both as `chat.tools_joins` (package) and flat `tools_joins`
(Lambda layout); `SCHEMAS` names == `IMPL` keys (module-level assert); py_compile clean.

## Two things for whoever wires this up

1. `infra/chat/deploy.sh` syncs handler sources by an explicit filename list
   (`for f in handler.py prompt.py tools.py blocks.py data_store.py`). **`tools_joins.py`
   must be added there** or the Lambda will not have it. I did not edit deploy.sh —
   three other agents need the same one-line change and would collide.
2. The same script copies `chat_data/*.json` wholesale, so `federal_context.json` ships
   automatically; it is not in the deploy-time "required artifact" check. `training_grants`
   degrades gracefully (national context null) if it is ever absent.
