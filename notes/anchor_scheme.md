# PhD Demographics — anchor audit and addressing scheme

Date: 2026-08-18. Source tree: `/Users/andy/usds_china_private/site` (symlinked as
`/Users/andy/usds_china/site`). Generator: `scripts/generate_name_lists_html.py`.

---

## 1. Audit — what worked, what was missing, what was broken

### 1.1 The generated university pages (`stem.html`, `non_stem.html`, `universities/**`)

| Thing | Addressable before? | Verdict |
|---|---|---|
| University, e.g. `stem.html#mit` | Yes | **Worked.** `applyUrlState` matched `UNI_MAP`, then fuzzy-matched the display name. |
| University with an underscore key, e.g. `#missouri_st` | Yes, by luck | **Worked, but inconsistently.** The rendered `<h2>` carried `id="missouri-st"` (`slug(key)`), not `missouri_st`. The link resolved through the fuzzy name match, not the id. Two spellings of the same thing existed side by side. |
| Department, e.g. `stem.html#utarlington--engineering` | No | **Broken.** `parseUrlState` treated the whole fragment as a university key. `UNI_MAP['utarlington--engineering']` missed, the fuzzy match missed, `applyUrlState` returned, and the page stayed on the national view. Verified cold against the deployed site: title never changed, nothing rendered. |
| Department on a per-university page, e.g. `/universities/mit.html#mit--chemistry` | Accidentally | **Worked by luck.** No code resolved it; Chrome's fragment-scroll retry happened to fire after the async render. Nothing guaranteed it, and it never worked on `stem.html`. |
| Year, e.g. `#mit--chemistry--2024` | No | **Broken**, same cause. The ids existed; nothing resolved them. |
| Master's year block (`#<uni>--<year>`) | No | **Broken**, and the block is CSS-hidden unless the master's toggle is on, so even a correct id landed on nothing. |
| Panel anchors `#<uni>--funding`, `--enrollment`, `--h1b` | No | **Broken, and actively misleading.** The three panels each had a share button that generated exactly these links (`shareAnchor((currentKey||'')+'--funding')`), and nothing anywhere could resolve them. Every link a reader copied off a panel was dead. |
| Toggle state `#<uni>?h1b=1` | Yes | **Worked.** Confirmed cold on the deployed site: the H-1B panel opened. |
| Toggle state combined with a deeper anchor | No | **Broken twice over.** The deeper anchor did not resolve, and `updateUrlState()` rebuilt the hash from `currentKey` alone, so flipping any toggle silently discarded the department and year from the URL. |
| National charts `#nat-phd` … `#nat-fields` | Yes | **Worked** (static markup, native scrolling), but had no copy-link control, so a reader had no way to discover the name. |
| Collapsed departments / years | n/a | **Broken by design.** Even a resolving link landed on a collapsed block. |
| Share affordance | Partial | Dept and year headers had one; panels had one that produced dead links; the university heading, master's blocks and national charts had none. All used an emoji glyph. |

### 1.2 The hand-written pages

