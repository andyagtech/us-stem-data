# Looking figures up, and the two tools that do it

Most questions here should start with a tool call, not with recall. Two tools
exist for that and both were added because the assistant could describe these
findings and not give a number from either.

## key_figures — call this first for anything broad

One call returns the headline figure from every finding on this site, currently
16: the non-resident shares at both degree levels, graduate
enrolment, institution counts, federal money, the wage comparison, the
green-card route and the foreign-born share of the workforce.

Use it for "what does this site find", "what is the headline", "is the share
rising", "how big is this". Do NOT assemble those answers from several narrower
tools — this is the one that has them all on one basis, from one build.

**Every figure comes back with a `limit` field. Quote it with the number.**
That is not politeness: a summary is exactly where a qualification gets lost
while the number survives, and several of these figures are wrong without
theirs. `dataset` and `path` say where each value was read from, so any figure
can be checked in one step.

For anything conditional — by year, state, institution, occupation — the
summary has nothing. Use the dataset named on the figure.

## Two counts that must not be confused

- **`universities_tracked` (106)** answers "how many universities does this site
  track". These are the universities with their own page, dissertation records and
  immigration-pipeline data.
- **`institutions_profiled` (2,290)** is the comparison table: every US institution
  with core-STEM graduate degrees, graduate enrolment or federal research money.

Answering "how many universities does this site track" with 2,290 is wrong, and it
has happened. The 106 were chosen for high non-resident share and data
availability, so no national rate may be computed from them.

## compare_institutions — one row per institution

2,290 institutions on the federal unit
identifier, with three modes:

- `lookup` — name one or more institutions, get a row each. Two or more is a
  comparison. This is the only tool that puts degrees, enrolment and federal
  money in the same sentence for one institution.
- `rank` — the national ranking on any of fifteen measures.
- `state` — the rollup, one row per state.

Field names are abbreviated and the `fields` map comes back with every result.
**An absent field means no data, never zero.** An institution with no federal
figures was not surveyed; it did not spend nothing. Saying "it received $0"
from a missing field is a reporting error, not a rounding one.

### The per-doctorate column needs care

`fpd` is federal obligations over the annual rate of core-STEM research
doctorates. **Lead with the site's headline figure, $874,630**
(`federal_per_doctorate_headline`) — the one on the front page and in the briefing,
across the institutions this site tracks. The national median over every qualifying
institution is $821,054; that is a wider population,
not a correction, and quoting it alone gives a reader a different number from the page.

**It is an intensity ratio, not a price.** Those obligations fund research
whose outputs include papers, instruments, facilities and staff, not only
degrees, so it does not establish that the public paid that sum for any
doctorate. What it establishes is the scale of public research money moving
through the institutions that produce them.

The top of that ranking is medical schools — Albert Einstein, Icahn, UCSF —
where the money funds clinical research and the doctorates counted are a
fraction of the degrees awarded. Two fields on the row say so: `fps` is
core-STEM as a share of all research doctorates, and `fpp` is professional
doctorates (MD, DDS, JD). **Check both before quoting a large ratio.**

## What neither tool will do

Neither breaks money down by citizenship, because no federal agency publishes
it that way. IPEDS reports tuition revenue without regard to who paid it; NSF
reports obligations without regard to who they train. A large federal figure
beside a large non-resident share is two things measured in the same place, not
a payment from one to the other. If asked to cross them, say it is not
collected — see [[03-limitations]].

Non-resident is a visa category, not a birthplace. Naturalised citizens and
permanent residents count as domestic, so every share from these tools is a
floor on the foreign-born proportion, never a ceiling. The exception is the
foreign-born labour figures, which come from the CPS and do include naturalised
citizens; their limits say so.

## The figures, as of this build

Quote these from a tool call, not from here — this list is to tell you what
exists, and the values move when the corpus is rebuilt.

- `masters_nra_share_latest` — Non-resident share of core-STEM master's degrees, 2025: **45.9** (pct)
- `masters_nra_share_1995` — The same share in 1995: **24.4** (pct)
- `doctorate_nra_share_latest` — Non-resident share of core-STEM research doctorates, 2025: **37.5** (pct)
- `masters_awarded_latest` — Core-STEM master's degrees awarded, 2025: **288,070** (count)
- `gss_foreign_share_latest` — Temporary-visa share of full-time S&E graduate enrolment, 2024: **38.5** (pct)
- `universities_tracked` — Universities this site tracks in depth -- the ones with their own page, dissertation records and immigration-pipeline data: **106** (count)
- `institutions_profiled` — Institutions on the comparison table (/institutions): every US institution with core-STEM graduate degrees, graduate enrolment or federal research money -- NOT the universities this site tracks in depth: **2,290** (count)
- `federal_per_doctorate_headline` — Median federal obligations per core-STEM research doctorate -- the figure on the front page and in the briefing, across the institutions this site tracks that award at least a hundred such doctorates: **874,630** (usd)
- `federal_per_doctorate_median` — Median federal obligations per core-STEM research doctorate awarded per year: **821,054** (usd)
- `majority_foreign_institutions` — Institutions where a majority of graduate students hold a temporary visa: **108** (count)
- `majority_foreign_federal_rd` — Federal R&D expenditure at those institutions: **19,367,645,000** (usd)
- `below_metro_median_pct` — Certified H-1B filings promising below the median for their occupation in their own metropolitan area: **84.0** (pct)
- `below_national_median_pct` — The same comparison against the national occupational median: **70.8** (pct)
- `eb_adjustment_share_pct` — Employment-based green cards going to people already in the United States, 2023: **74.6** (pct)
- `foreign_born_share_employment` — Foreign-born share of all US employment: **19.2** (pct)
- `foreign_born_share_computing` — Foreign-born share of computer and mathematical occupations: **29.0** (pct)
