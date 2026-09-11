# Comparing institutions on one key

`institution_profiles.json` is the only dataset here with **one row per
institution and every measure on it**. Every other institution-level dataset on
this site answers one question on one basis with its own key and its own floor.
When a question is "how does X compare with Y", or "which institutions are both
A and B", this is the dataset to use, and `/institutions.html` is the page to
send someone to.

Coverage: **2,290 institutions** — this is the comparison table, NOT the number of
universities the site tracks in depth (106 of those; see `universities_tracked`). 1,212 award
core-STEM graduate degrees, 2,017 report graduate
enrolment, 1,021 have federal money attached,
262 clear the floor for a per-doctorate ratio.

## The join, and why it is the interesting part

IPEDS completions, enrolment, tuition and the GSS all carry UNITID. **HERD and
the NSF Federal Support Survey do not** — NCSES publishes institution names in a
house style of its own ("U. Pennsylvania", "Johns Hopkins U.a") with no numeric
identifier. Those are resolved by exact match on a normalised token set, then by
a hand-verified crosswalk (`pipeline/ncses_crosswalk.json`).

**Subset matching was tried and rejected.** It maps "Florida A&M U." onto the
University of Florida, "Kutztown U. Pennsylvania" onto the University of
Pennsylvania and "State U. New York, Maritime C." onto New York University,
because a short famous name is a subset of many longer unrelated ones. If asked
how the join works, say it is exact-or-nothing and that unresolved names are
reported, not guessed at.

What stays unresolved: **1.7% of HERD dollars** and
**3.1% of Federal Support dollars**.
Nearly all of it is research bodies with no IPEDS teaching unit — Scripps, Woods
Hole, Cold Spring Harbor, UCAR, the Uniformed Services University. Unmatched
does not mean unfunded, and it does not mean a university was missed.

## Reading a row

- `masters` / `doctorate` — core-STEM degrees pooled
  2021–2025, with `share`,
  `early_share` (2010–2014) and
  `share_change` in percentage points.
- `graduate_enrolment` — autumn 2023, all fields and
  all levels of graduate study, so **not comparable** with the degree counts.
- `federal` — `obligations` (all agencies, FY2023), `training` (S&E fellowships,
  traineeships and training grants), `rd_federal` (federally financed R&D,
  FY2024). `match_kind` says what the money covers.
- `federal_per_doctorate` — see below.
- Absent fields are absent, never zero. **A missing federal block means the
  institution was not surveyed, not that it spent nothing.**

## match_kind, and when a row is looser than it looks

- `campus` — one IPEDS campus, the ordinary case.
- `campus_plus_affiliate` — folds in a hospital that enrols nobody. Vanderbilt's
  R&D includes Vanderbilt University Medical Center, legally separate since 2016.
- `multi_campus` — spans units that report degrees separately (Rutgers, ASU).
- `system_office` — administrative, no students at all. Never compute a
  per-student figure on one.

## federal_per_doctorate is an intensity ratio, not a price

FY2023 obligations over the annual rate of core-STEM research doctorates
2015–2022. It reproduces
the basis published on the funding page exactly: Missouri S&T comes out at
**$107,334** either way.

National median across the **262 institutions** that clear the floor:
**$821,054**. This is a *wider* population than the $874,630 quoted in
the briefing and on `/who-pays`, which covers this project's own university set.
Do not present the two as a correction of each other — they are different
populations of the same measure.

Federal obligations fund research whose outputs include papers, instruments,
facilities and staff, **not only degrees**. It does not establish that the public
paid that sum for any particular doctorate. What it establishes is the scale of
public research money moving through the institutions that produce them.

**The top of that ranking is medical schools** — Albert Einstein, Icahn, UCSF —
where the money funds clinical research and the doctorates counted are a fraction
of the degrees awarded. Every row carries
`cost_basis_share_of_all_doctorates` and `cost_basis_professional_doctorates` so
that a partial denominator is visible rather than asserted. Check them before
quoting a large ratio.

## States

`states` sums institutions to their state. **Every share is recomputed from the
sums**, never averaged across institutions — an average would let a department of
nine outvote a university of nine thousand. Fifty-six entries, including DC and
the territories.

## What this dataset is not

It is **not money broken down by citizenship**, because no federal agency
publishes that. IPEDS reports tuition revenue without regard to who paid it; NSF
reports obligations without regard to who they train. A large federal figure
beside a large non-resident share is two things measured in the same place, not a
payment from one to the other.

Non-resident is a **visa category, not a birthplace**. Naturalised citizens and
permanent residents count as domestic, so every share is a floor on the
foreign-born proportion.
