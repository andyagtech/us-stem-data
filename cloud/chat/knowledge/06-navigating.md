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

## Guided tours, and when to offer one

There are eighteen tours. Each is a short, narrated walk that opens in this panel,
rings the thing being discussed, and moves on when the reader presses Next.

**A tour is a link.** Adding `?tour=<name>` to any page starts that tour on
arrival, so a tour can be handed to a reader the same way a page is:

| name | stops | what it walks through |
|---|---|---|
| `full` | 12 | the whole argument, end to end |
| `step1` | 3 | the public pays for the doctorate |
| `step2` | 3 | the master's is where the change happened |
| `step3` | 3 | the degree becomes a work visa |
| `step4` | 3 | who profits |
| `universities` | 3 | the rankings, the comparison, one institution in full |
| `industries` | 4 | the five strategic industries and what restricts each |
| `h1b` | 4 | body shops, the public payroll, the uncounted route |
| `states` | 3 | the state pages and the labor-visa side by state |
| `international` | 3 | China, India and Canada as origins and destinations |
| `reference` | 4 | the sources, the repositories, the gaps, the SQL console |
| `india` | 4 | the largest sending country, and the American end of it |
| `china` | 4 | the peak and decline, and where the flow went instead |
| `canada` | 3 | the competitor running the same model, and the staging post |
| `uk` | 3 | the same model, stated more openly |
| `eu` | 3 | Germany as the counter-example: no tuition business to protect |
| `mexico` | 3 | the near neighbour that sends few, and where its citizens do appear |
| `vwp` | 3 | the comparison case: a flow with no visa pipeline attached |

There is also an on-page tour of the charts on `/stem` and `/non_stem`,
started by the **Take the tour** button there. It does not navigate.

**When to offer one.** A reader who asks a broad question — "what is this
site about", "where do I start", "can you show me the evidence" — is better
served by a tour than by a list of links. Offer the one that fits the
question, as a navigation to the page with the parameter attached: for
someone asking about master's degrees, `/overview?tour=step2`.

> Guidance, not text to repeat: do not offer a tour to someone who asked a
> narrow factual question. They want the number. Answer it, and mention the
> tour only if the answer opens onto a larger point.
