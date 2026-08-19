# Data-driven OpenGraph cards for phd-demographics.andy-barr.com

Date: 2026-08-18

## What existed before

- One static `site/og-image.png` (83 KB, dated 3 April), generic, unrelated to any
  particular page.
- Of 33 top-level pages, 12 had any OG tags at all — all pointing at that one image.
- All 207 university pages *did* have OG tags, but they were clones of `stem.html`'s:
  same `og-image.png`, and `twitter:title` / `twitter:description` still said
  "Thesis & Dissertation Lists — PhD Demographics / Tracking the outputs of American
  Academia" on every single one. `og:title` and `og:description` were per-university;
  the Twitter pair was not.

## What was built

`scripts/build_og_cards.py` plus a small package under `scripts/og/`:

| file | role |
|---|---|
| `scripts/build_og_cards.py` | driver: card specs, render, tag wiring. CLI with `--only`, `--pages`, `--no-tags`, `--no-render`, `--workers` |
| `scripts/og/card.py` | the 1200x630 HTML/CSS card template and the SVG chart primitives (line, vertical bar, horizontal bar) |
| `scripts/og/data.py` | derives real figures from `data/ipeds/nra_index.csv.gz` and `site/data/{stem,nonstem}/<key>.json` |
| `scripts/og/fonts.py` | fetches the latin subsets of Newsreader / Public Sans / IBM Plex Mono once, caches them in `~/.cache/phd-og-fonts`, inlines them base64 so rendering is deterministic and offline |
| `scripts/og/shoot.py` | headless-Chrome screenshotting, parallel |
| `scripts/og/tags.py` | the single definition of the OG/Twitter meta block, and the page->card filename mapping |

## Filename convention

The card path is the page path with `.html` swapped for `.png` and `og/` in front.
Nothing else — no hash, no counter, no timestamp, no cache-busting suffix — so a
re-run produces byte-identical names, and anyone who knows a page URL can write the
card URL by hand.

```
/index.html                      ->  /og/index.png
/overview.html                   ->  /og/overview.png
/concentration.html              ->  /og/concentration.png
/stem.html                       ->  /og/stem.png
/non_stem.html                   ->  /og/non_stem.png
/workforce.html                  ->  /og/workforce.png
/caltech_dashboard.html          ->  /og/caltech_dashboard.png
/universities/mit.html           ->  /og/universities/mit.png
/universities/purdue.html        ->  /og/universities/purdue.png
/universities/missouri_st.html   ->  /og/universities/missouri_st.png
/universities/nonstem/mit.html   ->  /og/universities/nonstem/mit.png
/universities/nonstem/ucsf.html  ->  /og/universities/nonstem/ucsf.png
```

The STEM and non-STEM variants of the same school cannot collide because the site's
own URLs do not collide — `nonstem/` is carried through verbatim.

University keys are taken from the filenames of the published pages, which are the
same tokens as `pipeline/universities.json`, the sidebar links and
`/data/<mode>/<key>.json`. Verified all 207 keys are lowercase `[a-z0-9_]` only, and
all 207 appear in `pipeline/universities.json`. The canonical underscore spelling is
used: `missouri_st`, never `missouri-st`. No second spelling was introduced.

## Coverage

Full coverage of everything with figures of its own.

- 30 of 33 top-level pages.
- 207 of 207 university pages (105 STEM + 102 non-STEM).

Three top-level pages have no card, each because the card would be empty rather than
to save space:

- `name_lists.html` — a 215-byte `<meta http-equiv="refresh">` stub that redirects to
  `stem.html`. It has no content and no data.
- `analytics.html` — password-gated traffic console; every value is fetched at runtime,
  the static page contains only em-dash placeholders.
- `chat-admin.html` — chat assistant admin console, same situation, and already
  `noindex, nofollow`.

Note: several country and pipeline pages carry `noindex, nofollow`. That stops search
indexing but does *not* stop a scraper reading OG tags when someone pastes the link
into X or Slack, so those pages did get cards.

## Data on the cards

Nothing on a card is invented, and no card shows two numbers that disagree with each
other.