| Page | Section ids before | Copy-link | Reads hash | Notable break |
|---|---|---|---|---|
| `china.html` | 8 of 9 chart-boxes | 8 (emoji) | no | 3 `<h2>` group headings and the table unaddressable |
| `india.html` | 7 of 7 | 7 | no | 2 `<h2>`, the FMGE table |
| `canada.html` | 8 of 8 | **5** | no | 3 sections had ids but no control; two id conventions (`-chart-section` vs `-section`) |
| `uk.html` | 9 of 9 | **5** | no | 4 sections had ids but no control |
| `eu.html` | 5 of 5 | 5 | no | table unaddressable |
| `mexico.html` | 4 of 4 | 4 | no | — |
| `vwp.html` | 8 of 8 | 8 | no | 3 `<h2>`; table sort not linkable |
| `immigration.html` | 101 JS cards | 101 | yes | re-scrolled to the hash on *every* re-render, so typing in the search box yanked the viewport; no `hashchange` handling |
| `workforce.html` | 4 of 4 | **0** | no | no copy control, no `:target` feedback; `industry-section` orphaned from nav |
| `medical.html` | 10 of 10 | **0** | no | same; six sections orphaned from nav |
| `pipeline.html` | 7 of 7 | 7 | no | `<h2>` group headings unaddressable; `h1b-diverge-chart-section` orphaned from nav |
| `data_sources.html` | 7 `<h2>` + TOC | 0 | no | 9 per-dataset cards unaddressable; `#links` and `#analytics` both numbered "6." |
| `implementation.html` | 6 `step-*` | 0 | no | ~30 `<h3>` unaddressable; SVG step clicks scrolled but never wrote the URL |
| `ipeds_dashboard.html` | 4 `panel-*` | 0 | no | **`sidebar.js` advertised `#panel-demographics` etc.; the page had no hash→tab activation, so those nav links scrolled to a `display:none` div and did nothing** |
| `stem_dashboard.html` | 5 `panel-*` | 0 | no | per-university detail view had no address at all |
| `department_reports.html` | 1 card + 3 tabs | 0 | no | `init()` hardcoded `selectUni('missouri_st')`; no university was linkable |
| `query.html` | 0 | 0 | **writes only** | `setActiveTable()` wrote `#<table>` via `replaceState` and nothing ever read it back — a half-built deep link that silently did nothing |
| `quality.html` | 0 | 0 | no | 6 panels, none addressable; page loads no nav script at all |
| `overview.html` | 0 | 0 | no | 6 sections, none addressable |
| `usaid.html` | 0 | 0 | no | identical `.chart-box` markup to `pipeline.html`, never given ids or controls |
| `webmcp.html` | 0 | 0 | no | developer reference with no `#available-tools` / `#record-format` |
| `index.html`, `about.html`, `submit.html` | 0 | 0 | no | prose sections unaddressable |
| `sidebar.js` | — | — | reads once | no `hashchange` listener, so sub-item highlighting went stale immediately |

### 1.3 Cold tests run against the **deployed** site before any change

| URL | Result |
|---|---|
| `https://phd-demographics.andy-barr.com/stem.html#mit` | Worked — MIT rendered, title updated |
| `.../stem.html#utarlington--engineering` | **Broken** — nothing rendered, title unchanged |
| `.../stem.html#missouri_st?h1b=1` | Worked — university rendered, H-1B panel open |
| `.../universities/mit.html#mit--chemistry` | Worked by accident (browser fragment retry), scrollY 82538 |

---

## 2. The scheme

One grammar for the whole site. It reconciles with what already existed rather than
replacing it: the `--` separator, the `?flag=1` toggles and every `-section` id on the
hand-written pages are all kept.

```
<page>#<target>[?<toggles>]

<target> = <segment>[--<segment>[--<segment>]]
```

Segments narrow from left to right.

### 2.1 The hierarchy

| Fragment | Addresses |
|---|---|
| `stem.html#missouri_st` | a university |
| `stem.html#missouri_st--chemistry` | a department within it |
| `stem.html#missouri_st--chemistry--2024` | one year of that department |
| `stem.html#missouri_st--2024` | that year's master's theses |
| `stem.html#missouri_st--funding` | the funding panel, opened |
| `stem.html#missouri_st--enrollment` | the enrollment panel, opened |
| `stem.html#missouri_st--h1b` | the H-1B / OPT panel, opened |
| `stem.html#nat-visas` | a national chart |
| `china.html#return-chart-section` | a named block on any hand-written page |

**The university token** is the key already used everywhere else on the site: sidebar
links (`/stem.html#mit`), page paths (`/universities/mit.html`) and data files
(`/data/stem/mit.json`). Choosing it over `slug(key)` is the one place the scheme
picks a winner between two existing spellings.

**The field token** is the department name lower-cased with every run of
non-alphanumerics collapsed to a single hyphen: *Computer Science* →
`computer-science`.

**The year token** is the four-digit year.

**Section names** on the hand-written pages are the heading text under the same rule,
with a leading enumerator dropped ("6. Links to Original Sources" → `links-to-original-sources`),
capped at 48 characters on a word boundary. Ids that already existed are never renamed.

### 2.2 Panel toggles

Panel state rides after the anchor, unchanged from what already shipped:

```
stem.html#missouri_st--chemistry?funding=1&h1b=1&ms=1
```

Flags: `funding`, `enrollment`, `h1b`, `ms`. Naming a panel as a segment
(`#missouri_st--h1b`) opens it without the flag, so the short form and the long form
agree.

### 2.3 Resolution is forgiving

