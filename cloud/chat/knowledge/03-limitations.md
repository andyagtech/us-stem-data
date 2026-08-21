# What this data cannot tell you

Say these plainly when they apply. A reader who learns a limit from the assistant
trusts the rest more, not less.

## Award dates are unreliable for some universities

Many OAI harvests captured `dc.date.accessioned` — when a repository ingested a
record — rather than `dc.date.issued`, the actual award date. The harvester now
captures the issued date, but **no CSV has been re-harvested**, so year
distributions drawn from dissertation records are wrong for an unknown subset of
universities.

This affects the **dissertation-record year series**, not the IPEDS-derived NRA
shares, which come from federal completions files and are unaffected. When a
reader leans on a per-university year trend from the records, say the date basis
is under repair.

## Degree labels are incomplete for some repositories

The PhD / master's split comes from degree metadata that repositories publish
unevenly. Coverage is near-complete for most repositories, substantially incomplete for a
few (notably George Mason and Oregon), and lowest for Montana State, which has no
degree-enrichment configuration at all.

Where labels are missing the records still count — the split between doctorate and
master's is what is uncertain, not the existence of the record.

## Record counts are repository coverage, not ground truth

A university's dissertation-record count reflects what its repository publishes
and what the harvest reached. It is **not** a census of degrees awarded. For
counts of degrees, IPEDS completions are the authority. Never present a record
count as a degree count.

## Small cohorts are noise

A 100% NRA share on a cohort of 3 means nothing. Cohort floors default to 20 and
must never go below 10. When a result rests on a small cohort, say so in a notice
rather than burying it.

## Federal employment data is employer-matched, not person-matched

LCA, PERM and H-1B figures are matched to universities by **employer name**. Name
matching is imperfect in both directions: it can miss subsidiaries and it can
over-collect on common substrings. These are indicators of scale, not exact counts
of individuals.

## Degree-level coverage varies by institution — check before splitting

Degree level (PhD vs master's) in the dissertation corpus comes from each
institution's OAI feed, and only seven repositories expose it. Coverage across
207 corpora ranges from 18% to 100%, and **10 sit below 50%**:

| university | STEM | non-STEM |
|---|---|---|
| Montana State | 24.3% | 18.2% |
| Boston University | 32.2% | 39.5% |
| George Mason | 38.1% | 51.6% |
| Cornell | 41.8% | 47.5% |
| MIT | 47.8% | 41.9% |

`degree_label_coverage` is on every university's JSON. If someone asks for a
master's/doctoral split at one of these institutions, give the figure **and say
what share of the corpus it covers**. MIT and Cornell are the easy mistakes —
they are well covered in every other respect.

This is a source limitation, not a processing gap: those feeds do not publish
degree level. Do not present a low-coverage split as if it described the whole
corpus, and do not compare a 24% corpus against a 99% one without saying so.

**This applies to the CORPUS only.** The IPEDS-based master's and doctorate
figures — including everything from `level_rankings` — are complete federal
counts and carry no such limitation. Never let a corpus caveat leak into an
IPEDS answer, or vice versa.
