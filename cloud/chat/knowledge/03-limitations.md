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
