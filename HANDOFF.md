# Session handoff — 2026-08-18

Written on low battery. Everything below is committed; both repos are clean.
39 commits in `usds_china`, 22 in `usds_china_private`.

## Where things stand

**A deploy was in flight when this was written.** `python3 -m pipeline run --step deploy`
was uploading 477 files / 335 MB and had not finished. S3 uploads are per-file
atomic, so a partial deploy leaves some files new and some old — nothing is
corrupted, but the site is in a mixed state until it is re-run.

**Re-run the deploy first thing.** It is idempotent.

```bash
python3 -m pipeline run --step deploy       # needs openpyxl; a venv works
curl -sS -o /dev/null -w "%{http_code}\n" \
  https://phd-demographics.andy-barr.com/og/universities/mit.png   # must be 200, not 404
python3 -c "import json,urllib.request as u; \
  print(json.load(u.urlopen('https://phd-demographics.andy-barr.com/data/stem/msu.json'))['nra'])"
# must print 49.0 — if it prints 16.7 the data files have not landed yet
```

## Two things that must be verified after the deploy

1. **OG cards resolve.** `step6_deploy.py` globbed `site/*.png` top-level only, so
   the 237 cards in `site/og/` would never have uploaded while every page's
   `og:image` pointed at them — shares would have fetched a 404, strictly worse
   than the static image they replaced. Fixed (an `aws s3 sync` of the directory),
   but the fix has not yet run to completion. Check the URL above.

2. **The cards are on the wrong STEM basis.** They were rendered with the broad
   16-family CIP set; the page headline uses the narrow 8-family set. Median gap
   1.9 points, but **UNLV is 32.3% narrow against 15.1% broad — 17.3 points**, and
   Missouri 50.2 vs 35.1. `scripts/og/data.py` is already corrected; the cards
   need regenerating and re-syncing:

   ```bash
   python3 scripts/build_og_cards.py        # ~60 min for 237 cards
   python3 -m pipeline run --step deploy
   ```

## Known-open items

- **Montana State** is the 105th university but its harvest stopped part-way
  (~8,000 of 12,397 records). It rate-limits hard; resume with
  `python3 scripts/scrape_oai_etds.py --repo montana_state --resume --delay 6`.
- **GMU labelling sits around 38%** because its re-harvest grew the corpus past
  what the degree enrichment had mapped. Re-run
  `python3 scripts/enrich_degree_metadata.py --repo gmu` then reprocess.
- **The award-date defect is unresolved.** OAI harvests took
  `dc.date.accessioned` rather than `dc.date.issued`. The harvester now captures
  `date_issued`, but **no CSV has been re-harvested**, so nothing on disk carries
  it and the published year distributions are still wrong for many universities.
  Repairing it means re-harvesting the DSpace repositories and repointing
  `date_field`. That moves the site's headline year series, so it is a decision,
  not a chore.
- **Chat is built but not deployed.** 19 data tools and 8 render tools, the
  rebuilt widget, and `chat_data/` at 8.2 MB. Deploy with
  `infra/chat/deploy.sh`. It has never been deployed with the new modules.

## What changed today, in one paragraph

Corpus went from 101 universities and 294,280 records at 78.4% labelled to 105
and 517,386 at 88.4%. Recovered 7,459 master's records that were silently
dropped, ~88,000 records from under-harvested repositories, and 12,000+ from
universities frozen since April. Fixed: a manifest that reported stale figures,
a harvest step that had never run, a parse error that silently truncated a
repository mid-walk, an employer matcher that folded WIPRO LIMITED and INFOSYS
LIMITED into MIT (LCA 565,883 → 3,487), and 37 of 103 headline NRA percentages
that were more than 5 points wrong (Michigan State 16.7% → 49.0%). Added NSF
Awards, NIH RePORTER and NCSES federal obligations; LCA now runs through FY2026
Q3. Built an NRA index, a slide deck at `/concentration.html`, a site-wide anchor
scheme, 237 share cards, and 13 new assistant tools.

## The finding worth keeping

National NRA share of US research doctorates is **flat** — 27.2% in 2010, 25.5%
in 2025. What changed is concentration: departments of 20+ doctorates that are
majority non-resident went from 82 to 193, and the share of all US doctorates
awarded inside them from 4.2% to 7.1%. In STEM alone, 1996–2025: 30 departments
to 162, and 3.7% to 12.9% of doctorates. Quote the STEM series or the post-2010
series — never a pre-2010 figure against a post-2010 one, because IPEDS recoded
award levels in 2010 and the comparison measures the recoding.

## Notes and scratch work

Agent findings, audits and studies are in
`/private/tmp/claude-501/-Users-andy-usds-china/5f48248f-d0fc-4a8c-9b94-e31e685a7ff6/scratchpad/`
— that path is temporary and will not survive indefinitely. Worth copying out if
any of it matters: `chat_contract.md`, `anchor_scheme.md`, `og_cards.md`,
`name_signal_study.md`, `tools_provenance.md`, `methodology_update.md`.
