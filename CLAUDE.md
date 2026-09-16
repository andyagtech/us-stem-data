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
make units                          # 873 tests
.venv/bin/python scripts/check_consistency.py    # 26 checks, all must pass
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

## Privacy

- **Store full IPs in analytics. Never hash or anonymise them.** The author
  wants them for geography.
- Private pages are declared once, in `scripts/private_pages.py`. Anything
  listed there stays out of the sidebar, the contents page and robots.txt.

## The assistant

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
