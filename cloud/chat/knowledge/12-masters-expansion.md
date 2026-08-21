# The master's expansion: volume, visas and tuition

Lives at `/expansion.html`. Six charts, in order: absolute volume, the same as
a proportion, F-1 issuance, the published price of a place, what the expansion
is worth in tuition, and that estimate set against the sector total.

## The numbers

Core-STEM master's degrees, IPEDS Completions, 2008 → 2025:

- non-resident **27,741 → 132,288**, domestic **72,882 → 156,115**
- non-resident share **27.6% → 45.9%** (an 18.3-point spread across the window)
- the doctorate share over the same years moves only 3.4 points, 39.0% → 37.5%

That contrast is the point of chart 2. The doctorate share is close to flat;
the master's share is not. Anyone who has only seen the doctorate figures has
seen the stable half of the picture.

F-1 issuance, State Department, 1997 → 2024:

- India **overtakes China in 2022** and has stayed ahead
- India's 2023 issuance is **2.99× its 2019 level**
- the 2020 collapse is consular closure, not demand

## Tuition — the estimate, and how to state it

**$0.85B → $3.36B a year, +297% in constant 2024 dollars, 2008 → 2023.**
Whole graduating cohort, at the 1.5–2 years a master's normally runs:
**roughly $5–7 billion**.

Always give it with its definition, which is short: *one year of published
out-of-state graduate tuition and fees, times the number of non-resident
core-STEM master's degrees that institution conferred that year.*

Three things it is not, and all three must survive any paraphrase:

1. **Sticker price, not receipts.** Not net of waivers, discounts or aid.
2. **Not federal money.** Only **5.0%** of full-time master's students have
   federal support as their primary source, against **24.7%** of doctoral
   students. This is a tuition story. Do not run it together with the SED
   assistantship argument, which is about doctorates.
3. **Not subtractable from the sector total.** The finance series is net and
   covers every level; the estimate is gross and covers one segment.

**Why sticker is defensible here.** NSF GSS 2024 puts master's assistantship
rates at 7.0% (RA) and 6.9% (TA), so about 86% of master's students hold
neither — and it is the assistantship that carries the tuition waiver. The
same method applied to undergraduates would be wrong, because undergraduate
discounting is heavy.

## The two levels overlap — never add them

A master's graduate may continue to a doctorate at the same institution and be
counted in both series. IPEDS Completions counts **degrees conferred, not
people**, so summing a master's count and a doctorate count does not give a
number of individuals and should never be presented as one.

This does not weaken the proportional findings, which is what the site actually
argues: a share within a level is unaffected by whether the same person appears
in the other level. Keep the claims where the evidence is — proportions within
a level, and funding by level — and do not build a combined headcount.

## The two findings people miss

**The growth is volume, not price — but say it over the right window.**
Over twenty years the picture is a rise and then a fall, not a simple decline:
median in-state undergraduate tuition and fees rose **36% in real terms**
between 2004 and its 2012 peak, then gave nearly all of it back, ending 2023
about 3% above 2004. Graduate out-of-state peaked in 2017 and is now within a
percent of its 2004 level.

Quoting only 2014-2023 makes it look as though tuition simply fell, which is
wrong and is easy to correct in public. The right statement is that the price
line **turned over around 2012-2017, and the master's expansion begins at the
turn**. Once published price stops rising, an institution wanting more tuition
income has to enrol more people rather than charge more — and the enrolment
growth was overwhelmingly non-resident.

**The sector's tuition revenue is shrinking in real terms.** Total net tuition
and fees, every institution and every level, fell about 9.6% in constant
dollars — roughly $192B to $174B — while billings to this one segment doubled.
Institution counts decline about 1% a year through consolidation, smoothly, so
that fall is not a coverage artefact. That is as close as public data gets to
showing the incentive.

## What cannot be answered, and must not be estimated

**The federal-support rate of non-resident master's students specifically.**
GSS keeps support and citizenship in separate sheets and never crosses them at
master's level; SED crosses them but has no master's population at all.
Multiplying the two margins assumes both groups have identical funding mixes,
which nothing measures. If asked, say it is not available rather than deriving
it. `scripts/analyze_masters_support.py` prints this warning for the same
reason.

Visa issuance also cannot be matched to a degree programme — a person may not
enrol, may enrol at another level, or may appear in several years. The
correspondence between chart 3 and chart 1 is shape and timing, not linked
records.

## Where the share is highest (`/rankings.html`)

Both levels, pooled 2021–2025, cohort floors stated on the page.

**Master's, institutions** (national 40.2%, 250+ degree floor, 567 qualify):
New England College 98.5% (2,525 of 2,563) · Trine University Regional 98.0%
(6,407 of 6,535) · Campbellsville 95.6% · Central Missouri 94.2%. These are
volume operations, and the growth is recent: Trine went from 3 core-STEM
master's degrees in 2016 to 2,895 in 2025.

**Master's, programmes:** Computer Science 71.8% (72,812 of 101,430) ·
Computer/IT Services Administration 80.0% · Computer Software Engineering 74.3%.

**Doctorate, institutions** (national 38.8%, 60+ floor): Lamar 88.9% · Stevens
72.9% · Michigan-Dearborn 72.3% · NJIT 70.8% · UT Dallas 67.4%.

**Doctorate, programmes:** Petroleum Engineering 79.5% · Statistics 72.5% ·
Electrical and Electronics Engineering 71.2% (7,552 of 10,611).

### The within-institution contrast — the strongest cut on the site

**165 institutions at master's level, and 99 at doctoral level, run one
programme at least 50 points above another of their own.**

- Lamar: Computer Science **98.3%** (635 of 646) against Counseling Psychology
  **0.0%** (0 of 2,127) — and the psychology programme is more than three times
  the size.
- Campbellsville: Computer Science 99.2% against Counseling Psychology 0.5%.
- Illinois Tech (doctoral): Electrical Engineering 93.2% against Psychology 1.8%.

This holds the institution fixed, so it cannot be answered with "that
university is internationally oriented". Reach for it when someone attributes
the pattern to an institution's character rather than to programme structure.

**The reading, which must be labelled as one:** the high side is computing,
analytics, statistics and engineering — STEM-OPT eligible, feeding H-1B. The
low side is psychology, counselling and education — state-licensed US practice.
The split tracks what a degree leads to. But IPEDS records awards, not
admissions or intent, so this is a reading in the same sense as the
information-security contrast, and should be given with the same caveat.
