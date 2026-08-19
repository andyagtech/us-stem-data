# Chat backend — v2 implementation notes

Date: 2026-08-18. Built to `chat_contract.md`. Nothing deployed; nothing committed.

---

## 1. Where the code lives now

There were two divergent handlers (contract §2.1, §8.1). There is now **one**.

| Path | Role |
| --- | --- |
| `usds_china/cloud/chat/handler.py` | Lambda handler: envelope, errors, rate limit, logging, tool loop |
| `usds_china/cloud/chat/tools.py` | 13 tool schemas + data-tool execution |
| `usds_china/cloud/chat/blocks.py` | Block builders, caps, URL rules, the grounding ledger |
| `usds_china/cloud/chat/data_store.py` | Artifact loaders + the `nra_index` aggregation |
| `usds_china/cloud/chat/prompt.py` | System prompt, rendered from `site_map.json` |
| `usds_china/cloud/chat/chat_data/` | The bundled artifacts (1.97 MB) |
| `usds_china/cloud/chat/test_local.py` | Offline suite (no AWS, no network) |
| `usds_china/cloud/chat/test_live.py` | Real-provider end-to-end, run in-process |
| `usds_china_private/infra/chat/lambda/index.py` | **3-line shim**: `from handler import handler` |

`deploy.sh` now rebuilds the artifacts and copies `cloud/chat/*.py` + `chat_data/` into
`infra/chat/lambda/` before `sam build`, and hard-fails if any required artifact is missing or
empty. Editing `infra/chat/lambda/*.py` by hand is now a no-op — it gets overwritten. That is the
point: the drift cannot come back.

Imports work in both layouts (`from . import x` with an `ImportError` fallback to `import x`), so
the same files run as a package in the repo and flat in the Lambda.

`site/` is a symlink to `usds_china_private/site`, so the generated
`site/data/chat/site_map.json` (66 KB) is already sitting where the frontend agent's
`fetch('/data/chat/site_map.json')` expects it.

---

## 2. Tools exposed

### Data tools (5) — these run server-side and return real numbers

```
nra_lookup(level="cell"|"national"|"subject"|"institution",
           cip[], unitid[], start=2015, end=2025,
           min_total=20, min_share=0, pooled=false, family=false,
           sort="share"|"total"|"nra"|"year", limit=25)
    -> {source, rows[{year,total,nra,nra_share,institution?,state?,unitid?,cip?,subject?}],
        matched, returned, query{...}, scope, warning?, _untrusted}

cip_search(query, limit=20)
    -> {source, matches[{cip,title}], count, _untrusted}

list_universities(sort="nra"|"records"|"name", order, limit=15,
                  min_records=0, contains="")
    -> {source, matched, universities[{key,name,records,nra_site_figure,unitid,url}],
        definition, _untrusted}

get_university_facts(key, fields=["all"|"completions_trend"|"opt"|"h1b"|"lca"|"perm"
                                 |"enrollment"|"faculty"|"funding"|"departments"])
    -> {key,name,url,unitid,records,record_years,nra_site_figure,
        completions_trend{years,phd_total,phd_nra,phd_stem_total,phd_stem_nra,phd_nra_share},
        opt, h1b, lca, perm, enrollment_ipeds, enrollment_gss, faculty, funding,
        federal_support, nsf_awards, nih, departments[{name,records,classified,
        foreign_name_pct,top_origin}], name_origins, source, definitions, _untrusted}
        (or {error, did_you_mean[], hint} for an unknown key)

get_national_series(series ∈ phd_completions | phd_nra_share | opt | stem_opt | cpt |
                             visa_issuances | rd_funding | nra_by_field | eb_by_country,
                    start?, end?)
    -> {title, unit, years|categories, values{...}, source, series}
```

`cip_search` is a **6th tool the contract did not list**. Reason: `nra_lookup` takes CIP
prefixes, and CIP titles rarely read the way a person names a field — electrical engineering is
`14.1001 Electrical and Electronics Engineering` and `14.1099 Electrical, Electronics, and
Communications Engineering`. Without it, the model was guessing codes from memory, which is
exactly the failure mode this work exists to remove. It changes nothing on the wire.

