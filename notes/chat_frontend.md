# chat-widget.js v2 — frontend implementation notes

Date: 2026-08-18
File: `/Users/andy/usds_china_private/site/chat-widget.js` (221 → 1,812 lines)
Contract: `chat_contract.md` v2. No other file was modified.

Test harnesses (scratchpad, not in the repo):
`scratchpad/testroot/harness.html`, `harness2.html`, `harness_light.html`, `probe.html`,
`narrow.html`, plus `scratchpad/cdp.mjs` + `eval_live.js` for driving a real site page.

---

## 1. The three XSS vectors, and how each is closed

The old widget built HTML strings from model output and assigned them to `innerHTML`.
The fix is not a better filter — it is the removal of the string-building step. **Every
visible character now arrives through `document.createTextNode` or `.textContent`, every
handler through `addEventListener`, every URL through a parsed `URL` object.** There is
no `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval` or
`new Function` anywhere in the file (verified by grep; the only three hits on `innerHTML`
are in comments explaining its absence).

That is deliberately stronger than the contract's §4.8 rule 1 ("escape, then format"):
an escape-then-format pipeline still has a format step that can un-escape. `escapeHtml`
is therefore **not** present — there is nothing for it to protect, and a stray
`escapeHtml` before a `textContent` write would render `&amp;lt;` to the reader.

### Vector (a) — `markdownToHtml()` output written to `div.innerHTML` unescaped

**Closed by:** `mdToNodes(md) -> DocumentFragment`. `parseMdBlocks` splits the markdown
into `{p|h|ul}` records; `renderInline` walks each record and appends `<strong>`, `<em>`,
`<code>`, `<a>` **elements** with their text set via `textContent`. Markup in the model's
prose can only ever become a text node.

Payloads tested (each inserted into `text.md`, `notice.md`, `notice.title`, `stat.label`,
`stat.value`, `table.title`, a column label, a table cell, `query.explanation`,
`suggest.label`, and a `[[nav:…|Label]]` label — 11 sinks, same string):

```
<img src=x onerror="__pwn('img')">
<script>__pwn("script")</script>
<svg/onload=__pwn("svg")>
"><iframe srcdoc="&lt;script&gt;__pwn(1)&lt;/script&gt;"></iframe>
');__pwn('breakout');//
```

Result: `window.__XSS` empty; `#chat-messages img`, `iframe`, `script` all zero;
`[onload],[onerror],[onmouseover],[onclick],[onfocus]` zero; the payload appears in
`textContent` as literal visible text.

### Vector (b) — `[label](href)` accepting any href, `javascript:` included

**Closed by:** three resolvers, all of which parse before they judge, and none of which
does a `startsWith` on the raw string.

- `resolveSiteUrl(raw)` — rejects control characters, requires exactly one leading `/`
  (this is what kills `//evil.host` and `/\evil.host`), rejects any backslash, then
  `new URL(raw, location.origin)` and checks `u.origin === location.origin` **and**
  `u.protocol === location.protocol`. Then caps: url ≤ 300, fragment ≤ 128 and matching
  the RFC 3986 fragment charset, query ≤ 256. Then `SITE_MAP.pages` membership.
- `resolveExternalUrl(raw)` — `new URL(raw)` then `u.protocol === 'https:'` exactly.
- `resolveMarkdownUrl(raw)` — site-relative goes through `resolveSiteUrl`; otherwise
  `https:`/`http:` only, and the resulting `<a>` gets `target="_blank" rel="noopener noreferrer"`.

A rejected URL makes the whole block **not render**; a rejected markdown link keeps the
label as plain text and produces no anchor.

Payloads tested against the site gate (all rejected):