Case never matters. `-` and `_` are interchangeable in the university token, so
`#missouri-st--chemistry` and `#missouri_st--chemistry` reach the same element. A loose
display-name match is kept as a last resort, because that is how `#missouri-st` used to
work. Unknown fragments fall back to a plain `getElementById`, then to a
heading-slug match.

### 2.4 What the scheme changed, and what that would have broken

Rendered ids moved from `slug(key)--field--year` to `key--field--year`. That is a real
change for the ~half of universities whose key contains an underscore. Two things could
have broken and both are covered:

* A link like `#missouri-st--chemistry` — handled by the normalising resolver, and
  verified cold.
* A raw `document.getElementById('missouri-st--chemistry')` from outside the page —
  `site/chat-widget.js` does exactly this for same-page navigation, and I am not
  permitted to edit it. So the generator also emits a zero-height
  `<span class="anchor-alias" id="<legacy-id>">` at the top of each department, year and
  master's block, but only when `slug(key) !== key`. `mit` emits none; `missouri_st`
  emits 166. Old ids therefore still resolve through plain DOM lookup.

Nothing was renamed on the hand-written pages; ids were only added.

---

## 3. What I implemented

### 3.1 `scripts/generate_name_lists_html.py` (owns `stem.html`, `non_stem.html`, and via `build_static_pages.py` the 207 per-university pages)

* Replaced the URL-state block with a documented anchor resolver: `parseUrlState`
  splits on `--`, `resolveUniKey` normalises the university token, `canonicalAnchorId`
  rebuilds the id that is actually rendered, `focusAnchor` expands every collapsed
  ancestor before scrolling and flashes the target.
* Deep links now survive a cold entry. Because `#content` renders asynchronously — and
  twice on the per-university pages, which inline their own data — a requested anchor
  stays live for 4 s and is re-applied after each render (`requestAnchor` /
  `consumePendingAnchor`), rather than being consumed by whichever render happened
  first. The per-university pages now seed `UNI_CACHE` from the inlined data instead of
  re-fetching the same JSON.
* Panel anchors resolve and open their panel. `#<uni>--<year>` turns the master's
  toggle on, since the block is otherwise hidden.
* `updateUrlState` keeps the deepest anchor, so flipping a toggle no longer discards
  the department and year.
* Canonical ids: `<key>`, `<key>--<field>`, `<key>--<field>--<year>`, `<key>--<year>`;
  legacy alias spans where the key contains an underscore.
* Copy-link controls added on the university heading, the master's blocks and all seven
  national charts; the existing department, year and panel controls were rewired to the
  canonical ids and given real `href`s so middle-click and "copy link address" work.
* All link glyphs are now `#`, not an emoji — including the coach-mark text that
  described them.
* `:target` and `.anchor-flash` highlighting, and `scroll-margin-top` on every `[id]`.
* Fixed a pre-existing crash: `populateDeptFilter()` threw on `sel.value` when
  `#dept-filter` was absent, killing the MutationObserver it ran under. One null guard.

### 3.2 `site/anchors.js` (new, shared by every hand-written page)

Gives each `h1`–`h4` outside the sidebar/nav/footer a descriptive id if the HTML has
none, puts one uniform `#` copy control beside it, and resolves the fragment on cold
load and on `hashchange`. Resolution opens `<details>`, un-collapses `.collapsed` /
`.yr-collapsed`, and activates a hidden tab panel by clicking the tab that points at it —
which is what makes `ipeds_dashboard.html#panel-states` work at all. Pages with their
own state register `window.ANCHOR_HOOKS`. `window.Anchors.refresh(root)` re-runs id
assignment after asynchronously rendered content.

### 3.3 `scripts/add_section_anchors.py` (new, idempotent)

Bakes the same slugs into the static HTML so they are visible to crawlers and to
readers viewing source: **151 ids added across 25 pages**. It also removed **49**
copy-pasted inline share buttons (each an emoji plus a duplicated clipboard snippet
that dropped any query string) in favour of the one control, and added the
`anchors.js` tag. Re-running it now reports zero changes.

### 3.4 Page-specific work

* `query.html` — the hash it always wrote is now read back. `query.html#stem_records`
  selects that table and previews it, firing as soon as the parquet finishes loading.
* `department_reports.html` — `#<uni_key>` and `#<uni_key>--<tab>` select a university
  and a tab; `selectUni` keeps the address bar in step. Falls back to the old default
  when the fragment names nothing it has.