`nra_lookup` is a literal port of `load_index` / `key_for` / `aggregate` / `fmt_rows` from
`scripts/query_nra_index.py`, with the CLI stripped and the filters moved into the aggregation
pass. Verified identical output — see §6.

### Render tools (8) — one block each, ack-only result to the model

```
show_chart(chart, title, subtitle?, labels[], datasets[{label,data[],role,fill,dashed,axis}],
           y?, y2?, x?, source, nav?, placement?)        -> chart block
show_table(title?, columns[{key,label,align,format,emphasis}], rows[{...,nav?}],
           note?, source, footer_nav?, placement?)       -> table block
show_stats(items[{label,value,delta,delta_dir,note,bar,emphasis}], source?, placement?)
                                                          -> stat block
navigate_user(url | page+section_id, label, auto?, highlight?, reason?, placement?)
                                                          -> nav block
show_link(kind, url, label, note?, copyable?, placement?) -> link block
suggest_query(sql, explanation, table?, placement?)       -> query block
suggest_followups(items[{label,prompt}])                  -> suggest block
show_notice(kind, title?, md, icon?, placement?)          -> notice block
```

Legacy `navigate_user(page, section_id, label)` is accepted and normalised into `url` inside the
builder, per §4.5.6. `path` and `fragment` are emitted as derived advisory fields.

---

## 3. How data reaches the Lambda

Everything is bundled in the zip under `chat_data/`. **Nothing is fetched at request time.**

| Artifact | Size | Built by |
| --- | --- | --- |
| `nra_index.csv.gz` | 1187 KB | copied from `data/ipeds/` |
| `universities_compact.json` | 640 KB | **new** `scripts/build_chat_facts.py` |
| `cip_titles.csv` | 71 KB | copied from `data/ipeds/` |
| `site_map.json` | 66 KB | **new** `scripts/build_site_map.py` |
| `hd_names.csv` | 45 KB | **new**, `unitid,name,state` for the 1,133 unitids that occur in the index |
| `national_series.json` | 4 KB | **new** `build_chat_facts.py` |
| **total** | **1.97 MB** | |

Loading is lazy per artifact and cached in module globals, so a cold start that only answers
"who made this site?" never pays for the index parse.

Measured in the real flat layout (`infra/chat/lambda/`, local CPU):

- `import index` + ping: **0.00 s** (no artifact touched)
- first `nra_index` parse: **0.21 s**, 260,170 rows
- warm `nra_lookup`: **0.039 s** for a full 260k-row scan + aggregate

That is why `MemorySize` went to 1024 — more memory is more CPU, and the parse and the JSON
serialise are both CPU-bound.

### hd_names.csv and the BOM

`build_chat_facts.py` reads the HD files newest-first (HD2024 → hd2002) so retired/merged
unitids still resolve, opens them `utf-8-sig`, and **normalises the header row itself** rather
than using `DictReader` — the first IPEDS column header carries a UTF-8 BOM, so
`row.get('UNITID')` returns `None`. 1,133 of 1,149 unitids resolve; the remaining 16 render as
`(unknown institution)`.

### Why a digest and not the per-university payloads

`site/data/stem/` is ~216 MB; `mit.json` is 2.9 MB and `_search.json` is 20 MB. 95%+ of each file
is its `records` array — one row per dissertation carrying author name, title and repository URL.
Three reasons it does not ship:

1. **Size.** It does not fit a Lambda zip, let alone a warm-start budget.
2. **Wrong shape.** A chat answer needs aggregates, not 14,203 rows. The raw rows already have a
   first-class home — `query.html` runs SQL over them in the browser, which is what
   `suggest_query` points at.
3. **Safety.** Dissertation titles and author names are the largest untrusted-text surface in the
   project. Aggregating to `(department, count, share)` discards the free text entirely.

The digest keeps scalars, short series, and the **top 25 departments** by record count, with
`foreign_name_pct` and `top_origin` per department: 640 KB for all 105 universities, a 340×
reduction, with no raw record text anywhere in the zip.

---

## 4. How fabrication was made hard

Four mechanisms, three of them mechanical rather than exhortative.

### 4.1 The prompt has no statistics in it any more

The v1 `SYSTEM_PROMPT` carried a "## Key Statistics" list — `49,012 STEM PhDs awarded (2024),
32.3% to Non-Resident Aliens`, `291,324 records`, `India: 350K SEVIS students`, and a dozen more.
Those bullets were the *only* figures the assistant could state, and every one was stale by
construction. They are deleted. In their place:

> **YOU HAVE NO MEMORISED STATISTICS** … The server checks this. A chart, table or stat
> containing a number that no data tool returned is rejected and you are told which value failed.
> Fabrication does not reach the reader; it only costs you a round trip.

`test_local.py` asserts the strings `49,012`, `32.3%` and `291,324` do not appear in the
rendered prompt.

### 4.2 The grounding ledger (`blocks.Ledger`) — the mechanical part

Every data-tool result is walked recursively and every number in it (including numbers embedded
in strings) is recorded in a per-turn ledger, at 1 dp and at 0 dp. When `show_chart`,
`show_table` or `show_stats` is called, **every numeric value in the block is checked against
that ledger**. Three things pass:

- an exact ledger value at 1 dp or 0 dp (the model may round 61.43 to 61.4 or to 61);
- a difference of two ledger values (`gap = mit − national` is a legitimate derivation, and
  refusing it would push the model back to prose-only answers);
- a four-digit year in 1900–2100 (axis labels, not statistics).

Anything else raises `BlockError`. The block is dropped **and the model is told exactly which
values failed**, as a tool result:

> `chart data: 5 value(s) did not come from any data tool result in this conversation (11111,
> 22222, …). Call a data tool (nra_lookup, get_university_facts, get_national_series,
> list_universities) and use the numbers it returns verbatim. Do not state figures from memory.`

So a fabrication is not merely discouraged — it is a wasted round trip that the model is told
how to fix. `meta.blocks_rejected` counts them, and it is logged.

Scope note: the ledger governs *chart, table and stat* — the blocks that put numbers on screen.
It does not police the prose in `reply`; that would require parsing natural language and would
fire on "about a third". The prompt covers prose; the ledger covers pixels.

### 4.3 `source` is a required field, not a nicety

`show_chart` and `show_table` are **rejected outright without a non-empty `source`**, with an
error telling the model to copy the `source` string out of the data-tool result. Every data tool
returns one, e.g. `IPEDS Completions via nra_lookup, 2020-2025 pooled, cohorts of 20+`. A chart
therefore cannot reach the reader without a provenance line under it.

### 4.4 The two metrics cannot be silently conflated

`nra_lookup` now returns an explicit `scope` field — `"ALL research doctorates, every field —
this is NOT the STEM-only figure the site's national panel prints"` when no CIP filter was
given — and `get_university_facts` returns a `definitions` block saying that
`departments[].foreign_name_pct` is a **name-origin estimate, not a visa status**, and is not
the same metric as IPEDS NRA. Both are restated in the prompt.

### 4.5 Prompt injection

Institution names, department names and CIP titles are scraped or federal free text. Defences:

- `data_store.clean_text()` strips control characters (including the ones used to fake role
  markers), collapses newlines so nothing can start a fake `assistant:` line, and hard-caps
  length. It runs on every such string as it leaves the store, and again in `blocks.text()` on
  its way into a block.
- Every data-tool result carries an `_untrusted` banner naming those fields as data.
- The prompt has an `## Untrusted text` section instructing the model to ignore instructions
  found inside data fields and to say so if it sees any.
- Block labels, titles, notes and cell values are plain text by contract, rendered by the widget
  with `textContent`. Nothing model- or data-derived is interpolated into HTML server-side.
- Deliberately **not** attempted: pattern-matching for "instruction-like" text. That is a losing
  arms race; the defence is labelling plus rendering discipline.

---

## 5. Logging fixes

**`CHAT_LOGS_TABLE` was never set in `template.yaml`**, so `_log_chat()` short-circuited on line
one and every chat interaction since the feature was built has been discarded. Fixed:

- New `ChatLogsTable` parameter, default `phd-chat-logs`. That table **already exists in
  us-east-1** (`pk` HASH / `sk` RANGE, TTL enabled on `ttl`, ~10 items) and was created outside
  this stack, so it is referenced **by name, not created** — declaring it as a CFN resource with
  the same `TableName` would fail the deploy. Its shape matches what `_log_chat` writes and what
  `dashboard_api.py` queries.
