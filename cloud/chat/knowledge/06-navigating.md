# What lives where on this site

Use this to send readers to the right place. Paths are authoritative; the
site-map section below this one is generated from the actual HTML and wins on
any disagreement.

## The argument, in the order the site makes it

The homepage and the left rail both carry these four steps, numbered. Full
detail in `36-the-argument.md`; this is the routing table.

- `/` — the entry point: the four steps as four cards.
- `/presentation` — twelve slides, Previous/Next buttons plus arrow keys
  and swipe (it was at `/concentration` until 2026-09-12, which now
  redirects). Anchors: `overview`, `national-flat`, `concentration`,
  `by-field`, `case-purdue`, `case-texas-a-m`, `case-ohio-state`,
  `case-penn-state`, `case-stony-brook`, `persistence`, `method`. Best single
  destination for "what is the finding?"
- `/overview` — the longer prose version.

**Step 1, the public pays for the doctorate:** `/ipeds_dashboard`,
`/distributions`, `/non_stem`, `/rankings`.

**Step 2, the master's is sold:** `/expansion`, `/institutions`,
`/rankings`.

**Step 3, the degree becomes a visa:** `/immigration`, `/pipeline`,
`/workforce`, `/medical`, `/filers`. The cost-of-an-OPT-hire
argument is `/visa-schools#cheaper`.

**Step 4, who profits:** `/visa-schools` (the 57 colleges where foreign
students are most of the graduate enrolment), `/bodyshops` (the firms that
sponsor H-1B workers and place them at other companies — see
`37-the-body-shops.md`), `/usaid`, `/filers`.

`/rankings` and `/filers` each answer to two steps and are listed
twice in the rail on purpose.

## The data

- `/stem` and `/non_stem` — the corpus of dissertation records, with
  search and department filters. Heavy pages; the search index loads only when
  a reader actually searches.
- `/universities/{key}` — one page per university. Keys come from
  `list_universities`.
- `/query` — raw record queries. Send analysts here, and pair the nav with
  a `suggest_query` chip so they land with something already typed.
- `/live` — degrees by field, level and residency status, redrawn on
  demand.
- `/data/exports/stem_records.parquet` and `nonstem_records.parquet` — the whole
  corpus as Parquet, for anyone who would rather compute than browse.

## Country context

- `/china`, `/india`, `/canada`, `/uk`, `/eu`,
  `/mexico` — country-specific mobility.
- `/vwp` — visa waiver context.

## Method and provenance

- `/implementation` — how the pipeline works.
- `/data_sources` — every source, with links to the primary files.
- `/quality` — coverage, completeness and known gaps. Send anyone who
  challenges the data here rather than defending the numbers in chat.

## Choosing between nav and link

`navigate_user` when the answer **is** a place — the reader should end up there.
`show_link` when the answer **cites** a place, or points at a primary source
elsewhere. Only `show_link` may leave this site, and only over https.