* `stem_dashboard.html` — `#<uni_key>` opens that university's detail tab;
  `showUniDetail` writes the hash.
* `immigration.html` — the 101 per-card emoji share buttons were removed from the
  card template; `Anchors.refresh` renders the uniform control after each render; the
  hash is chased on the **first** render only, so typing in the search box no longer
  yanks the viewport; added a `hashchange` handler.
* `sidebar.js` — added a `hashchange` listener so sub-item highlighting stays current;
  filled in the anchor lists for the seven country pages, completed the `medical` and
  `workforce` lists, and added the orphaned `h1b-diverge-chart-section`.
* `data_sources.html` — new section **6. Linking to This Data** documenting the scheme
  for readers, plus the fix for the two sections both numbered "6.", and the analytics
  prose updated to describe the `#` control rather than the old emoji.

### 3.5 Numbers after the change

Copy-link controls per page, from a cold browser sweep: `implementation` 41,
`data_sources` 32, `pipeline` 14, `china` 14, `ipeds_dashboard` 13, `medical` 13,
`vwp` 12, `india`/`uk`/`webmcp` 11, `canada` 10, `immigration` 102,
`universities/mit.html` 299, `stem.html`/`non_stem.html` 10 static plus one per
department and year once a university is loaded. Zero page errors on all 27 pages.

---

## 4. What I deliberately left

* **SQL is still not shareable.** `query.html#<table>` works, but the query text itself
  is not encoded in the URL. Doing that well means `?sql=<base64url>` plus a "copy link
  to this query" control, which is a feature rather than an anchor, so I stopped at the
  table.
* **Sort and filter state is still not in the URL** — `vwp.html` table sort,
  `overview.html` sort and search, `immigration.html` search and sort,
  `quality.html`'s `#filter` select, `ipeds_dashboard.html`'s year-range and mode
  selects, `department_reports.html`'s department checkboxes. Each is a separate design
  decision about what belongs in a citable link.
* **`implementation.html`'s SVG step clicks still do not write the URL.** The six
  `step-*` targets are addressable; the diagram just does not push them.
* **`site/chat-widget.js` untouched**, as instructed. The alias spans exist precisely
  so its raw `getElementById` calls keep working.
* **No deployment, no cache changes, no commits.** `site/stem.html` and
  `site/non_stem.html` were regenerated from local pipeline data, which now carries 105
  STEM / 105 non-STEM schools rather than the 102 currently deployed — that is local
  data drift, not an anchor change.
* **`sitemap.xml`** was rewritten by `build_static_pages.py` as a side effect of the
  rebuild (222 URLs). I did not hand-edit it, and it lists pages, not fragments.

---

## 5. Cold-entry tests

Every URL below was opened in a fresh headless Chrome page — no prior navigation, no
in-page clicking — against a local server serving the built tree. "landed" means the
element the fragment names was found, its ancestors were expanded, and it was inside
the viewport after load.

### 5.1 Before any change, against the deployed site

| URL | Result |
|---|---|
| `https://phd-demographics.andy-barr.com/stem.html#mit` | landed |
| `.../stem.html#utarlington--engineering` | **failed** — page never left the national view |
| `.../stem.html#missouri_st?h1b=1` | landed, H-1B panel open |
| `.../universities/mit.html#mit--chemistry` | landed (browser fragment retry, not by design) |

### 5.2 After the change, against the built tree