```
javascript:alert(1)                    JaVaScRiPt:alert(1)
"\tj\na\tvascript:alert(1)"            " javascript:alert(1)"   (leading space)
"java\0script:alert(1)"                data:text/html,<script>__pwn("data-url")</script>
data:text/html;base64,PHNjcmlwdD5fX3B3bigxKTwvc2NyaXB0Pg==
blob:https://evil.host/x               vbscript:msgbox(1)
file:///etc/passwd                     //evil.host/x
/\evil.host/x                          \\evil.host\x
https://evil.host/x                    http://localhost/stem.html
/stem.html#<200 chars>                 /stem.html?<300 chars>
/<400 chars>.html                      /nope-not-a-real-page.html
/stem.html#frag'><img src=x onerror=__pwn(2)>
/stem.html#<img src=x onerror=__pwn(3)>
```

Against the external gate (all rejected): `http://x.com`, `javascript:alert(1)`,
`data:text/html,x`, `//evil.host`, `blob:https://x/y`, `file:///etc/passwd`, `vbscript:x`.

Accepted, as they must be: `/stem.html`, `/stem.html#nat-phd`,
`/pipeline.html#eb-chart-section`, `/concentration.html#anything-at-all`,
`/universities/mit.html?funding=1#completions-trend-chart`,
`https://nces.ed.gov/ipeds/use-the-data`.

One case is **accepted and inert** rather than rejected:
`/stem.html#frag"onmouseover="__pwn(1)`. `new URL` percent-encodes the quote, so the
carried fragment is `frag%22onmouseover=%22__pwn(1)` — no quote reaches the DOM, the
`href` is set with `setAttribute` (no parsing), and the decoded form is only ever passed
to `getElementById` / `window.Anchors.goTo`, neither of which interpolates into a
selector. Asserted explicitly in the harness.

### Vector (c) — `section_id` interpolated into `onclick="…'${sectionId}'…"`

**Closed by:** that construction is gone. Nav cards, inline nav chips, table row chips,
link blocks and suggest chips are all real elements with
`addEventListener('click', …)` closing over the already-resolved target object. The
fragment never appears in an attribute other than a `setAttribute('href', …)` of a
re-serialised, validated URL. `#chat-messages [onclick]` is asserted to be zero.

Two related hardenings:
- `stat.bar` is clamped `Math.max(0, Math.min(100, Number(v) || 0))` and applied with
  `element.style.width`, never interpolated into a style attribute string. Tested with
  `bar: '80"onload=__pwn(4)'`, `-50`, `100000`, `'abc'` — all render 0–100%.
- Chart.js configs are built field by field in `chartConfigFor`. Model JSON is **never**
  spread into an options object, so a smuggled function value has nowhere to land. Tested
  with a chart block carrying `options: {onClick: 'alert(1)'}` and `plugins: {evil: 1}` —
  both ignored.

---

## 2. How each block type renders

All widget CSS is scoped under `#phd-chat-root` / `#chat-panel`; every element the widget
creates carries a `cb-` class. The one global rule is `.cb-target-ring`, which has to
apply to a host-page element.