- National series are computed from `data/ipeds/nra_index.csv.gz` at build time. The
  computation reproduces the known figures exactly: national NRA share of research
  doctorates 27.2% in 2010 and 25.5% in 2025.
- The concentration card uses the `D.concentration.dept_count` series embedded in
  `site/concentration.html` itself (82 in 2010 -> 193 in 2025).
- University cards use that university's own `completions_trend` arrays, which are
  IPEDS-derived and reconcile exactly with the index (spot-checked Caltech, unitid
  110404: 179 doctorates / 55 NRA in 2010, 221 / 94 in 2025 — identical in both).
- Top-level page cards use figures quoted from each page or the JSON it loads.

### Resolved: the nra field conflict

First pass flagged that `site/data/*/<key>.json`'s `nra` field disagreed with the
IPEDS completions series in the same file (Caltech 64.9% stored against 40.1%
computed). The maintainer audited all 105: **37 of 103 stored figures were more
than 5 points from IPEDS, in both directions, by as much as 32** — Michigan State
was published at 16.7% against an actual 49.0%. Every value is now recomputed by
`scripts/compute_nra_shares.py` on a pinned, documented basis, and the site data,
the CONFIGS literal and `pipeline/universities.json` agree.

### Resolved: two live STEM definitions

The national STEM figure I could not reproduce was a definitional difference, not
an error. Two STEM CIP sets are live in this codebase and disagree:

| set | families | used by |
|---|---|---|
| narrow (8) | 11, 14, 15, 26, 27, 30, 40, 42 | the headline NRA share on every university page, via `compute_nra_shares.py` |
| broad (16) | + 01, 03, 04, 10, 29, 41, 45, 51 | `enrich_university_json.py`, which produced the `phd_stem_*` completions arrays |

On the narrow set the national STEM series reproduces the quoted 31.9% (1996) ->
37.5% (2025) **exactly**. Both sets are now in `scripts/og/data.py`, narrow as
`STEM_CIPS` and broad as `STEM_CIPS_BROAD`, with a comment explaining which is
which.

### The consequence for the cards, and what was changed

Switching only the national baseline to the narrow set would have made things
worse, not better: the grey national line would have been narrow-set while the
red school line stayed broad-set, so the two lines in one chart would have been
measuring different things.

Measured across all 105 universities, the gap between what the card hero printed
(broad set, pooled 2010-2025) and the headline published on the page (narrow set,
pooled 2015-2022):

| | median | mean | max | over 3 pts | over 5 pts |
|---|---|---|---|---|---|
| card hero on the broad set | 3.2 | 3.7 | 17.6 | 58 of 105 | 28 of 105 |
| card hero on the narrow set | 1.2 | 1.6 | 6.4 | 18 of 105 | 3 of 105 |

Worst cases under the old method: UNLV page 32.3% vs card 14.7%, U Missouri 50.2%
vs 36.4%, Duke 37.3% vs 25.6%. Far larger than the 0.2-2.9 point spread the
national-baseline sample suggested.

So the whole STEM path moved onto the pinned basis, not just the national line.
`scripts/og/data.py` gained `uni_stem_index()`, which reads per-university series
straight out of `data/ipeds/nra_index.csv.gz` on the narrow CIP set with the
correct award-level basis per year (aw17 from 2010, aw09 before; never both, as
2008 and 2009 carry both codings and summing double-counts).

Result: **a STEM card's hero figure is now exactly the share published on its own
page** — verified identical for 103 of the 105 registered universities — and the
school line, the national line and the hero all sit on one definition.

The hero label states the pinned window ("2015-2022") and the chart subtitle
states the plotted range ("2010-2025"), so the two figures cannot be mistaken for
each other.

**Non-STEM cards deliberately stayed on the broad complement.** The narrow set is
defined as the basis for the STEM headline; its complement would sweep health,
agriculture and psychology in with education and the humanities and misdescribe
what the non-STEM pages actually cover.

