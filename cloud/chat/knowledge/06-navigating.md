# What lives where on this site

Use this to send readers to the right place. Paths are authoritative; the
site-map section below this one is generated from the actual HTML and wins on
any disagreement.

## The argument

- `/` — the entry point and the summary of the finding.
- `/presentation.html` — the presentation. Twelve slides, with Previous and Next
  buttons as well as arrow keys and swipe (it was at `/concentration.html` until
  2026-09-12, which now redirects),
  each with a descriptive anchor: `overview`, `national-flat`, `concentration`,
  `by-field`, `case-purdue`, `case-texas-a-m`, `case-ohio-state`,
  `case-penn-state`, `case-stony-brook`, `persistence`, `method`. This is the
  best single destination for a reader who asks "what is the finding?"
- `/overview.html` — the longer prose version.

## The data

- `/stem.html` and `/non_stem.html` — the corpus of dissertation records, with
  search and department filters. Heavy pages; the search index loads only when
  a reader actually searches.
- `/universities/{key}.html` — one page per university. Keys come from
  `list_universities`.
- `/query.html` — raw record queries. Send analysts here, and pair the nav with
  a `suggest_query` chip so they land with something already typed.
- `/data/exports/stem_records.parquet` and `nonstem_records.parquet` — the whole
  corpus as Parquet, for anyone who would rather compute than browse.

## The pipelines and context

- `/pipeline.html` — enrolment through doctorate through work authorisation
  through green card. The EB bottleneck lives here.
- `/china.html`, `/india.html`, `/canada.html`, `/uk.html`, `/eu.html`,
  `/mexico.html` — country-specific mobility.
- `/vwp.html` — visa waiver context.
- `/workforce.html` — labor-market outcomes.
- `/medical.html` — medical and health fields, which sit outside the narrow STEM
  definition and need their own treatment.
- `/usaid.html` — foreign assistance context.

## Method and provenance

- `/implementation.html` — how the pipeline works.
- `/data_sources.html` — every source, with links to the primary files.
- `/quality.html` — coverage, completeness and known gaps. Send anyone who
  challenges the data here rather than defending the numbers in chat.

## Choosing between nav and link

`navigate_user` when the answer **is** a place — the reader should end up there.
`show_link` when the answer **cites** a place, or points at a primary source
elsewhere. Only `show_link` may leave this site, and only over https.
