# Before tomorrow's re-harvest

Written 2026-08-21. Ordered by what blocks what. Items 1-3 are prerequisites:
the re-harvest is unsafe until 1 and 2 are done, and 3 protects the run.

---

## BLOCKING — the re-harvest cannot run until these are done

### 1. Teach the harvester to read ETDMS dates
A pilot on binghamton destroyed every date in its CSV: 543 rows at 100% date
fill became 561 rows at 0%, and `date_issued` was empty too. Restored from a
backup taken beforehand.

Cause: binghamton is configured `metadata_prefix: "oai_etdms"` (chosen because
ETDMS exposes degree.name/level/discipline), but `scrape_oai_etds.py` reads
dates via `get_text("date")`, a `dc:` namespace lookup, and **ETDMS has no
`dc:date`**. Confirmed against the live feed: `oai_dc` returns
`<dc:date>2013-10-01T07:00:00Z</dc:date>`; `oai_etdms` returns a `<thesis>`
root with no `dc:` dates.

The existing CSVs were harvested under `oai_dc` before the prefix was switched.
That is the only reason their dates survive. Running all 110 repositories today
would destroy the year series for every ETDMS repository at once.

- [ ] Read the ETDMS date element (`etdms:date` under the `thesis` root) with a
      `dc:date` fallback, so both prefixes yield a date
- [ ] Verify **per platform**, not once: bepress, dspace, figshare, hyrax,
      blacklight each need checking

### 2. Add a date-fill guard to the harvester
The pilot was only survivable because a backup happened to be taken first. Make
it safe by construction.

- [ ] Refuse to overwrite a CSV when date fill drops sharply against the file
      being replaced (e.g. >20 points), exit non-zero, name the file
- [ ] Same guard for row count collapse

### 3. Back up the corpus before any bulk run
- [ ] `data/western_us_dissertations/` (1.2 GB, 110 CSVs) to S3 or a local copy
- [ ] Check free disk first — currently 12 GB, and the LCA rebuild in item 4
      wants ~6 GB of it

### 4. Re-pilot, then measure
- [ ] Pilot ONE ETDMS repo and ONE DSpace repo
- [ ] Assert date fill stays ~100% and `date_issued` is populated
- [ ] **Only then** measure accession-vs-issued drift. It is still UNMEASURED:
      the first pilot produced no dates to compare
- [ ] Decide from that measurement whether the full 110-repo run is worth it

---

## The LCA dedup (independent of the re-harvest, but wants the same disk)

DOL's quarterly files overlap inconsistently. FY2021 by its own DECISION_DATE
spans: Q1 is 2020-10-01→2020-12-31 (one quarter), Q3 is 2020-10-01→2021-03-25
(cumulative, only to March), Q4 is 2021-07-01→2021-09-30 (one quarter).
**99.0% of Q1's case numbers reappear in Q3.**

`step3_parse_federal.py` unioned every CSV with no dedup, so `total_lcas` on
every university page is inflated. Live now — MIT publishes 3,487.

- [x] Dedup on `COALESCE(CASE_NUMBER, LCA_CASE_NUMBER)` added to
      `step3_parse_federal.py`, prints the duplicate count each run
- [x] **MEASURED, and smaller than first reported.** A full DECISION_DATE span
      map of all 32 files shows the overlap is NOT uniform. Only three fiscal
      years overlap internally:

        FY2018  lca_H-1B_FY2018 (Oct17-Mar18) sits inside FY2018_EOY  ~410,605
        FY2021  Q2 and Q3 are cumulative; 3 overlapping pairs          297,403 (measured)
        FY2023  Q1 sits inside a cumulative Q2                         ~98,735

      Nine fiscal years (2015, 2016, 2017, 2019, 2020, 2022, 2024, 2025, 2026)
      have NO internal overlap - their quarterly files are cleanly disjoint.

      So **aggregate inflation is ~1.06x (5.8% of 13,909,863 rows)**, not the
      1.56x I first reported. That 1.56x is FY2021 alone and I wrongly
      generalised it to the whole corpus. Per-university impact depends on
      which years an employer filed in, so it cannot be stated as one factor.

      The dedup fix is still correct and still needed - it just corrects less
      than first claimed.

- [ ] **FY2013 overlap status is UNKNOWN.** lca_LCA_FY2013.xlsx (442,275 rows)
      names its column `Decision_Date`, not `DECISION_DATE`, so the span scan
      returned nothing for it. Check it with case-insensitive matching before
      the rebuild - and check whether the pipeline's own `find_col` handles the
      case difference, since it upper-cases keys but the CSV header may not
      round-trip the same way
- [ ] Rebuild `csv_cache` (~6 GB) and re-run parse_federal → enrich → generate
      → build_pages
- [ ] Redeploy: this changes published per-university figures
- [ ] Correct `data/h1b/LCA_ARCHIVE.md`, which asserts the files are cumulative
      and prescribes deleting superseded quarters. Both wrong, in opposite
      directions. I rewrote that file today and preserved the claim without
      testing it

---

## Deploy backlog — committed, tested, NOT live

One deploy clears all three. The site is correct today; these are improvements
that have not shipped.