**cuny and mines have no unitid in the registry**, so their headline shares could
not be recomputed and are legacy values of unknown basis — possibly two of the 37
that had drifted. Rather than print a percentage I cannot stand behind, both now
get the records-based fallback card (record count plus department bars, no
percentage). 2 cards of 207.

Also worth knowing: `site/data/nonstem/<key>.json` carries the same `nra` value as
the STEM file, so the non-STEM pages display a STEM figure. The non-STEM cards do
not use that field.

## Card design

Matches the deck at `site/concentration.html`: paper `#F3F4F2`, ink `#171A18`, accent
`#A32B3C` for the non-resident series, `#8A918B` for baselines; Newsreader for
display, Public Sans for body, IBM Plex Mono for figures.

Two deliberate departures:

- **One fixed light ground.** An OG card is a static PNG; there is no dark mode to
  respond to, and it will sit in dark timelines as often as light ones, so the card
  paints its own background rather than inheriting one.
- **Everything scaled up.** A 1200x630 card renders at roughly 500px wide in a
  timeline, so deck-sized type turns to grey mush. Layout is one large figure on the
  left and one chart on the right, nothing else: hero figure at 82px, headline at
  44px Newsreader, axis labels at 14px.

Axes use round-number ladders in both directions. An earlier pass produced gridlines
at 56.2% and 187.5 because the axis had been fitted to the data; both chart types now
pick a top-of-axis whose divisions are round, and large counts are abbreviated
(1,200,000 renders as 1.2M).

No name, face, avatar or personal branding appears on any card. The only identifier
is the domain in the footer rule.

## Tags

`scripts/og/tags.py` writes one fenced block into `<head>`:

```html
<!-- og:cards -->
og:title, og:description, og:url, og:type, og:site_name
og:image, og:image:secure_url, og:image:type, og:image:width=1200, og:image:height=630, og:image:alt
twitter:card=summary_large_image, twitter:title, twitter:description, twitter:image, twitter:image:alt
<!-- /og:cards -->
```

All URLs absolute against `https://phd-demographics.andy-barr.com` — scrapers fetch
`og:image` from their own servers with no page context, so a relative path resolves
to nothing.

Injection first removes any previously fenced block *and* any loose `og:`/`twitter:`
tags the page carried, then writes the canonical block, so it is idempotent: running
it twice yields identical bytes. Verified.

`og:title` and `og:description` describe the page, not the site. Every university
page now gets its own `twitter:title` and `twitter:description` instead of the shared
site-wide pair.

## Repeatability

`python3 scripts/build_og_cards.py` rebuilds everything. `--pages` does top-level only,
`--only <names>` a subset, `--no-render` re-wires tags without re-screenshotting,
`--no-tags` renders without touching HTML.

Because generated pages would otherwise lose their tags on the next pipeline run, the
two generators that own pages were patched to emit the same block from the same module:

- `scripts/generate_name_lists_html.py` — owns `stem.html` and `non_stem.html`. Its
  hand-written OG block was replaced with `og_tags.generated_page_block(...)`.
- `scripts/build_static_pages.py` — owns all 207 university pages. Its three
  `re.sub` calls on `og:title`/`og:description`/`og:url` were replaced with a single
  `og_tags.wire_html(...)` that also sets the per-university `og:image`.

Two pre-existing bugs were fixed in passing while doing that, both consequences of
getting `og:url` right:

- Non-STEM university pages had `og:url` **and** `<link rel="canonical">` pointing at
  `/universities/<key>.html` — the STEM page — telling crawlers the two were the same
  document. They now point at `/universities/nonstem/<key>.html`.
- The generated meta description said "NRA share of STEM doctoral completions" on
  non-STEM pages too; it now says non-STEM there.

## Verification

Bulk audit over all 237 PNGs:

- All 237 are exactly 1200x630, read from the PNG IHDR header rather than assumed.
- None is blank. Smallest is 59,494 bytes (`og/universities/nonstem/njit.png`, a
  sparse fallback card); largest 96,456. A blank 1200x630 card compresses to
  roughly 6 KB, so nothing near that exists.
