# Working on this repo

Editorial research site about US graduate programmes, foreign enrolment and the
visa routes out of them. Public repo; a private sibling holds the deployable
parts. Everything published is built from federal data by a script in
`scripts/`, and no figure is typed into a page by hand.

If this file and the code disagree, the code is right and this file is a bug.

## Where things are

| | |
|---|---|
| `~/usds_china` | this repo: builders, tests, pipeline, `site/`, `cloud/chat/` |
| `~/usds_china_private` | deploy scripts and infra; `site/`, `infra/chat/`, `infra/analytics/` reach back here by symlink |
| `site/` | the published site. `site/data/*.json` is built output, never hand-edited |
| `scripts/build_*.py` | one builder per dataset; each writes one JSON and prints what it wrote |
| `pipeline/datasets.py` | the catalogue. A builder not registered here is invisible to the pipeline |
| `cloud/chat/` | the assistant's Lambda source, including `knowledge/` |

## The gate, before any deploy

```
make units                          # <!--auto:test_count-->1,450<!--/auto--> tests
.venv/bin/python scripts/check_consistency.py    # <!--auto:consistency_checks-->37<!--/auto--> checks, all must pass
```

Both green, then `.venv/bin/python -m pipeline run --step deploy`. Never chain
a deploy after a build in one command without the gate in between — a deploy
has gone out with a failing test that way.

`make check` runs the whole offline suite. `scripts/sync_docs.py --write`
refills generated numbers in prose when consistency reports them stale.

## The site and the assistant deploy separately

This is the trap. `pipeline run --step deploy` publishes the site. The chat
assistant is a separate Lambda, deployed by
`~/usds_china_private/infra/chat/deploy.sh prod`, and **it ships its own copy of
the site map inside its bundle**. The prompt tells the model that the paths in
that copy are the only valid navigation targets.

So a page can be live, linked, in the sidebar and in the search index while the
assistant is unable to mention it. That happened to `/visa-schools.html` and
`/bodyshops.html`, and every link check passed throughout, because link checks
compare the site with itself.

`check_consistency.py` now fails when the chat bundle is behind the site. If
you add or rename a page, redeploy the assistant too.

## Writing, on the site and in the knowledge base

- **Short declarative sentences. One idea each.** Prefer a full stop to a comma
  or a dash. Avoid asides and run-ons. This is the author's explicit
  instruction and it applies to page copy, chart labels and knowledge files.
- **The author owns the editorial.** "Schools that launder visas" and "body
  shops" are his words and they stay. Do not soften them.
- **Never upgrade a characterisation into a legal claim.** No page says any
  school or firm broke a law. The pages show what public records show.
- Every number on a page comes from built data at render time, so a rebuild
  moves the page and a stale figure cannot survive one.

## Data rules that have already been got wrong

- **Retrieved data is append-only.** A harvest may add records and fill empty
  fields. It may never remove a record, drop a column, or blank a field that
  held a value. See `HANDOFF.md` for the incident that set this rule.
- **Never sum initial and continuing H-1B approvals.** A continuing approval is
  the same person renewed; adding them counts one worker once a year for as
  long as they stay.
- **Count LCAs by application, not by position.** One application can cover
  forty workers. Weighting by positions hands every share to the bulk filers.
- **Positions are not people.** A certified LCA is permission to employ, not
  proof of hiring. Every LCA figure is a ceiling on intent.
- **Partial fiscal years get shares, never counts.** The missing quarter is
  rarely average: January–March is H-1B cap season and the busiest of the four.
- **Federal file headers drift between years.** `H_1B_DEPENDENT` becomes
  `H-1B_DEPENDENT` in FY2025. Read each needed column through a list of known
  spellings and **fail the build** when none matches — a silently missing
  column reads as a firm that is never dependent, which is worse than a crash.
- **IPEDS recoded award levels in 2010.** Never compare across that break.
- **A two-digit NAICS is a sector, not an industry.** The USCIS hub publishes
  only two digits, so it cannot separate a staffing firm from a law firm. That
  classification needs the DOL disclosure files, which carry six.

## Large source data lives in S3

Raw federal sources are big and are read only when their builder runs, so they
are archived to `s3://phd-demographics-raw-data/` and deleted locally. The
bucket is **private** (it granted `s3:GetObject` to `Principal: "*"` until
2026-09-22; anonymous reads now 403). Every restore uses `--profile personal`,
and the EC2 rebuild job uses an IAM instance profile.

Three rules, in order:

1. **Verify before deleting.** Compare every file with the object of the same
   key, by size at minimum, and look at the DIRECTION of any difference. A
   local file larger than its copy means the harvest grew and S3 is stale. A
   local file smaller means something truncated it -- that is the 2026-08
   incident's signature, and it means S3 holds the good copy.