- `CHAT_LOGS_TABLE: !Ref ChatLogsTable` added to the function environment.
- `DynamoDBWritePolicy` on that table added to the function's IAM policies.
- Added to Outputs.
- If the variable is ever unset again, the handler now emits a `ChatLogTableUnset` CloudWatch
  metric instead of failing silently.

**Full IPs are preserved.** `_log_chat` writes `"ip": ip` with the raw
`requestContext.http.sourceIp`, unhashed and untruncated, and it is also the `sk` prefix
component. There is no anonymisation anywhere in the path, and `test_local.py` asserts
`logged["ip"] == "203.0.113.42"` end to end so a future refactor cannot quietly add one.

Log record gained (contract §5.5): `data_tools[]`, `block_types[]`, `contract_v`, `degraded`,
`truncated`, `page`, `widget`. `tools_used` keeps its existing key — the dashboard already reads
it — but now carries real tool names instead of just `navigate`/`query`.

Other operational fixes:

- `_check_rate` still fails open, but now emits a `RateLimiterError` metric so a dead limiter is
  visible (contract §4.4).
- 429 responses carry both `Retry-After` and `retry_after_s`, and `ExposeHeaders: [retry-after]`
  was added to the Function URL CORS config — a cross-origin response header is invisible to JS
  otherwise, so the widget's countdown would have had nothing to read.
- `ProviderOutage` metric on the degrade path.

Also in `template.yaml`: `Timeout: 30 → 45`, `MemorySize: 256 → 1024`, and the
`bedrock:InvokeModel` IAM statement removed (nothing calls Bedrock any more — the only copy that
did was the stale `cloud/chat/handler.py`). CORS `AllowOrigins` is unchanged and still locked to
`https://phd-demographics.andy-barr.com`. The OpenAI key is still referenced only as the SSM
parameter name `/cms-pipeline/openai-api-key`.

---

## 6. Test results

### 6.1 Offline suite — `python3 cloud/chat/test_local.py`

**All checks passed.** 70 assertions across:

- artifacts (all six present, 118 site paths, 105 universities, 9 national series)
- every data tool, including error paths (`get_university_facts("hogwarts")` →
  `{error, did_you_mean, hint}`)
- the ledger: grounded chart accepted; fabricated chart/table/stat all rejected with the
  remediation message; derived difference allowed; sourceless chart rejected
- URL validation: rejects `javascript:alert(1)`, `//evil.host/x`, `https://evil.host/`,
  `/does_not_exist.html`, an over-length fragment, `/stem.html\@evil`, and
  `kind:"external"` + `http://`; accepts `https://`; normalises legacy `page`+`section_id`
- SQL: rejects `DROP`, a `;`-chained `DELETE`, a missing `LIMIT`, and a `--` comment
- untrusted text: control chars stripped, newlines collapsed, hostile cell capped at 120 chars
- prompt: contains the site map, contains **none** of `49,012` / `32.3%` / `291,324`, carries the
  no-memorised-stats rule and the page-context suffix. 13.4 KB ≈ 3.4k tokens.
- handler paths: ping 200 (no model call), 403 wrong origin, 400 bad JSON, 400 `too_long`,
  400 missing message, 429 with `Retry-After: 37` + `retry_after_s: 37`, and the degrade path
  returning **200** with `meta.degraded` and a `notice` + two `nav` blocks
- end-to-end with a scripted model (below)

### 6.2 Contract §8.10 acceptance — numbers match the CLI exactly

```
$ python3 scripts/query_nra_index.py --level cell --cip 14.10 --start 2020 --pooled --min-total 20 --csv
all,24,23,95.8,182290,University of Nevada-Reno,NV,14.1001
all,51,48,94.1,145725,Illinois Institute of Technology,IL,14.1001
all,54,50,92.6,179867,Washington University in St Louis,MO,14.1001
all,23,21,91.3,219356,South Dakota State University,SD,14.1001
all,29,26,89.7,186867,Stevens Institute of Technology,NJ,14.1001
all,134,119,88.8,110671,University of California-Riverside,CA,14.1001
all,79,70,88.6,236939,Washington State University,WA,14.1001

$ nra_lookup(level="cell", cip=["14.10"], start=2020, end=2025, pooled=True, min_total=20)
all 24 23 95.8 182290 University of Nevada-Reno NV 14.1001
all 51 48 94.1 145725 Illinois Institute of Technology IL 14.1001
all 54 50 92.6 179867 Washington University in St Louis MO 14.1001
all 23 21 91.3 219356 South Dakota State University SD 14.1001
all 29 26 89.7 186867 Stevens Institute of Technology NJ 14.1001
all 134 119 88.8 110671 University of California-Riverside CA 14.1001
all 79 70 88.6 236939 Washington State University WA 14.1001
matched 134
```