| URL | Result |
|---|---|
| `/stem.html#mit` | landed, scrollY 210 |
| `/stem.html#utarlington--engineering` | landed, top 16 — **was broken** |
| `/stem.html#missouri_st--chemistry--2024` | landed, scrollY 14835 |
| `/stem.html#missouri-st--chemistry` | landed (legacy hyphen form) |
| `/stem.html#missouri-st` | landed |
| `/stem.html#missouri_st?h1b=1` | landed, H-1B toggle on |
| `/stem.html#mit--funding` | funding panel opened and scrolled to, top 16 — **was broken** |
| `/stem.html#mit--h1b` | panel visible, toggle on, top 16 |
| `/stem.html#uiuc--computer-science--2023?funding=1&h1b=1&ms=1` | landed, all three toggles on, hash preserved |
| `/stem.html#missouri_st--2024` | landed, master's toggle turned on automatically |
| `/stem.html#missouri-st--chemistry--2023` | landed, top 16 |
| `/stem.html#nat-visas` | landed |
| `/stem.html#nat-phd` | landed |
| `/non_stem.html#uiuc--education` | landed, department expanded |
| `/universities/mit.html#mit--chemistry` | landed, scrollY 86888 |
| `/universities/mit.html#mit--funding` | panel opened and scrolled to |
| `/universities/missouri_st.html#missouri_st--chemistry--2023` | landed |
| `/universities/missouri_st.html#missouri-st--chemistry` | landed (legacy form) |
| `/universities/nonstem/mit.html#mit--political-science` | landed |
| `/china.html#return-chart-section` | landed |
| `/china.html#united-states-peak-and-decline` | landed — **new**, the `<h2>` had no id |
| `/china.html#us-chart-section` | landed |
| `/medical.html#nrmp-rate-section` | landed |
| `/medical.html#history-section` | landed |
| `/workforce.html#industry-section` | landed |
| `/workforce.html#by-field-section` | landed |
| `/data_sources.html#federal` | landed |
| `/data_sources.html#ice-sevis-data-sevp` | landed — **new**, per-dataset card |
| `/data_sources.html#analytics` | landed |
| `/ipeds_dashboard.html#panel-states` | tab activated and scrolled to — **was a dead nav link** |
| `/ipeds_dashboard.html#panel-trends` | tab activated |
| `/webmcp.html#record-format` | landed — **new**, page had zero ids |
| `/implementation.html#step-federal` | landed |
| `/implementation.html#step-harvest` | landed |
| `/overview.html#phd-funding-sources` | landed — **new**, page had zero section ids |
| `/pipeline.html#eb-chart-section` | landed, 14 copy controls, 0 emoji buttons left |
| `/vwp.html#vwp-table-section` | landed |
| `/uk.html#ho-region-section` | landed |
| `/canada.html#pgwp-section` | landed |
| `/immigration.html#mit` | landed, card at top |
| `/immigration.html#uiuc` | landed, 102 copy controls present |
| `/department_reports.html#missouri_st--trend-chart` | university selected, trend tab active — **new** |
| `/department_reports.html#mit` | fell back to the default view (this dataset holds only 9 universities) — correct |
| `/stem_dashboard.html#binghamton` | detail panel active, university selected — **new** |
| `/query.html#nonstem_records` | table selected, editor previewing `FROM nonstem_records` — **the hash it always wrote now round-trips** |

### 5.3 Copy controls

Clicking a control and reading the clipboard back:

| Control | Copied |
|---|---|
| department header on `stem.html#missouri_st` | `…/stem.html#missouri_st--geosciences-geo-petroleum-eng` |
| university heading | `…/stem.html#missouri_st` |
| fourth heading control on `china.html` | `…/china.html#sevis-chart-section` |

### 5.4 Regression sweep

All 27 pages loaded cold: **zero uncaught page errors, zero console errors.** The
pre-existing `populateDeptFilter` TypeError on the generated pages is gone.

---

## 6. Files changed

| File | Change |
|---|---|
| `scripts/generate_name_lists_html.py` | anchor resolver, canonical ids, alias spans, copy controls, CSS, de-emoji, one null guard |
| `site/anchors.js` | **new** — shared id assignment, copy controls, forgiving hash resolution |
| `scripts/add_section_anchors.py` | **new** — idempotent id baking + inline-share removal + script tag |
| `site/*.html` (25 pages) | 151 ids added, 49 inline share buttons removed, `anchors.js` tag |
| `site/query.html` | table deep link round-trips |
| `site/department_reports.html` | university + tab deep link, address bar sync |
| `site/stem_dashboard.html` | university detail deep link, address bar sync |
| `site/immigration.html` | `Anchors.refresh` after render, first-render-only scroll, `hashchange` |
| `site/data_sources.html` | new "Linking to This Data" section; duplicate "6." numbering fixed |
| `site/sidebar.js` | `hashchange` sync, anchor lists for 7 country pages + medical/workforce/pipeline |
| `site/stem.html`, `site/non_stem.html`, `site/universities/**` | regenerated |
| `site/sitemap.xml` | rewritten by `build_static_pages.py` |

Untouched, as instructed: `pipeline/manifest.json`, `pipeline/universities.json`,
`scripts/generate_name_lists.py`, `site/chat-widget.js`, all cache configuration.
No deployment, no commits.