| type | rendering |
| --- | --- |
| `text` | `mdToNodes`: `<p>` / `cb-h1..3` / `<ul><li>`, inline `**bold**` `*italic*` `` `code` `` `[label](url)`, plus `[[nav:/url\|Label]]` and `[[university_key]]` chips. Unknown path ⇒ the token renders as literal text and no link is made. |
| `chart` | `line`, `bar`, `hbar`, `stacked_bar`, `area`, `doughnut`, `scatter`. Container 190px (240px for doughnut/hbar > 6 categories), built lazily on `IntersectionObserver` intersection inside the panel's scroll box. Colour comes only from `datasets[].role`; number formatting only from `y.format`. Title, optional subtitle, `source` caption, an optional `nav` chip beneath, `aria-label` on the canvas and a visually-hidden `<table>` of the same numbers. `hbar` swaps which axis carries the value formatting. |
| `table` | `<table class="cb-table">` in an `overflow-x:auto` wrapper, sticky header, zebra rows, per-column `align`/`format`/`emphasis`, per-row `nav` chip in the first left-aligned cell, `note` / `source` captions, optional `footer_nav`. |
| `stat` | 1–4 cards, flex, 2-up at panel width and stacked below 500px. Label, value, optional `delta` with a ▲/▼/– glyph coloured by `delta_dir`, optional `note`, optional `bar` proportion track (Sunfire's score-bar, same clamp). `emphasis` tints value and bar. |
| `nav` | Card with a chart glyph, the label, an optional muted `reason`, and — cross-page only — a secondary open-in-new-tab control. Same-page: `scrollIntoView` + `history.pushState(url)` + a 2,500 ms `cb-target-ring`. Cross-page: click only. |
| `link` | `kind:"site"` → anchor routed through `performNav`, plus a copy button that writes `https://phd-demographics.andy-barr.com` + url. `kind:"external"` → `target="_blank" rel="noopener noreferrer"`, an SVG box-arrow, the hostname muted beneath, optional note. `kind` is required; it is never inferred from the string. |
| `query` | Muted explanation, `<pre>` with the SQL set via `textContent`, and a "Run on the query page" link to `/query.html`. Nothing is executed. |
| `suggest` | Pill buttons; clicking fills and **sends immediately**; `title` carries the full prompt. Always rendered last regardless of position in `blocks`, and cleared as soon as the next turn is sent. |
| `notice` | Left rule + tinted bold title, body through `mdToNodes`. `info` sky, `ok` emerald, `warn` amber, `bad` red. The wire's `icon` field is deliberately **ignored** (see §5). |
| unknown | skipped silently — the forward-compat hinge. Tested with `{"type":"wormhole"}`. |

Navigation and addressing: **no fragment grammar is parsed anywhere.** `resolveUrl`
validates the *path* against `SITE_MAP` and treats `?query` and `#fragment` as opaque
strings that are length- and charset-capped, carried, and handed to the browser. Same-page
resolution delegates to `window.Anchors.goTo(fragment)` when `anchors.js` is on the page
(it already handles hidden tabs and forgiving id matching), and falls back to polling
`getElementById` 20× at 150 ms for ids minted in JS after load. A fragment that never
resolves leaves the reader at the top of a real page and logs nothing.
`window.dispatchEvent(new CustomEvent('phdchat:navigate', {detail:{url,path,fragment,auto}}))`
fires on every navigation.

Also implemented per §6: 45 s `AbortController`, one cold-start retry restricted to
network failures that died in under 5 s, `sendSeq` stale guard, `sessionStorage`
transcript (`phd-chat-history`, prose only, 20 turns), warm-up ping on first open,
`error_code → {title, help}` mapping, `Retry-After` countdown that disables Send, a Retry
chip for `upstream_*`/`internal`/`network`, `prefers-reduced-motion` handling, `Escape` to
close, and a v1 `renderLegacy` fallback when `blocks` is absent.

---

## 3. The 103/135 page coverage problem

**The stated figure is stale, and the remaining gap is 8 pages, not 32.**

Measured over the real tree (33 root + 105 university = **138** pages):

- 107 pages carry `<script src="/chat-widget.js">` directly (`stem.html`, `non_stem.html`,
  and all 105 `universities/*.html`).
- 21 more carry `<script src="/sidebar.js">`, and `sidebar.js` **already appends the
  widget itself** at its tail (`site/sidebar.js:320`, committed, not new).
- Union = **128 of 138**. The two sets are disjoint, so nothing double-loads today.

The 10 pages that load it by neither route:

| page | note |
| --- | --- |
| `analytics.html` | standalone, no shared chrome |
| `caltech_dashboard.html` | legacy one-off |
| `caltech_field_demographics.html` | legacy one-off |
| `caltech_ipeds_tables.html` | legacy one-off |
| `concentration.html` | the new slide deck, own layout |
| `department_reports.html` | generated |
| `name_lists.html` | generated by `scripts/generate_name_lists_html.py` (off-limits to me) |
| `quality.html` | standalone |
| `chat-admin.html` | admin dashboard — **excluded from `site_map.json` on purpose**; should probably stay without it |
| `submit.html` | tip line — also excluded from `site_map.json` |

**What I did:** I could not close it, because every remaining fix is a one-line edit to a
`site/*.html` file or to the generator, both of which are owned by other agents. What I
did instead was make the fix safe to apply:

1. **Added an idempotency guard.** The widget returns immediately if `window.__phdChat`
   already exists. Without it, adding `<script src="/chat-widget.js">` to any of the 21
   sidebar pages — the obvious thing for someone to do — produces two bubbles, two panels
   and duplicate element ids. Tested: a page with the script tag twice yields exactly one
   bubble and one panel.
2. **Made the widget safe on pages that have no Chart.js.** 6 of the 128 covered pages
   (`about`, `data_sources`, `implementation`, `index`, `query`, `webmcp`) do not load
   Chart.js; `ensureChartJs()` lazy-injects the same pinned CDN URL and degrades to a
   table if it never arrives.

**What needs to happen, for whoever owns those files** — add before `</body>`:

```html
<script src="/chat-widget.js"></script>
```

to `analytics.html`, `caltech_dashboard.html`, `caltech_field_demographics.html`,
`caltech_ipeds_tables.html`, `concentration.html`, `quality.html`, and to the
`department_reports.html` / `name_lists.html` generators. Leave `chat-admin.html` and
`submit.html` alone unless the assistant is meant to appear on the admin surface.
Alternatively, one line in `sidebar.js` is not the answer — those 8 pages do not load
`sidebar.js` either, which is exactly why they are the gap.

**One bug in the sibling's artifact.** `site/data/chat/site_map.json` marks 28 pages
`"widget": false`, but **20 of them do load the widget** via `sidebar.js`
(`about`, `canada`, `china`, `data_sources`, `eu`, `immigration`, `implementation`,
`index`, `india`, `ipeds_dashboard`, `medical`, `mexico`, `overview`, `pipeline`,
`query`, `stem_dashboard`, `uk`, `usaid`, `vwp`, `workforce`). `scripts/build_site_map.py`
looks only for a literal `chat-widget.js` script tag. If the backend uses `widget:false`
to decide anything, it is wrong for those 20. The genuinely-false set is the 8 above.
I did not edit the script — it is the backend implementer's file.

---

## 4. Test results

Served locally with `python3 -m http.server` (testroot on :8931, the real `site/` on
:8932) and driven by headless Chrome — `--dump-dom` for the assertion harnesses,
`--screenshot` for layout, and CDP (`cdp.mjs`) to script the widget on a real page.

| suite | assertions | result |
| --- | --- | --- |
| `harness.html?chart=local` — 9 block types, 22 hostile URLs, 11 injection sinks, caps | 76 | **76 pass** |
| `harness.html?chart=none` with `MAP cdn.jsdelivr.net 127.0.0.1:1` — Chart.js absent *and* CDN unreachable | 76 | **76 pass** (all charts degrade to tables) |
| `harness_light.html` — light host page | 76 | **76 pass** |
| `harness2.html` — transport, mocked Lambda | 31 | **31 pass** |
| **total** | **259** | **259 pass, 0 fail, 0 console errors** |

All four suites were then re-run against the **real** `site/data/chat/site_map.json`
(32 pages, 105 universities) produced by `scripts/build_site_map.py`, with two harness
pages appended: still 259/259.

Transport suite covers: double `<script>` load ⇒ one bubble; warm-up ping on open;
a normal v2 turn (typing indicator, blocks, `v:2`/`page`/`client` in the request,
prose-only `sessionStorage`); chip click sends its prompt and clears old chips;
429 + `Retry-After` ⇒ warn notice, live countdown, Send disabled; 502 ⇒ bad notice +
Retry chip that resends the same turn and recovers; the §4.4 degraded 200 envelope
rendering as an ordinary turn with two nav cards and Send still enabled; a network
failure rendering a notice rather than a raw exception; `too_long` putting the text back
in the input; and no interleaving or duplication when a second send races an in-flight one.

Live page checks (`http://localhost:8932/…`, real site files): `stem.html`,
`universities/mit.html`, `pipeline.html`, `index.html`, `query.html` each mount exactly
one bubble with no console errors; `concentration.html` mounts none (it is one of the 8).
Driving the §4.11 worked example on the real `stem.html` gave: 1 bubble, site map loaded
and rejecting unknown paths, 1 live Chart.js canvas in the site palette, 2 nav cards,
2 inline nav chips, `location.hash === '#nat-phd'` from the auto-nav, 1 element carrying
`cb-target-ring`, 0 unsafe hrefs.

Layout: verified at 420px and 320px by rendering the widget inside fixed-width iframes
(headless Chrome clamps `--window-size` to a 500px minimum viewport, so a naive narrow
screenshot is misleading). At 320px the panel is 302px wide, stat cards stack full-width,
the chart resizes, and a wide table scrolls inside its own container without widening the
panel. Light and dark both verified by screenshot.

---

## 5. Contract items I did not honour, and why

1. **`escapeHtml()` is absent.** §4.8 rule 1 and §6 name it. Building DOM nodes (rule 2)
   makes it not merely redundant but harmful — escaping before a `textContent` write
   shows the reader `&amp;lt;`. The security property the rule was protecting is met more
   strongly. Nothing else in the contract depends on the function existing.

2. **No emoji in the UI, and no `↗`.** The contract specifies 📊 on nav cards, 📋 on copy
   buttons, 🔍 on the query link, ℹ️/✓/⚠️/✕ on notices, and `↗` on external and
   cross-page links. The user has explicitly rejected emoji and the `↗` character, so all
   of these are inline SVG icons instead, and `notice.icon` from the wire is ignored
   entirely (the model may put an emoji there). The `kind` is expressed by the left rule
   and title colour. `▲`/`▼` on stat deltas are kept — they are geometric symbols, not
   emoji; say the word and they become SVG too.

3. **Client `blocks` cap raised from 8 to 12.** §4.7 caps `blocks` at 8, but the §4.11
   worked example carries 10 and acceptance criterion 9 requires **all nine block types
   from that example to render**. Those cannot both hold. I took the acceptance test as
   authoritative and set the client cap to 12; `suggest` is lifted out *before* the cap so
   follow-up chips are never what falls off the end. A client more permissive than the
   server can only fail to hide something the server deliberately sent, so this opens
   nothing. **This is a real inconsistency in the contract and should be resolved on the
   spec side** — either raise the cap to 12 or shorten the worked example.

4. **`SITE_MAP` unavailable ⇒ lenient path check, not total rejection.** §4.5.5 rule 2
   validates paths against `SITE_MAP.pages`. If `/data/chat/site_map.json` 404s or the
   fetch fails, rejecting every path would silence every link the assistant offers — the
   opposite of degrade-don't-fail. In that state the hard security gate (single leading
   slash, same origin, same protocol, caps) is still fully enforced; only the
   does-this-page-exist test relaxes to a shape test (`/…/name.html`), and university keys
   fall back to `/data/universities_index.json`. The map is now fetched eagerly at load,
   so this path is rare.

5. **Markdown inline links also accept site-relative URLs.** §4.5.1 says http/https only.
   `[label](/stem.html#nat-phd)` now works, routed through the same `resolveSiteUrl` gate
   as everything else, because the model will write them and rendering the label as bare
   text is a worse outcome than a validated internal link. http/https external links
   behave exactly as specified.

6. **Header identity changed.** The old panel showed `/andy-avatar.jpeg` and read
   "Ask about Academia" / "Hi! I'm Andy's AI assistant." Per the user's standing
   rejection of their name and face on the assistant, it is now "Data assistant" with no
   image and a neutral greeting.

7. **Charts are destroyed on `_clear()` and `pagehide`, not per removed message.** §6 says
   "destroy on message removal"; no code path removes a chart-bearing message
   individually (only the typing indicator and stale suggest chips are removed), so the
   distinction is currently unobservable.

8. **`page_action` is not implemented** — correct per §4.5.11; it is skipped by the
   unknown-type rule, so the backend can ship it whenever the widget learns it.

Nothing in the contract had to be renegotiated to make the frontend work. Item 3 is the
only one I would like a decision on.