- All 240 pages were checked for a resolvable `og:image`: every referenced card
  exists on disk, and exactly the three intentionally excluded pages
  (`chat-admin.html`, `analytics.html`, `name_lists.html`) have none.
- Re-running the tag wiring reports "0 pages updated" — idempotent.
- No `og-image.png` reference remains in any HTML file (was 240).

Images opened and read individually (11 at full size, 2 downscaled):

| card | checks |
|---|---|
| `og/universities/mit.png` | 1200x630. Hero 42.6% pooled, chart ends 40.0% — consistent. Round axis ticks 0/15/30/45/60. School line and national dashed baseline distinguishable. |
| `og/universities/nonstem/mit.png` | 1200x630. Correct non-STEM series (43.6% pooled vs 12.5% national), labelled "non-STEM" not "stem". |
| `og/universities/utarlington.png` | 1200x630. 61.9% hero, 54.5% endpoint. One of the six re-rendered after the parallel failures — clean. |
| `og/universities/nonstem/njit.png` | 1200x630. Fallback card: 23 records, department bars of 7/4/4/2. Prints the small real numbers rather than a noisy percentage. |
| `og/universities/nonstem/dartmouth.png` | 1200x630. Fallback card for a school with zero IPEDS non-STEM doctorates. |
| `og/index.png` | 1200x630. 471K hero, national NRA line flat at 25.5%. |
| `og/concentration.png` | 1200x630. "82 → 193" hero over the department-count bars; axis 0/50/100/150/200. |
| `og/overview.png` | 1200x630. OPT bar chart 2007–2024, axis 0/50K/100K/150K/200K. |
| `og/workforce.png` | 1200x630. Horizontal bars 70.5 / 65.1 / 59.9 / 38.1 percent. |
| `og/canada.png` | 1200x630. Large-count line chart, axis abbreviated to 300K/600K/900K/1.2M. |
| `og/stem.png` | 1200x630. |

Legibility at timeline size: cards were downscaled to 504px wide (roughly what X
shows) and re-read. At that size the headline, the hero figure, the chart title,
both plotted lines and the stat numbers are all clearly readable; the footer source
line reduces to texture, which is what it is there for. The first draft failed this
test — deck-sized type was unreadable — which is why the card type scale is
substantially larger than `concentration.html`'s.

## Cost

- 237 PNGs: 20,296,005 bytes (19.36 MiB).
- 237 HTML files: net +111,350 bytes (the meta block, less the tags it replaced).
- **Total added: 20,407,355 bytes, about 19.5 MiB.**

Free space on `/Users/andy`: 10 GiB before, 6.7 GiB after. Only ~20 MiB of that is
this work — the volume sits at 99-100% full and other processes moved it during the
run. One 2.7 MB orphaned Chrome profile left by the killed first run was cleaned up;
the renderer removes its own profiles on exit.

Render cost: about 2.5s per card, 4 workers, roughly 18 minutes for the full set.

## Not done / flagged

- `analytics.html` is an internal traffic console but carries no `noindex`. Not my
  call to add one, but worth knowing.
- `cuny` and `mines` have no unitid in `pipeline/universities.json`, so their
  headline NRA shares (38.5% / 39.8%) are legacy values that could not be
  recomputed on the pinned basis. Their cards print no percentage.
- `site/data/nonstem/<key>.json` stores the STEM `nra` value, so non-STEM pages
  show a STEM headline share. The cards avoid the field; the pages still use it.
- The broad and narrow STEM sets both remain live in the codebase — narrow drives
  the headline shares, broad drives the `phd_stem_*` completions arrays. Cards now
  pick per purpose and say which; the underlying duplication is unresolved.
- `non_stem.html`'s national chart arrays (`phdTotal` / `phdNRA`) are byte-identical
  to `stem.html`'s STEM arrays, i.e. the page plots STEM data under a non-STEM label.
  The card avoids them and uses an independently computed national non-STEM series.
- `data_sources.html` still has the stale "— USDS China" title suffix.
- Nothing was deployed to S3 or CloudFront; `python -m pipeline run` was not run;
  nothing was committed.
