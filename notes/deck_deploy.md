# Deck deploy — The Concentration Effect

Date: 2026-08-18
Live URL: https://phd-demographics.andy-barr.com/concentration.html

## 1. Filename

`site/concentration.html`

Existing site pages use short, lowercase, snake_case topic nouns (`stem.html`,
`non_stem.html`, `immigration.html`, `quality.html`, `implementation.html`,
`data_sources.html`). `concentration.html` is the single-word topic noun for
this deck ("The Concentration Effect") and matches that convention. It is also
the source deck's own filename, so nothing had to be renamed.

## 2. Document shell

The source artefact had no `<!DOCTYPE>`/`<html>`/`<head>`/`<body>` — it was
authored for the Artifact wrapper, starting directly at `<title>`. It was
wrapped in a full standalone document with the site's usual head furniture:
charset, viewport, title `The Concentration Effect — PhD Demographics`,
description, og:/twitter: card tags pointing at the site's existing
`og-image.png`, and the four favicon links used by `index.html`. The deck's own
font links, `<style>` block, markup and `<script>` were carried over verbatim —
no data, chart code or theming was altered.

## 3. Shared chrome: deliberately NOT applied

`sidebar.js` is a shared script that, on include, injects a `position: fixed`
220px-wide nav at `left: 0; top: 0; height: 100vh; z-index: 100`, adds
`.has-sidebar` to `<body>`, appends a `.site-footer` element, and side-loads
`chat-widget.js`. It offsets page content only via `.has-sidebar .page
{ margin-left: 220px }`.

It was not added, for four concrete reasons:

1. The deck has no `.page` wrapper — its slides are `position: absolute;
   inset: 0`. The margin rule would never apply, so the sidebar would simply
   cover the left 220px of every slide, including chart gutters and axis labels.
2. The deck's own bottom chrome bar (slide counter, progress rail, hint) is
   `position: fixed; z-index: 10`. The sidebar's `z-index: 100` would sit on
   top of it.
3. `body` is `overflow: hidden` and `.deck` is `100dvh`. The injected
   `.site-footer` would be appended below the fold with no way to scroll to it —
   dead markup.
4. It is a keyboard-driven full-viewport experience. Arrow/Space/PageUp/PageDown
   are captured by the deck; injecting a second fixed panel plus the chat widget
   adds focusable surfaces that compete for those keys.

**Route back to the site instead.** A "← PHD DEMOGRAPHICS" link was added into
the deck's own chrome bar, right of the keyboard hint, styled with the deck's
own tokens (mono type, `--rule2` border, `--nra` on hover, visible focus ring).
It is always on screen at every slide, works in both themes, and collapses to a
bare arrow below 520px so it never crowds the counter on mobile. It points at
`/index.html`.

## 4. Where it was linked

- `site/sidebar.js` — added to the existing **National** section, as the last
  item after "STEM Workforce (SDR)":
  `{ href: '/concentration.html', label: 'The Concentration Effect' }`.
  National is where the site's other US-wide analyses live (National Charts,
  IPEDS PhD Dashboard, Immigration Pipeline, Pipeline Analysis, Medical
  Immigration, STEM Workforce); the deck is a national NRA-concentration
  analysis, so it belongs there. No new section was invented. Because
  `sidebar.js` is shared, the link now appears on all ~23 pages that include it.
- `site/index.html` — a card under the existing **National Overview** section,
  next to the IPEDS dashboard card, using the same `a.card` markup
  (title / desc / meta) as its siblings.
- `site/sitemap.xml` — one `<url>` entry alongside the other top-level pages.

## 5. Local verification

Served `site/` over `python3 -m http.server 8899` and drove headless Chrome
(puppeteer). All checks passed:

| Check | Result |
|---|---|
| HTTP | 200 |
| Title | The Concentration Effect — PhD Demographics |
| Slides rendered | 11 |
| Inline SVG charts rendered | 19 |
| Progress-rail buttons | 11 |
| Counter on load | `01 / 11`, slide `s0` visible |
| ArrowRight x3 | `04 / 11`, slide `s3` visible, heading advanced correctly |
| ArrowLeft | `03 / 11` |
| End / Home | `11 / 11` (last slide has content) / `01 / 11` |
| Arrow keys scroll the document? | No — `window.scrollY` stayed 0 |
| Light theme | `--paper` resolves `rgb(243,244,242)`, ink `rgb(23,26,24)` |
| Dark theme (`prefers-color-scheme: dark`) | `rgb(20,22,20)` / `rgb(236,238,234)` |
| `data-theme="light"` override under dark media | wins — `rgb(243,244,242)` |
| Console errors / warnings | none |
| Uncaught page errors | none |
| Failed network requests | none (Google Fonts loaded) |
| Mobile 390x844 | no horizontal document overflow |
| Shared sidebar injected? | No (as intended) |
| Back link | `href="/index.html"`, visible in chrome bar |
| index.html card | present, title "The Concentration Effect" |
| index.html sidebar link | present, resolved into section **National** |
| index.html console errors | none |

