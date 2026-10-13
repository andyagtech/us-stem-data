# What the assistant can put on screen

The assistant does not emit HTML. It emits **blocks** — data plus a semantic
role — and `site/chat-widget.js` owns every pixel. No colour, no markup and no
Chart.js config ever crosses the wire. That split is deliberate: a model that
cannot write markup cannot write a style that breaks the panel, and the panel
can be restyled without touching the prompt.

So "can the assistant do rich text?" has two answers, and both matter:

- **In prose**, it may use a small markdown subset. The panel parses it.
- **Alongside prose**, it calls render tools that produce real components —
  tables, charts, KPI strips, notices, links.

Everything below is enforced in code, not just asked for in the prompt. Each
rule names the file that enforces it.

## The house style

**Prefer a bulleted list.** Two or more parallel findings, caveats,
institutions or definitions belong in bullets, one idea per bullet, never
packed into a paragraph. This is the author's standing preference and it holds
unless the answer is a single sentence. It is stated in the Response Style
section of `prompt.py`.

Short declarative sentences, one idea each — the same rule the site's prose
follows (see `CLAUDE.md`).

## The markdown subset the panel renders

`parseMdBlocks` in `site/chat-widget.js`. Nothing outside this list is parsed;
anything else lands as plain text.

| Written | Renders as |
|---|---|
| `### Heading` (1–3 `#`) | a heading, `.cb-h1`–`.cb-h3` |
| `- item`, `* item`, `+ item`, `• item` | an unordered list |
| `1. item`, `1) item` | an ordered list |
| two-space indent under an item | one level of nesting, and only one |
| `**bold**`, `*italic*`, `` `code` `` | inline marks |
| `[label](/path)` | a link; site paths navigate, https opens a new tab |
| `[[nav:/page.html#id\|Label]]` | an inline nav chip |
| `[[mit]]` | shorthand for `/universities/mit.html` |
| a pipe table with a `\|---\|` rule | a table, capped at 3 columns |
| `---` on its own | a paragraph break |

Three of those used to fall through to the paragraph branch and come out as
run-on text: `*` bullets, `1.` numbered lists, and pipe tables. The `*` case
was the worst, because the inline italic rule `\*([^*\n]+?)\*` then matched
across the line and set the whole list in italics. `tests/test_chat_rendering.py`
runs the parser under node and holds all three.

**A numbered list is for a real sequence only** — steps in order, or a ranking
where the position is the point. Otherwise use `-`.

**Never write a table in prose.** A row of pipes is not a table block: it
carries no source, no alignment and no number check. The panel will render one
rather than print garbage, but tabular data belongs in `show_table`.

## Tables

The chat panel is **420px wide**. That is the whole constraint.

- **Three columns, maximum.** One label column plus the two measures that
  matter. `blocks.MAX_COLUMNS = 3`.
- **A fourth column is trimmed, and the note names what went** —
  `4 columns sent, 3 shown; dropped NRA count`. The reader can see that the
  table is narrower than what was measured.
- **25 rows, maximum**, trimmed the same way with the same disclosure.

  Rejecting the fourth column was tried first, on 2026-10-13, on the reasoning
  that a silently narrower table can disagree with the prose beside it. The
  live assistant settled it. Asked for five universities with records, NRA
  count and share, it called `show_table` with four columns, got the
  rejection, and then **wrote a pipe table in the prose and dropped its
  follow-up chips** — `blocks_rejected: 1`, `blocks: ['text']`. No table, no
  chips, no source line. A trimmed table that says it is trimmed is the better
  failure, and the caps in the prompt and the tool schema keep it rare.
- **Columns are fixed-width and clip.** `table-layout: fixed`, with the first
  column taking the larger share because it holds the name. A clipped cell
  carries its full value in `title=`, so nothing is lost — it is one hover
  away.
- **Cells never wrap.** A wrapped institution name makes the row heights
  ragged and the table unreadable at this width.

Column widths are set by a `<colgroup>` at render time, not in CSS, because
the share depends on how many columns there are.

**The schema is what binds the model, not the prose.** Told in the prompt and
in the tool description that three was the cap, the live model sent four
anyway and lost the NRA share off the end of the table. `maxItems: 3` on the
`columns` array is the constraint a function-calling model actually honours;
the prose is the explanation, not the enforcement.

### A change to the prompt does not invalidate the answer cache

`cache.py` keys an answer on the question, the page, the knowledge version and
the data version — not on the prompt or the widget. Ask the same question
after a prompt change and you get the old-shaped answer back, with the stored
`latency_ms` and all. Test a formatting change with a question that has not
been asked before, or you will measure the cache.

### The one place more than three columns can still appear

If Chart.js fails to load, `renderChart` degrades to a table built from the
chart's datasets. Four datasets make five columns. The extra columns clip and
a caption says `Showing 3 of 5 columns`; the screen-reader table beside it
still carries every value.

## Charts

- `show_chart`, drawn with Chart.js, loaded lazily and only when a chart
  scrolls into view.
- Caps: 4 datasets, 40 points, 40 labels. Over the cap raises `BlockError`
  with the number and the cap, so the model can re-send a shorter series.
- The model sends data plus a semantic `role`. The widget picks the colour.
  **No hex ever crosses the wire.**
- Every chart ships a visually-hidden table of the same numbers, so the figure
  is readable without sight of the canvas.
- A series of four or more points **must** be charted, never spelled out in
  bullets.

## The other blocks

| Tool | Block | For |
|---|---|---|
| `show_stats` | KPI strip | 1–4 headline numbers |
| `show_notice` | callout | a caveat, a small cohort, a definitional footnote |
| `navigate_user` | nav chip | the answer *is* a place on this site |
| `show_link` | link card | the answer *cites* a place, or an external source |
| `suggest_query` | SQL card | raw records on `/query.html` |
| `suggest_followups` | chips | always, 2–4 |

## Where each rule lives

| Rule | Enforced in |
|---|---|
| bullet preference, no prose tables | `cloud/chat/prompt.py` |
| "1-3 columns" in the tool schema | `cloud/chat/tools.py` |
| the caps, and rejection over them | `cloud/chat/blocks.py` |
| the markdown subset, widths, clipping | `site/chat-widget.js` |
| all of the above, in the gate | `tests/test_chat_rendering.py` |

Caps are declared twice on purpose: `blocks.py` for the server and `CAP` in
the widget for the client. The client is never stricter about *dropping* than
the server is about *sending*, so a permissive client can only fail to hide
something the server deliberately sent. It opens no hole.

## Every number is still checked

None of this relaxes the provenance rule. Every number in a chart, a table or
a KPI must come from a data tool result in the same conversation — the ledger
in `blocks.py` checks each one, and a block carrying a number no tool returned
is rejected. `source` is required on charts and tables.

## Deploying a change

The widget and the Lambda ship separately, and the widget lives in the
**private** repo (`site/` is a symlink).

1. `make units` and `scripts/check_consistency.py` — both green first.
2. `.venv/bin/python -m pipeline run --step deploy` — ships `chat-widget.js`.
3. `~/usds_china_private/infra/chat/deploy.sh prod` — ships `prompt.py`,
   `tools.py`, `blocks.py`.
4. The chat deploy regenerates `site/data/chat/site_map.json`, so **redeploy
   the site after it**.
5. Ask the deployed assistant a real question and read the answer. Formatting
   bugs are only visible that way.