2. **Never sync with `--delete`.** Retrieved data is append-only in S3 too.
3. **Declare where it went.** A catalogued `consumes` path may be absent only
   if that `Dataset` sets `archived_at`; `check_consistency.py` enforces it.
   The builder should also print the restore command when the path is empty.

## Privacy

- **Store full IPs in analytics. Never hash or anonymise them.** The author
  wants them for geography.
- Private pages are declared once, in `scripts/private_pages.py`. Anything
  listed there stays out of the sidebar, the contents page and robots.txt.

## Voice

`/live.html` has a voice session: the browser talks straight to OpenAI over
WebRTC and audio never reaches our servers. Three things about it:

- **The key comes from SSM**, like every other model call, not from a plain
  `OPENAI_API_KEY` env var. That mismatch is why voice answered
  "not_configured" for two days while a perfectly good key sat in Parameter
  Store.
- **A session is charged its worst case before the token is minted, and there
  is no settlement**, because no usage report comes back. It has its own daily
  sub-ceiling inside the $25 so voice cannot starve typed questions. A mint
  that fails is refunded; a session that started never is.
- **Do not set CORS headers in a Lambda response.** The Function URL sets
  `Access-Control-Allow-Origin` itself, and a duplicated header makes the
  browser refuse a response that `curl` sees as a perfect 200.

The OpenAI realtime API is GA: mint at `/v1/realtime/client_secrets` (the token
is `value`, at the top level), exchange SDP at `/v1/realtime/calls`. The beta
paths `/v1/realtime/sessions` and `/v1/realtime` both fail now.

## The assistant

- **What it may put on screen is written down: `cloud/chat/RENDERING.md`.**
  The markdown subset the panel parses, the bullet preference, the three-column
  table cap, and which file enforces each rule. Read it before changing
  `prompt.py`, `blocks.py` or `chat-widget.js` — the caps are declared in two
  places and the prompt promises what the widget can actually render.
- **The answer cache can serve a question nobody asked.** Similarity alone
  put the mechanical-engineering answer in front of a civil-engineering
  question: one word different out of thirty scores higher than the
  paraphrases the cache exists to catch, so no threshold separates them. A
  semantic hit now also has to name the same entities — fields, institutions,
  years — read from `cip_titles.csv`, `hd_names.csv` and the knowledge base
  itself. Testing a prompt change by re-asking a question measures the cache,
  not the change.
- **Three checks guard the numbers in knowledge/, and they prove different
  things.** Know which one to reach for.
  - `knowledge_figures.py` (73) **recomputes** a figure, so it proves the
    arithmetic as well as the value. One resolver each, so it is for headline
    figures and anything with a derivation worth re-running.
  - `knowledge_pins.py` (208) names the **exact field** a figure came from, as
    `by_state[state=CA].priced`. No resolver — one line per figure. This is the
    drift alarm for data that moves: the DOL files land quarterly and the visa
    bulletin monthly, and when they do, every share recomputes. A **hard** check:
    a pin was right when written, so a mismatch means the prose is now wrong.
    Regenerate candidates with `scripts/pin_kb_figures.py --propose`, then
    review — it refuses a figure whose value repeats across fields the prose
    does not name, because a right number read off an arbitrary row passes
    forever and proves nothing.
  - `check_kb_provenance.py` (all 1,361) proves every figure is **findable** in
    a dataset the file draws on. Cheap, total, and the only thing that catches a
    number that was invented or mistyped. A **ratchet**: the backlog sits in
    `kb_provenance_baseline.json` and new prose may not add to it.
  - A file declares its datasets in `knowledge_sources.py`, or by naming them in
    its own prose. A declared source may be a build input (`pipeline:universities`)
    — real provenance that simply is not shipped.
  - **Pin the field, never the row position.** These lists are sorted by volume,
    so `by_state.0` quietly becomes a different state after a rebuild and the
    check still passes.
- Prose lives in `cloud/chat/knowledge/*.md`; figures come from tools. A
  knowledge file may carry a headline total, but anything by year, institution
  or department must be fetched.
- `36-the-argument.md` holds the four-step case; `01-central-finding.md` holds
  the measured finding. Keep them apart: a reader may reject the argument and
  accept every figure in it.
- **Mark guidance as guidance.** Instructions written next to facts get echoed
  at the reader ("if a reader assumes X, it is important to clarify…").
- After changing knowledge, **ask the deployed assistant a real question** and
  read the answer. Two errors in the last batch were only visible that way.

## Verifying

- **Load what a reader loads.** Check `/`, not just `/index.html` — they take
  different code paths, and the homepage lost its sidebar once because only the
  second was ever checked.
- **Measure the thing, not a proxy.** Compare content width to the device
  width, not `innerWidth`, which mobile emulation inflates.
- **Prove a new check fails before trusting it.** Break the code, watch it go
  red, restore. A check that has never failed is a check that may not work.
- An absence can be the finding. "No agency publishes this list" is a result,
  and it belongs on the page with the search that established it.