Screenshots in this scratchpad: `deck_light.png`, `deck_dark.png`,
`deck_mobile.png`, `slide_4.png`, `slide_7.png`, `index_after.png`.

## 6. Deploy — scoped, and why

**The stock deploy step was NOT run as-is, because it would have shipped
unrelated in-flight work.** `pipeline/step6_deploy.py` takes no file filter: it
walks the whole `site/` tree. Comparing local state against the bucket before
deploying:

- **204 regenerated data JSONs** — every file in `site/data/stem/*.json` and
  `site/data/nonstem/*.json` was rewritten today at 08:52. The S3 copies date
  from 2026-04-09 / 2026-04-20. This is the data work flagged as in-flight.
- **`site/data/universities_index.json`** — local 2026-04-20 (6,436 B) vs an
  older S3 object.
- **3 unrelated HTML pages** committed today by other work and never deployed:
  `canada.html` (local 26,278 B vs S3 26,289 B), `eu.html` (11,831 vs 11,582),
  `data_sources.html` (34,451 vs 34,449).
- Plus 101 university pages and 2 Parquet exports.

Additionally, `python -m pipeline run --step deploy` routes through
`runner.run_pipeline`, which unconditionally calls `save_manifest()` and
rewrites `pipeline/manifest.json` — a file this task was told not to modify.

**What was done instead:** `pipeline.step6_deploy.step6_deploy()` was invoked
verbatim against a temporary staging tree containing only the four changed
files. Same code path, same `CACHE_RULES`, same content types, same
`aws cloudfront create-invalidation --paths /*` — no ad-hoc `aws s3 cp`, no
cache-header changes, and `runner.run_pipeline` (and therefore `manifest.json`)
was never touched. Script: `scratchpad/scoped_deploy.py`.

Published (4 objects):

- `concentration.html`
- `index.html`
- `sidebar.js`
- `sitemap.xml`

Step output: `Uploaded 4 files` / `CloudFront: invalidation started` /
`errors: 0`.

`git diff --stat site/` confirms the three edited files carry only this task's
changes (+5 / +1 / +1 lines); nothing else went out. Nothing was committed or
pushed.

### Withheld — needs your call

The regenerated data JSONs, `universities_index.json`, the university pages, and
the `canada.html` / `eu.html` / `data_sources.html` updates are still local-only.
A full `python -m pipeline run --step deploy` will publish all of them in one
shot whenever you want them live.

### One header note

`step6_deploy`'s content-type table sets `.js` to `application/javascript`,
whereas the existing S3 object for `sidebar.js` had
`application/javascript; charset=utf-8`. Cache-Control is byte-identical
(`public, max-age=300, stale-while-revalidate=86400`) — caching behaviour is
unchanged. The dropped `charset` is what the project's own deploy step always
sets. Verified live that it causes no mojibake: the non-ASCII sidebar label
`F. Country × State` renders correctly on the deployed `pipeline.html`.

## 7. Live verification

Headless Chrome against `https://phd-demographics.andy-barr.com`:

- `/concentration.html` → HTTP 200,
  `cache-control: public, max-age=300, stale-while-revalidate=86400`,
  `content-type: text/html; charset=utf-8`, `x-cache: Hit from cloudfront`
- 11 slides, 19 SVG charts rendered
- Counter `01 / 11`; ArrowRight x2 → `03 / 11`
- Back link resolves to `https://phd-demographics.andy-barr.com/index.html`
- Dark `rgb(20,22,20)` / light `rgb(243,244,242)`
- Zero console errors, zero page errors
- `/index.html` live: card "The Concentration Effect" present; sidebar link
  present and resolved into the **National** group; zero console errors
- `/pipeline.html` live: sidebar label `F. Country × State` renders correctly

Live screenshots: `live_light.png`, `live_dark.png`, `live_index.png`.