- [ ] JSON pre-compression change (only >9 MB pre-compressed; 225 files upload
      plain so `urllib`/`curl` can read them). `mit.json` still returns
      `content-encoding: gzip`
- [ ] `degree_label_coverage` on 207 site JSONs and the registry
- [ ] Landing page: `#same-campus` contrast section, the $874,630 lead, the two
      reworded qualifiers
- [ ] Push 2 commits to `origin/assistant`

---

## Waiting on Andy

- [ ] `cloud/chat/curated_answers.yaml` — 31 answers, `--check` clean, currently
      seeded in my wording. Edit, then `--check`, then `--seed`. Flagged STALE
      and high priority by the dataset catalog
- [ ] Decide on the "find your representatives" lookup (the alternative to a
      bulk list of officials' accounts), which would also fix the missing
      ending — the page builds a case and stops at a contact address
- [ ] Decide whether the human/testimony gap gets addressed at all: the social
      research found no Americans describing rejection or lost funding. The
      quotes that exist validate the site's framing but are not evidence of harm

---

## Smaller, unblocked

- [ ] `scripts/build_pipeline_correlation.py` is written but unpublished — its
      H-1B leg depends on the dedup above. F-1 and master's are solid;
      master's↔OPT is r=0.751 but OPT is a shifting-roster sample, not national
- [ ] OPT legislative tracking: DHS sent RIN 1653-AB01 to OIRA on 2026-08-20,
      reportedly a $100,000 OPT fee. H.R. 2315 would end OPT; the Keep
      Innovators in America Act would codify it; Sen. Scott's bill would defund
      it. OPT exists by regulation, not statute — which is why a fee rule can
      reshape it without Congress
- [ ] 53 of 72 scripts uncatalogued in `pipeline/datasets.py` — no staleness
      tracking, which is how the Parquet exports shipped a four-month-old
      snapshot
- [ ] Montana State has no degree-enrichment config (18.2% labelled). Adding
      one means identifying which prefix its repository exposes degree level
      under. New configuration, not a fix

---

## PIPELINE QUALITY PLAN (added after the 2026-08-21 audit)

Ordered by value per hour. Tier 1 needs no rebuild and no deploy, so it can
land before anything else. Tier 3 is the only part that changes published
numbers.

### Tier 1 - minutes each, nothing downstream (DO FIRST)

- [ ] **Deploy must fail when it fails.** `step6_deploy.py` sets
      `success=True` inside `if errors:`. Today it printed "1 succeeded, 0
      failed" while every JSON upload errored and nothing shipped. One line.
- [ ] **Make the duckdb skip loud.** `step2_process.py` catches ImportError,
      prints "Parquet export skipped", and returns. That exact path shipped an
      April snapshot for four months. Raise instead - the dependency is now
      declared in requirements.txt, so a missing one is a broken environment.
- [ ] **Stop `tests/` lying.** `tests/test_chat_assistant.py` fails 18 of 19
      when run as a file, because it calls the LIVE Lambda and trips its rate
      limiter (`assert 429 == 200`). It also burns production quota and model
      spend. Either add backoff (as scripts/test_chat_answers.py now does) or
      move it out of `tests/` into an explicitly-integration path. A suite that
      is always red trains everyone to ignore red.

### Tier 2 - hours, still no rebuild

- [ ] **Enforce `pipeline/models.py`.** 11 files define their own STEM CIP set;
      only 7 import it. Two of the offenders were written today. Convert them,
      then add a check to `scripts/check_consistency.py` that FAILS when a new
      local copy appears - otherwise this regrows.
- [ ] **Kill the stray award-level rule.** `build_concentration_cases.py` has
      `return "aw17" if year >= 2010 else "aw09"` with no delegation and no
      window guard. Correct today only because callers filter to 2015-2022;
      silently wrong the moment it is reused across 2008-09.
- [ ] **Triage the 30 silent exception handlers.** 11 are in
      step3_parse_federal alone. Categorise each: legitimate (a per-file skip
      that is logged and counted) vs a swallow that can hide an empty result.
      Convert the second kind into failures.
- [ ] **Give the steps the ability to fail.** Five of eight call
      `StepOutcome.ok()` unconditionally. A step that cannot report failure is
      not evidence of success.
- [ ] **FY2013 column case.** `lca_LCA_FY2013.xlsx` uses `Decision_Date`, not
      `DECISION_DATE`. Confirm `find_col` matches it, and re-scan that file's
      span so its overlap status stops being unknown.
- [ ] **Add a pipeline-step test.** Nothing imports step1-step6 today; all
      coverage is of downstream artifacts. One end-to-end test on a small
      fixture would have caught the deploy-success bug.

### Tier 3 - changes published numbers, needs rebuild + deploy

- [ ] LCA dedup rebuild (see the section above). Aggregate correction is ~1.06x
      and concentrated in FY2018, FY2021, FY2023
- [ ] Correct `data/h1b/LCA_ARCHIVE.md`, which still asserts the files are
      cumulative
- [ ] Clear the deploy backlog in one run: compression change,
      degree_label_coverage, landing-page changes, then push

### Tier 4 - blocked on the ETDMS work at the top of this file

- [ ] The re-harvest itself