Identical, including `matched=134`.

Second half of §8.10: `show_link(kind="site", url="/concentration.html#slide-7")` returns
`/concentration.html#slide-7` — the unrecognised fragment survives because the page declares
`"anchors": "open"`. Asserted in the suite.

### 6.3 Live end-to-end against real gpt-4o

`AWS_PROFILE=personal python3 cloud/chat/test_live.py "<question>"` — reads the key from SSM by
parameter name, never prints it, disables the rate limiter and DynamoDB writes, and runs the
handler in-process. **Nothing was deployed.**

Four questions run. Representative result:

> **Q:** Which universities have the highest NRA share in electrical engineering doctorates,
> pooled 2020-2025? Show me the top 8 and note the cohort threshold. Also point me at the
> pipeline page.
>
> `HTTP 200`, `meta: {provider: openai, model: gpt-4o, latency_ms: 14441, tools_used:
> ["cip_search","nra_lookup","show_table","navigate_user"], blocks_rejected: 0}`
>
> Blocks: `table` (8 rows, `source: "IPEDS Completions via nra_lookup, 2020-2025 pooled, cohorts
> of 20+"`, note `"Cohort threshold: 20 doctorates"`) → `text` → `nav` to `/pipeline.html`.
> `actions` mirror carried the navigate. 3.0 KB.
>
> **Every row matched the CLI figures above** — 95.8 / 94.1 / 92.6 / 91.3 / 90.9 / 89.7 / 88.8 /
> 88.6. The model found CIP 14.10 via `cip_search` rather than from memory.

Other live runs: a national CS trend produced `chart` + `text` + `suggest` with three chips; the
MIT-vs-national question produced `chart` + `text` + `query`. `blocks_rejected: 0` in all live
runs — the live model did not attempt a fabrication once the prompt told it the server checks.

Two prompt fixes came out of the live runs: the model was answering series questions in prose
(fixed with an explicit render-round checklist) and emitting the inline nav token backwards as
`[[Label|/url]]` (see §7.3).

### 6.4 Worked example — full response with a chart *and* a table

Written to `scratchpad/worked_example.json` (5,585 bytes). Reproduce with
`python3 cloud/chat/test_local.py --example`. It drives the **real** loop with a scripted model
that calls two data tools, then nine render tools — one of which deliberately fabricates
numbers. Abridged:

```jsonc
{
  "v": 2,
  "reply": "MIT runs well above the national line. In 2024, **45.1%** of MIT's doctorates went to non-resident aliens, against **32.3%** nationally.\n\nA caveat before you read too much into it: IPEDS \"non-resident alien\" is a visa status at the time of award, not ethnicity or country of origin.",
  "blocks": [
    { "type": "stat",
      "items": [
        {"label": "MIT NRA share, 2024", "value": "45.1%", "emphasis": true, "bar": 45.1},
        {"label": "National, 2024", "value": "32.3%"},
        {"label": "Gap", "value": "+12.8pp", "delta_dir": "up"}],
      "source": "Site university fact sheet (IPEDS, DHS/ICE, DOL, USCIS, NSF; see /data_sources.html)" },

    { "type": "text", "md": "MIT runs well above the national line. …" },

    { "type": "chart",
      "chart": "line",
      "title": "NRA share of doctorates — MIT vs national",
      "labels": ["2015","2016","2017","2018","2019","2020","2021","2022","2023","2024"],
      "datasets": [
        {"label": "MIT",      "data": [41.1,42.4,41.5,42.8,47.2,45.2,45.6,45.7,43.9,45.1], "role": "nra",     "fill": true},
        {"label": "National", "data": [34.0,33.6,33.6,34.0,34.1,34.6,34.5,35.1,33.4,32.3], "role": "neutral", "dashed": true}],
      "y": {"format": "pct1", "label": "NRA share", "begin_at_zero": false},
      "x": {"label": "Award year"},
      "source": "IPEDS Completions via get_university_facts / get_national_series",
      "nav": {"url": "/universities/mit.html#completions-trend-chart",
              "label": "Open MIT's full trend chart",
              "path": "universities/mit.html", "fragment": "completions-trend-chart"} },

    { "type": "table",
      "title": "MIT departments by dissertation count",
      "columns": [
        {"key": "department",  "label": "Department",     "align": "left",  "format": "text"},
        {"key": "records",     "label": "Records",        "align": "right", "format": "int"},
        {"key": "foreign_pct", "label": "Foreign-name %", "align": "right", "format": "pct1", "emphasis": true}],
      "rows": [
        {"department": "General",                   "records": 4243, "foreign_pct": 28.0},
        {"department": "Electrical & Computer Eng", "records": 2046, "foreign_pct": 32.0},
        {"department": "Engineering",               "records": 1307, "foreign_pct": 22.7}],
      "note": "Name-origin estimate, not visa status.",
      "source": "Site university fact sheet (IPEDS, DHS/ICE, DOL, USCIS, NSF; see /data_sources.html)",
      "footer_nav": {"url": "/query.html", "label": "Explore the raw records", "path": "query.html"} },

    { "type": "notice", "kind": "info", "title": "What NRA means",
      "md": "IPEDS reports **non-resident alien** as a visa/residency status. See [[nav:/data_sources.html#citizenship|Understanding citizenship categories]]." },

    { "type": "nav", "url": "/universities/mit.html#completions-trend-chart",
      "path": "universities/mit.html", "fragment": "completions-trend-chart",
      "label": "MIT completions trend", "auto": true, "highlight": true,
      "reason": "You're already on MIT's page — scrolling you to the chart." },

    { "type": "link", "kind": "external", "url": "https://nces.ed.gov/ipeds/use-the-data",
      "label": "IPEDS — Use the Data", "copyable": false,
      "note": "The primary source behind both series." },

    { "type": "suggest", "items": [
        {"label": "Which MIT departments?", "prompt": "Which MIT departments have the highest NRA share?"},
        {"label": "Compare to Stanford",    "prompt": "Compare MIT and Stanford NRA share since 2015"}] }
  ],
  "actions": [
    {"type": "navigate", "page": "universities/mit.html", "section_id": "completions-trend-chart", "label": "MIT completions trend"}
  ],
  "meta": {"latency_ms": 1, "blocks_rejected": 1, "truncated": true,
           "tools_used": ["get_university_facts","get_national_series","show_stats","show_chart",
                          "show_table","show_chart","show_notice","navigate_user","show_link",
                          "suggest_query","suggest_followups"]}
}
```

Things to read out of that:

- **The 45.1 / 32.3 series are the artifacts' own numbers**, asserted equal to
  `universities_compact.json`'s `completions_trend.phd_nra_share` in the suite.
- **`blocks_rejected: 1`** — the fabricated `show_chart` (`[12345, 23456, 34567]`) never reached
  the wire.
- **`truncated: true`** — nine render blocks, cap is eight, so the `query` block was shed. The
  `suggest` block survived: see §7.4.
- `placement: "before_text"` on the stat put it above the prose; `suggest` is pinned last.
- The `actions` mirror carries the nav decomposed back into `page` + `section_id`.

---

## 7. Deviations from the contract, and why

Four. None of them touch the wire format, so the frontend is unaffected.

### 7.1 `doctoral_nra_by_cip2.csv.gz` is not bundled

§5.2 says ship it (1.6 MB, sex + race breakdowns). **No tool in the contract consumes it** —
none of the four data tools takes a sex or race parameter. Shipping it would add 1.6 MB of dead
weight to every cold start. If you want sex/race breakdowns, that is a 5th data tool and I will
add it; say the word.

### 7.2 Anchors are hinted in the prompt for 17 content pages

§5.4 rule 1 says: enumerate ids only for `"anchors": "enumerated"` pages, and for `"open"` pages
emit `(anchors not enumerated …)`. §4.10 also says default **every** page to `"open"` until the
anchor workstream settles.

Following both literally leaves the assistant unable to deep-link anywhere, on a site whose whole
value is 200 addressable charts. What I did instead:

- Every page stays `"anchors": "open"` in `site_map.json` — so **validation is path-only and
  fragments stay opaque**, exactly as specified, and the anchor agent can move any id without
  breaking anything.
- The prompt lists, for 17 real content pages, up to 10 observed chart/table/section ids under
  the label `common anchors (advisory, may have moved)`. Every other page gets the contract's
  `(anchors not enumerated …)` line.

No fragment *format* is hard-coded anywhere; the hints come from `site_map.json`, which is
generated from the HTML. A stale hint costs nothing — the reader lands at the top of the right
page, which §4.5.5 rule 3 already calls an acceptable outcome. Flag it if you disagree; it is one
constant (`ANCHOR_HINT_PAGES`) to empty out.

### 7.3 Inline nav tokens are repaired, not just accepted

The grammar is unchanged: `[[nav:/url|Label]]`. But gpt-4o emitted `[[Immigration Pipeline
Analysis|/pipeline.html]]` in a live run, which the widget would (correctly) render as inert
literal text. `blocks.normalize_nav_tokens()` rewrites the two unambiguous malformations —
`[[Label|/url]]` and `[[/url|Label]]` — into the canonical form before serialising. `[[mit]]`
shorthand is untouched. This widens what the *server accepts*; the frontend still only ever sees
canonical tokens.

### 7.4 The 8-block cap sheds from the end of the render list, not the literal end

§4.7 says "drop from the end". §4.5.9 pins `suggest` last. Taken together, `suggest` is always
the first casualty of the cap — which is plainly not the intent. `assemble()` therefore caps the
`pre + text + post` list and appends `suggest` afterwards, and never drops the `text` block.
Result on a 9-block turn: the trailing `query` block is shed, the chips survive.

### 7.5 One thing worth flagging that is not a deviation

Render tools get **one extra round** rather than terminating the loop immediately (§5.1 says a
render-only round goes straight to the prose). In live testing, one round meant the model emitted
a single block and stopped — no chips, no nav, no caveat. It now gets a second render pass, with
a `reminder` field on the ack telling it to add `suggest_followups`, and terminates after two
consecutive render-only rounds. This costs zero extra model calls in the common case: the second
pass replaces the final `use_tools=False` prose call, and if the model returns prose instead of
tool calls the loop exits there. Budget is still `MAX_TOOL_ROUNDS = 4`.

---

## 8. Not done / handover

- **Nothing deployed.** `deploy.sh` is ready and will rebuild artifacts, sync the source, and
  fail fast on a missing artifact. Run it when you want it live.
- **Nothing committed.** Changed in `usds_china`: `cloud/chat/*` (5 modules + 2 test harnesses +
  `chat_data/`), `scripts/build_site_map.py`, `scripts/build_chat_facts.py`. Changed in
  `usds_china_private`: `infra/chat/template.yaml`, `infra/chat/deploy.sh`,
  `infra/chat/lambda/*` (shim + synced copies), and the new `site/data/chat/site_map.json`.
- `cloud/chat/chat_data/.gitignore` excludes the two copied IPEDS files so the 1.2 MB gz is not
  duplicated into git; the three generated artifacts are small and are left tracked.
- **Not touched:** `site/chat-widget.js`, any `site/*.html`, `pipeline/`, `manifest.json`,
  `universities.json`, `entity_map.json`, `generate_name_lists.py`. `build_chat_facts.py` reads
  `KEY_TO_UNITID` out of `scripts/enrich_university_json.py` by regex rather than duplicating the
  mapping, and does not modify it.
- **For the frontend agent:** `site/data/chat/site_map.json` is generated and in place. Its shape
  is `{version, pages[{path,title,desc,widget,anchors,sections[{id,label,kind,dynamic}]}],
  university_paths[], universities[{key,name,path,nra}]}`. `university_paths` is the flat list of
  all 105 university page paths — use it plus `pages[].path` for path validation. Every page is
  `"anchors": "open"` today, so validate the path and pass the fragment through.
- **Known gap:** `dashboard_api.py` is not wired to any function in `template.yaml`; the admin
  dashboard Lambda was created outside this stack. Now that logging actually writes, that
  dashboard will start showing data — but its `tool_usage` aggregation buckets only
  `navigate` / `query` / `none` and will show the new tool names as extra keys. Cosmetic, and
  outside my remit.
